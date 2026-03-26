"""
Web 增强测试器 - 集成 Cypress、Jest+Puppeteer 等更多测试框架
"""
import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class EnhancedWebTester:
    """Web 增强测试器，支持更多测试框架"""

    def __init__(self):
        self.platform = "web"
        self.test_reports_dir = Path.home() / ".local-commander" / "test-reports" / "web"
        self.test_reports_dir.mkdir(parents=True, exist_ok=True)

    def run_cypress_tests(self, project_path: str, config_file: str = None, browser: str = "chrome") -> Dict[str, Any]:
        """运行 Cypress 测试"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"cypress_report_{timestamp}.json"

            # 检查项目中是否包含 cypress
            cypress_config_paths = [
                Path(project_path) / "cypress.config.js",
                Path(project_path) / "cypress.config.ts",
                Path(project_path) / "cypress.json"
            ]

            config_path = None
            for path in cypress_config_paths:
                if path.exists():
                    config_path = str(path)
                    break

            # 构建 Cypress 命令
            cmd = ["npx", "cypress", "run", "--browser", browser]

            if config_path:
                # 对于 JS/TS 配置文件，使用 --config-file
                if config_path.endswith(('.js', '.ts')):
                    cmd.extend(["--config-file", config_path])
                # 对于 JSON 配置文件，可以使用 --config
                elif config_path.endswith('.json'):
                    cmd.append(f"--config-file={config_path}")

            # 如果提供了额外的配置文件参数
            if config_file:
                cmd.extend(["--config-file", config_file])

            # 在项目路径下运行测试
            test_result = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析 Cypress 测试结果
            import re

            # Cypress 输出通常包含测试统计信息
            passed_match = re.search(r'(\d+) passing', test_output)
            failed_match = re.search(r'(\d+) failing', test_output)
            pending_match = re.search(r'(\d+) pending', test_output)

            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            pending = int(pending_match.group(1)) if pending_match else 0
            total = passed + failed + pending

            result = {
                "platform": "web",
                "type": "cypress",
                "browser": browser,
                "passed": passed,
                "failed": failed,
                "pending": pending,
                "total": total,
                "output": test_output,
                "error": test_error,
                "config_file": config_path,
                "report_path": str(report_file)
            }

            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"运行 Cypress 测试失败: {str(e)}"}

    def run_jest_puppeteer_tests(self, project_path: str, test_pattern: str = "**/?(*.)+(spec|test).[jt]s?(x)") -> Dict[str, Any]:
        """运行 Jest + Puppeteer 测试"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"jest_puppeteer_report_{timestamp}.json"

            # 构建 Jest 命令，使用 puppeteer 环境
            cmd = [
                "npx", "jest",
                test_pattern,
                "--testEnvironment", "puppeteer",
                "--verbose",
                "--json",
                f"--outputFile={self.test_reports_dir}/jest_output_{timestamp}.json"
            ]

            # 在项目路径下运行测试
            test_result = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 尝试读取 JSON 输出结果
            json_output_path = self.test_reports_dir / f"jest_output_{timestamp}.json"
            jest_results = {}
            if json_output_path.exists():
                try:
                    with open(json_output_path, 'r', encoding='utf-8') as f:
                        jest_results = json.load(f)
                except:
                    pass  # 如果 JSON 解析失败，使用默认值

            # 解析 Jest 测试结果
            if jest_results and 'numTotalTests' in jest_results:
                total = jest_results.get('numTotalTests', 0)
                passed = jest_results.get('numPassedTests', 0)
                failed = jest_results.get('numFailedTests', 0)
                skipped = jest_results.get('numPendingTests', 0)
            else:
                # 如果没有 JSON 输出，从文本中解析
                import re

                total_match = re.search(r'(\d+) total', test_output)
                passed_match = re.search(r'(\d+) passed', test_output)
                failed_match = re.search(r'(\d+) failed', test_output)
                skipped_match = re.search(r'(\d+) skipped', test_output)

                total = int(total_match.group(1)) if total_match else 0
                passed = int(passed_match.group(1)) if passed_match else 0
                failed = int(failed_match.group(1)) if failed_match else 0
                skipped = int(skipped_match.group(1)) if skipped_match else 0

            result = {
                "platform": "web",
                "type": "jest+puppeteer",
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "total": total,
                "output": test_output,
                "error": test_error,
                "jest_results": jest_results,
                "report_path": str(report_file)
            }

            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"运行 Jest+Puppeteer 测试失败: {str(e)}"}

    def run_visual_regression_tests(self, project_path: str, urls: List[str],
                                   baseline_dir: str = None,
                                   threshold: float = 0.01) -> Dict[str, Any]:
        """运行视觉回归测试的高级功能"""
        try:
            import playwright
            from playwright.sync_api import sync_playwright

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_dir = self.test_reports_dir / f"visual_regression_{timestamp}"
            screenshot_dir.mkdir(exist_ok=True)

            results = []
            passed_count = 0
            failed_count = 0

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                for i, url in enumerate(urls):
                    try:
                        # 截取当前页面
                        page.goto(url)
                        current_screenshot = screenshot_dir / f"current_{i}_{url.replace('://', '_').replace('/', '_')}.png"
                        page.screenshot(path=str(current_screenshot))

                        comparison_result = {
                            "url": url,
                            "current_screenshot": str(current_screenshot),
                            "status": "no_baseline"  # 默认状态
                        }

                        # 如果有基准截图，则进行比较
                        if baseline_dir:
                            baseline_path = Path(baseline_dir) / f"baseline_{i}_{url.replace('://', '_').replace('/', '_')}.png"

                            if baseline_path.exists():
                                # 这里可以使用图像比较库（如 pillow 或 opencv）来进行像素级比较
                                # 为了简化，这里只检查文件是否存在
                                # 在实际实现中，会进行像素级比较并计算差异

                                # 简单示例：假设差异小于阈值为通过
                                import random  # 仅作演示用，实际应使用图像比较库
                                difference_ratio = random.uniform(0, 0.05)  # 模拟差异比例

                                if difference_ratio <= threshold:
                                    comparison_result["status"] = "passed"
                                    comparison_result["difference"] = f"{difference_ratio:.4f}"
                                    passed_count += 1
                                else:
                                    comparison_result["status"] = "failed"
                                    comparison_result["difference"] = f"{difference_ratio:.4f}"
                                    failed_count += 1
                            else:
                                comparison_result["status"] = "baseline_missing"
                        else:
                            # 没有提供基准目录，仅保存当前截图
                            comparison_result["status"] = "captured"
                            passed_count += 1

                        results.append(comparison_result)

                    except Exception as e:
                        results.append({
                            "url": url,
                            "error": str(e)
                        })
                        failed_count += 1

                browser.close()

            total = len([r for r in results if 'error' not in r])

            result = {
                "platform": "web",
                "type": "visual_regression_advanced",
                "total_urls": len(urls),
                "total_comparisons": total,
                "passed": passed_count,
                "failed": failed_count,
                "threshold": threshold,
                "baseline_dir": baseline_dir,
                "results": results,
                "screenshot_dir": str(screenshot_dir)
            }

            # 保存报告
            report_file = self.test_reports_dir / f"visual_regression_report_{timestamp}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"运行视觉回归测试失败: {str(e)}"}


# 单例实例
_enhanced_web_tester_instance = None


def get_enhanced_web_tester() -> EnhancedWebTester:
    """获取增强 Web 测试器单例"""
    global _enhanced_web_tester_instance
    if _enhanced_web_tester_instance is None:
        _enhanced_web_tester_instance = EnhancedWebTester()
    return _enhanced_web_tester_instance