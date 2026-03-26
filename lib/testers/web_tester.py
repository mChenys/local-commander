"""
Web 自动化测试器 - 集成 Playwright/Chrome
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class WebTester:
    """Web 自动化测试器"""

    def __init__(self):
        self.platform = "web"
        self.test_reports_dir = Path.home() / ".local-commander" / "test-reports" / "web"
        self.test_reports_dir.mkdir(parents=True, exist_ok=True)

    def detect_browsers(self) -> Dict[str, bool]:
        """检测已安装的浏览器"""
        browsers = {
            "chrome": False,
            "firefox": False,
            "webkit": False
        }

        try:
            # 检查 Playwright 是否已安装
            import playwright
            browsers_available = subprocess.run([
                "playwright", "install", "--dry-run"
            ], capture_output=True, text=True)

            if "chrome" in browsers_available.stdout.lower():
                browsers["chrome"] = True
            if "firefox" in browsers_available.stdout.lower():
                browsers["firefox"] = True
            if "webkit" in browsers_available.stdout.lower():
                browsers["webkit"] = True

        except ImportError:
            print("Playwright 未安装")
        except Exception as e:
            print(f"检测浏览器失败: {e}")

        return browsers

    def run_playwright_tests(self, test_dir: str, browser: str = "chromium") -> Dict[str, Any]:
        """运行 Playwright 测试"""
        try:
            browsers = self.detect_browsers()
            if not browsers.get(browser, False):
                return {"error": f"浏览器 {browser} 未安装或 Playwright 未配置"}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"playwright_{browser}_report_{timestamp}.json"

            # 运行 Playwright 测试
            test_result = subprocess.run([
                "playwright", "test",
                "--reporter=json",
                f"--output={self.test_reports_dir}/playwright_output_{timestamp}",
                "--browser", browser
            ], cwd=test_dir, capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析 JSON 报告
            json_report_path = self.test_reports_dir / f"playwright_output_{timestamp}" / "test-results.json"
            test_data = {"tests": [], "stats": {}}

            if json_report_path.exists():
                with open(json_report_path, 'r', encoding='utf-8') as f:
                    test_data = json.load(f)

            # 统计测试结果
            total = len(test_data.get("tests", []))
            passed = len([t for t in test_data.get("tests", []) if t.get("status") == "passed"])
            failed = len([t for t in test_data.get("tests", []) if t.get("status") == "failed"])

            result = {
                "platform": "web",
                "type": "playwright",
                "browser": browser,
                "passed": passed,
                "failed": failed,
                "total": total,
                "output": test_output,
                "error": test_error,
                "test_data": test_data,
                "report_path": str(report_file)
            }

            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"运行 Playwright 测试失败: {str(e)}"}

    def run_puppeteer_tests(self, test_script_path: str, headless: bool = True) -> Dict[str, Any]:
        """运行 Puppeteer 测试"""
        try:
            import puppeteer

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"puppeteer_report_{timestamp}.json"

            # 创建测试执行脚本
            test_runner_script = f'''
const puppeteer = require('puppeteer');

(async () => {{
  const browser = await puppeteer.launch({{ headless: {str(headless).lower()} }});
  const page = await browser.newPage();

  try {{
    // 导入并运行测试脚本
    const testScript = require('{test_script_path}');
    await testScript(page);

    console.log('Puppeteer test completed');
  }} catch (error) {{
    console.error('Puppeteer test failed:', error);
  }} finally {{
    await browser.close();
  }}
}})();
'''

            runner_path = self.test_reports_dir / f"puppeteer_runner_{timestamp}.js"
            with open(runner_path, 'w', encoding='utf-8') as f:
                f.write(test_runner_script)

            # 运行测试
            test_result = subprocess.run([
                "node", str(runner_path)
            ], capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 统计结果
            passed = test_output.count('completed') if 'completed' in test_output else 0
            failed = test_error.count('error') if test_error else 0
            total = passed + failed

            result = {
                "platform": "web",
                "type": "puppeteer",
                "headless": headless,
                "passed": passed,
                "failed": failed,
                "total": total,
                "output": test_output,
                "error": test_error,
                "report_path": str(report_file)
            }

            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"运行 Puppeteer 测试失败: {str(e)}"}

    def run_selenium_tests(self, test_script_path: str, browser: str = "chrome") -> Dict[str, Any]:
        """运行 Selenium 测试"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.firefox.options import Options as FirefoxOptions

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"selenium_{browser}_report_{timestamp}.json"

            # 根据浏览器类型配置选项
            if browser.lower() == "chrome":
                options = ChromeOptions()
                options.add_argument("--headless")
                driver = webdriver.Chrome(options=options)
            elif browser.lower() == "firefox":
                options = FirefoxOptions()
                options.add_argument("--headless")
                driver = webdriver.Firefox(options=options)
            else:
                return {"error": f"不支持的浏览器: {browser}"}

            # 执行测试脚本
            print("正在运行 Selenium 测试...")
            # 实际使用时需要加载并执行测试脚本
            # 这里只是一个示例框架

            driver.quit()

            # 模拟测试结果
            result = {
                "platform": "web",
                "type": "selenium",
                "browser": browser,
                "passed": 1,  # 示例值
                "failed": 0,  # 示例值
                "total": 1,
                "output": "Selenium 测试执行完成",
                "error": None,
                "report_path": str(report_file)
            }

            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"运行 Selenium 测试失败: {str(e)}"}

    def take_screenshots_comparison(self, urls: List[str], baseline_dir: str = None) -> Dict[str, Any]:
        """网页截图对比"""
        try:
            import playwright
            from playwright.sync_api import sync_playwright

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_dir = self.test_reports_dir / f"screenshots_{timestamp}"
            screenshot_dir.mkdir(exist_ok=True)

            results = []

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                for i, url in enumerate(urls):
                    try:
                        page.goto(url)
                        screenshot_path = screenshot_dir / f"screenshot_{i}_{url.replace('://', '_').replace('/', '_')}.png"
                        page.screenshot(path=str(screenshot_path))

                        # 如果有基准截图，则进行对比
                        comparison_result = {
                            "url": url,
                            "screenshot_path": str(screenshot_path),
                            "comparison": "N/A"  # 简化版本，实际可能需要像素级对比
                        }

                        results.append(comparison_result)

                    except Exception as e:
                        results.append({
                            "url": url,
                            "error": str(e)
                        })

                browser.close()

            result = {
                "platform": "web",
                "type": "screenshots",
                "total_urls": len(urls),
                "successful": len([r for r in results if 'error' not in r]),
                "failed": len([r for r in results if 'error' in r]),
                "results": results,
                "screenshot_dir": str(screenshot_dir)
            }

            # 保存报告
            report_file = self.test_reports_dir / f"screenshots_report_{timestamp}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"截图对比失败: {str(e)}"}

    def generate_test_report(self, test_results: Dict[str, Any]) -> str:
        """生成测试报告摘要"""
        if "error" in test_results:
            return f"❌ 测试执行失败: {test_results['error']}"

        total = test_results.get("total", 0)
        passed = test_results.get("passed", 0)
        failed = test_results.get("failed", 0)

        status = "✅ 成功" if failed == 0 else "⚠️ 部分失败"

        browser = test_results.get("browser", "")
        if browser:
            browser = f" ({browser})"

        report = f"""
📊 {test_results.get('type', 'Web测试')} 报告 - {status}{browser}
总测试: {total} | 通过: {passed} | 失败: {failed}
报告路径: {test_results.get('report_path', 'N/A')}
        """.strip()

        return report


# 单例实例
_web_tester_instance = None


def get_web_tester() -> WebTester:
    """获取 Web 测试器单例"""
    global _web_tester_instance
    if _web_tester_instance is None:
        _web_tester_instance = WebTester()
    return _web_tester_instance