#!/bin/bash

# Whisper-CLI 快速启动脚本
# 跳过检查，直接启动

echo "🚀 快速启动 Whisper-CLI..."

if command -v uv &> /dev/null; then
    exec uv run python main.py
else
    exec python3 main.py
fi