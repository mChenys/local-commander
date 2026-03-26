"""
项目结构分析器 - 扫描项目、建立索引、支持符号搜索
"""

import os
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class CodeSymbol:
    """代码符号"""
    name: str
    type: str  # class, function, method, variable, interface, enum
    file_path: str
    line_start: int
    line_end: int
    parent: Optional[str] = None  # 父级（如类名）
    modifiers: List[str] = field(default_factory=list)  # public, private, static, etc.


@dataclass
class FileInfo:
    """文件信息"""
    path: str
    language: str
    size: int
    symbols: List[CodeSymbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)


class ProjectAnalyzer:
    """项目分析器"""

    # 支持的语言及其文件扩展名
    LANGUAGE_EXTENSIONS = {
        "kotlin": [".kt"],
        "java": [".java"],
        "swift": [".swift"],
        "python": [".py"],
        "javascript": [".js", ".jsx"],
        "typescript": [".ts", ".tsx"],
        "go": [".go"],
        "rust": [".rs"],
        "c": [".c", ".h"],
        "cpp": [".cpp", "hpp", "cc"],
        "xml": [".xml"],
        "json": [".json"],
        "yaml": [".yaml", ".yml"],
        "markdown": [".md"],
    }

    # 忽略的目录
    IGNORE_DIRS = {
        "build", ".gradle", ".idea", ".git", "node_modules",
        "__pycache__", ".pytest_cache", "venv", ".venv",
        "Pods", "DerivedData", ".build", "out", "target",
        "dist", ".next", ".nuxt", "coverage"
    }

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root) if project_root else None
        self.files: Dict[str, FileInfo] = {}
        self.symbols: Dict[str, List[CodeSymbol]] = {}  # 按符号名索引
        self.project_type: str = "unknown"
        self.index_path: Optional[Path] = None

    def set_project(self, project_root: Path):
        """设置项目根目录"""
        self.project_root = Path(project_root)
        self.index_path = self.project_root / ".local-commander" / "index.json"

    def detect_project_type(self) -> str:
        """检测项目类型"""
        if not self.project_root:
            return "unknown"

        # Android 项目
        if (self.project_root / "build.gradle").exists() or \
           (self.project_root / "build.gradle.kts").exists():
            self.project_type = "android"
            return "android"

        # iOS 项目
        if list(self.project_root.glob("*.xcodeproj")) or \
           list(self.project_root.glob("*.xcworkspace")):
            self.project_type = "ios"
            return "ios"

        # Flutter 项目
        if (self.project_root / "pubspec.yaml").exists():
            self.project_type = "flutter"
            return "flutter"

        # React Native 项目
        if (self.project_root / "package.json").exists():
            pkg = self.project_root / "package.json"
            try:
                content = json.loads(pkg.read_text())
                deps = {**content.get("dependencies", {}), **content.get("devDependencies", {})}
                if "react-native" in deps:
                    self.project_type = "react-native"
                    return "react-native"
                if "react" in deps or "next" in deps:
                    self.project_type = "web-react"
                    return "web-react"
                if "vue" in deps:
                    self.project_type = "web-vue"
                    return "web-vue"
            except:
                pass
            self.project_type = "web"
            return "web"

        # Python 项目
        if (self.project_root / "requirements.txt").exists() or \
           (self.project_root / "setup.py").exists() or \
           (self.project_root / "pyproject.toml").exists():
            self.project_type = "python"
            return "python"

        return "unknown"

    def scan_project(self, force: bool = False) -> Dict[str, Any]:
        """扫描项目"""
        if not self.project_root:
            return {"error": "项目根目录未设置"}

        # 先检测项目类型
        if self.project_type == "unknown":
            self.detect_project_type()

        # 检查是否有缓存的索引
        if not force and self.index_path and self.index_path.exists():
            try:
                cached = json.loads(self.index_path.read_text())
                if datetime.now().timestamp() - cached.get("timestamp", 0) < 3600:  # 1小时缓存
                    self._load_cached_index(cached)
                    return {"status": "cached", "files": len(self.files), "symbols": sum(len(v) for v in self.symbols.values())}
            except:
                pass

        # 扫描文件
        for file_path in self._walk_project():
            self._analyze_file(file_path)

        # 保存索引
        self._save_index()

        return {
            "project_type": self.project_type,
            "files": len(self.files),
            "symbols": sum(len(v) for v in self.symbols.values()),
            "classes": sum(len(f.classes) for f in self.files.values()),
            "functions": sum(len(f.functions) for f in self.files.values())
        }

    def _walk_project(self) -> List[Path]:
        """遍历项目文件"""
        files = []
        for root, dirs, filenames in os.walk(self.project_root):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith(".")]

            for filename in filenames:
                file_path = Path(root) / filename
                # 检查文件类型
                ext = file_path.suffix.lower()
                for lang, exts in self.LANGUAGE_EXTENSIONS.items():
                    if ext in exts:
                        files.append(file_path)
                        break

        return files

    def _analyze_file(self, file_path: Path):
        """分析单个文件"""
        ext = file_path.suffix.lower()

        # 确定语言
        language = None
        for lang, exts in self.LANGUAGE_EXTENSIONS.items():
            if ext in exts:
                language = lang
                break

        if not language:
            return

        try:
            content = file_path.read_text(encoding="utf-8")
        except:
            return

        relative_path = str(file_path.relative_to(self.project_root))
        file_info = FileInfo(
            path=relative_path,
            language=language,
            size=file_path.stat().st_size
        )

        # 根据语言解析符号
        if language == "kotlin":
            self._parse_kotlin(content, file_info)
        elif language == "java":
            self._parse_java(content, file_info)
        elif language == "swift":
            self._parse_swift(content, file_info)
        elif language == "python":
            self._parse_python(content, file_info)
        elif language in ("javascript", "typescript"):
            self._parse_js_ts(content, file_info)

        self.files[relative_path] = file_info

    def _parse_kotlin(self, content: str, file_info: FileInfo):
        """解析 Kotlin 代码"""
        lines = content.split("\n")

        # 类定义
        class_pattern = re.compile(r'(?:public|private|protected|internal|open|sealed|data|abstract|enum)?\s*(?:class|interface|object)\s+(\w+)')
        # 函数定义
        func_pattern = re.compile(r'(?:public|private|protected|internal|suspend|inline|override)?\s*fun\s+(\w+)\s*\(')
        # 变量定义
        var_pattern = re.compile(r'(?:val|var)\s+(\w+)\s*[:=]')

        current_class = None

        for i, line in enumerate(lines, 1):
            # 匹配类
            class_match = class_pattern.search(line)
            if class_match:
                class_name = class_match.group(1)
                current_class = class_name
                file_info.classes.append(class_name)
                symbol = CodeSymbol(
                    name=class_name,
                    type="class",
                    file_path=file_info.path,
                    line_start=i,
                    line_end=i  # 会在后续更新
                )
                self._add_symbol(symbol)

            # 匹配函数
            func_match = func_pattern.search(line)
            if func_match:
                func_name = func_match.group(1)
                file_info.functions.append(func_name)
                symbol = CodeSymbol(
                    name=func_name,
                    type="method" if current_class else "function",
                    file_path=file_info.path,
                    line_start=i,
                    line_end=i,
                    parent=current_class
                )
                self._add_symbol(symbol)

    def _parse_java(self, content: str, file_info: FileInfo):
        """解析 Java 代码"""
        lines = content.split("\n")

        class_pattern = re.compile(r'(?:public|private|protected|abstract|final)?\s*(?:class|interface|enum)\s+(\w+)')
        method_pattern = re.compile(r'(?:public|private|protected|static|final|abstract)?\s*\w+\s+(\w+)\s*\(')

        current_class = None

        for i, line in enumerate(lines, 1):
            class_match = class_pattern.search(line)
            if class_match:
                class_name = class_match.group(1)
                current_class = class_name
                file_info.classes.append(class_name)
                symbol = CodeSymbol(
                    name=class_name,
                    type="class",
                    file_path=file_info.path,
                    line_start=i,
                    line_end=i
                )
                self._add_symbol(symbol)

            method_match = method_pattern.search(line)
            if method_match:
                method_name = method_match.group(1)
                if method_name not in ("if", "for", "while", "switch"):  # 过滤关键字
                    file_info.functions.append(method_name)
                    symbol = CodeSymbol(
                        name=method_name,
                        type="method",
                        file_path=file_info.path,
                        line_start=i,
                        line_end=i,
                        parent=current_class
                    )
                    self._add_symbol(symbol)

    def _parse_swift(self, content: str, file_info: FileInfo):
        """解析 Swift 代码"""
        lines = content.split("\n")

        class_pattern = re.compile(r'(?:public|private|internal|open|final)?\s*(?:class|struct|protocol|enum)\s+(\w+)')
        func_pattern = re.compile(r'(?:public|private|internal|override|static)?\s*func\s+(\w+)\s*\(')

        current_class = None

        for i, line in enumerate(lines, 1):
            class_match = class_pattern.search(line)
            if class_match:
                class_name = class_match.group(1)
                current_class = class_name
                file_info.classes.append(class_name)
                symbol = CodeSymbol(
                    name=class_name,
                    type="class",
                    file_path=file_info.path,
                    line_start=i,
                    line_end=i
                )
                self._add_symbol(symbol)

            func_match = func_pattern.search(line)
            if func_match:
                func_name = func_match.group(1)
                file_info.functions.append(func_name)
                symbol = CodeSymbol(
                    name=func_name,
                    type="method" if current_class else "function",
                    file_path=file_info.path,
                    line_start=i,
                    line_end=i,
                    parent=current_class
                )
                self._add_symbol(symbol)

    def _parse_python(self, content: str, file_info: FileInfo):
        """解析 Python 代码"""
        lines = content.split("\n")

        class_pattern = re.compile(r'class\s+(\w+)')
        func_pattern = re.compile(r'def\s+(\w+)')

        current_class = None

        for i, line in enumerate(lines, 1):
            class_match = class_pattern.search(line)
            if class_match:
                class_name = class_match.group(1)
                current_class = class_name
                file_info.classes.append(class_name)
                symbol = CodeSymbol(
                    name=class_name,
                    type="class",
                    file_path=file_info.path,
                    line_start=i,
                    line_end=i
                )
                self._add_symbol(symbol)

            func_match = func_pattern.search(line)
            if func_match:
                func_name = func_match.group(1)
                if not line.strip().startswith("#"):
                    file_info.functions.append(func_name)
                    symbol = CodeSymbol(
                        name=func_name,
                        type="method" if current_class and line.startswith("    ") else "function",
                        file_path=file_info.path,
                        line_start=i,
                        line_end=i,
                        parent=current_class if current_class and line.startswith("    ") else None
                    )
                    self._add_symbol(symbol)

    def _parse_js_ts(self, content: str, file_info: FileInfo):
        """解析 JavaScript/TypeScript 代码"""
        lines = content.split("\n")

        class_pattern = re.compile(r'(?:export\s+)?class\s+(\w+)')
        func_pattern = re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)|(\w+)\s*\([^)]*\)\s*\{')
        arrow_pattern = re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=])\s*=>')

        current_class = None

        for i, line in enumerate(lines, 1):
            class_match = class_pattern.search(line)
            if class_match:
                class_name = class_match.group(1)
                current_class = class_name
                file_info.classes.append(class_name)
                symbol = CodeSymbol(
                    name=class_name,
                    type="class",
                    file_path=file_info.path,
                    line_start=i,
                    line_end=i
                )
                self._add_symbol(symbol)

            func_match = func_pattern.search(line)
            if func_match:
                func_name = func_match.group(1) or func_match.group(2)
                if func_name and func_name not in ("if", "for", "while", "switch", "catch"):
                    file_info.functions.append(func_name)
                    symbol = CodeSymbol(
                        name=func_name,
                        type="function",
                        file_path=file_info.path,
                        line_start=i,
                        line_end=i
                    )
                    self._add_symbol(symbol)

            arrow_match = arrow_pattern.search(line)
            if arrow_match:
                func_name = arrow_match.group(1)
                file_info.functions.append(func_name)
                symbol = CodeSymbol(
                    name=func_name,
                    type="function",
                    file_path=file_info.path,
                    line_start=i,
                    line_end=i
                )
                self._add_symbol(symbol)

    def _add_symbol(self, symbol: CodeSymbol):
        """添加符号到索引"""
        if symbol.name not in self.symbols:
            self.symbols[symbol.name] = []
        self.symbols[symbol.name].append(symbol)

    def find_symbol(self, name: str) -> List[CodeSymbol]:
        """查找符号"""
        # 精确匹配
        if name in self.symbols:
            return self.symbols[name]

        # 模糊匹配
        results = []
        for symbol_name, symbols in self.symbols.items():
            if name.lower() in symbol_name.lower():
                results.extend(symbols)
        return results

    def find_by_keyword(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """根据关键词查找相关文件"""
        results = []

        for file_path, file_info in self.files.items():
            score = 0
            matched_symbols = []

            # 检查文件名
            file_name = Path(file_path).stem.lower()
            for kw in keywords:
                if kw.lower() in file_name:
                    score += 10

            # 检查类名
            for cls in file_info.classes:
                for kw in keywords:
                    if kw.lower() in cls.lower():
                        score += 5
                        matched_symbols.append(cls)

            # 检查函数名
            for func in file_info.functions:
                for kw in keywords:
                    if kw.lower() in func.lower():
                        score += 3
                        matched_symbols.append(func)

            if score > 0:
                results.append({
                    "file": file_path,
                    "score": score,
                    "language": file_info.language,
                    "classes": file_info.classes,
                    "functions": matched_symbols[:10]
                })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:10]

    def find_for_task(self, task: str) -> Dict[str, Any]:
        """根据任务描述找到相关文件"""
        # 提取关键词
        keywords = self._extract_keywords(task)

        # 查找相关文件
        files = self.find_by_keyword(keywords)

        # 查找相关符号
        symbols = []
        for kw in keywords:
            symbols.extend(self.find_symbol(kw))

        return {
            "keywords": keywords,
            "files": files,
            "symbols": [{"name": s.name, "type": s.type, "file": s.file_path, "line": s.line_start} for s in symbols[:10]]
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        # 停用词
        stop_words = {"的", "是", "在", "和", "了", "我", "有", "这", "个", "也", "就", "不", "人", "都", "一", "一个", "上", "也", "要", "为", "以", "到", "能", "会", "可", "写", "实现", "添加", "创建", "修改", "删除"}

        # 分词（简单实现）
        words = re.findall(r'[\w]+', text)

        keywords = []
        for word in words:
            if len(word) > 1 and word.lower() not in stop_words:
                # 驼峰命名拆分
                parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', word)
                if parts:
                    keywords.extend([p.lower() for p in parts if len(p) > 1])
                else:
                    keywords.append(word.lower())

        return list(set(keywords))

    def _save_index(self):
        """保存索引到文件"""
        if not self.index_path:
            return

        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "timestamp": datetime.now().timestamp(),
            "project_type": self.project_type,
            "project_root": str(self.project_root),
            "files": {k: {"path": v.path, "language": v.language, "size": v.size,
                         "classes": v.classes, "functions": v.functions} for k, v in self.files.items()},
            "symbols": {k: [asdict(s) for s in v] for k, v in self.symbols.items()}
        }

        self.index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _load_cached_index(self, data: dict):
        """加载缓存的索引"""
        self.project_type = data.get("project_type", "unknown")

        for path, info in data.get("files", {}).items():
            file_info = FileInfo(
                path=info["path"],
                language=info["language"],
                size=info["size"],
                classes=info.get("classes", []),
                functions=info.get("functions", [])
            )
            self.files[path] = file_info

        for name, symbols in data.get("symbols", {}).items():
            self.symbols[name] = [CodeSymbol(**s) for s in symbols]

    def get_project_structure(self) -> Dict[str, Any]:
        """获取项目结构概览"""
        if not self.project_root:
            return {}

        structure = {
            "type": self.project_type,
            "root": str(self.project_root),
            "total_files": len(self.files),
            "by_language": {},
            "main_directories": set(),
            "entry_points": []
        }

        for file_path, file_info in self.files.items():
            # 统计语言
            lang = file_info.language
            if lang not in structure["by_language"]:
                structure["by_language"][lang] = 0
            structure["by_language"][lang] += 1

            # 收集目录
            dir_name = str(Path(file_path).parent)
            structure["main_directories"].add(dir_name)

            # 入口文件检测
            file_name = Path(file_path).name.lower()
            if file_name in ("main.kt", "main.java", "main.swift", "main.py", "index.js", "index.ts", "app.kt", "app.java"):
                structure["entry_points"].append(file_path)

        structure["main_directories"] = list(structure["main_directories"])[:20]
        return structure


# 单例实例
_analyzer_instance = None


def get_analyzer() -> ProjectAnalyzer:
    """获取分析器单例"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = ProjectAnalyzer()
    return _analyzer_instance