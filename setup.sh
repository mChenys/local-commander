#!/usr/bin/env bash
#
# Local Commander - 一键安装脚本
# 自动检测系统配置并安装最佳模型组合
# 支持 Apple Silicon (MLX) 和 Intel Mac (llama.cpp)
#
# 兼容 bash 3.x+ (macOS 默认 bash)
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
HAS_MLX=false
HAS_LLAMACPP=false
BACKEND=""

# GGUF 模型配置 (用于 Intel Mac)
# 小模型优先，适合低内存系统

# 获取模型大小 (兼容 bash 3.x)
get_model_size() {
    case "$1" in
        coder) echo "8" ;;
        vl)    echo "5" ;;
        35b)   echo "18" ;;
        4b)    echo "3.5" ;;
        *)     echo "0" ;;
    esac
}

# 获取 GGUF 模型大小
get_gguf_model_size() {
    case "$1" in
        mini)     echo "3.5" ;;
        fast)     echo "5.5" ;;
        coder)    echo "5" ;;
        coder_large) echo "9" ;;
        vl)       echo "5.5" ;;
        minicpm_v) echo "5" ;;
        *)        echo "0" ;;
    esac
}

# 获取模型 ID (兼容 bash 3.x) - MLX
get_model_id() {
    case "$1" in
        coder) echo "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit" ;;
        vl)    echo "mlx-community/Qwen2.5-VL-7B-Instruct-4bit" ;;
        35b)   echo "custom" ;;
        4b)    echo "custom" ;;
        *)     echo "" ;;
    esac
}

# 获取 GGUF 模型信息
# 格式: repo|gguf_file|mmproj_file (多模态模型需要 mmproj)
get_gguf_model_info() {
    case "$1" in
        mini)       echo "unsloth/gemma-4-E2B-it-GGUF|gemma-4-E2B-it-Q4_K_M.gguf|mmproj-gemma-4-E2B-it-f16.gguf" ;;
        fast)       echo "unsloth/gemma-4-E4B-it-GGUF|gemma-4-E4B-it-Q4_K_M.gguf|mmproj-gemma-4-E4B-it-f16.gguf" ;;
        coder)      echo "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF|qwen2.5-coder-7b-instruct-q4_k_m.gguf" ;;
        coder_large) echo "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF|qwen2.5-coder-14b-instruct-q4_k_m.gguf" ;;
        vl)         echo "unsloth/gemma-4-E4B-it-GGUF|gemma-4-E4B-it-Q4_K_M.gguf|mmproj-gemma-4-E4B-it-f16.gguf" ;;
        minicpm_v)  echo "mobiuslabsgmbh/MiniCPM-V-2_6-gguf|MiniCPM-V-2_6-Q4_K_M.gguf|mmproj-model-f16.gguf" ;;
        *)          echo "" ;;
    esac
}

# ─────────────────────────────────────────────────────────────
# 进度条和旋转指示器
# ─────────────────────────────────────────────────────────────

# 旋转指示器 (后台任务)
SPINNER_PID=""
SPINNER_CHARS="⠋⠙⠹ⸯ⣷⣯⣟⡿⢿⣻⣽⣾⣷"

start_spinner() {
    local msg="${1:-处理中}"
    tput sc 2>/dev/null || true
    {
        i=0
        while true; do
            char="${SPINNER_CHARS:$((i % ${#SPINNER_CHARS})):1}"
            printf "\r${CYAN}%s${NC} %s" "$char" "$msg"
            sleep 0.1
            ((i++))
        done
    } &
    SPINNER_PID=$!
}

stop_spinner() {
    if [[ -n "$SPINNER_PID" ]]; then
        kill "$SPINNER_PID" 2>/dev/null || true
        wait "$SPINNER_PID" 2>/dev/null || true
        SPINNER_PID=""
        tput rc 2>/dev/null || true
        tput el 2>/dev/null || true
    fi
}

# 进度条显示
show_progress() {
    local current=$1
    local total=$2
    local msg="${3:-下载中}"
    local width=40

    if [[ $total -eq 0 ]]; then
        return
    fi

    local percent=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))

    # 构建进度条
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done

    printf "\r${CYAN}%s${NC} [${GREEN}%s${NC}] %3d%% (%d/%d)" "$msg" "$bar" "$percent" "$current" "$total"
}

