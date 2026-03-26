"""
测试覆盖率分析器 - 支持 Android (JaCoCo), iOS (Xcode built-in), Web (Istanbul/nyc)
"""

import os
import subprocess
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class CoverageAnalyzer:
    """测试覆盖率分析器，支持多平台覆盖率分析"""

    def __init__(self):
        self.reports_dir = Path.home() / ".local-commander" / "coverage-reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def analyze_android_coverage(self, project_path: str, variant: str = "debug") -> Dict[str, Any]:
        """分析 Android 项目的测试覆盖率 (JaCoCo)"""
        try:
            project_path = Path(project_path)

            # 检查是否为 Android 项目
            if not (project_path / "build.gradle").exists() and not (project_path / "build.gradle.kts").exists():
                return {"error": "不是有效的 Android 项目"}

            # 检查是否有 Jacoco 插件
            build_gradle_files = list(project_path.rglob("build.gradle*"))
            has_jacoco = False
            for gradle_file in build_gradle_files:
                try:
                    content = gradle_file.read_text(encoding='utf-8')
                    if 'jacoco' in content.lower():
                        has_jacoco = True
                        break
                except:
                    continue

            if not has_jacoco:
                return {"error": "项目中未配置 JaCoCo 插件"}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = self.reports_dir / f"android_coverage_{timestamp}"
            report_dir.mkdir(exist_ok=True)

            # 构建并运行测试以生成覆盖率数据
            gradle_wrapper = project_path / "gradlew"
            if gradle_wrapper.exists():
                # 使用 Gradle wrapper
                test_cmd = [str(gradle_wrapper), f"create{variant.capitalize()}CoverageReport"]
                subprocess.run(test_cmd, cwd=project_path, capture_output=True, text=True)
            else:
                # 使用全局 Gradle
                test_cmd = ["gradle", f"create{variant.capitalize()}CoverageReport"]
                subprocess.run(test_cmd, cwd=project_path, capture_output=True, text=True)

            # 查找 JaCoCo 报告文件
            jacoco_report_files = list(project_path.rglob(f"jacocoTestReport/**/jacocoTestReport.xml")) + \
                                  list(project_path.rglob(f"jacocoTestReport.xml")) + \
                                  list(project_path.rglob(f"build/reports/jacoco/**/jacoco.xml")) + \
                                  list(project_path.rglob(f"build/reports/jacoco/**/test/jacocoTestReport.xml"))

            if not jacoco_report_files:
                return {"error": "未找到 JaCoCo 覆盖率报告文件"}

            # 解析 JaCoCo XML 报告
            jacoco_file = jacoco_report_files[0]
            coverage_data = self._parse_jacoco_xml(jacoco_file)

            # 生成 JSON 报告
            coverage_json = report_dir / "coverage.json"
            with open(coverage_json, 'w', encoding='utf-8') as f:
                json.dump(coverage_data, f, ensure_ascii=False, indent=2)

            result = {
                "platform": "android",
                "type": "jacoco",
                "project_path": str(project_path),
                "variant": variant,
                "coverage": coverage_data,
                "report_path": str(coverage_json),
                "timestamp": timestamp
            }

            return result

        except Exception as e:
            return {"error": f"分析 Android 覆盖率失败: {str(e)}"}

    def _parse_jacoco_xml(self, xml_file: Path) -> Dict[str, Any]:
        """解析 JaCoCo XML 报告"""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # 计算总体覆盖率
            counters = {}
            for counter in root.findall(".//counter"):
                type_attr = counter.get('type', '')
                covered = int(counter.get('covered', 0))
                missed = int(counter.get('missed', 0))
                total = covered + missed

                if type_attr not in counters:
                    counters[type_attr] = {
                        "covered": 0,
                        "missed": 0,
                        "total": 0
                    }
                counters[type_attr]["covered"] += covered
                counters[type_attr]["missed"] += missed
                counters[type_attr]["total"] += total

            # 计算百分比
            coverage_percentages = {}
            for coverage_type, data in counters.items():
                if data["total"] > 0:
                    percentage = round((data["covered"] / data["total"]) * 100, 2)
                else:
                    percentage = 100.0  # 如果总数为0，默认为100%
                coverage_percentages[coverage_type] = {
                    "percentage": percentage,
                    "covered": data["covered"],
                    "missed": data["missed"],
                    "total": data["total"]
                }

            return {
                "overall_coverage": coverage_percentages,
                "counters": counters
            }

        except Exception as e:
            return {"error": f"解析 JaCoCo XML 失败: {str(e)}"}

    def analyze_ios_coverage(self, project_path: str, scheme: str, destination: str = "platform=iOS Simulator,name=iPhone 14") -> Dict[str, Any]:
        """分析 iOS 项目的测试覆盖率 (Xcode built-in)"""
        try:
            project_path = Path(project_path)

            # 检查项目类型
            xcodeproj_files = list(project_path.glob("*.xcodeproj"))
            if not xcodeproj_files:
                return {"error": "未找到 Xcode 项目文件"}

            xcodeproj = xcodeproj_files[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = self.reports_dir / f"ios_coverage_{timestamp}"
            report_dir.mkdir(exist_ok=True)

            # 运行测试并生成覆盖率数据
            cmd = [
                "xcodebuild", "test",
                "-project", str(xcodeproj),
                "-scheme", scheme,
                "-destination", destination,
                "-enableCodeCoverage", "YES"
            ]

            test_result = subprocess.run(cmd, capture_output=True, text=True)
            test_output = test_result.stdout
            test_error = test_result.stderr

            if test_result.returncode != 0:
                return {"error": f"测试执行失败: {test_error}"}

            # 查找代码覆盖率文件 (xcresult bundle)
            xcresult_files = list(project_path.rglob("*.xcresult"))
            if not xcresult_files:
                return {"error": "未找到 Xcode 结果文件"}

            # 获取最新的 xcresult 文件
            xcresult_file = max(xcresult_files, key=lambda f: f.stat().st_mtime)

            # 导出覆盖率报告
            export_cmd = [
                "xcrun", "xccov", "view",
                "--report",
                "--json",
                str(xcresult_file)
            ]

            export_result = subprocess.run(export_cmd, capture_output=True, text=True)
            if export_result.returncode != 0:
                return {"error": f"导出覆盖率数据失败: {export_result.stderr}"}

            try:
                coverage_data = json.loads(export_result.stdout)

                # 计算总体覆盖率
                targets_coverage = {}
                for target in coverage_data.get("targets", []):
                    target_name = target.get("name", "unknown")

                    # 计算目标覆盖率
                    lines_covered = sum(file.get("coveredLines", 0) for file in target.get("files", []))
                    lines_executable = sum(file.get("executableLines", 0) for file in target.get("files", []))

                    if lines_executable > 0:
                        target_percentage = round((lines_covered / lines_executable) * 100, 2)
                    else:
                        target_percentage = 100.0

                    targets_coverage[target_name] = {
                        "percentage": target_percentage,
                        "covered_lines": lines_covered,
                        "executable_lines": lines_executable
                    }

                # 整体统计
                total_lines_covered = sum(t["covered_lines"] for t in targets_coverage.values())
                total_lines_executable = sum(t["executable_lines"] for t in targets_coverage.values())

                overall_percentage = 0.0
                if total_lines_executable > 0:
                    overall_percentage = round((total_lines_covered / total_lines_executable) * 100, 2)

                coverage_summary = {
                    "overall_coverage": overall_percentage,
                    "targets_coverage": targets_coverage,
                    "total_covered_lines": total_lines_covered,
                    "total_executable_lines": total_lines_executable,
                    "total_targets": len(targets_coverage)
                }

                # 保存覆盖率数据
                coverage_json = report_dir / "coverage.json"
                with open(coverage_json, 'w', encoding='utf-8') as f:
                    json.dump({
                        "summary": coverage_summary,
                        "details": coverage_data
                    }, f, ensure_ascii=False, indent=2)

                result = {
                    "platform": "ios",
                    "type": "xcode_builtin",
                    "project_path": str(project_path),
                    "scheme": scheme,
                    "destination": destination,
                    "coverage": coverage_summary,
                    "report_path": str(coverage_json),
                    "timestamp": timestamp
                }

                return result

            except json.JSONDecodeError:
                return {"error": "无法解析 Xcode 覆盖率数据"}

        except Exception as e:
            return {"error": f"分析 iOS 覆盖率失败: {str(e)}"}

    def analyze_web_coverage(self, project_path: str, test_command: str = "npm test", coverage_dir: str = "coverage") -> Dict[str, Any]:
        """分析 Web 项目的测试覆盖率 (Istanbul/nyc)"""
        try:
            project_path = Path(project_path)

            # 检查是否为 Web 项目
            if not (project_path / "package.json").exists():
                return {"error": "不是有效的 Web 项目"}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = self.reports_dir / f"web_coverage_{timestamp}"
            report_dir.mkdir(exist_ok=True)

            # 检查 package.json 中的覆盖率配置
            package_json_path = project_path / "package.json"
            coverage_tool = None
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    pkg = json.load(f)

                # 检查是否使用 nyc 或直接使用 Jest 内置覆盖率
                if 'nyc' in pkg or 'nyc' in pkg.get('scripts', {}).values():
                    coverage_tool = 'nyc'
                elif 'jest' in pkg.get('devDependencies', {}) or 'jest' in pkg.get('dependencies', {}):
                    coverage_tool = 'jest'
                else:
                    # 检查 scripts 中是否有覆盖率相关命令
                    scripts = pkg.get('scripts', {})
                    for script in scripts.values():
                        if 'nyc' in script or 'istanbul' in script or '--coverage' in script:
                            coverage_tool = 'nyc'
                            break
                    if coverage_tool is None:
                        coverage_tool = 'nyc'  # 默认假设使用 nyc
            except:
                coverage_tool = 'nyc'  # 默认

            # 运行测试并生成覆盖率报告
            env = os.environ.copy()
            env['NODE_ENV'] = 'test'

            # 构建覆盖率命令
            if coverage_tool == 'nyc':
                # 如果命令本身不含覆盖率选项，添加覆盖率参数
                coverage_cmd = []
                if '--coverage' not in test_command and 'nyc' not in test_command:
                    coverage_cmd = ['npx', 'nyc', '--reporter=lcov', '--reporter=json', '--all']
                    if test_command.startswith('npm test'):
                        coverage_cmd.extend(['npm', 'test'])
                    elif test_command.startswith('yarn test'):
                        coverage_cmd.extend(['yarn', 'test'])
                    else:
                        coverage_cmd.append(test_command)
                else:
                    coverage_cmd = test_command.split()
            else:  # jest
                if '--coverage' not in test_command:
                    test_command_with_coverage = test_command.replace('test', 'test --coverage')
                else:
                    test_command_with_coverage = test_command
                coverage_cmd = test_command_with_coverage.split()

            # 执行测试并收集覆盖率
            test_result = subprocess.run(coverage_cmd, cwd=project_path,
                                        capture_output=True, text=True, env=env)

            test_output = test_result.stdout
            test_error = test_result.stderr

            if test_result.returncode != 0:
                return {"error": f"测试执行失败: {test_error}"}

            # 查找覆盖率报告文件
            coverage_path = project_path / coverage_dir
            if not coverage_path.exists():
                # 尝试其他常见的覆盖率输出目录
                possible_dirs = ['coverage', 'reports', 'test-results']
                for d in possible_dirs:
                    possible_path = project_path / d
                    if possible_path.exists():
                        coverage_path = possible_path
                        break

            coverage_files = []
            if coverage_path.exists():
                coverage_files = list(coverage_path.rglob("*.json")) + list(coverage_path.rglob("*.lcov"))

            if not coverage_files:
                # 尝试在项目根目录查找
                coverage_files = list(project_path.glob("*coverage*.json")) + list(project_path.glob("lcov.info"))

            if not coverage_files:
                return {"error": "未找到覆盖率报告文件"}

            # 尝试解析覆盖率数据
            coverage_data = None
            for coverage_file in coverage_files:
                try:
                    if coverage_file.suffix == '.json':
                        with open(coverage_file, 'r', encoding='utf-8') as f:
                            coverage_data = json.load(f)
                        break
                    elif coverage_file.suffix == '.info' or coverage_file.name == 'lcov.info':
                        # 解析 lcov 文件
                        coverage_data = self._parse_lcov_file(coverage_file)
                        break
                except:
                    continue

            if not coverage_data:
                return {"error": "无法解析覆盖率数据文件"}

            # 分析覆盖率数据
            if isinstance(coverage_data, dict):
                # 这是 Istanbul/NYC 的 JSON 格式
                summary = self._calculate_istanbul_coverage(coverage_data)
            else:
                # 假设是从 LCOV 解析的数据
                summary = coverage_data  # 这应该已经是计算好的摘要

            # 保存最终的覆盖率报告
            final_report = {
                "summary": summary,
                "raw_data_path": str(coverage_files[0]),
                "tool_used": coverage_tool
            }

            coverage_json = report_dir / "coverage.json"
            with open(coverage_json, 'w', encoding='utf-8') as f:
                json.dump(final_report, f, ensure_ascii=False, indent=2)

            result = {
                "platform": "web",
                "type": "istanbul_nyc",
                "project_path": str(project_path),
                "test_command": test_command,
                "coverage_dir": str(coverage_path),
                "coverage": summary,
                "report_path": str(coverage_json),
                "timestamp": timestamp
            }

            return result

        except Exception as e:
            return {"error": f"分析 Web 覆盖率失败: {str(e)}"}

    def _parse_lcov_file(self, lcov_file: Path) -> Dict[str, Any]:
        """解析 LCOV 覆盖率文件"""
        try:
            with open(lcov_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 简化的 LCOV 解析器
            lines_total = 0
            lines_covered = 0
            functions_total = 0
            functions_covered = 0
            branches_total = 0
            branches_covered = 0

            current_file_totals = {
                'lines': {'found': 0, 'hit': 0},
                'functions': {'found': 0, 'hit': 0},
                'branches': {'found': 0, 'hit': 0}
            }

            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('LF:'):
                    current_file_totals['lines']['found'] += int(line[3:])
                    lines_total += int(line[3:])
                elif line.startswith('LH:'):
                    current_file_totals['lines']['hit'] += int(line[3:])
                    lines_covered += int(line[3:])
                elif line.startswith('FNDA:'):
                    parts = line[5:].split(',')
                    hit_count = int(parts[0])
                    if hit_count > 0:
                        current_file_totals['functions']['hit'] += 1
                        functions_covered += 1
                    functions_total += 1
                elif line.startswith('BRF:'):
                    current_file_totals['branches']['found'] += int(line[4:])
                    branches_total += int(line[4:])
                elif line.startswith('BRH:'):
                    current_file_totals['branches']['hit'] += int(line[4:])
                    branches_covered += int(line[4:])

            # 计算百分比
            lines_percentage = round((lines_covered / lines_total * 100), 2) if lines_total > 0 else 100.0
            functions_percentage = round((functions_covered / functions_total * 100), 2) if functions_total > 0 else 100.0
            branches_percentage = round((branches_covered / branches_total * 100), 2) if branches_total > 0 else 100.0

            return {
                "lines": {
                    "percentage": lines_percentage,
                    "covered": lines_covered,
                    "total": lines_total
                },
                "functions": {
                    "percentage": functions_percentage,
                    "covered": functions_covered,
                    "total": functions_total
                },
                "branches": {
                    "percentage": branches_percentage,
                    "covered": branches_covered,
                    "total": branches_total
                },
                "overall_percentage": round(((lines_covered + functions_covered + branches_covered) /
                                           (lines_total + functions_total + branches_total) * 100), 2) if (lines_total + functions_total + branches_total) > 0 else 100.0
            }

        except Exception as e:
            return {"error": f"解析 LCOV 文件失败: {str(e)}"}

    def _calculate_istanbul_coverage(self, coverage_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算 Istanbul/NYC 覆盖率摘要"""
        try:
            total_statements = 0
            covered_statements = 0
            total_branches = 0
            covered_branches = 0
            total_functions = 0
            covered_functions = 0
            total_lines = 0
            covered_lines = 0

            for file_path, file_data in coverage_data.items():
                if isinstance(file_data, dict) and 'statementMap' in file_data:
                    statements = file_data.get('s', {})
                    statement_map = file_data.get('statementMap', {})

                    total_statements += len(statement_map)
                    covered_statements += sum(1 for hits in statements.values() if hits > 0)

                if isinstance(file_data, dict) and 'fnMap' in file_data:
                    functions = file_data.get('f', {})
                    fn_map = file_data.get('fnMap', {})

                    total_functions += len(fn_map)
                    covered_functions += sum(1 for hits in functions.values() if hits > 0)

                if isinstance(file_data, dict) and 'branchMap' in file_data:
                    branches = file_data.get('b', {})
                    branch_map = file_data.get('branchMap', {})

                    for branch_hits in branches.values():
                        total_branches += len(branch_hits)
                        covered_branches += sum(1 for hits in branch_hits if hits > 0)

                if isinstance(file_data, dict) and 'lineMap' in file_data:
                    lines = file_data.get('l', {})
                    line_map = file_data.get('lineMap', {})

                    total_lines += len(lines)
                    covered_lines += sum(1 for hits in lines.values() if hits > 0)

            # 计算百分比
            statement_pct = round((covered_statements / total_statements * 100), 2) if total_statements > 0 else 100.0
            branch_pct = round((covered_branches / total_branches * 100), 2) if total_branches > 0 else 100.0
            function_pct = round((covered_functions / total_functions * 100), 2) if total_functions > 0 else 100.0
            line_pct = round((covered_lines / total_lines * 100), 2) if total_lines > 0 else 100.0

            return {
                "statements": {
                    "percentage": statement_pct,
                    "covered": covered_statements,
                    "total": total_statements
                },
                "branches": {
                    "percentage": branch_pct,
                    "covered": covered_branches,
                    "total": total_branches
                },
                "functions": {
                    "percentage": function_pct,
                    "covered": covered_functions,
                    "total": total_functions
                },
                "lines": {
                    "percentage": line_pct,
                    "covered": covered_lines,
                    "total": total_lines
                },
                "overall_percentage": round((covered_statements + covered_branches + covered_functions + covered_lines) /
                                          (total_statements + total_branches + total_functions + total_lines) * 100, 2) if (total_statements + total_branches + total_functions + total_lines) > 0 else 100.0
            }

        except Exception as e:
            return {"error": f"计算 Istanbul 覆盖率失败: {str(e)}"}


# 单例实例
_coverage_analyzer_instance = None


def get_coverage_analyzer() -> CoverageAnalyzer:
    """获取覆盖率分析器单例"""
    global _coverage_analyzer_instance
    if _coverage_analyzer_instance is None:
        _coverage_analyzer_instance = CoverageAnalyzer()
    return _coverage_analyzer_instance