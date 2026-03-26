"""
文件操作模块 - 智能文件读取、写入和定位
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple


class FileOperations:
    """文件操作类 - 支持智能定位和精确修改"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._analyzer = None

    def set_project_root(self, path: Path):
        """设置项目根目录"""
        self.project_root = Path(path)
        if self._analyzer:
            self._analyzer.set_project(path)

    def _get_analyzer(self):
        """懒加载分析器"""
        if self._analyzer is None:
            from .analyzer import get_analyzer
            self._analyzer = get_analyzer()
            self._analyzer.set_project(self.project_root)
        return self._analyzer

    def scan_project(self) -> Dict[str, Any]:
        """扫描项目并建立索引"""
        analyzer = self._get_analyzer()
        return analyzer.scan_project()

    # ==================== 文件读写操作 ====================

    def read_file(self, file_path: str) -> Tuple[bool, str]:
        """读取文件内容"""
        try:
            full_path = self._resolve_path(file_path)

            if not full_path.exists():
                return False, f"文件不存在: {file_path}"

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            return True, content

        except Exception as e:
            return False, str(e)

    def read_file_lines(self, file_path: str, start: int = 0, end: int = -1) -> Tuple[bool, List[str]]:
        """读取文件的指定行"""
        success, content = self.read_file(file_path)
        if not success:
            return False, []

        lines = content.split("\n")
        if end == -1:
            return True, lines[start:]
        return True, lines[start:end]

    def write_file(self, file_path: str, content: str, create_dirs: bool = True) -> Tuple[bool, str]:
        """写入文件"""
        try:
            full_path = self._resolve_path(file_path)

            if create_dirs:
                full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            return True, f"文件已写入: {full_path}"

        except Exception as e:
            return False, str(e)

    def append_file(self, file_path: str, content: str) -> Tuple[bool, str]:
        """追加内容到文件"""
        try:
            full_path = self._resolve_path(file_path)

            with open(full_path, "a", encoding="utf-8") as f:
                f.write(content)

            return True, f"内容已追加到: {full_path}"

        except Exception as e:
            return False, str(e)

    # ==================== 精确编辑操作 ====================

    def edit_file(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        replace_all: bool = False
    ) -> Tuple[bool, str]:
        """编辑文件（替换内容）"""
        try:
            success, content = self.read_file(file_path)
            if not success:
                return False, content

            if old_content not in content:
                return False, f"未找到要替换的内容"

            if replace_all:
                new_file_content = content.replace(old_content, new_content)
            else:
                new_file_content = content.replace(old_content, new_content, 1)

            return self.write_file(file_path, new_file_content)

        except Exception as e:
            return False, str(e)

    def insert_at_line(self, file_path: str, line_number: int, content: str) -> Tuple[bool, str]:
        """在指定行插入内容"""
        try:
            success, file_content = self.read_file(file_path)
            if not success:
                return False, file_content

            lines = file_content.split("\n")

            # 确保行号有效
            line_number = max(0, min(line_number, len(lines)))

            # 插入内容
            lines.insert(line_number, content)

            return self.write_file(file_path, "\n".join(lines))

        except Exception as e:
            return False, str(e)

    def insert_after_pattern(self, file_path: str, pattern: str, content: str) -> Tuple[bool, str]:
        """在匹配模式后插入内容"""
        try:
            success, file_content = self.read_file(file_path)
            if not success:
                return False, file_content

            lines = file_content.split("\n")
            inserted = False

            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    lines.insert(i + 1, content)
                    inserted = True
                    break

            if not inserted:
                return False, f"未找到匹配的模式: {pattern}"

            return self.write_file(file_path, "\n".join(lines))

        except Exception as e:
            return False, str(e)

    def insert_before_pattern(self, file_path: str, pattern: str, content: str) -> Tuple[bool, str]:
        """在匹配模式前插入内容"""
        try:
            success, file_content = self.read_file(file_path)
            if not success:
                return False, file_content

            lines = file_content.split("\n")
            inserted = False

            for i, line in enumerate(lines):
                if re.search(pattern, line):
                    lines.insert(i, content)
                    inserted = True
                    break

            if not inserted:
                return False, f"未找到匹配的模式: {pattern}"

            return self.write_file(file_path, "\n".join(lines))

        except Exception as e:
            return False, str(e)

    def replace_lines(self, file_path: str, start: int, end: int, new_content: str) -> Tuple[bool, str]:
        """替换指定行范围"""
        try:
            success, file_content = self.read_file(file_path)
            if not success:
                return False, file_content

            lines = file_content.split("\n")

            # 替换行
            new_lines = lines[:start] + [new_content] + lines[end:]

            return self.write_file(file_path, "\n".join(new_lines))

        except Exception as e:
            return False, str(e)

    def insert_into_class(
        self,
        file_path: str,
        class_name: str,
        content: str,
        position: str = "end"  # start, end
    ) -> Tuple[bool, str]:
        """在类中插入内容"""
        try:
            success, file_content = self.read_file(file_path)
            if not success:
                return False, file_content

            lines = file_content.split("\n")

            # 找到类的位置
            class_start = -1
            class_end = -1
            brace_count = 0

            for i, line in enumerate(lines):
                # 匹配类定义
                if re.search(rf'\bclass\s+{class_name}\b', line):
                    class_start = i
                    # 找到类开始的 {
                    for j in range(i, len(lines)):
                        brace_count += lines[j].count('{') - lines[j].count('}')
                        if '{' in lines[j] and brace_count > 0:
                            break

                # 找到类的结束
                if class_start >= 0:
                    for j in range(class_start, len(lines)):
                        brace_count += lines[j].count('{') - lines[j].count('}')
                        if brace_count == 0:
                            class_end = j
                            break

            if class_start < 0:
                return False, f"未找到类: {class_name}"

            # 确定插入位置
            if position == "start":
                # 在类开始后插入
                insert_line = class_start + 1
            else:
                # 在类结束前插入
                insert_line = class_end

            lines.insert(insert_line, content)

            return self.write_file(file_path, "\n".join(lines))

        except Exception as e:
            return False, str(e)

    # ==================== 智能定位操作 ====================

    def find_file_for_task(self, task: str) -> Dict[str, Any]:
        """根据任务描述找到相关文件"""
        analyzer = self._get_analyzer()

        # 确保项目已扫描
        if not analyzer.files:
            analyzer.scan_project()

        return analyzer.find_for_task(task)

    def find_symbol(self, symbol_name: str) -> List[Dict[str, Any]]:
        """查找符号"""
        analyzer = self._get_analyzer()

        if not analyzer.files:
            analyzer.scan_project()

        symbols = analyzer.find_symbol(symbol_name)
        return [
            {
                "name": s.name,
                "type": s.type,
                "file": s.file_path,
                "line": s.line_start,
                "parent": s.parent
            }
            for s in symbols
        ]

    def find_class_file(self, class_name: str) -> Optional[str]:
        """找到类所在的文件"""
        symbols = self.find_symbol(class_name)
        for s in symbols:
            if s["type"] == "class":
                return s["file"]
        return None

    def find_function_file(self, function_name: str) -> Optional[str]:
        """找到函数所在的文件"""
        symbols = self.find_symbol(function_name)
        for s in symbols:
            if s["type"] in ("function", "method"):
                return s["file"]
        return None

    def get_file_context(self, file_path: str, context_lines: int = 50) -> Dict[str, Any]:
        """获取文件上下文"""
        success, content = self.read_file(file_path)
        if not success:
            return {"error": content}

        lines = content.split("\n")

        return {
            "path": file_path,
            "total_lines": len(lines),
            "preview": "\n".join(lines[:context_lines]),
            "language": self._detect_language(file_path)
        }

    # ==================== 辅助方法 ====================

    def _resolve_path(self, file_path: str) -> Path:
        """解析路径"""
        path = Path(file_path)
        if path.is_absolute():
            return path
        return self.project_root / path

    def _detect_language(self, file_path: str) -> str:
        """检测文件语言"""
        ext = Path(file_path).suffix.lower()
        lang_map = {
            ".kt": "kotlin",
            ".java": "java",
            ".swift": "swift",
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".xml": "xml",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
        }
        return lang_map.get(ext, "unknown")

    def _should_ignore(self, path: Path) -> bool:
        """判断是否应该忽略"""
        ignore_patterns = [
            ".git", ".gradle", "build", "node_modules",
            ".idea", "*.iml", "DerivedData", ".DS_Store",
            "__pycache__", ".pytest_cache", "venv", ".venv",
            "Pods", "target", "dist", ".next"
        ]

        for pattern in ignore_patterns:
            if pattern.startswith("*"):
                if path.name.endswith(pattern[1:]):
                    return True
            elif pattern in path.parts:
                return True

        return False

    def analyze_project(self) -> Dict[str, Any]:
        """分析项目结构"""
        result = {
            "root": str(self.project_root),
            "type": "unknown",
            "files": [],
            "dirs": []
        }

        # 使用分析器检测项目类型
        analyzer = self._get_analyzer()
        result["type"] = analyzer.detect_project_type()

        # 收集文件
        for item in self.project_root.rglob("*"):
            if item.is_file() and not self._should_ignore(item):
                rel_path = item.relative_to(self.project_root)
                result["files"].append(str(rel_path))
            elif item.is_dir() and not self._should_ignore(item):
                rel_path = item.relative_to(self.project_root)
                result["dirs"].append(str(rel_path))

        return result

    def find_files(self, pattern: str) -> List[Path]:
        """查找匹配的文件"""
        return list(self.project_root.rglob(pattern))

    def get_file_tree(self, max_depth: int = 3) -> str:
        """获取文件树"""
        lines = []

        for item in sorted(self.project_root.rglob("*")):
            if self._should_ignore(item):
                continue

            rel_path = item.relative_to(self.project_root)
            depth = len(rel_path.parts) - 1

            if depth > max_depth:
                continue

            indent = "  " * depth
            prefix = "├── " if not item.is_dir() else "├── 📁 "
            lines.append(f"{indent}{prefix}{item.name}")

        return "\n".join(lines)


# 单例实例
_file_ops_instance = None


def get_file_ops() -> FileOperations:
    """获取文件操作单例"""
    global _file_ops_instance
    if _file_ops_instance is None:
        _file_ops_instance = FileOperations()
    return _file_ops_instance