# 下载进度监控 (用于 huggingface-cli)
monitor_download() {
    local repo="$1"
    local file="$2"
    local cache_dir="$HF_CACHE/models--${repo//\//--}"
    local expected_size="${3:-0}"  # GB

    # 检查下载目录
    if [[ ! -d "$cache_dir" ]]; then
        return 1
    fi

    local start_time=$(date +%s)
    local last_size=0
    local count=0

    while true; do
        # 计算当前已下载大小
        local current_size=0
        if [[ -d "$cache_dir/blobs" ]]; then
            for blob in "$cache_dir/blobs"/*; do
                if [[ -f "$blob" ]]; then
                    current_size=$((current_size + $(stat -f%z "$blob" 2>/dev/null || stat -c%s "$blob" 2>/dev/null || echo 0)))
                fi
            done
        fi

        # 转换为 MB
        local current_mb=$((current_size / 1024 / 1024))
        local expected_mb=$(echo "$expected_size * 1024" | bc 2>/dev/null || echo "0")
        expected_mb=${expected_mb%.*}  # 取整数

        # 显示进度
        if [[ $expected_mb -gt 0 ]]; then
            local percent=$((current_mb * 100 / expected_mb))
            printf "\r  ${CYAN}下载中${NC} ${GREEN}%d MB${NC} / ~%d MB (%d%%)" "$current_mb" "$expected_mb" "$percent"
        else
            printf "\r  ${CYAN}下载中${NC} ${GREEN}%d MB${NC}" "$current_mb"
        fi

        # 检查是否完成 (文件大小不再变化)
        if [[ $current_size -eq $last_size ]]; then
            count=$((count + 1))
            if [[ $count -gt 10 ]]; then
                break
            fi
        else
            count=0
        fi

        last_size=$current_size
        sleep 1
    done

    echo ""
}

# 打印函数
print_header() {
    echo -e "${PURPLE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║         Local Commander - 本地模型指挥官                   ║"
    echo "║            一键安装脚本 v2.0                                ║"
    echo "║         支持 Apple Silicon + Intel Mac                     ║"
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

    # GPU 检测 & 后端选择
    if [[ "$OS" == "Darwin" && "$ARCH" == "arm64" ]]; then
        GPU="Apple Silicon (Metal)"
        HAS_METAL=true
        BACKEND="mlx"
        print_info "GPU: $GPU"
        print_success "将使用 MLX 后端"
    elif [[ "$OS" == "Darwin" && "$ARCH" == "x86_64" ]]; then
        GPU="Intel Mac (CPU)"
        HAS_METAL=false
        BACKEND="llamacpp"
        print_info "GPU: $GPU"
        print_warning "将使用 llama.cpp 后端 (CPU 推理)"
    elif command -v nvidia-smi &> /dev/null; then
        GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
        HAS_NVIDIA=true
        BACKEND="llamacpp"
        print_info "GPU: $GPU"
        print_success "将使用 llama.cpp 后端 (CUDA 加速)"
    else
        GPU="无专用 GPU"
        BACKEND="llamacpp"
        print_info "GPU: $GPU"
        print_warning "将使用 llama.cpp 后端 (CPU 推理)"
    fi

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
    print_info "后端: $BACKEND"
}

# 推荐模型配置
recommend_config() {
    print_section "推荐模型配置"

    if [[ "$BACKEND" == "mlx" ]]; then
        # MLX 配置 (Apple Silicon)
        if [[ $TOTAL_MEM_GB -lt 16 ]]; then
            CONFIG="minimal"
            RECOMMENDED_MODELS="4b coder"
            print_warning "内存较少 (${TOTAL_MEM_GB}GB)，推荐 minimal 配置"
        elif [[ $TOTAL_MEM_GB -lt 24 ]]; then
            CONFIG="balanced"
            RECOMMENDED_MODELS="4b coder vl"
            print_info "内存适中 (${TOTAL_MEM_GB}GB)，推荐 balanced 配置"
        elif [[ $TOTAL_MEM_GB -lt 32 ]]; then
            CONFIG="standard"
            RECOMMENDED_MODELS="4b coder vl 35b"
            print_info "内存充足 (${TOTAL_MEM_GB}GB)，推荐 standard 配置"
        else
            CONFIG="full"
            RECOMMENDED_MODELS="4b coder vl 35b"
            print_success "内存充裕 (${TOTAL_MEM_GB}GB)，推荐 full 配置"
        fi

        # 计算预计占用
        TOTAL_SIZE=0
        for model in $RECOMMENDED_MODELS; do
            size=$(get_model_size "$model")
            TOTAL_SIZE=$(echo "$TOTAL_SIZE + $size" | bc)
        done

    else
        # llama.cpp 配置 (Intel Mac / Linux)
        # 使用 Gemma 4 多模态系列 - 文本+视觉一体
        if [[ $TOTAL_MEM_GB -lt 12 ]]; then
            CONFIG="mini"
            RECOMMENDED_MODELS="mini"
            print_warning "内存较少 (${TOTAL_MEM_GB}GB)，推荐 mini 配置"
        elif [[ $TOTAL_MEM_GB -lt 20 ]]; then
            CONFIG="balanced"
            RECOMMENDED_MODELS="mini fast coder"
            print_info "内存适中 (${TOTAL_MEM_GB}GB)，推荐 balanced 配置"
        elif [[ $TOTAL_MEM_GB -lt 32 ]]; then
            CONFIG="standard"
            RECOMMENDED_MODELS="fast coder"
            print_info "内存充足 (${TOTAL_MEM_GB}GB)，推荐 standard 配置"
        else
            CONFIG="full"
            RECOMMENDED_MODELS="mini fast coder coder_large"
            print_success "内存充裕 (${TOTAL_MEM_GB}GB)，推荐 full 配置"
        fi

        # 计算预计占用 (GGUF 模型)
        TOTAL_SIZE=0
        for model in $RECOMMENDED_MODELS; do
            size=$(get_gguf_model_size "$model")
            TOTAL_SIZE=$(echo "$TOTAL_SIZE + $size" | bc)
        done
    fi

    echo ""
    echo -e "${CYAN}配置详情:${NC}"
    echo "┌─────────────────────────────────────────────┐"
    echo "│ 后端:     $BACKEND                              "
    echo "│ 配置级别: $CONFIG                              "
    echo "│ 推荐模型: $RECOMMENDED_MODELS                 "
    printf "│ 预计占用: %.1fGB                            \n" "$TOTAL_SIZE"
    echo "└─────────────────────────────────────────────┘"
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

    echo ""
    echo -e "${PURPLE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}  安装依赖包${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════════════════════${NC}"

    if [[ "$BACKEND" == "mlx" ]]; then
        # Apple Silicon - 安装 MLX
        echo ""
        echo -e "${CYAN}[1/2]${NC} 安装 MLX 相关包..."
        echo -e "${CYAN}├──${NC} mlx, mlx-lm, mlx-vlm"

        start_spinner "安装中"
        python3 -m pip install --user --break-system-packages \
            mlx mlx-lm mlx-vlm \
            sentence-transformers \
            chromadb \
            numpy \
            pillow \
            openai >/dev/null 2>&1 || true
        stop_spinner
        print_success "MLX 核心包安装完成"

        HAS_MLX=true

    else
        # Intel Mac / Linux - 安装 llama.cpp
        echo ""
        echo -e "${CYAN}[1/2]${NC} 安装 llama.cpp..."

        # macOS 使用 Homebrew
        if [[ "$OS" == "Darwin" ]]; then
            if command -v brew &> /dev/null; then
                start_spinner "brew install llama.cpp"
                brew install llama.cpp >/dev/null 2>&1 || true
                stop_spinner

                if command -v llama-cli &> /dev/null; then
                    print_success "llama.cpp 安装完成"
                    HAS_LLAMACPP=true
                else
                    print_warning "llama.cpp 安装可能需要更多时间"
                fi
            else
                print_warning "未安装 Homebrew"
                print_info "  请运行: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                print_info "  然后运行: brew install llama.cpp"
            fi
        fi

        # Linux
        if [[ "$OS" == "Linux" ]]; then
            print_info "请手动安装 llama.cpp:"
            print_info "  git clone https://github.com/ggml-org/llama.cpp"
            print_info "  cd llama.cpp && make"
        fi

        # 安装基础 Python 依赖
        echo ""
        echo -e "${CYAN}[2/2]${NC} 安装 Python 依赖..."
        echo -e "${CYAN}├──${NC} huggingface_hub, sentence-transformers, chromadb..."

        start_spinner "安装中"
        python3 -m pip install --user --break-system-packages \
            huggingface_hub \
            sentence-transformers \
            chromadb \
            numpy \
            pillow \
            openai >/dev/null 2>&1 || true
        stop_spinner
        print_success "Python 依赖安装完成"
    fi

    echo ""
}

# 下载模型
download_models() {
    print_section "下载模型"

    if [[ "$BACKEND" == "mlx" ]]; then
        download_mlx_models
    else
        download_gguf_models
    fi
}

# 下载 MLX 模型
download_mlx_models() {
    local total_models=$(echo "$RECOMMENDED_MODELS" | wc -w | tr -d ' ')
    local current=0

    for model in $RECOMMENDED_MODELS; do
        current=$((current + 1))
        local model_id=$(get_model_id "$model")
        local size=$(get_model_size "$model")

        echo ""
        show_progress $current $total_models "准备下载"
        echo -e " ${CYAN}$model${NC} ($size GB)"

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

        # 使用 Python 下载 (带进度)
        print_info "正在下载 $model_id..."
        echo ""

        # 使用 huggingface-cli 显示进度
        if command -v huggingface-cli &> /dev/null; then
            start_spinner "下载中..."
            huggingface-cli download "$model_id" 2>&1
            stop_spinner
            print_success "$model 下载完成"
        else
            # 备用方式
            python3 -c "from huggingface_hub import snapshot_download; snapshot_download('$model_id')" 2>&1 | while read -r line; do
                echo -ne "\r  $line"
            done
            echo ""
            print_success "$model 下载完成"
        fi
    done
}

# 下载 GGUF 模型 (Intel Mac) - 带进度条
download_gguf_models() {
    local total_models=$(echo "$RECOMMENDED_MODELS" | wc -w | tr -d ' ')
    local current=0

    echo ""
    echo -e "${PURPLE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}  开始下载 ${GREEN}$total_models${PURPLE} 个模型${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════════════════════${NC}"

    for model in $RECOMMENDED_MODELS; do
        current=$((current + 1))
        local model_info=$(get_gguf_model_info "$model")
        local size=$(get_gguf_model_size "$model")

        if [[ -z "$model_info" ]]; then
            print_warning "未知模型: $model"
            continue
        fi

        # 解析模型信息
        local repo=$(echo "$model_info" | cut -d'|' -f1)
        local file=$(echo "$model_info" | cut -d'|' -f2)
        local mmproj=$(echo "$model_info" | cut -d'|' -f3)

        # 检查是否已下载
        local cache_dir="$HF_CACHE/models--${repo//\//--}"
        local skip_download=false

        if [[ -d "$cache_dir" ]]; then
            for snapshot_dir in "$cache_dir"/snapshots/*; do
                if [[ -f "$snapshot_dir/$file" ]]; then
                    skip_download=true
                    break
                fi
            done
        fi

        echo ""
        echo -e "${CYAN}┌─────────────────────────────────────────────────────────────┐${NC}"
        printf "${CYAN}│${NC} ${GREEN}[%d/%d]${NC} %-30s %8s      ${CYAN}│${NC}\n" "$current" "$total_models" "$model" "${size}GB"
        echo -e "${CYAN}├─────────────────────────────────────────────────────────────┤${NC}"

        if $skip_download; then
            echo -e "${CYAN}│${NC}  ✓ 模型已存在，跳过下载                              ${CYAN}│${NC}"
            echo -e "${CYAN}└─────────────────────────────────────────────────────────────┘${NC}"
            continue
        fi

        # 显示下载信息
        echo -e "${CYAN}│${NC}  仓库: $repo"
        echo -e "${CYAN}│${NC}  文件: $file"
        echo -e "${CYAN}├─────────────────────────────────────────────────────────────┤${NC}"

        # 使用 huggingface-cli 下载
        if command -v huggingface-cli &> /dev/null; then
            # 下载主模型文件
            echo -e "${CYAN}│${NC}  ${YELLOW}下载中...${NC}"
            huggingface-cli download "$repo" "$file" --local-dir "$cache_dir" 2>&1 | while read -r line; do
                # 过滤并显示进度
                if [[ "$line" == *"%"* ]] || [[ "$line" == *"Downloading"* ]] || [[ "$line" == *"download"* ]]; then
                    # 截断过长的行
                    local short_line="${line:0:50}"
                    printf "\r${CYAN}│${NC}  %-55s${CYAN}│${NC}" "$short_line"
                fi
            done
            echo ""

            # 下载 mmproj (视觉模型)
            if [[ -n "$mmproj" ]]; then
                echo -e "${CYAN}│${NC}  ${YELLOW}下载视觉模块 (mmproj)...${NC}"
                huggingface-cli download "$repo" "$mmproj" --local-dir "$cache_dir" 2>&1 | while read -r line; do
                    if [[ "$line" == *"%"* ]] || [[ "$line" == *"Downloading"* ]]; then
                        local short_line="${line:0:50}"
                        printf "\r${CYAN}│${NC}  %-55s${CYAN}│${NC}" "$short_line"
                    fi
                done
                echo ""
            fi

            echo -e "${CYAN}│${NC}  ${GREEN}✓ 下载完成${NC}                                            ${CYAN}│${NC}"
        else
            echo -e "${CYAN}│${NC}  ${RED}✗ 未安装 huggingface-cli${NC}"
            echo -e "${CYAN}│${NC}    pip install huggingface_hub"
            echo -e "${CYAN}│${NC}    huggingface-cli download $repo $file"
        fi

        echo -e "${CYAN}└─────────────────────────────────────────────────────────────┘${NC}"
    done

    echo ""
    echo -e "${GREEN}✓ 所有模型下载完成${NC}"
}

# 安装 Skill 文件
install_skill() {
    print_section "安装 Skill 文件"

    # 创建目录
    mkdir -p "$SKILL_DIR"

    # 检查是否在管道模式
    if ! is_interactive; then
        # 管道模式：从 GitHub 下载
        print_info "从 GitHub 下载文件..."

        # 下载 zip 文件
        local tmp_dir=$(mktemp -d)
        local zip_url="https://github.com/mChenys/local-commander/archive/refs/heads/main.zip"

        if command -v curl &> /dev/null; then
            curl -fsSL "$zip_url" -o "$tmp_dir/local-commander.zip"
        elif command -v wget &> /dev/null; then
            wget -q "$zip_url" -O "$tmp_dir/local-commander.zip"
        else
            print_error "需要 curl 或 wget 来下载文件"
            exit 1
        fi

        # 解压
        if command -v unzip &> /dev/null; then
            unzip -q "$tmp_dir/local-commander.zip" -d "$tmp_dir"
        else
            print_error "需要 unzip 来解压文件"
            exit 1
        fi

        # 复制文件
        cp -r "$tmp_dir/local-commander-main/"* "$SKILL_DIR/"
        rm -rf "$tmp_dir"

    else
        # 交互模式：从本地复制
        if [[ "$SCRIPT_DIR" != "$SKILL_DIR" ]]; then
            print_info "复制文件到 $SKILL_DIR..."
            cp -r "$SCRIPT_DIR/"* "$SKILL_DIR/"
        fi
    fi

    # 添加执行权限
    chmod +x "$SKILL_DIR/local-commander.py" 2>/dev/null || true
    chmod +x "$SKILL_DIR/setup.sh" 2>/dev/null || true

    # 创建后端配置
    create_backend_config

    print_success "Skill 文件安装完成"
}

# 创建后端配置
create_backend_config() {
    local config_dir="$SKILL_DIR/config"
    mkdir -p "$config_dir"

    local config_file="$config_dir/models.json"

    if [[ "$BACKEND" == "mlx" ]]; then
        # MLX 配置
        cat > "$config_file" << 'EOF'
{
  "backend": "mlx",
  "models": {
    "coder": {
      "id": "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
      "alias": "coder",
      "memory_gb": 8,
      "use_cases": ["代码生成", "代码审查", "Bug诊断", "重构"],
      "keywords": ["代码", "编程", "Kotlin", "Swift", "函数", "类", "实现", "写", "生成"]
    },
    "vl": {
      "id": "mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
      "alias": "vl",
      "memory_gb": 5,
      "use_cases": ["图像分析", "UI验证", "OCR", "截图分析"],
      "keywords": ["图片", "截图", "图像", "UI", "界面", "分析图", "看"]
    }
  },
  "default_model": "coder"
}
EOF
    else
        # llama.cpp 配置 - 使用 Gemma 4 多模态系列
        cat > "$config_file" << 'EOF'
{
  "backend": "llamacpp",
  "models": {
    "mini": {
      "hf_repo": "unsloth/gemma-4-E2B-it-GGUF",
      "gguf_file": "gemma-4-E2B-it-Q4_K_M.gguf",
      "mmproj_file": "mmproj-gemma-4-E2B-it-f16.gguf",
      "alias": "mini",
      "memory_gb": 3.5,
      "use_cases": ["快速对话", "简单问答", "图像分析"],
      "keywords": ["你好", "hello", "hi", "快速", "简单"],
      "description": "Gemma 4 E2B - 多模态 (文本+视觉)",
      "is_multimodal": true
    },
    "fast": {
      "hf_repo": "unsloth/gemma-4-E4B-it-GGUF",
      "gguf_file": "gemma-4-E4B-it-Q4_K_M.gguf",
      "mmproj_file": "mmproj-gemma-4-E4B-it-f16.gguf",
      "alias": "fast",
      "memory_gb": 5.5,
      "use_cases": ["对话", "问答", "图像分析", "OCR"],
      "keywords": ["快速", "对话", "分析"],
      "description": "Gemma 4 E4B MoE - 多模态 (文本+视觉)",
      "is_multimodal": true
    },
    "coder": {
      "hf_repo": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
      "gguf_file": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
      "alias": "coder",
      "memory_gb": 5,
      "use_cases": ["代码生成", "代码审查", "Bug诊断"],
      "keywords": ["代码", "编程", "Kotlin", "Swift", "函数", "类", "实现"],
      "description": "Qwen2.5-Coder 7B - 代码专家"
    },
    "coder_large": {
      "hf_repo": "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
      "gguf_file": "qwen2.5-coder-14b-instruct-q4_k_m.gguf",
      "alias": "coder_large",
      "memory_gb": 9,
      "use_cases": ["代码生成", "代码审查"],
      "keywords": ["代码", "复杂"],
      "description": "Qwen2.5-Coder 14B (24GB+)"
    },
    "vl": {
      "hf_repo": "unsloth/gemma-4-E4B-it-GGUF",
      "gguf_file": "gemma-4-E4B-it-Q4_K_M.gguf",
      "mmproj_file": "mmproj-gemma-4-E4B-it-f16.gguf",
      "alias": "vl",
      "memory_gb": 5.5,
      "use_cases": ["图像分析", "UI验证", "OCR"],
      "keywords": ["图片", "截图", "图像", "UI"],
      "description": "Gemma 4 E4B - 视觉",
      "is_multimodal": true
    }
  },
  "default_model": "fast",
  "model_groups": {
    "multimodal": ["mini", "fast", "vl"],
    "code_models": ["coder", "coder_large"]
  }
}
EOF
    fi

    print_info "创建后端配置: $BACKEND"
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
        "LOCAL_COMMANDER_PATH": "$SKILL_DIR",
        "LOCAL_COMMANDER_BACKEND": "$BACKEND"
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

    print_info "检查后端状态..."

    if [[ "$BACKEND" == "mlx" ]]; then
        if python3 -c "import mlx" 2>/dev/null; then
            print_success "MLX 后端可用"
        else
            print_warning "MLX 后端不可用"
        fi
    else
        if command -v llama-cli &> /dev/null; then
            print_success "llama.cpp 后端可用"
            llama-cli --version 2>&1 | head -1 | while read -r line; do
                print_info "  版本: $line"
            done || true
        elif [[ -f "$HOME/llama.cpp/main" ]]; then
            print_success "llama.cpp 后端可用 (本地编译)"
        else
            print_warning "llama.cpp 未安装"
            print_info "请安装: brew install llama.cpp"
        fi
    fi

    print_info "检查模型配置..."
    if python3 "$SKILL_DIR/local-commander.py" --validate 2>/dev/null; then
        print_success "模型配置有效"
    else
        print_warning "模型配置验证失败，请检查 config/models.json"
    fi
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
    echo -e "${CYAN}系统配置:${NC}"
    echo "  后端: ${GREEN}$BACKEND${NC}"
    echo "  架构: $ARCH"
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

    if [[ "$BACKEND" == "llamacpp" ]]; then
        echo ""
        echo -e "${YELLOW}Intel Mac 注意事项:${NC}"
        echo "  • CPU 推理速度较慢，建议使用小模型 (7B)"
        echo "  • 确保有足够内存 (推荐 16GB+)"
        echo "  • 视觉模型使用 MiniCPM-V 或 LLaVA"
    fi

    echo ""
    echo -e "${YELLOW}自定义模型配置:${NC}"
    echo "   编辑 ${BLUE}~/.claude/skills/local-commander/config/models.json${NC}"
}

# 检测是否在交互模式
is_interactive() {
    [ -t 0 ] && [ -t 1 ]
}

# 交互式选择
interactive_select() {
    # 检测是否在管道模式（curl | bash）
    if ! is_interactive; then
        print_warning "检测到非交互模式，使用自动推荐配置"
        print_info "如需自定义配置，请下载脚本后运行:"
        print_info "  curl -fsSL https://raw.githubusercontent.com/mChenys/local-commander/main/setup.sh -o setup.sh"
        print_info "  bash setup.sh"
        echo ""
        return
    fi

    echo ""
    echo -e "${CYAN}请选择安装配置:${NC}"

    if [[ "$BACKEND" == "mlx" ]]; then
        echo "  1) minimal   - 4b + coder (~12GB)    [内存 < 16GB]"
        echo "  2) balanced  - 4b + coder + vl (~16GB) [内存 16-24GB]"
        echo "  3) standard  - 全部模型 (~34GB)       [内存 24-32GB]"
        echo "  4) full      - 全部模型 (~42GB)       [内存 > 32GB]"
    else
        echo "  1) mini      - E2B 多模态 (~4GB)      [内存 < 12GB]"
        echo "  2) balanced  - E2B + E4B + coder (~14GB) [内存 12-20GB]"
        echo "  3) standard  - E4B + coder (~11GB)   [内存 20-32GB]"
        echo "  4) full      - 全部模型 (~23GB)       [内存 > 32GB]"
    fi

    echo "  5) custom    - 自定义选择"
    echo "  6) 退出"
    echo ""
    read -p "请输入选项 [1-6]: " choice

    case $choice in
        1)
            if [[ "$BACKEND" == "mlx" ]]; then
                CONFIG="minimal"
                RECOMMENDED_MODELS="4b coder"
            else
                CONFIG="mini"
                RECOMMENDED_MODELS="mini"
            fi
            ;;
        2)
            if [[ "$BACKEND" == "mlx" ]]; then
                CONFIG="balanced"
                RECOMMENDED_MODELS="4b coder vl"
            else
                CONFIG="balanced"
                RECOMMENDED_MODELS="mini fast coder"
            fi
            ;;
        3)
            if [[ "$BACKEND" == "mlx" ]]; then
                CONFIG="standard"
                RECOMMENDED_MODELS="4b coder vl 35b"
            else
                CONFIG="standard"
                RECOMMENDED_MODELS="fast coder"
            fi
            ;;
        4)
            if [[ "$BACKEND" == "mlx" ]]; then
                CONFIG="full"
                RECOMMENDED_MODELS="4b coder vl 35b"
            else
                CONFIG="full"
                RECOMMENDED_MODELS="mini fast coder coder_large"
            fi
            ;;
        5)
            echo ""
            if [[ "$BACKEND" == "mlx" ]]; then
                echo "可用模型:"
                echo "  - coder (8GB): 代码生成"
                echo "  - vl (5GB): 图像分析"
                echo "  - 35b (18GB): 复杂推理"
                echo "  - 4b (3.5GB): 快速问答"
            else
                echo "可用模型 (Gemma 4 多模态系列):"
                echo "  - mini (3.5GB): E2B - 文本+视觉 (快速)"
                echo "  - fast (5.5GB): E4B - 文本+视觉 (推荐)"
                echo "  - coder (5GB): Qwen-Coder 7B - 代码专用"
                echo "  - coder_large (9GB): Qwen-Coder 14B"
                echo ""
                echo "💡 提示: mini/fast 都支持文本和图像，无需单独安装视觉模型"
            fi
            echo ""
            read -p "请输入要安装的模型 (空格分隔): " custom_models
            RECOMMENDED_MODELS="$custom_models"
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

    # 确认安装（非交互模式自动确认）
    if is_interactive; then
        echo ""
        read -p "开始安装? [Y/n]: " confirm
        if [[ "$confirm" == "n" || "$confirm" == "N" ]]; then
            echo "取消安装"
            exit 0
        fi
    else
        echo ""
        print_info "开始安装..."
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
