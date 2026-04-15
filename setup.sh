#!/bin/bash
#
# Local Commander - 一键安装脚本
# 自动检测系统配置并安装最佳模型组合
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$HOME/.claude/skills/local-commander"
HF_CACHE="$HOME/.cache/huggingface/hub"

# 模型配置
declare -A MODEL_SIZES=(
    ["coder"]=8
    ["vl"]=5
    ["35b"]=18
    ["4b"]=3.5
)

declare -A MODEL_IDS=(
    ["coder"]="mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"
    ["vl"]="mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
    ["35b"]="custom"
    ["4b"]="custom"
)

# 打印函数
print_header() {
    echo -e "${PURPLE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║         Local Commander - 本地模型指挥官                   ║"
    echo "║            一键安装脚本 v1.0                                ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_section() {
    echo -e "\n${CYAN}▶ $1${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}  $1${NC}"
}

# 检测系统信息
detect_system() {
    print_section "检测系统配置"

    # 操作系统
    OS="$(uname -s)"
    print_info "操作系统: $OS"

    # CPU 架构
    ARCH="$(uname -m)"
    print_info "CPU 架构: $ARCH"

    # 内存
    if [[ "$OS" == "Darwin" ]]; then
        TOTAL_MEM=$(sysctl -n hw.memsize)
        TOTAL_MEM_GB=$((TOTAL_MEM / 1024 / 1024 / 1024))
    else
        TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))
    fi
    print_info "总内存: ${TOTAL_MEM_GB}GB"

    # GPU 检测
    if [[ "$OS" == "Darwin" && "$ARCH" == "arm64" ]]; then
        GPU="Apple Silicon (Metal)"
        HAS_METAL=true
    elif command -v nvidia-smi &> /dev/null; then
        GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
        HAS_NVIDIA=true
    else
        GPU="无专用 GPU"
    fi
    print_info "GPU: $GPU"

    # Python 检测
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_info "Python: $PYTHON_VERSION"
        HAS_PYTHON=true
    else
        print_warning "未检测到 Python 3"
        HAS_PYTHON=false
    fi

    echo ""
}

# 推荐模型配置
recommend_config() {
    print_section "推荐模型配置"

    if [[ $TOTAL_MEM_GB -lt 16 ]]; then
        CONFIG="minimal"
        RECOMMENDED_MODELS=("4b" "coder")
        print_warning "内存较少 (${TOTAL_MEM_GB}GB)，推荐 minimal 配置"
    elif [[ $TOTAL_MEM_GB -lt 24 ]]; then
        CONFIG="balanced"
        RECOMMENDED_MODELS=("4b" "coder" "vl")
        print_info "内存适中 (${TOTAL_MEM_GB}GB)，推荐 balanced 配置"
    elif [[ $TOTAL_MEM_GB -lt 32 ]]; then
        CONFIG="standard"
        RECOMMENDED_MODELS=("4b" "coder" "vl" "35b")
        print_info "内存充足 (${TOTAL_MEM_GB}GB)，推荐 standard 配置"
    else
        CONFIG="full"
        RECOMMENDED_MODELS=("4b" "coder" "vl" "35b")
        print_success "内存充裕 (${TOTAL_MEM_GB}GB)，推荐 full 配置"
    fi

    # 计算预计占用
    TOTAL_SIZE=0
    for model in "${RECOMMENDED_MODELS[@]}"; do
        size=${MODEL_SIZES[$model]}
        TOTAL_SIZE=$(echo "$TOTAL_SIZE + $size" | bc)
    done

    echo ""
    echo -e "${CYAN}配置详情:${NC}"
    echo "┌─────────────────────────────────────────────┐"
    echo "│ 配置级别: $CONFIG                              "
    echo "│ 推荐模型: ${RECOMMENDED_MODELS[*]}            "
    printf "│ 预计占用: %.1fGB                            \n" "$TOTAL_SIZE"
    echo "└─────────────────────────────────────────────┘"

    # 检查是否为 Apple Silicon
    if [[ "$OS" != "Darwin" || "$ARCH" != "arm64" ]]; then
        print_warning "非 Apple Silicon Mac，部分功能可能受限"
        print_info "建议使用 NVIDIA GPU 或云服务运行大模型"
    fi
}

