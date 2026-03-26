"""
工具函数
"""

import re
import json
from typing import Optional, Dict, Any, List


def parse_command(text: str) -> Dict[str, Any]:
    """
    解析 /local 命令

    Args:
        text: 用户输入的文本

    Returns:
        {
            "is_command": bool,
            "action": str,  # start, task, status, exit
            "model": Optional[str],
            "team": Optional[List[str]],
            "task": Optional[str]
        }
    """
    result = {
        "is_command": False,
        "action": None,
        "model": None,
        "team": None,
        "task": None
    }

    text = text.strip()

    # 检查是否是 /local 命令
    if text.startswith("/local") or text.startswith("cmd "):
        result["is_command"] = True
    else:
        return result

    # 移除命令前缀
    if text.startswith("/local "):
        content = text[7:].strip()
    elif text.startswith("cmd "):
        content = text[4:].strip()
    else:
        # 单独的 /local
        result["action"] = "start"
        return result

    # 检查退出命令
    if content.lower() in ["exit", "quit", "退出"]:
        result["action"] = "exit"
        return result

    # 检查状态命令
    if content.lower() in ["status", "状态"]:
        result["action"] = "status"
        return result

    # 解析参数
    result["action"] = "task"

    # 检查 --model 参数
    model_match = re.search(r"--model\s+(\S+)", content)
    if model_match:
        result["model"] = model_match.group(1)
        content = re.sub(r"--model\s+\S+", "", content).strip()

    # 检查 --team 参数
    team_match = re.search(r"--team\s+(\S+)", content)
    if team_match:
        result["team"] = team_match.group(1).split(",")
        content = re.sub(r"--team\s+\S+", "", content).strip()

    # 剩余部分是任务描述
    result["task"] = content.strip()

    return result


def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """
    从文本中提取代码块

    Returns:
        [{"language": "kotlin", "code": "..."}]
    """
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)

    return [
        {"language": lang or "text", "code": code.strip()}
        for lang, code in matches
    ]


def extract_json(text: str) -> Optional[Any]:
    """从文本中提取 JSON"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except:
        pass

    # 尝试从代码块中提取
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except:
            pass

    # 尝试找到 JSON 对象
    json_match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            pass

    return None


def format_response(
    success: bool,
    output: str,
    model: str,
    metadata: Optional[Dict] = None
) -> str:
    """格式化响应"""
    status = "✅" if success else "❌"
    lines = [
        f"### {status} 本地模型执行结果",
        f"",
        f"**模型:** {model}",
        f"",
        "---",
        f"",
        output
    ]

    return "\n".join(lines)


def truncate(text: str, max_length: int = 2000) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + f"\n\n... (已截断，共 {len(text)} 字符)"