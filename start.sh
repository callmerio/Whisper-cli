#!/bin/bash

# Whisper-CLI 语音转录系统启动脚本 v2.0
# 支持智能通知、AI纠错、用户词典等功能

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

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
    echo -e "${PURPLE}🎤 Whisper-CLI 语音转录系统 v2.0${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo -e "${GREEN}🔔 新增功能: 智能通知系统${NC}"
    echo -e "${GREEN}🤖 AI纠错: Gemini 2.5 Flash${NC}"  
    echo -e "${GREEN}📚 用户词典: 智能匹配优化${NC}"
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
    
    # 检查 whisper.cpp
    if command -v whisper-cli &> /dev/null; then
        print_success "Whisper引擎: whisper-cli"
    elif command -v whisper-cpp &> /dev/null; then
        print_success "Whisper引擎: whisper-cpp"  
    elif command -v main &> /dev/null; then
        print_success "Whisper引擎: main"
    else
        print_warning "Whisper引擎: 未检测到 whisper.cpp"
        print_info "安装方法: brew install whisper-cpp"
    fi
    
    # 检查模型文件
    if [[ -f "/Users/bigdan/Library/Application Support/MacWhisper/models/ggml-model-whisper-turbo.bin" ]]; then
        print_success "Whisper模型: turbo (已找到)"
    else
        print_warning "Whisper模型: turbo 模型文件未找到"
        print_info "请确保模型文件位于正确路径"
    fi
    
    # 检查 .env 文件
    if [[ -f ".env" ]]; then
        if grep -q "GEMINI_API_KEY" .env && [[ $(grep "GEMINI_API_KEY" .env | cut -d'=' -f2) != "" ]]; then
            print_success "配置: Gemini API 密钥已设置"
        else
            print_warning "配置: Gemini API 密钥未设置"
            print_info "AI纠错功能将不可用"
        fi
    else
        print_warning "配置: .env 文件未找到"
        print_info "复制 .env.sample 为 .env 并配置API密钥"
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

# 显示使用方法
show_usage() {
    echo ""
    echo -e "${CYAN}📖 使用方法:${NC}"
    echo -e "${GREEN}1. 双击 Option 键${NC} → 开始录音"
    echo -e "${GREEN}2. 再次双击 Option 键${NC} → 停止录音并处理"
    echo -e "${GREEN}3. Cmd+V${NC} → 在任意应用中粘贴结果"
    echo ""
    echo -e "${CYAN}🔔 通知功能:${NC}"
    echo -e "${GREEN}• 系统通知${NC} → macOS 通知中心弹窗"
    echo -e "${GREEN}• 声音反馈${NC} → 不同操作播放不同音效"
    echo -e "${GREEN}• 视觉提示${NC} → 精美的控制台显示框"
    echo ""
    echo -e "${CYAN}⚙️  配置文件:${NC}"
    echo -e "${GREEN}• config.py${NC} → 基础配置和功能开关"
    echo -e "${GREEN}• dic.txt${NC} → 用户词典文件"
    echo -e "${GREEN}• .env${NC} → API 密钥配置"
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
    
    # 检查权限
    check_permissions
    
    # 显示使用方法
    show_usage
    
    # 询问是否继续
    echo -e "${YELLOW}按 Enter 启动程序，或 Ctrl+C 取消...${NC}"
    read -r
    
    # 启动程序
    print_info "正在启动 Whisper-CLI..."
    echo ""
    
    # 选择运行方式
    if command -v uv &> /dev/null; then
        print_success "使用 uv 运行 (推荐)"
        exec uv run python main.py
    else
        print_success "使用 python3 运行"
        exec python3 main.py
    fi
}

# 错误处理
trap 'print_error "启动脚本被中断"; exit 1' INT TERM

# 运行主函数
main