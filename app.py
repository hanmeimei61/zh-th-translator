"""
中泰极简大字翻译器（字节豆包 · 火山方舟版）
============================================
- 强制只输出泰文翻译（屏蔽一切寒暄/解释/标点修饰）
- 全屏大字号展示，方便面对面翻译时给泰方看
- 支持快捷键：Ctrl/Cmd + Enter 立即翻译
- 后端 LLM：字节跳动 豆包（doubao-lite-32k），OpenAI 兼容

为什么选豆包:
  - 沙盒在国内，到 Google / DeepSeek / 智谱的 endpoint 都能通；
    但 DeepSeek 免费额度用完会卡 402 余额不足；智谱需实名 + 邮箱注册
  - 火山方舟新用户送代金券，且 doubao-lite-32k 价格极低，几乎等于免费
  - 豆包中文→泰文翻译质量稳定，泰国本地化表现好
  - 注册：https://www.volcengine.com/product/doubao
        → 火山引擎账号（手机号）→ 实名 → 开通「方舟 ARK」→ 创建 API Key
"""

import socket
import json
import streamlit as st
import streamlit.components.v1 as components
import requests

# === 1. 页面基本配置 ===
st.set_page_config(
    page_title="中泰纯净翻译器",
    page_icon="🇹🇭",
    layout="centered",
)

