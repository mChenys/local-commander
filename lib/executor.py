"""
任务执行器 - 调用本地模型执行任务，支持智能代码修改和自动化测试
"""

import subprocess
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

# 导入测试器
try:
    from .testers import get_test_executor
    TEST_EXECUTOR_AVAILABLE = True
except ImportError:
    TEST_EXECUTOR_AVAILABLE = False
    print("警告: 测试器模块不可用，将跳过自动化测试")


class TaskExecutor:
    """任务执行器，负责调用本地模型并智能处理代码"""

    # 默认配置 - 本地模型不用钱，尽情用
    DEFAULT_MAX_TOKENS = 8192  # 足够长的输出
    DEFAULT_CONTEXT_FILES = 5  # 读取更多文件（从3增加到5）
    DEFAULT_CONTEXT_LINES = 300  # 每个文件读更多行（从100增加到300）
    DEFAULT_TEMPERATURE = 0.0

    def __init__(self):
        self.max_tokens = self.DEFAULT_MAX_TOKENS
        self.temperature = self.DEFAULT_TEMPERATURE
        self._file_ops = None
        self._analyzer = None

    def _get_file_ops(self):
        """懒加载文件操作"""
        if self._file_ops is None:
            from .file_ops import get_file_ops
            self._file_ops = get_file_ops()
        return self._file_ops

    def _get_analyzer(self):
        """懒加载分析器"""
        if self._analyzer is None:
            from .analyzer import get_analyzer
            self._analyzer = get_analyzer()
        return self._analyzer

    def execute(
        self,
        model_id: str,
        prompt: str,
        image_path: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """执行任务"""
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        # 判断是视觉模型还是文本模型
        is_vl_model = "VL" in model_id or "vl" in model_id

        if is_vl_model and image_path:
            return self._execute_vl(model_id, prompt, image_path, max_tokens, temperature)
        else:
            return self._execute_lm(model_id, prompt, max_tokens, temperature)

    def execute_with_context(
        self,
        model_id: str,
        task: str,
        project_root: Optional[Path] = None,
        max_tokens: Optional[int] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        带上下文的智能执行

        流程：
        1. 分析任务，提取关键词
        2. 扫描项目，找到相关文件
        3. 读取相关代码作为上下文
        4. 构建增强的 prompt
        5. 执行并返回结果
        """
        file_ops = self._get_file_ops()
        analyzer = self._get_analyzer()

        # 设置项目根目录
        if project_root:
            file_ops.set_project_root(project_root)
            analyzer.set_project(project_root)

        # 扫描项目
        scan_result = analyzer.scan_project()

        # 分析任务，找到相关文件
        related = analyzer.find_for_task(task)

        # 构建上下文
        context_parts = []

        # 1. 项目概览
        context_parts.append(f"项目类型: {analyzer.project_type}")
        context_parts.append(f"总文件数: {len(analyzer.files)}")
        context_parts.append(f"总符号数: {sum(len(v) for v in analyzer.symbols.values())}")

        # 2. 项目结构（主要目录）
        structure = analyzer.get_project_structure()
        if structure.get('by_language'):
            lang_stats = ', '.join([f"{k}: {v}" for k, v in sorted(structure['by_language'].items(), key=lambda x: -x[1])[:5]])
            context_parts.append(f"语言分布: {lang_stats}")

        if structure.get('entry_points'):
            context_parts.append(f"入口文件: {', '.join(structure['entry_points'][:5])}")

        # 3. 读取关键配置文件
        config_files = self._find_config_files(project_root or Path.cwd())
        for cfg_file in config_files[:3]:
            success, content = file_ops.read_file(cfg_file)
            if success:
                lines = content.split('\n')[:100]  # 配置文件读前100行
                context_parts.append(f"\n--- {cfg_file} ---\n" + '\n'.join(lines))

        # 4. 读取相关文件的内容
        context_parts.append(f"\n相关文件 ({len(related['files'])} 个):")
        for i, file_info in enumerate(related['files'][:self.DEFAULT_CONTEXT_FILES]):
            file_path = file_info['file']
            success, content = file_ops.read_file(file_path)
            if success:
                lines = content.split('\n')[:self.DEFAULT_CONTEXT_LINES]
                context_parts.append(f"\n--- {file_path} ---\n" + '\n'.join(lines))

        # 5. 相关符号信息
        if related['symbols']:
            context_parts.append(f"\n相关符号 ({len(related['symbols'])} 个):")
            for sym in related['symbols'][:20]:
                context_parts.append(f"  - {sym['name']} ({sym['type']}) in {sym['file']}:{sym['line']}")

        context = '\n'.join(context_parts)

        # 构建增强的 prompt
        enhanced_prompt = self._build_enhanced_prompt(task, context, analyzer.project_type)

        # 执行 - 使用更大的 max_tokens
        tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        return self.execute(model_id, enhanced_prompt, max_tokens=tokens)

    def _find_config_files(self, project_root: Path) -> List[str]:
        """查找关键配置文件"""
        config_patterns = [
            "build.gradle", "build.gradle.kts",
            "settings.gradle", "settings.gradle.kts",
            "app/build.gradle", "app/build.gradle.kts",
            "gradle.properties",
            "Package.swift", "Podfile",
            "package.json", "tsconfig.json",
            "requirements.txt", "pyproject.toml",
            "go.mod", "Cargo.toml"
        ]

        found = []
        for pattern in config_patterns:
            path = project_root / pattern
            if path.exists():
                found.append(pattern)
        return found

    def execute_and_modify(
        self,
        model_id: str,
        task: str,
        project_root: Optional[Path] = None,
        auto_save: bool = True
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        执行任务并自动修改代码

        适合：修改现有功能、添加方法到类中等
        """
        file_ops = self._get_file_ops()
        analyzer = self._get_analyzer()

        if project_root:
            file_ops.set_project_root(project_root)
            analyzer.set_project(project_root)

        # 找到目标文件
        related = analyzer.find_for_task(task)

        if not related['files']:
            # 没有找到相关文件，使用普通执行
            return self.execute_with_context(model_id, task, project_root)

        # 取最相关的文件
        target_file = related['files'][0]['file']
        target_symbols = related['symbols']

        # 读取目标文件
        success, file_content = file_ops.read_file(target_file)
        if not success:
            return False, f"无法读取文件: {target_file}", {}

        # 构建修改指令的 prompt
        modify_prompt = self._build_modify_prompt(
            task, target_file, file_content, target_symbols
        )

        # 执行
        success, output, metadata = self.execute(model_id, modify_prompt, max_tokens=2048)

        if not success:
            return success, output, metadata

        # 提取修改指令
        modifications = self._extract_modifications(output)

        if not modifications:
            # 没有提取到修改指令，返回原始输出
            metadata['type'] = 'no_modification'
            return success, output, metadata

        # 应用修改
        results = []
        for mod in modifications:
            action = mod.get('action')
            if action == 'replace':
                ok, msg = file_ops.edit_file(
                    target_file,
                    mod['old'],
                    mod['new']
                )
                results.append(f"替换: {msg}")
            elif action == 'insert_after':
                ok, msg = file_ops.insert_after_pattern(
                    target_file,
                    mod['pattern'],
                    mod['code']
                )
                results.append(f"插入: {msg}")
            elif action == 'insert_before':
                ok, msg = file_ops.insert_before_pattern(
                    target_file,
                    mod['pattern'],
                    mod['code']
                )
                results.append(f"插入: {msg}")

        metadata['modifications'] = results
        metadata['target_file'] = target_file

        return True, f"已修改 {target_file}\n" + '\n'.join(results), metadata

    def _build_enhanced_prompt(self, task: str, context: str, project_type: str) -> str:
        """构建增强的 prompt"""
        return f"""<|im_start|>system
You are an expert developer assistant. You understand project context and write clean, efficient code.
Project type: {project_type}
<|im_end|>
<|im_start|>user
Context:
{context}

Task: {task}

Please provide a clear, well-structured solution. Include code examples if needed.
<|im_end|>
<|im_start|>assistant
"""

    def _build_modify_prompt(
        self,
        task: str,
        file_path: str,
        file_content: str,
        symbols: List[Dict]
    ) -> str:
        """构建修改指令的 prompt"""
        symbols_info = '\n'.join([
            f"  - {s['name']} ({s['type']}) at line {s['line']}"
            for s in symbols[:5]
        ])

        return f"""<|im_start|>system
You are a code modification assistant. You analyze existing code and suggest precise modifications.
Output modifications in this JSON format:
```json
{{
  "analysis": "Brief analysis of what needs to be done",
  "modifications": [
    {{
      "action": "replace|insert_after|insert_before",
      "target": "symbol name or pattern",
      "old": "exact text to replace (for replace action)",
      "new": "new text (for replace action)",
      "pattern": "regex pattern (for insert actions)",
      "code": "code to insert (for insert actions)"
    }}
  ]
}}
```
<|im_end|>
<|im_start|>user
File: {file_path}

Existing symbols:
{symbols_info}

Current file content:
```
{file_content[:5000]}
```

Task: {task}

Analyze the code and provide modifications in JSON format.
<|im_end|>
<|im_start|>assistant
"""

    def _extract_modifications(self, output: str) -> List[Dict]:
        """从输出中提取修改指令"""
        # 尝试提取 JSON
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', output)
        if not json_match:
            json_match = re.search(r'\{[\s\S]*"modifications"[\s\S]*\}', output)

        if not json_match:
            return []

        try:
            data = json.loads(json_match.group(1) if '```' in output else json_match.group(0))
            return data.get('modifications', [])
        except json.JSONDecodeError:
            return []

    def _execute_lm(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """执行文本模型"""
        cmd = [
            "mlx_lm.generate",
            "--model", model_id,
            "--prompt", prompt,
            "--max-tokens", str(max_tokens),
            "--temp", str(temperature)
        ]

        metadata = {
            "model": model_id,
            "type": "text"
        }

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )

            if result.returncode != 0:
                return False, result.stderr, metadata

            output = self._parse_output(result.stdout)
            return True, output, metadata

        except subprocess.TimeoutExpired:
            return False, "执行超时", metadata
        except Exception as e:
            return False, str(e), metadata

    def _execute_vl(
        self,
        model_id: str,
        prompt: str,
        image_path: str,
        max_tokens: int,
        temperature: float
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """执行视觉模型"""
        cmd = [
            "mlx_vlm.generate",
            "--model", model_id,
            "--prompt", prompt,
            "--image", image_path,
            "--max-tokens", str(max_tokens)
        ]

        metadata = {
            "model": model_id,
            "image": image_path,
            "type": "vision"
        }

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )

            if result.returncode != 0:
                return False, result.stderr, metadata

            output = self._parse_output(result.stdout)
            return True, output, metadata

        except subprocess.TimeoutExpired:
            return False, "执行超时", metadata
        except Exception as e:
            return False, str(e), metadata

    def _parse_output(self, raw: str) -> str:
        """解析模型输出"""
        lines = raw.strip().split("\n")
        in_output = False
        output_lines = []

        for line in lines:
            if "==========" in line:
                if in_output:
                    break
                in_output = True
                continue

            if in_output:
                output_lines.append(line)

        if output_lines:
            return "\n".join(output_lines).strip()

        return raw

    def self_review(self, model_id: str, code: str) -> Tuple[bool, str]:
        """代码自检"""
        review_prompt = f"""<|im_start|>system
You are a code reviewer. Check for:
1. Syntax errors
2. Logic errors
3. Potential bugs
4. Code style issues

Reply "代码检查通过" if no issues, otherwise list problems and fixes.
<|im_end|>
<|im_start|>user
Check this code:
```
{code}
```
<|im_end|>
<|im_start|>assistant
"""

        success, output, _ = self.execute(model_id, review_prompt)
        has_issues = "代码检查通过" not in output
        return has_issues, output

    def analyze_task(self, task: str, project_root: Optional[Path] = None) -> Dict[str, Any]:
        """分析任务，返回相关信息"""
        analyzer = self._get_analyzer()

        if project_root:
            analyzer.set_project(project_root)

        if not analyzer.files:
            analyzer.scan_project()

        return analyzer.find_for_task(task)

    def run_automated_tests(self, project_path: str, test_type: str = "auto") -> Dict[str, Any]:
        """运行自动化测试"""
        if not TEST_EXECUTOR_AVAILABLE:
            return {"error": "测试器模块不可用"}

        try:
            test_executor = get_test_executor()
            return test_executor.execute_test(project_path, test_type)
        except Exception as e:
            return {"error": f"运行自动化测试失败: {str(e)}"}

    def execute_with_testing(self, model_id: str, task: str, project_root: Optional[Path] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        执行任务并运行自动化测试
        在代码生成后自动运行对应平台的测试
        """
        # 首先执行任务
        success, output, metadata = self.execute_with_context(model_id, task, project_root)

        if not success:
            return success, output, metadata

        # 如果成功生成代码，在项目目录尝试运行测试
        if project_root:
            print(f"正在为项目 {project_root} 运行自动化测试...")
            test_result = self.run_automated_tests(str(project_root))

            if "error" not in test_result:
                # 测试执行成功，添加测试结果到元数据
                metadata["test_results"] = test_result

                # 分析测试结果
                if test_result.get("failed", 0) > 0:
                    # 测试失败，需要修复
                    test_summary = f"⚠️ 自动测试发现 {test_result.get('failed', 0)} 个失败用例"
                    output += f"\n\n{test_summary}\n"
                    metadata["test_status"] = "failed"
                else:
                    # 测试全部通过
                    test_summary = f"✅ 所有 {test_result.get('passed', 0)} 个测试用例通过"
                    output += f"\n\n{test_summary}\n"
                    metadata["test_status"] = "passed"
            else:
                # 测试执行失败
                test_error = test_result["error"]
                output += f"\n\n⚠️ 自动测试执行失败: {test_error}\n"
                metadata["test_status"] = "execution_failed"
                metadata["test_error"] = test_error

        return True, output, metadata


# 单例实例
_executor_instance = None


def get_executor() -> TaskExecutor:
    """获取执行器单例"""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = TaskExecutor()
    return _executor_instance