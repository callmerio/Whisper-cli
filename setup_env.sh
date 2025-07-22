#!/bin/bash

# 语音转录系统环境配置脚本

echo "🔧 设置语音转录系统环境变量"
echo "=================================="

# 检查是否提供了API密钥参数
if [ -z "$1" ]; then
    echo "用法: ./setup_env.sh YOUR_GEMINI_API_KEY"
    echo ""
    echo "示例:"
    echo "  ./setup_env.sh AIzaSyCghQgmKgIeG4pWjCWlhS44cwcGWBpgFLE"
    echo ""
    echo "或者手动设置:"
    echo "  export GEMINI_API_KEY='YOUR_API_KEY'"
    exit 1
fi

API_KEY="$1"

# 添加到当前shell
export GEMINI_API_KEY="$API_KEY"

# 添加到 .bash_profile 或 .zshrc
SHELL_RC=""
if [ -f ~/.zshrc ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f ~/.bash_profile ]; then
    SHELL_RC="$HOME/.bash_profile"
elif [ -f ~/.bashrc ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    # 检查是否已存在
    if grep -q "GEMINI_API_KEY" "$SHELL_RC"; then
        echo "⚠️  GEMINI_API_KEY 已存在于 $SHELL_RC"
        echo "请手动更新或删除旧的配置"
    else
        echo "" >> "$SHELL_RC"
        echo "# 语音转录系统 Gemini API 配置" >> "$SHELL_RC"
        echo "export GEMINI_API_KEY='$API_KEY'" >> "$SHELL_RC"
        echo "✅ 已添加到 $SHELL_RC"
    fi
else
    echo "⚠️  未找到shell配置文件，请手动设置环境变量:"
    echo "export GEMINI_API_KEY='$API_KEY'"
fi

echo ""
echo "🔐 安全提醒:"
echo "  - 请勿在代码中直接写入API密钥"
echo "  - 请勿将API密钥提交到git仓库"
echo "  - 定期更换API密钥"
echo ""
echo "✅ 配置完成！重启终端或执行 'source $SHELL_RC' 后即可使用"