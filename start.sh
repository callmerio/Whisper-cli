#!/bin/bash

# Gemini 语音转录系统启动脚本
# 基于 Gemini-2.5-Flash 模型，无需本地 whisper.cpp

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

HOTKEY_INFO=$(python3 <<'PY'
try:
    import config
    labels = list(dict.fromkeys(getattr(config, "HOTKEY_DISPLAY_LABELS", None) or [getattr(config, "HOTKEY_PRIMARY_LABEL", "Command")]))
    hint = " / ".join(labels)
    primary = labels[0] if labels else "Command"
except Exception:
    hint = "Command"
    primary = "Command"
print(hint)
print(primary)
PY
)

if [[ -n "$HOTKEY_INFO" ]]; then
    IFS=$'\n' read -r HOTKEY_HINT HOTKEY_PRIMARY_LABEL <<< "$HOTKEY_INFO"
fi

HOTKEY_HINT="${HOTKEY_HINT:-Command}"
HOTKEY_PRIMARY_LABEL="${HOTKEY_PRIMARY_LABEL:-$HOTKEY_HINT}"

# 项目虚拟环境路径（优先使用外部传入的 UV_PROJECT_ENVIRONMENT）
PROJECT_VENV_PATH="${UV_PROJECT_ENVIRONMENT:-.venv}"
VENV_ACTIVATED=0

if [[ -f ".venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
    PROJECT_VENV_PATH=".venv"
    VENV_ACTIVATED=1
    export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$PROJECT_VENV_PATH}"
    echo "已预加载本地虚拟环境 .venv"
fi

# 打印彩色信息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${PURPLE}🤖 Gemini 语音转录系统 v1.0${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "${GREEN}🌐 云端转录: Gemini-2.5-Flash${NC}"
    echo -e "${GREEN}🤖 智能纠错: Gemini-2.0-Flash-Exp${NC}"  
    echo -e "${GREEN}📚 用户词典: 智能匹配优化${NC}"
    echo -e "${GREEN}🔔 通知系统: 全方位反馈${NC}"
    echo -e "${CYAN}========================================${NC}"
}

# 检查系统要求
check_requirements() {
    print_info "检查系统环境..."
    
    # 检查操作系统
    if [[ "$OSTYPE" == "darwin"* ]]; then
        print_success "操作系统: macOS (支持全局快捷键)"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_warning "操作系统: Linux (快捷键功能可能受限)"
    else
        print_warning "操作系统: $OSTYPE (可能存在兼容性问题)"
    fi
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        print_error "未找到 Python3，请先安装 Python 3.8+"
        echo "安装方法:"
        echo "  macOS: brew install python"
        echo "  Linux: sudo apt install python3"
        exit 1
    else
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        print_success "Python: $PYTHON_VERSION"
    fi
    
    # 检查 uv
    if command -v uv &> /dev/null; then
        print_success "包管理器: uv (推荐)"
    else
        print_warning "包管理器: 未找到 uv，将使用 python3"
        print_info "推荐安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    fi
    
    # 检查 Google Generative AI SDK
    if python3 -c "import google.generativeai" 2>/dev/null; then
        print_success "Gemini SDK: google-generativeai"
    else
        print_warning "Gemini SDK: 未安装 google-generativeai"
        print_info "将尝试自动安装依赖"
    fi
    
    # 检查 .env 文件
    if [[ -f ".env" ]]; then
        if grep -q "GEMINI_API_KEY" .env && [[ $(grep "GEMINI_API_KEY" .env | cut -d'=' -f2) != "" ]]; then
            print_success "配置: Gemini API 密钥已设置"
        else
            print_error "配置: Gemini API 密钥未设置"
            print_info "请在 .env 文件中设置 GEMINI_API_KEY"
            echo ""
            echo "获取 API 密钥的方法:"
            echo "1. 访问 https://aistudio.google.com/app/apikey"
            echo "2. 创建新的 API 密钥"
            echo "3. 在 .env 文件中添加: GEMINI_API_KEY=your_api_key"
            exit 1
        fi
    else
        print_error "配置: .env 文件未找到"
        print_info "请创建 .env 文件并设置 GEMINI_API_KEY"
        echo ""
        echo "创建 .env 文件:"
        echo "echo 'GEMINI_API_KEY=your_api_key' > .env"
        echo ""
        echo "获取 API 密钥: https://aistudio.google.com/app/apikey"
        exit 1
    fi
    
    # 检查用户词典
    if [[ -f "dic.txt" ]]; then
        DICT_COUNT=$(grep -v '^#' dic.txt | grep -v '^$' | wc -l | tr -d ' ')
        print_success "用户词典: $DICT_COUNT 个词汇"
    else
        print_info "用户词典: 将自动创建默认词典"
    fi
}

