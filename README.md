# 中泰极简大字翻译器

一个基于 **Streamlit + 字节豆包（豆包 ARK）** 的极简中文 ↔ 泰文翻译工具，主打"纯净、大字、零废话"。

## 特性

- 🎯 **纯净输出**：通过 system instruction 强约束 AI 只输出翻译结果，屏蔽所有寒暄、解释、装饰
- 🔠 **大字号展示**：38px 翻译结果，蓝底高亮，适合面对面翻译时给泰方看
- 🔄 **双向切换**：一键在"中 → 泰"和"泰 → 中"之间切换
- 🎤 **语音输入**：浏览器内嵌麦克风识别（zh-CN / th-TH）
- 🔊 **语音播放**：浏览器原生 TTS 朗读翻译结果
- 🔑 **Key 鲁棒清洗**：自动从用户复制粘贴中抠出真正可用的 API Key

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

打开 http://localhost:8501，左侧边栏粘贴你的豆包 ARK API Key 即可使用。

## 部署

可一键部署到 **Streamlit Community Cloud**（免费、稳定、不会休眠）。

### 一、需要准备的资料

1. **豆包 ARK API Key**
   - 去 https://www.volcengine.com/product/doubao 注册、实名、开通方舟
   - 进入方舟控制台 → 系统管理 → API Key 管理 → 创建 Key（形如 `ark-xxxx-...`）
   - 进入方舟控制台 → https://console.volcengine.com/ark/region:cn-beijing/openManagement → 「一键开通所有模型」或点开 turbo 模型

2. **GitHub 账号**（一次性）
   - 没账号的话去 https://github.com 注册一个

### 二、3 分钟部署步骤

1. **把这个项目推到 GitHub**
   - 登录 GitHub → 点右上角 `+` → `New repository` → 名字填 `zh-th-translator`（必须 Public）→ `Create`
   - 在本地命令行执行：
     ```bash
     cd path/to/zh-th-translator
     git init
     git add .
     git commit -m "init"
     git branch -M main
     git remote add origin git@github.com:你的用户名/zh-th-translator.git
     git push -u origin main
     ```

2. **Streamlit Community Cloud 部署**
   - 打开 https://share.streamlit.io
   - 用 GitHub 账号登录
   - 点 `New app` → 选 repo `你的用户名/zh-th-translator` → branch `main` → main file path `app.py`
   - 点 `Deploy!`
   - 等 1-2 分钟，会拿到一个永久链接：
     ```
     https://你的用户名-zh-th-translator-app-xxxxxxxx.streamlit.app/
     ```
   - 打开链接，左侧边栏粘 API Key → 翻译

## 技术栈

- **Streamlit**（前端 + 服务端）
- **requests**（直接调豆包 ARK OpenAI 兼容 API，避免 google-genai SDK 在 AQ.Key 上的兼容问题）
- **浏览器原生 Web Speech API**（语音识别 + TTS，零成本）

## API 调用要点

- Endpoint：`https://ark.cn-beijing.volces.com/api/v3/chat/completions`
- Model：`doubao-seed-2-1-turbo-260628`
- 请求体关键参数：
  ```json
  {
    "thinking": {"type": "disabled"},
    "temperature": 0.2
  }
  ```
  **`thinking.disabled` 必加**：Seed 2.1 系列默认深度思考模式，单次请求会跑到 60 秒超时。

## License

MIT
