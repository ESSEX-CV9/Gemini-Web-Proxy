# 🚀 Gemini to OpenAI API Proxy

将 Gemini 网页版包装为 OpenAI API 格式，让你能在其他前端中使用。

## ✨ 特性

- ✅ 完全兼容 OpenAI API 格式
- ✅ 支持流式响应（SSE）
- ✅ 自动复用 Chrome 登录态，无需重复登录
- ✅ 使用浏览器自动化，绕过 API 限制
- ✅ 简单易用，开箱即用

## 📋 前置要求

1. **Python 3.8+**
2. **Google Chrome 浏览器** 已安装并登录 Gemini Pro

## 🔧 安装步骤

### 1. 克隆或下载项目

```bash
cd gemini-proxy
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 4. 配置 Chrome 路径（可选）

编辑 `config.py`，确认 `CHROME_USER_DATA` 路径正确：

**Windows:**
```python
CHROME_USER_DATA = "C:/Users/你的用户名/AppData/Local/Google/Chrome/User Data"
```

**Mac:**
```python
CHROME_USER_DATA = "/Users/你的用户名/Library/Application Support/Google/Chrome"
```

**Linux:**
```python
CHROME_USER_DATA = "/home/你的用户名/.config/google-chrome"
```

> 💡 程序会自动检测系统并设置默认路径，通常不需要手动修改。

### 5. 启动服务

```bash
python main.py
```

你会看到：

```
🚀 Gemini to OpenAI API Proxy
============================================================
📍 监听地址: http://127.0.0.1:5000
🌐 Chrome 用户数据: /path/to/chrome/user/data
👁️  Headless 模式: True
============================================================

💡 提示：
   1. 请确保 Chrome 浏览器已登录 Gemini Pro
   2. 首次启动会打开浏览器，请保持运行
   3. 在模型API链接中配置:
      API Base URL: http://127.0.0.1:5000/v1
      Model: gemini-pro
```

## 🎮 使用方法

### 一键启动

运行 run.bat/run.sh 文件，其会自动安装需求，并启动反代

### 在你需要LLM的程序中配置

1. 打开openAI或者openAI兼容的API设置
2. 配置 API：
   - **API Base URL**: `http://127.0.0.1:5000/v1`
   - **API Key**: 任意填写（会被忽略）
   - **Model**: `gemini-pro`

### 测试 API

```bash
# 测试健康状态
curl http://127.0.0.1:5000/health

# 列出模型
curl http://127.0.0.1:5000/v1/models

# 发送聊天请求（非流式）
curl http://127.0.0.1:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-pro",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'

# 发送聊天请求（流式）
curl http://127.0.0.1:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-pro",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

## ⚙️ 配置选项

在 `config.py` 中可以修改：

```python
# Flask 服务器配置
HOST = "127.0.0.1"  # 监听地址
PORT = 5000         # 监听端口

# 浏览器配置
HEADLESS = True     # 是否无头模式（不显示浏览器窗口）
TIMEOUT = 30000     # 超时时间（毫秒）

# 调试模式
DEBUG = True        # 是否打印调试信息

# DOM流式配置 ---- 实验性功能 谨慎使用 ----
USE_DOM_STREAMING = True # 流式模式是否使用DOM监听（True=真流式，False=假流式）
```

## 🐛 故障排除

### 问题 1: "Chrome 用户数据目录不存在"

**解决方案：**
1. 确保 Chrome 已安装
2. 手动设置 `config.py` 中的 `CHROME_USER_DATA` 路径
3. 确保 Chrome 已经运行过至少一次

### 问题 2: "未登录 Gemini"

**解决方案：**
1. 手动打开 Chrome 浏览器
2. 访问 gemini.google.com 并登录
3. 重新启动代理服务

### 问题 3: "浏览器启动失败"

**解决方案：**
1. 运行 `playwright install chromium`
2. 确保没有其他程序占用 Chrome 配置文件，**最好直接关闭所有的当前正在使用的Chrome浏览器！**
3. 尝试设置 `HEADLESS = False` 查看浏览器窗口

### 问题 4: "响应超时"

**解决方案：**
1. 增加 `config.py` 中的 `TIMEOUT` 值
2. 检查网络连接
3. 查看是否触发了 Gemini 的安全验证

## 📖 工作原理

```
IDE (Kilo Code)
    ↓ HTTP (OpenAI API 格式)
Flask 服务器 (localhost:5000)
    ↓ Playwright 控制
Chrome 浏览器 (Headless)
    ↓ 已登录
Gemini Pro 网页版
```

1. **启动**: Playwright 启动 Chrome，使用你现有的用户配置（保留登录态）
2. **请求**: Flask 接收 OpenAI 格式的 API 请求
3. **转发**: 在 Gemini 网页中模拟用户输入
4. **响应**: 监听网络响应，提取文本内容
5. **转换**: 将 Gemini 格式转换为 OpenAI SSE 格式返回

## ⚠️ 注意事项

1. **服务条款**: 此方法可能违反 Google 的服务条款，使用风险自负
2. **账号安全**: 建议使用小号测试，避免主账号被封
3. **性能**: 首次请求会较慢（需要打开浏览器），后续请求会快很多

## 🔒 安全建议

- 仅在本地使用，不要暴露到公网
- 不要分享你的 API 服务给他人
- 定期检查 Google 账号的安全日志

## 💡 常见问题

**Q: 为什么不直接用 Google AI Studio API？**
A: Pro 会员不提供额外的 API 配额，如果你不想用GAS的免费层级key或者GAS的key当日额度用完了，可以用这个临时凑合一下。

**Q: 这个方案稳定吗？**
A: 相对稳定，但 Google 可能随时更改网页结构导致失效。

**Q: 支持多轮对话吗？**
A: 目前每次请求都是独立的，不保存对话历史。可以通过在请求中包含完整对话历史来实现。

**Q: 可以部署到服务器吗？**
A: 可以，但需要在服务器上安装图形界面或使用 Xvfb。

## 📞 联系方式

有问题？欢迎提 Issue！
