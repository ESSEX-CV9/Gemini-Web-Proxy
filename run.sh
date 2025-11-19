#!/bin/bash
# Linux/Mac 智能启动脚本 - 自动检测并安装依赖

echo "=============================="
echo "Gemini Web Proxy"
echo "=============================="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装 Python 3.8+"
    echo "[提示] Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "[提示] Mac: brew install python3"
    exit 1
fi

echo "[成功] Python 已安装"
python3 --version
echo ""

# 检查依赖是否安装
echo "[检查] 正在检查依赖..."
if ! python3 -c "import flask" &> /dev/null; then
    echo "[提示] 检测到依赖未安装，开始自动安装..."
    echo ""
    
    # 安装 Python 依赖
    echo "[进行中] 安装 Python 依赖..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[错误] 依赖安装失败"
        exit 1
    fi
    
    # 安装 Playwright 浏览器
    echo ""
    echo "[进行中] 安装 Playwright 浏览器..."
    playwright install chromium
    if [ $? -ne 0 ]; then
        echo "[错误] Playwright 浏览器安装失败"
        exit 1
    fi
    
    echo ""
    echo "[成功] 依赖安装完成！"
    echo ""
else
    echo "[成功] 依赖已安装"
    echo ""
fi

# 启动服务
echo "=============================="
echo "[启动] 正在启动 Gemini Proxy 服务..."
echo "=============================="
echo ""
echo "[提示] 按 Ctrl+C 可停止服务"
echo ""
echo "[配置信息]"
echo "   API Base URL: http://127.0.0.1:5000/v1"
echo "   Model: gemini-pro"
echo ""
echo "=============================="
echo ""

# 启动主程序
python3 main.py

echo ""
echo "[信息] 服务已停止"