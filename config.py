"""
配置文件
"""
import os
from pathlib import Path

# Flask 服务器配置
HOST = "127.0.0.1"
PORT = 5000

# Chrome 用户数据目录（根据你的系统调整）
# Windows: C:/Users/你的用户名/AppData/Local/Google/Chrome/User Data
# Mac: ~/Library/Application Support/Google/Chrome
# Linux: ~/.config/google-chrome

# 自动检测系统并设置默认路径
if os.name == 'nt':  # Windows
    CHROME_USER_DATA = str(Path.home() / "AppData/Local/Google/Chrome/User Data")
elif os.sys.platform == 'darwin':  # Mac
    CHROME_USER_DATA = str(Path.home() / "Library/Application Support/Google/Chrome")
else:  # Linux
    CHROME_USER_DATA = str(Path.home() / ".config/google-chrome")

# 如果需要自定义，取消注释下面这行
# CHROME_USER_DATA = "/path/to/your/chrome/user/data"

# Gemini 配置
GEMINI_URL = "https://gemini.google.com/app"

# 浏览器配置
HEADLESS = False  # 是否无头模式（True = 不显示浏览器窗口）
TIMEOUT = 60000  # 浏览器操作超时时间（毫秒）

# 响应等待配置
RESPONSE_TIMEOUT = 1200  # 响应等待超时时间（秒），默认20分钟

# 调试模式
DEBUG = False

# 模型配置
AVAILABLE_MODELS = {
    "gemini-pro": {
        "name": "思考",
        "description": "让 Gemini Pro 协助你深入思考复杂主题",
        "selector_text": "思考"
    },
    "gemini-flash": {
        "name": "快速",
        "description": "快速回答",
        "selector_text": "快速"
    }
}

DEFAULT_MODEL = "gemini-pro"

# 思维链配置
THINKING_FORMAT = "reasoning_content"  # 可选值: "reasoning_content" (o1格式) 或 "inline" (内联格式)
ENABLE_THINKING = True  # 是否启用思维链返回

# DOM流式配置 ---- 实验性功能 谨慎使用 ----
USE_DOM_STREAMING = True  # 流式模式是否使用DOM监听（True=真流式，False=假流式）
DOM_POLL_INTERVAL = 0.2  # DOM轮询间隔（秒）
DOM_STABLE_TIMEOUT = 20  # 文本不变化多少秒后判定完成（秒）