# === 2. 全局样式：大字体 + 高亮 ===
st.markdown(
    """
    <style>
    .translated-text {
        font-size: 38px !important;
        font-weight: bold;
        color: #0D47A1;
        background-color: #E3F2FD;
        padding: 24px 28px;
        border-radius: 14px;
        line-height: 1.6;
        word-wrap: break-word;
        border-left: 6px solid #1E88E5;
        margin-top: 12px;
        font-family: "Noto Sans Thai", "Sarabun", "Tahoma", sans-serif;
    }
    .stTextArea textarea {
        font-size: 18px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================
# ★★★ def 必须在 with st.sidebar: 之前定义 ★★★
# =============================================================


def network_diagnose() -> dict:
    """检测沙盒能否访问火山方舟 endpoint，返回结构化诊断信息。"""
    result = {
        "dns_ok": None,
        "resolved_ip": None,
        "tcp_ok": None,
        "https_status": None,
        "error": None,
    }
    host = "ark.cn-beijing.volces.com"
    try:
        ip = socket.gethostbyname(host)
        result["dns_ok"] = True
        result["resolved_ip"] = ip
    except Exception as e:
        result["dns_ok"] = False
        result["error"] = f"DNS 解析失败: {e!r}"
        return result

    try:
        with socket.create_connection((host, 443), timeout=8) as s:
            result["tcp_ok"] = True
    except Exception as e:
        result["tcp_ok"] = False
        result["error"] = f"TCP 握手失败: {e!r}"
        return result

    try:
        resp = requests.get(f"https://{host}/", timeout=8, allow_redirects=False)
        result["https_status"] = resp.status_code
    except Exception as e:
        result["error"] = f"HTTPS 请求失败: {e!r}"

    return result


def translate(text: str, key: str, model: str, direction: str = "zh2th") -> str:
    """调用火山方舟 ARK（OpenAI 兼容）API，返回纯净的翻译结果。

    direction: "zh2th" 中文→泰文，"th2zh" 泰文→中文
    """
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

    # ★ 鲁棒清洗 Key：用户可能粘了 "Bearer xxx"、JSON、双引号、换行、终端回显……
    # 规则：先去掉所有空白/常见引号，再用正则提取真实 Key 子串
    import re
    stripped = (
        key.replace('"', "")
        .replace("'", "")
        .replace("`", "")
        .replace("Bearer", "")  # 兼容用户粘了 "Bearer ark-..."
        .strip()
    )
    m = re.search(r"(ark-[A-Za-z0-9-]+|AIza[A-Za-z0-9_-]+)", stripped)
    clean_key = m.group(1) if m else "".join(stripped.split())

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {clean_key}",
        "Accept": "application/json",
    }

    if direction == "zh2th":
        system_instruction = (
            "你是一名专业的中泰翻译官。"
            "任务：把用户输入的中文准确、地道地翻译成泰文。"
            "严格要求："
            "1) 只输出最终翻译好的泰文，禁止任何寒暄、解释、注脚；"
            "2) 不要在结果前后加引号、星号、破折号等装饰；"
            "3) 如果原文包含数字、人名、地名，请保留原始写法（必要时给出泰文音译）；"
            "4) 保持口语自然度，适合直接念给对方听。"
        )
        user_message = f"请翻译下面这段中文：\n{text}"
    else:  # th2zh
        system_instruction = (
            "你是一名专业的泰中翻译官。"
            "任务：把用户输入的泰文准确、地道地翻译成中文。"
            "严格要求："
            "1) 只输出最终翻译好的中文，禁止任何寒暄、解释、注脚；"
            "2) 不要在结果前后加引号、星号、破折号等装饰；"
            "3) 如果原文包含数字、人名、地名，请保留原始写法（必要时给出中文意译）；"
            "4) 保持口语自然度，适合直接念给对方听。"
        )
        user_message = f"请翻译下面这段泰文：\n{text}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
        "stream": False,
        # ★ 关掉深度思考：Seed 2.1 系列默认会"先想再说"，单次 60s+ 超时
        # 翻译是相对简单的任务，禁用思考既能秒回也省 token
        "thinking": {"type": "disabled"},
        # 注：service_tier="fast" 虽能进一步提速，但需要单独开通「快速档位」，会卡 ModelNotOpen
    }

    # ★ 关键：沙盒里 requests 默认会走系统 locale（latin-1），把 body 显式编码成 UTF-8 字节
    # 否则中文/泰文字符会报 "ordinal not in range(256)"
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    # 超时放到 90s，给网络抖动留余地（关思考后实际 2-3s 即可）
    resp = requests.post(url, headers=headers, data=body_bytes, timeout=90)
    resp.raise_for_status()
    data = resp.json()

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"豆包没有返回结果：{data}")

    content = choices[0].get("message", {}).get("content", "")
    if not content or not content.strip():
        raise RuntimeError("豆包返回了空内容。")

    return content.strip()


# === 3. 标题 + 侧边栏 ===
st.title("🇨🇳 🇹🇭 中泰互译")
st.caption("中泰双向翻译 · 大字显示 · 语音播放 · 麦克风输入")

with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input(
        "豆包 ARK API Key",
        type="password",
        placeholder="ark-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-xxxxx",
        help="火山方舟控制台 → 系统管理 → API Key 管理 → 创建，得到的 Key 以 `ark-` 开头。注意：不是 IAM 的 AK/SK。",
    )
    # 显示已识别 Key 的「前 4 字符…后 4 字符」让用户确认清洗对不对
    if api_key:
        import re
        stripped = (
            api_key.replace('"', "")
            .replace("'", "")
            .replace("`", "")
            .replace("Bearer", "")
            .strip()
        )
        m = re.search(r"(ark-[A-Za-z0-9-]+|AIza[A-Za-z0-9_-]+)", stripped)
        clean = m.group(1) if m else "".join(stripped.split())
        if clean and clean != stripped:
            st.caption(
                f"🔧 已自动清洗：检测到夹带字符，最终使用的 Key = `{clean[:6]}…{clean[-4:]}`（共 {len(clean)} 位）"
            )
        elif clean:
            st.caption(
                f"🔑 当前 Key = `{clean[:6]}…{clean[-4:]}`（共 {len(clean)} 位）"
            )
    model_name = st.text_input(
        "模型 ID",
        value="doubao-seed-2-1-turbo-260628",
        help=(
            "默认填 doubao-seed-2-1-turbo-260628（你账号下已实测可用、200 OK）。"
            "如果将来要换 Pro，只需把名字改一下即可。"
            "其他可选：`doubao-seed-2-1-pro-260628` / `doubao-seed-translation-250915`（专用翻译模型）。"
        ),
    )
    st.markdown("---")
    st.markdown(
        "**使用说明**\n\n"
        "1. 去 [火山引擎](https://www.volcengine.com/product/doubao) 注册并实名\n"
        "2. 进「**方舟 ARK**」→ 左侧「**系统管理 → API Key 管理**」→ 创建并复制 Key（`ark-` 开头）\n"
        "3. **开启安心体验模式**（**零费用**：只消耗 50w 免费 tokens，用完自动暂停，不扣费）→ 打开 [开通管理](https://console.volcengine.com/ark/region:cn-beijing/openManagement) → 在模型列表**最上方**「安心体验模式」横幅点开关\n"
        "4. 把 Key 粘到上方 → 输入中文 → **立即翻译**\n"
        "5. 按 `Ctrl/Cmd + Enter` 也可触发\n\n"
        "> ⚠️ **别点「一键开通所有模型」或「开通服务」**——那些是付费开通，会扣费。认准顶部「安心体验模式」开关。"
    )

    # === 网络诊断：测火山方舟连通性 ===
    st.markdown("---")
    st.markdown("**🩺 网络诊断**（首次刷新页面跑一次）")
    if "_net_diag" not in st.session_state:
        with st.spinner("检测沙盒出站…"):
            st.session_state["_net_diag"] = network_diagnose()
    diag = st.session_state["_net_diag"]

    if diag["dns_ok"] is False:
        st.error("❌ DNS 解析不到 ark.cn-beijing.volces.com")
        st.caption(f"详情：{diag['error']}")
    elif diag["tcp_ok"] is False:
        st.error("❌ TCP 握手失败（443 不通）")
        st.caption(f"详情：{diag['error']}")
    elif diag["https_status"] is None:
        st.error("❌ HTTPS 被截断 / TLS 失败")
        st.caption(f"详情：{diag['error']}")
    elif diag["https_status"] >= 400:
        st.warning(
            f"⚠️ 网络可达，但 HTTPS {diag['https_status']} — 通常是 Key 或权限问题，不是网络问题。"
        )
    else:
        st.success(
            f"✅ 出站正常：DNS → {diag['resolved_ip']}，TLS 通过，HTTPS {diag['https_status']}"
        )


# === 4. 翻译方向选择 + 输入区 ===
direction = st.radio(
    "翻译方向",
    options=["zh2th", "th2zh"],
    format_func=lambda x: "🇨🇳 中文 → 🇹🇭 泰文" if x == "zh2th" else "🇹🇭 泰文 → 🇨🇳 中文",
    horizontal=True,
    key="direction",
    label_visibility="collapsed",
)

input_label = "请输入中文：" if direction == "zh2th" else "请输入泰文："
input_placeholder_zh = "例如：你吃饭了吗？我们下午三点在酒店大堂见面。"
input_placeholder_th = "例如：สวัสดีครับ เราจะเจอกันที่ล็อบบี้ตอนบ่ายสามโมง"
user_input = st.text_area(
    input_label,
    height=120,
    placeholder=input_placeholder_zh if direction == "zh2th" else input_placeholder_th,
    key=f"user_input_{direction}",
)

# === 4.5 语音输入按钮（嵌入 iframe，不破坏 Streamlit React 树） ===
voice_input_lang = "zh-CN" if direction == "zh2th" else "th-TH"
voice_html = f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 4px 0;">
    <button id="micBtn" style="
        font-size: 18px; padding: 12px 22px;
        border: 2px solid #1E88E5; background: white; color: #1E88E5;
        border-radius: 12px; cursor: pointer; font-weight: 600;
    ">🎤 点击开始语音输入</button>
    <span id="status" style="margin-left: 12px; color: #666; font-size: 14px;"></span>
</div>
<script>
(function() {{
    const btn = document.getElementById('micBtn');
    const status = document.getElementById('status');
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {{
        btn.disabled = true;
        btn.style.opacity = 0.5;
        status.textContent = '⚠️ 当前浏览器不支持语音识别（iOS Safari / Chrome / Edge 可用）';
        return;
    }}
    let recognition = null;
    let recognizing = false;
    function releaseMic() {{
        if (recognition && recognizing) {{
            try {{
                // ★ 用 abort() 而不是 stop()，立即释放 mic 权限（iOS 上 stop() 会留尾巴）
                recognition.abort();
            }} catch (_) {{}}
            recognizing = false;
            btn.textContent = '🎤 点击开始语音输入';
            btn.style.background = 'white';
            status.textContent = '⏹ 已自动停止（页面切到后台）';
        }}
    }}
    btn.addEventListener('click', () => {{
        if (recognizing) {{
            releaseMic();
            return;
        }}
        recognition = new SR();
        recognition.lang = '{voice_input_lang}';
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.onstart = () => {{
            recognizing = true;
            btn.textContent = '⏹ 点击停止';
            btn.style.background = '#FFE0E0';
            status.textContent = '请说话…';
        }};
        recognition.onresult = (e) => {{
            let final = '', interim = '';
            for (let i = e.resultIndex; i < e.results.length; i++) {{
                if (e.results[i].isFinal) final += e.results[i][0].transcript;
                else interim += e.results[i][0].transcript;
            }}
            const text = (final || interim).trim();
            if (text) {{
                // ★ 把识别结果写回父页面的 textarea（绕过 React value 追踪）
                const ta = window.parent.document.querySelector('textarea');
                if (ta) {{
                    const setter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, 'value').set;
                    setter.call(ta, text);
                    ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
                status.textContent = '✓ ' + text;
            }}
        }};
        recognition.onend = () => {{
            recognizing = false;
            btn.textContent = '🎤 点击开始语音输入';
            btn.style.background = 'white';
        }};
        recognition.onerror = (e) => {{
            recognizing = false;
            btn.textContent = '🎤 点击开始语音输入';
            btn.style.background = 'white';
            if (e.error === 'not-allowed') {{
                status.textContent = '❌ 请允许麦克风权限';
            }} else if (e.error === 'no-speech') {{
                status.textContent = '⚠️ 没听到声音，再试一次';
            }} else if (e.error === 'aborted') {{
                status.textContent = '⏹ 已停止';
            }} else {{
                status.textContent = '❌ ' + e.error;
            }}
        }};
        recognition.start();
    }});
    // ★ 关键：监听页面可见性变化，自动释放麦克风
    //   - iOS 后台 / 锁屏 / Home → visibilitychange
    //   - 用户切到别的 app / 标签页 → visibilitychange
    //   - 浏览器卸载 / 导航走 → pagehide / beforeunload
    document.addEventListener('visibilitychange', () => {{
        if (document.hidden) releaseMic();
    }});
    window.addEventListener('pagehide', releaseMic);
    window.addEventListener('beforeunload', releaseMic);
    // ★ 监听来自父页面（Streamlit 主页面）隐藏事件（iframe 不一定会触发自己的 visibilitychange）
    try {{
        window.parent.document.addEventListener('visibilitychange', () => {{
            if (window.parent.document.hidden) releaseMic();
        }});
    }} catch (_) {{
        // 跨域时可能捕获不到，忽略即可
    }}
}})();
</script>
"""
components.html(voice_html, height=80)

# === 5. 翻译按钮 ===
translate_clicked = st.button("立即翻译", type="primary", use_container_width=True)
# 注：原计划用 <script> 注入监听 Ctrl/Cmd+Enter，但实测会破坏 Streamlit 的 React 树
# 报 "NotFoundError: insertBefore" 错；这里先去掉快捷键，纯按钮触发更稳


# === 6. 主逻辑 ===
if translate_clicked:
    if not api_key.strip():
        st.error("⚠️ 请先在左侧边栏填写豆包 ARK API Key。")
        st.stop()
    if not user_input.strip():
        st.warning("请输入要翻译的内容。")
        st.stop()

    try:
        with st.spinner("翻译中…"):
            result_text = translate(user_input, api_key, model_name, direction)

        result_label = "📝 泰文翻译" if direction == "zh2th" else "📝 中文翻译"
        st.subheader(result_label)
        st.markdown(
            f'<div class="translated-text">{result_text}</div>',
            unsafe_allow_html=True,
        )

        with st.expander("📋 复制用（纯文本）"):
            st.code(result_text, language="text")

        # === 6.5 播放语音按钮 ===
        tts_lang = "th-TH" if direction == "zh2th" else "zh-CN"
        tts_label_text = "泰文" if direction == "zh2th" else "中文"
        # 安全的属性值转义
        safe_text = result_text.replace("&", "&amp;").replace('"', "&quot;").replace("'", "&#39;").replace("\n", " ")
        tts_html = f"""
<div style="margin-top: 12px;">
    <button id="ttsBtn" data-text="{safe_text}" data-lang="{tts_lang}" style="
        font-size: 18px; padding: 12px 22px;
        border: none; background: #1E88E5; color: white;
        border-radius: 12px; cursor: pointer; font-weight: 600;
    ">🔊 播放 {tts_label_text}语音</button>
    <button id="stopBtn" style="
        font-size: 18px; padding: 12px 22px;
        border: 2px solid #ccc; background: white; color: #666;
        border-radius: 12px; cursor: pointer; margin-left: 8px;
    ">⏹ 停止</button>
    <span id="ttsStatus" style="margin-left: 12px; color: #666; font-size: 13px;"></span>
</div>
<script>
(function() {{
    const ttsBtn = document.getElementById('ttsBtn');
    const stopBtn = document.getElementById('stopBtn');
    const status = document.getElementById('ttsStatus');
    let targetLang = ttsBtn.getAttribute('data-lang');
    function pickVoice() {{
        const voices = speechSynthesis.getVoices();
        if (!voices.length) return null;
        // 优先选精确语言匹配；其次同语言族
        return voices.find(v => v.lang === targetLang)
            || voices.find(v => v.lang.startsWith(targetLang.split('-')[0]))
            || null;
    }}
    ttsBtn.addEventListener('click', () => {{
        const text = ttsBtn.getAttribute('data-text');
        if (!text) return;
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = targetLang;
        u.rate = 0.9;
        u.pitch = 1.0;
        const v = pickVoice();
        if (v) u.voice = v;
        u.onstart = () => {{ status.textContent = '🔊 播放中…'; }};
        u.onend = () => {{ status.textContent = '✓ 播放完毕'; }};
        u.onerror = (e) => {{ status.textContent = '❌ 播放失败：' + e.error; }};
        speechSynthesis.speak(u);
        // 如果设备没装目标语言包，给出提示
        if (!v) {{
            setTimeout(() => {{
                if (speechSynthesis.speaking === false && speechSynthesis.pending === false) {{
                    status.textContent = '⚠️ 设备可能未安装 ' + targetLang + ' 语音包';
                }}
            }}, 800);
        }}
    }});
    stopBtn.addEventListener('click', () => {{
        speechSynthesis.cancel();
        status.textContent = '⏹ 已停止';
    }});
    // 部分浏览器 getVoices 是异步的
    if (typeof speechSynthesis.onvoiceschanged !== 'undefined') {{
        speechSynthesis.onvoiceschanged = () => pickVoice();
    }}
    // ★ 切走页面时自动停止朗读（避免后台空响、节省电）
    function autoStop() {{
        if (speechSynthesis.speaking || speechSynthesis.pending) {{
            speechSynthesis.cancel();
            status.textContent = '⏹ 已停止（切后台）';
        }}
    }}
    document.addEventListener('visibilitychange', () => {{
        if (document.hidden) autoStop();
    }});
    window.addEventListener('pagehide', autoStop);
    window.addEventListener('beforeunload', autoStop);
    try {{
        window.parent.document.addEventListener('visibilitychange', () => {{
            if (window.parent.document.hidden) autoStop();
        }});
    }} catch (_) {{}}
}})();
</script>
"""
        components.html(tts_html, height=80)

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        detail = ""
        try:
            err_json = e.response.json()
            err = err_json.get("error", {})
            if isinstance(err, dict):
                detail = err.get("message") or err_json
            else:
                detail = str(err_json)
        except Exception:
            detail = e.response.text[:200]

        if status == 401:
            st.error(f"API Key 无效（401）：{detail}")
            st.caption(
                "多半是 Key 拿错了或格式不对。请到「方舟控制台 → 系统管理 → API Key 管理」"
                "重新创建，确认是 `ark-` 开头的 Key，且完整复制（不要带空格/换行）。"
                "注意：IAM 的 AK/SK 不能用。"
            )
        elif status == 402:
            st.error(f"余额不足（402）：{detail}")
        elif status == 429:
            st.error("请求太频繁（429），请稍后再试。")
        elif status == 400:
            st.error(f"请求参数错误（400）：{detail}")
        elif status == 403:
            st.error(f"无权限调用该模型（403）：{detail} — 可能需要先在 ARK 控制台开通该模型权限")
        elif status == 404:
            if "not activated" in str(detail) or "ModelNotOpen" in str(detail):
                st.error("模型未开通（ModelNotOpen）")
                st.caption(
                    "你的 Key 是对的，但需要先在方舟开启「**安心体验模式**」才能用免费额度。"
                    "打开 https://console.volcengine.com/ark/region:cn-beijing/openManagement "
                    "→ 在模型列表**最上方**「安心体验模式」横幅点开关（**零费用**：50w tokens 用完自动暂停，不扣费）。"
                )
            else:
                st.error(f"模型不存在（404）：{detail}")
                st.caption(
                    "model 字段填错了。豆包方舟要填「模型 ID」（带版本日期，如 doubao-seed-2-1-pro-260628）"
                    "或推理接入点 ID（ep- 开头）。去方舟控制台「模型列表」复制最新的模型 ID。"
                )
        else:
            st.error(f"HTTP 错误 {status}：{detail}")

    except Exception as e:
        st.error(f"翻译出错：{e}")
        st.caption(
            "常见原因：API Key 不正确 / 该 Key 没开通方舟 ARK / 模型没在控制台开通权限 / 网络异常。"
        )

st.markdown("---")
st.caption("Powered by 字节豆包 · Made with Streamlit")
