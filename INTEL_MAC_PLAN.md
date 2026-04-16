# Intel Mac + llama.cpp 支持实现计划

## 目标
为 local-commander 添加 llama.cpp 后端支持，使 Intel Mac 用户也能使用本地模型。

## 架构变化

```
当前架构 (Apple Silicon only):
┌─────────────────┐     ┌─────────────┐     ┌─────────────┐
│  local-commander │────>│  MLX 后端   │────>│ MLX 模型    │
└─────────────────┘     └─────────────┘     └─────────────┘

新架构 (跨平台):
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│  local-commander │────>│  后端路由器          │────>│ MLX (Arm64)     │
└─────────────────┘     │  ┌───────────────┐   │     │ llama.cpp (x86) │
                        │  │ 检测架构选择   │   │     └─────────────────┘
                        │  └───────────────┘   │
                        └─────────────────────┘
```

## 修改清单

### 1. setup.sh (安装脚本)

**修改内容：**
- 添加 Intel Mac (x86_64) 检测
- 安装 llama.cpp 而非 MLX
- 使用 GGUF 格式模型
- 添加模型下载逻辑

```bash
# 架构检测
if [[ "$ARCH" == "arm64" ]]; then
    BACKEND="mlx"
    install_mlx_dependencies
else
    BACKEND="llamacpp"
    install_llamacpp_dependencies
fi
```

### 2. lib/executor.py (执行器)

**修改内容：**
- 添加 `_detect_backend()` 方法
- 添加 `_execute_llamacpp()` 方法
- 修改 `execute()` 方法支持双后端

```python
def _detect_backend(self) -> str:
    """检测可用的后端"""
    import platform
    if platform.machine() == "arm64" and platform.system() == "Darwin":
        return "mlx"
    return "llamacpp"

def _execute_llamacpp(self, model_path: str, prompt: str, ...) -> Tuple[bool, str, Dict]:
    """使用 llama.cpp 执行"""
    # 支持 llama-cli 和 llama-server 两种模式
```

### 3. config/models.json (模型配置)

**添加 backend 字段：**
```json
{
  "backend": "auto",  // auto, mlx, llamacpp
  "models": {
    "coder": {
      "id": "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
      "gguf_id": "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
      "gguf_file": "qwen2.5-coder-14b-instruct-q4_k_m.gguf",
      "backend": "auto",
      ...
    }
  }
}
```

### 4. 新建 lib/backends/__init__.py

**创建后端抽象层：**
```python
class Backend(ABC):
    @abstractmethod
    def execute(self, model_id: str, prompt: str, ...) -> Tuple[bool, str, Dict]: pass

class MLXBackend(Backend): ...
class LlamaCppBackend(Backend): ...

def get_backend() -> Backend:
    """根据系统自动选择后端"""
```

### 5. 新建 lib/backends/llamacpp.py

**llama.cpp 后端实现：**
- 支持本地 GGUF 模型
- 支持 llama-cli 命令行
- 支持 llama.cpp Python 绑定（可选）

## GGUF 模型推荐

| 用途 | GGUF 模型 | 大小 |
|------|-----------|------|
| 代码生成 | Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf | ~9GB |
| 图像分析 | llava-v1.6-mistral-7b.Q4_K_M.gguf | ~5GB |
| 快速对话 | Qwen2.5-7B-Instruct-Q4_K_M.gguf | ~5GB |
| 推理 | Qwen2.5-14B-Instruct-Q4_K_M.gguf | ~9GB |

## 实现步骤

1. **Phase 1: 后端抽象层**
   - 创建 lib/backends/ 目录
   - 实现 Backend 基类
   - 迁移 MLX 代码到 MLXBackend

2. **Phase 2: llama.cpp 后端**
   - 实现 LlamaCppBackend
   - 支持 GGUF 模型加载
   - 实现 prompt 格式化

3. **Phase 3: 安装脚本更新**
   - 添加 Intel Mac 检测
   - 安装 llama.cpp
   - 下载 GGUF 模型

4. **Phase 4: 测试与文档**
   - 在 Intel Mac 上测试
   - 更新 README
   - 更新帮助信息

## 注意事项

1. **视觉模型支持**: llama.cpp 对视觉模型支持有限，可能需要 minicpm-v 或 llava
2. **性能**: Intel Mac 没有 Metal 加速，纯 CPU 推理会较慢
3. **内存**: 确保用户有足够内存加载模型