# 检查权限
check_permissions() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        print_info "检查 macOS 权限..."
        print_warning "首次运行需要授权以下权限:"
        print_info "1. 辅助功能 (全局快捷键)"
        print_info "2. 麦克风访问 (音频录制)"  
        print_info "3. 通知权限 (系统通知)"
        echo ""
        print_info "如遇权限问题，请前往:"
        print_info "系统偏好设置 > 隐私与安全 > 辅助功能"
        echo ""
    fi
}

# 安装依赖
install_dependencies() {
    print_info "检查并安装依赖..."

    if command -v uv &> /dev/null; then
        if [[ -z "$UV_PROJECT_ENVIRONMENT" ]]; then
            export UV_PROJECT_ENVIRONMENT="$PROJECT_VENV_PATH"
        else
            PROJECT_VENV_PATH="$UV_PROJECT_ENVIRONMENT"
        fi

        print_info "检测到 uv，使用环境: $PROJECT_VENV_PATH"
        UV_PROJECT_ENVIRONMENT="$PROJECT_VENV_PATH" uv sync
        print_success "uv 同步完成"

        if [[ -f "$PROJECT_VENV_PATH/bin/activate" ]]; then
            # shellcheck disable=SC1091
            source "$PROJECT_VENV_PATH/bin/activate"
            VENV_ACTIVATED=1
            print_success "已切换到 UV 虚拟环境 $PROJECT_VENV_PATH"
        else
            print_warning "未找到 $PROJECT_VENV_PATH/bin/activate，uv 将在运行时自动管理环境"
        fi
    else
        if [[ ! -f ".venv/bin/activate" ]]; then
            print_info "创建本地虚拟环境 (.venv)..."
            python3 -m venv .venv
        fi

        # shellcheck disable=SC1091
        source ".venv/bin/activate"
        PROJECT_VENV_PATH=".venv"
        VENV_ACTIVATED=1
        print_success "已启用虚拟环境 .venv"

        REQUIRED_PACKAGES=("google-generativeai" "pyperclip" "python-dotenv" "pynput" "sounddevice" "numpy")
        for package in "${REQUIRED_PACKAGES[@]}"; do
            if ! python3 -c "import $package" 2>/dev/null; then
                print_info "安装 $package..."
                python3 -m pip install "$package"
            fi
        done
        print_success "pip 依赖安装完成"
    fi

    print_success "依赖检查完成"
}

activate_virtualenv() {
    if [[ "$VENV_ACTIVATED" -eq 1 ]]; then
        return
    fi

    if [[ -f "$PROJECT_VENV_PATH/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "$PROJECT_VENV_PATH/bin/activate"
        VENV_ACTIVATED=1
        print_success "已切换到虚拟环境 $PROJECT_VENV_PATH"
    else
        print_warning "未找到虚拟环境 $PROJECT_VENV_PATH，将继续使用系统 Python"
    fi
}

export VOICE_SESSION_MODE="batch"
export SEGMENT_ENABLE_AUTO_OUTPUT="False"
export SEGMENT_OUTPUT_METHOD="clipboard"

# 选择转录模型
select_transcription_model() {
    echo ""
    echo -e "${CYAN}📋 选择转录模型:${NC}"
    echo -e "${GREEN}1.${NC} Gemini 2.5 Pro - 最高精度，功能最全面"
    echo -e "${GREEN}2.${NC} Gemini 2.5 Flash ${YELLOW}(推荐)${NC} - 平衡性能和精度"
    echo -e "${GREEN}3.${NC} Gemini 2.5 Flash Lite - 最快速度，无思考模式"
    echo ""
    
    while true; do
        read -p "请选择模型 (1-3，默认2): " choice
        case $choice in
            1)
                export GEMINI_TRANSCRIPTION_MODEL="gemini-2.5-pro"
                export MODEL_SUPPORTS_THINKING=true
                print_success "已选择: Gemini 2.5 Pro"
                break
                ;;
            ""|2)
                export GEMINI_TRANSCRIPTION_MODEL="gemini-2.5-flash"
                export MODEL_SUPPORTS_THINKING=true
                print_success "已选择: Gemini 2.5 Flash (推荐)"
                break
                ;;
            3)
                export GEMINI_TRANSCRIPTION_MODEL="gemini-2.5-flash-lite"
                export MODEL_SUPPORTS_THINKING=false
                export GEMINI_THINKING_BUDGET=0
                print_success "已选择: Gemini 2.5 Flash Lite (固定快速模式)"
                break
                ;;
            *)
                print_warning "无效选择，请输入 1-3"
                ;;
        esac
    done
}

