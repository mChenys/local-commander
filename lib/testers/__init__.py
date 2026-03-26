"""
测试器工厂 - 统一管理各平台测试器
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Union
from .android_tester import get_android_tester, AndroidTester
from .ios_tester import get_ios_tester, IOSTester
from .web_tester import get_web_tester, WebTester
# 导入增强测试器
from .android_enhanced_tester import get_enhanced_android_tester, EnhancedAndroidTester
from .ios_enhanced_tester import get_enhanced_ios_tester, EnhancedIOSTester
from .web_enhanced_tester import get_enhanced_web_tester, EnhancedWebTester
# 导入覆盖率分析器
from ..coverage_analyzer import get_coverage_analyzer, CoverageAnalyzer


class TestExecutor:
    """测试执行器 - 协调各平台测试"""

    def __init__(self):
        self.android_tester = get_android_tester()
        self.ios_tester = get_ios_tester()
        self.web_tester = get_web_tester()
        # 添加增强测试器
        self.enhanced_android_tester = get_enhanced_android_tester()
        self.enhanced_ios_tester = get_enhanced_ios_tester()
        self.enhanced_web_tester = get_enhanced_web_tester()
        # 添加覆盖率分析器
        self.coverage_analyzer = get_coverage_analyzer()

    def detect_platform(self, project_path: str) -> str:
        """检测项目平台类型"""
        project_path = Path(project_path)

        # Android 项目特征
        if (project_path / "build.gradle").exists() or (project_path / "build.gradle.kts").exists():
            if list((project_path / "app/src/main/java").glob("**/*.java")) or \
               list((project_path / "app/src/main/kotlin").glob("**/*.kt")):
                return "android"

        # iOS 项目特征
        if list(project_path.glob("*.xcodeproj")) or list(project_path.glob("*.xcworkspace")):
            return "ios"

        # Web 项目特征
        if (project_path / "package.json").exists():
            with open(project_path / "package.json", "r", encoding="utf-8") as f:
                import json
                try:
                    pkg = json.load(f)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    if any(web_framework in deps for web_framework in ["react", "vue", "angular", "svelte"]):
                        return "web"
                except:
                    pass

        # 通过文件扩展名判断
        for root, dirs, files in os.walk(project_path):
            # 排除无关目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'build', 'dist']]

            for file in files:
                if file.endswith('.java') or file.endswith('.kt'):
                    # 检查是否包含 Android 特定内容
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            content = f.read()
                            if 'android.' in content or 'Activity' in content or 'Service' in content:
                                return 'android'
                    except:
                        pass
                elif file.endswith('.swift') or file.endswith('.m'):
                    return 'ios'
                elif file.endswith('.js') or file.endswith('.ts') or file.endswith('.jsx') or file.endswith('.tsx'):
                    return 'web'

        return "unknown"

    def execute_test(self, project_path: str, test_type: str = "auto", **kwargs) -> Dict[str, Any]:
        """执行测试"""
        platform = self.detect_platform(project_path)

        print(f"检测到项目平台: {platform}")

        if platform == "android":
            return self._execute_android_test(test_type, **kwargs)
        elif platform == "ios":
            return self._execute_ios_test(test_type, **kwargs)
        elif platform == "web":
            return self._execute_web_test(test_type, **kwargs)
        else:
            return {"error": f"不支持的平台类型: {platform}"}

    def _execute_android_test(self, test_type: str, **kwargs) -> Dict[str, Any]:
        """执行 Android 测试"""
        if test_type == "auto" or test_type == "espresso":
            apk_path = kwargs.get("apk_path")
            test_apk_path = kwargs.get("test_apk_path")
            if apk_path:
                return self.android_tester.run_espresso_tests(apk_path, test_apk_path)
            else:
                return {"error": "需要提供 APK 路径"}

        elif test_type == "uiautomator":
            test_script_path = kwargs.get("test_script_path")
            if test_script_path:
                return self.android_tester.run_uiautomator_tests(test_script_path)
            else:
                return {"error": "需要提供测试脚本路径"}

        elif test_type == "appium":
            capabilities = kwargs.get("capabilities", {})
            return self.android_tester.run_appium_tests(capabilities)

        elif test_type == "robolectric":
            project_path = kwargs.get("project_path")
            if project_path:
                return self.enhanced_android_tester.run_robolectric_tests(project_path)
            else:
                return {"error": "需要提供项目路径"}

        elif test_type == "instrumentation":
            package_name = kwargs.get("package_name")
            test_runner = kwargs.get("test_runner")
            if package_name:
                return self.enhanced_android_tester.run_instrumentation_tests(package_name, test_runner)
            else:
                return {"error": "需要提供包名"}

        elif test_type == "uiautomator2":
            project_path = kwargs.get("project_path")
            return self.enhanced_android_tester.run_uiautomator2_tests(project_path)

        else:
            return {"error": f"不支持的 Android 测试类型: {test_type}"}

    def _execute_ios_test(self, test_type: str, **kwargs) -> Dict[str, Any]:
        """执行 iOS 测试"""
        if test_type == "auto" or test_type == "xctest":
            app_bundle_path = kwargs.get("app_bundle_path")
            test_bundle_path = kwargs.get("test_bundle_path")
            if app_bundle_path and test_bundle_path:
                return self.ios_tester.run_xctest(app_bundle_path, test_bundle_path)
            else:
                return {"error": "需要提供 App Bundle 和测试 Bundle 路径"}

        elif test_type == "xcuitest":
            app_path = kwargs.get("app_path")
            test_target = kwargs.get("test_target")
            if app_path and test_target:
                test_class = kwargs.get("test_class")
                return self.ios_tester.run_xcuitest(app_path, test_target, test_class)
            else:
                return {"error": "需要提供 App 路径和测试 Target"}

        elif test_type == "kif":
            project_path = kwargs.get("project_path")
            scheme = kwargs.get("scheme")
            destination = kwargs.get("destination")
            if project_path and scheme:
                return self.enhanced_ios_tester.run_kif_tests(project_path, scheme, destination)
            else:
                return {"error": "需要提供项目路径和scheme"}

        elif test_type == "earlgrey":
            project_path = kwargs.get("project_path")
            scheme = kwargs.get("scheme")
            destination = kwargs.get("destination")
            if project_path and scheme:
                return self.enhanced_ios_tester.run_earlgrey_tests(project_path, scheme, destination)
            else:
                return {"error": "需要提供项目路径和scheme"}

        elif test_type == "perf" or test_type == "performance":
            project_path = kwargs.get("project_path")
            scheme = kwargs.get("scheme")
            destination = kwargs.get("destination")
            if project_path and scheme:
                return self.enhanced_ios_tester.run_perf_tests(project_path, scheme, destination)
            else:
                return {"error": "需要提供项目路径和scheme"}

        else:
            return {"error": f"不支持的 iOS 测试类型: {test_type}"}

    def _execute_web_test(self, test_type: str, **kwargs) -> Dict[str, Any]:
        """执行 Web 测试"""
        if test_type == "auto" or test_type == "playwright":
            test_dir = kwargs.get("test_dir", ".")
            browser = kwargs.get("browser", "chromium")
            return self.web_tester.run_playwright_tests(test_dir, browser)

        elif test_type == "puppeteer":
            test_script_path = kwargs.get("test_script_path")
            if test_script_path:
                headless = kwargs.get("headless", True)
                return self.web_tester.run_puppeteer_tests(test_script_path, headless)
            else:
                return {"error": "需要提供测试脚本路径"}

        elif test_type == "selenium":
            test_script_path = kwargs.get("test_script_path")
            browser = kwargs.get("browser", "chrome")
            if test_script_path:
                return self.web_tester.run_selenium_tests(test_script_path, browser)
            else:
                return {"error": "需要提供测试脚本路径"}

        elif test_type == "screenshots":
            urls = kwargs.get("urls", [])
            if urls:
                baseline_dir = kwargs.get("baseline_dir")
                return self.web_tester.take_screenshots_comparison(urls, baseline_dir)
            else:
                return {"error": "需要提供 URL 列表"}

        elif test_type == "cypress":
            project_path = kwargs.get("project_path")
            config_file = kwargs.get("config_file")
            browser = kwargs.get("browser", "chrome")
            if project_path:
                return self.enhanced_web_tester.run_cypress_tests(project_path, config_file, browser)
            else:
                return {"error": "需要提供项目路径"}

        elif test_type == "jest-puppeteer" or test_type == "jest+puppeteer":
            project_path = kwargs.get("project_path")
            test_pattern = kwargs.get("test_pattern", "**/?(*.)+(spec|test).[jt]s?(x)")
            if project_path:
                return self.enhanced_web_tester.run_jest_puppeteer_tests(project_path, test_pattern)
            else:
                return {"error": "需要提供项目路径"}

        elif test_type == "visual-regression" or test_type == "visual_regression":
            project_path = kwargs.get("project_path")
            urls = kwargs.get("urls", [])
            baseline_dir = kwargs.get("baseline_dir")
            threshold = kwargs.get("threshold", 0.01)
            if urls:
                return self.enhanced_web_tester.run_visual_regression_tests(project_path, urls, baseline_dir, threshold)
            else:
                return {"error": "需要提供 URL 列表"}

        else:
            return {"error": f"不支持的 Web 测试类型: {test_type}"}

    def run_coverage_analysis(self, project_path: str, platform: str = "auto", **kwargs) -> Dict[str, Any]:
        """运行覆盖率分析"""
        # 如果平台是 auto，自动检测
        if platform == "auto":
            platform = self.detect_platform(project_path)

        print(f"检测到项目平台: {platform}")

        if platform == "android":
            variant = kwargs.get("variant", "debug")
            return self.coverage_analyzer.analyze_android_coverage(project_path, variant)
        elif platform == "ios":
            scheme = kwargs.get("scheme", "")
            destination = kwargs.get("destination", "platform=iOS Simulator,name=iPhone 14")
            if not scheme:
                return {"error": "iOS 覆盖率分析需要提供 scheme 参数"}
            return self.coverage_analyzer.analyze_ios_coverage(project_path, scheme, destination)
        elif platform == "web":
            test_command = kwargs.get("test_command", "npm test")
            coverage_dir = kwargs.get("coverage_dir", "coverage")
            return self.coverage_analyzer.analyze_web_coverage(project_path, test_command, coverage_dir)
        else:
            return {"error": f"不支持的平台类型: {platform}，无法进行覆盖率分析"}

    def generate_summary_report(self, test_results: Dict[str, Any]) -> str:
        """生成汇总报告"""
        if "error" in test_results:
            return f"❌ 测试执行失败: {test_results['error']}"

        tester_map = {
            "android": self.android_tester,
            "ios": self.ios_tester,
            "web": self.web_tester
        }

        platform = test_results.get("platform", "unknown")
        tester = tester_map.get(platform)

        if tester:
            return tester.generate_test_report(test_results)
        else:
            return f"📊 测试完成 - 平台: {platform}"


# 单例实例
_test_executor_instance = None


def get_test_executor() -> TestExecutor:
    """获取测试执行器单例"""
    global _test_executor_instance
    if _test_executor_instance is None:
        _test_executor_instance = TestExecutor()
    return _test_executor_instance