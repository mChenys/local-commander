"""
会话管理器 - 管理 Local Commander 的会话状态
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class SessionManager:
    """会话管理器"""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".local-commander"

        self.data_dir = Path(data_dir)
        self.session_file = self.data_dir / "session.json"
        self.history_file = self.data_dir / "history.jsonl"

        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def start_session(self) -> Dict[str, Any]:
        """开始新会话"""
        session = {
            "active": True,
            "started_at": datetime.now().isoformat(),
            "current_model": None,
            "task_count": 0
        }
        self._save_session(session)
        return session

    def end_session(self) -> Dict[str, Any]:
        """结束会话"""
        session = self.get_session()
        if session:
            session["active"] = False
            session["ended_at"] = datetime.now().isoformat()
            self._save_session(session)
        return session

    def get_session(self) -> Optional[Dict[str, Any]]:
        """获取当前会话"""
        if not self.session_file.exists():
            return None

        with open(self.session_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def is_active(self) -> bool:
        """检查会话是否激活"""
        session = self.get_session()
        return session.get("active", False) if session else False

    def update_session(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新会话"""
        session = self.get_session() or {}
        session.update(updates)
        self._save_session(session)
        return session

    def _save_session(self, session: Dict[str, Any]):
        """保存会话"""
        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

    def add_history(self, task: str, model: str, result: str, success: bool):
        """添加历史记录"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "model": model,
            "result": result[:500] if result else "",  # 截断结果
            "success": success
        }

        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取历史记录"""
        if not self.history_file.exists():
            return []

        history = []
        with open(self.history_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines[-limit:]:
            if line.strip():
                history.append(json.loads(line))

        return history


# 单例实例
_session_instance = None

def get_session_manager() -> SessionManager:
    """获取会话管理器单例"""
    global _session_instance
    if _session_instance is None:
        _session_instance = SessionManager()
    return _session_instance