# 选择思考模式
select_thinking_mode() {
    # 如果模型不支持思考模式，直接跳过
    if [[ "$MODEL_SUPPORTS_THINKING" != "true" ]]; then
        print_info "当前模型不支持思考模式配置，已设为快速模式"
        return
    fi
    
    echo ""
    echo -e "${CYAN}🧠 选择思考模式:${NC}"
    echo -e "${GREEN}1.${NC} 快速模式 ${YELLOW}(推荐)${NC} - 无思考，响应快速"
    echo -e "${GREEN}2.${NC} 平衡模式 - 适度思考，平衡速度和精度"
    echo -e "${GREEN}3.${NC} 精确模式 - 深度思考，最高精度"
    echo ""
    
    while true; do
        read -p "请选择模式 (1-3，默认1): " choice
        case $choice in
            ""|1)
                export GEMINI_THINKING_BUDGET=0
                print_success "已选择: 快速模式 (无思考)"
                break
                ;;
            2)
                export GEMINI_THINKING_BUDGET=5000
                print_success "已选择: 平衡模式 (适度思考)"
                break
                ;;
            3)
                export GEMINI_THINKING_BUDGET=10000
                print_success "已选择: 精确模式 (深度思考)"
                break
                ;;
            *)
                print_warning "无效选择，请输入 1-3"
                ;;
        esac
    done
}

# 显示使用方法
show_usage() {
    echo ""
    echo -e "${CYAN}📖 使用方法:${NC}"
    echo -e "${GREEN}1. 按住 ${HOTKEY_HINT} 键${NC} → 开始录音"
    echo -e "${GREEN}2. 松开 ${HOTKEY_PRIMARY_LABEL} 键${NC} → 停止录音并处理"
    echo -e "${GREEN}3. 系统会自动粘贴，如需再次使用可按 Cmd+V${NC}"
    echo ""
    echo -e "${CYAN}🌐 一口气流程:${NC}"
    echo -e "${GREEN}• 本地录音${NC} → 高质量音频采集"
    echo -e "${GREEN}• Gemini转录${NC} → 云端智能转录并即时润色"
    echo -e "${GREEN}• 词典优化${NC} → 专业术语匹配"
    echo -e "${GREEN}• 自动输出${NC} → 复制到剪贴板"
    
    echo ""
    echo -e "${CYAN}🔔 通知功能:${NC}"
    echo -e "${GREEN}• 系统通知${NC} → macOS 通知中心弹窗"
    echo -e "${GREEN}• 声音反馈${NC} → 不同操作播放不同音效"
    echo -e "${GREEN}• 视觉提示${NC} → 精美的控制台显示框"
    echo ""
    echo -e "${CYAN}⚙️  配置文件:${NC}"
    echo -e "${GREEN}• config.py${NC} → 基础配置和功能开关"
    echo -e "${GREEN}• dic.txt${NC} → 用户词典文件"
    echo -e "${GREEN}• .env${NC} → Gemini API 密钥配置"
    echo ""
    
    # 显示选择的配置摘要
    echo -e "${CYAN}📋 当前配置摘要:${NC}"
    echo -e "${GREEN}• 工作模式:${NC} 一口气模式"
    echo -e "${GREEN}• 输出方式:${NC} 复制到剪贴板"
    echo -e "${GREEN}• 转录模型:${NC} ${GEMINI_TRANSCRIPTION_MODEL:-gemini-2.5-flash}"
    if [[ "$MODEL_SUPPORTS_THINKING" == "true" ]]; then
        echo -e "${GREEN}• 思考模式:${NC} budget=${GEMINI_THINKING_BUDGET:-0}"
    fi
    echo ""
    
    echo -e "${CYAN}🆚 模式说明:${NC}"
    echo -e "${GREEN}• 一口气模式${NC} → 录音结束后统一输出，更稳定可靠"
    echo ""
}

# 主函数
main() {
    # 清屏
    clear
    
    # 显示标题
    print_header
    
    # 检查要求
    check_requirements
    
    # 安装依赖
    install_dependencies
    
    # 配置选择
    select_transcription_model
    select_thinking_mode

    # 检查权限
    check_permissions

    # 切换虚拟环境
    activate_virtualenv

    # 显示使用方法
    show_usage
    
    # 询问是否继续
    echo -e "${YELLOW}按 Enter 启动 Gemini 语音转录系统，或 Ctrl+C 取消...${NC}"
    read -r
    
    # 启动程序
    print_info "正在启动 Gemini 语音转录系统..."
    echo ""
    
    # 选择运行方式
    if command -v uv &> /dev/null; then
        if [[ "$VENV_ACTIVATED" -eq 1 ]]; then
            print_success "使用虚拟环境中的 python 运行"
            exec python main.py
        else
            print_success "使用 uv run 启动（自动加载环境）"
            exec uv run python main.py
        fi
    else
        print_success "使用 python3 运行"
        exec python3 main.py
    fi
}

# 错误处理
trap 'print_error "启动脚本被中断"; exit 1' INT TERM

# 运行主函数
main
