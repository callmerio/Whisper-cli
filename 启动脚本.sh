#!/bin/bash

# Whisper-CLI 语音转录系统启动脚本

echo "🎤 启动 Whisper-CLI 语音转录系统"
echo "=================================="

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装 Python"
    exit 1
fi

# 检查 uv 是否安装
if command -v uv &> /dev/null; then
    echo "✅ 检测到 uv，使用 uv 运行"
    uv run python main.py
elif command -v python3 &> /dev/null; then
    echo "✅ 使用 Python3 运行"
    python3 main.py
else
    echo "❌ 无法运行，请检查 Python 环境"
    exit 1
fi