# 安装 Python 依赖
install_dependencies() {
    print_section "安装 Python 依赖"

    if [[ "$HAS_PYTHON" != "true" ]]; then
        print_error "请先安装 Python 3.10+"
        exit 1
    fi

    # 检查 pip
    if ! python3 -m pip --version &> /dev/null; then
        print_error "pip 未安装"
        exit 1
    fi

    print_info "安装 MLX 相关包..."

    # 根据系统选择依赖
    if [[ "$OS" == "Darwin" && "$ARCH" == "arm64" ]]; then
        # Apple Silicon Mac
        python3 -m pip install --user --break-system-packages \
            mlx mlx-lm mlx-vlm \
            sentence-transformers \
            chromadb \
            numpy \
            pillow \
            openai 2>&1 | while read -r line; do
                print_info "  $line"
            done
    else
        # Linux / Intel Mac
        print_warning "非 Apple Silicon，跳过 MLX 安装"
        print_info "安装替代依赖..."
        python3 -m pip install --user --break-system-packages \
            sentence-transformers \
            chromadb \
            numpy \
            pillow \
            openai 2>&1 | while read -r line; do
                print_info "  $line"
            done
    fi

    print_success "Python 依赖安装完成"
}

# 下载模型
download_models() {
    print_section "下载模型"

    local total_models=${#RECOMMENDED_MODELS[@]}
    local current=0

    for model in "${RECOMMENDED_MODELS[@]}"; do
        current=$((current + 1))
        local model_id="${MODEL_IDS[$model]}"
        local size="${MODEL_SIZES[$model]}"

        echo ""
        echo -e "${CYAN}[$current/$total_models] 下载 $model ($size GB)${NC}"

        if [[ "$model_id" == "custom" ]]; then
            print_warning "自定义模型 $model 需要手动配置"
            print_info "请编辑 config/models.json 设置模型路径"
            continue
        fi

        # 检查是否已下载
        local cache_dir="$HF_CACHE/models--${model_id//\//--}"
        if [[ -d "$cache_dir" ]]; then
            print_info "模型已存在，跳过下载"
            continue
        fi

        # 使用 Python 下载
        print_info "正在下载 $model_id..."
        if python3 -c "from mlx_vlm import load; load('$model_id')" 2>&1 | while read -r line; do
            # 只显示关键信息
            if [[ "$line" == *"Downloading"* ]] || [[ "$line" == *"Loading"* ]]; then
                print_info "  $line"
            fi
        done; then
            print_success "$model 下载完成"
        else
            print_warning "$model 下载可能需要更长时间，请稍后重试"
        fi
    done
}

# 安装 Skill 文件
install_skill() {
    print_section "安装 Skill 文件"

    # 创建目录
    mkdir -p "$HOME/.claude/skills"

    # 复制文件
    if [[ "$SCRIPT_DIR" != "$SKILL_DIR" ]]; then
        print_info "复制文件到 $SKILL_DIR..."
        cp -r "$SCRIPT_DIR" "$SKILL_DIR"
    fi

    # 添加执行权限
    chmod +x "$SKILL_DIR/local-commander.py"

    print_success "Skill 文件安装完成"
}

# 配置 MCP
configure_mcp() {
    print_section "配置 MCP 服务"

    local mcp_file="$HOME/.claude/.mcp.json"
    local mcp_config=$(cat <<EOF
{
  "mcpServers": {
    "local-commander-router": {
      "command": "python3",
      "args": ["$SKILL_DIR/lib/mcp_router.py"],
      "env": {
        "LOCAL_COMMANDER_PATH": "$SKILL_DIR"
      }
    }
  }
}
EOF
)

    if [[ -f "$mcp_file" ]]; then
        # 检查是否已配置
        if grep -q "local-commander-router" "$mcp_file"; then
            print_info "MCP 配置已存在"
        else
            print_warning "MCP 配置文件已存在，请手动添加以下配置:"
            echo "$mcp_config"
        fi
    else
        echo "$mcp_config" > "$mcp_file"
        print_success "MCP 配置完成"
    fi
}

# 验证安装
verify_installation() {
    print_section "验证安装"

    print_info "检查模型配置..."
    if python3 "$SKILL_DIR/local-commander.py" --validate 2>/dev/null; then
        print_success "模型配置有效"
    else
        print_warning "模型配置验证失败，请检查 config/models.json"
    fi

    print_info "列出可用模型..."
    python3 "$SKILL_DIR/local-commander.py" --models 2>/dev/null || true

    print_info "检查知识库..."
    python3 "$SKILL_DIR/local-commander.py" --kb-stats 2>/dev/null || true
}

# 打印完成信息
print_completion() {
    echo ""
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                 安装完成!                                  ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${CYAN}下一步:${NC}"
    echo ""
    echo "1. 重启 Claude Code 使 MCP 配置生效"
    echo ""
    echo "2. 测试安装:"
    echo "   ${BLUE}python3 ~/.claude/skills/local-commander/local-commander.py --validate${NC}"
    echo ""
    echo "3. 使用方式:"
    echo "   ${BLUE}/local 写一个 Python 函数${NC}"
    echo "   ${BLUE}/local --image ~/test.png 分析这个图片${NC}"
    echo ""
    echo -e "${YELLOW}自定义模型配置:${NC}"
    echo "   编辑 ${BLUE}~/.claude/skills/local-commander/config/models.json${NC}"
    echo "   设置 35b 和 4b 的本地模型路径"
    echo ""
}

# 交互式选择
interactive_select() {
    echo ""
    echo -e "${CYAN}请选择安装配置:${NC}"
    echo "  1) minimal   - 4b + coder (~12GB)    [内存 < 16GB]"
    echo "  2) balanced  - 4b + coder + vl (~16GB) [内存 16-24GB]"
    echo "  3) standard  - 全部模型 (~34GB)       [内存 24-32GB]"
    echo "  4) full      - 全部模型 (~42GB)       [内存 > 32GB]"
    echo "  5) custom    - 自定义选择"
    echo "  6) 退出"
    echo ""
    read -p "请输入选项 [1-6]: " choice

    case $choice in
        1)
            CONFIG="minimal"
            RECOMMENDED_MODELS=("4b" "coder")
            ;;
        2)
            CONFIG="balanced"
            RECOMMENDED_MODELS=("4b" "coder" "vl")
            ;;
        3)
            CONFIG="standard"
            RECOMMENDED_MODELS=("4b" "coder" "vl" "35b")
            ;;
        4)
            CONFIG="full"
            RECOMMENDED_MODELS=("4b" "coder" "vl" "35b")
            ;;
        5)
            echo ""
            echo "可用模型:"
            echo "  - coder (8GB): 代码生成"
            echo "  - vl (5GB): 图像分析"
            echo "  - 35b (18GB): 复杂推理"
            echo "  - 4b (3.5GB): 快速问答"
            echo ""
            read -p "请输入要安装的模型 (空格分隔，如: coder vl 4b): " custom_models
            RECOMMENDED_MODELS=($custom_models)
            CONFIG="custom"
            ;;
        6)
            echo "退出安装"
            exit 0
            ;;
        *)
            print_warning "无效选项，使用自动推荐配置"
            ;;
    esac
}

# 主函数
main() {
    print_header

    # 检测系统
    detect_system

    # 推荐配置
    recommend_config

    # 交互式选择
    if [[ "$1" != "--auto" ]]; then
        interactive_select
    fi

    # 确认安装
    echo ""
    read -p "开始安装? [Y/n]: " confirm
    if [[ "$confirm" == "n" || "$confirm" == "N" ]]; then
        echo "取消安装"
        exit 0
    fi

    # 安装依赖
    install_dependencies

    # 下载模型
    download_models

    # 安装 Skill
    install_skill

    # 配置 MCP
    configure_mcp

    # 验证
    verify_installation

    # 完成
    print_completion
}

# 运行
main "$@"
