"""
Android 增强测试器 - 集成 Robolectric、Instrumentation 等更多测试框架
"""
import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class EnhancedAndroidTester:
    """Android 增强测试器，支持更多测试框架"""

    def __init__(self):
        self.platform = "android"
        self.test_reports_dir = Path.home() / ".local-commander" / "test-reports" / "android"
        self.test_reports_dir.mkdir(parents=True, exist_ok=True)

    def run_robolectric_tests(self, project_path: str) -> Dict[str, Any]:
        """运行 Robolectric 单元测试"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"robolectric_report_{timestamp}.json"

            # 检查是否为 Gradle 项目
            gradle_wrapper = Path(project_path) / "gradlew"
            if gradle_wrapper.exists():
                # 使用 Gradle wrapper 运行 Robolectric 测试
                test_result = subprocess.run([
                    str(gradle_wrapper), "test", "--continue"
                ], cwd=project_path, capture_output=True, text=True)
            else:
                # 使用全局 Gradle 命令
                test_result = subprocess.run([
                    "gradle", "test", "--continue"
                ], cwd=project_path, capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析测试结果
            passed = test_output.count('PASSED') + test_output.count('SUCCESSFUL')
            failed = test_output.count('FAILED') + test_output.count('FAILED.')

            # 更精确的统计方式
            import re
            # 匹配测试统计信息，如 "4 tests completed, 3 failed"
            test_stats = re.findall(r'(\d+) tests?,?\s*(\d+)?\s*(completed|passed|failed|succeeded)', test_output, re.IGNORECASE)
            total = 0
            actual_passed = 0
            actual_failed = 0

            for stat in test_stats:
                if len(stat) >= 3:
                    num = int(stat[0])
                    if 'failed' in stat[2].lower():
                        actual_failed = num
                        total = num
                    elif 'pass' in stat[2].lower() or 'succeed' in stat[2].lower():
                        actual_passed = num
                    elif 'complete' in stat[2].lower():
                        total = num

            # 如果正则表达式未找到结果，使用基本统计
            if total == 0:
                total = passed + failed
                actual_passed = passed
                actual_failed = failed

            result = {
                "platform": "android",
                "type": "robolectric",
                "passed": actual_passed,
                "failed": actual_failed,
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
            return {"error": f"运行 Robolectric 测试失败: {str(e)}"}

    def run_instrumentation_tests(self, package_name: str, test_runner: str = None) -> Dict[str, Any]:
        """运行 Instrumentation 测试"""
        try:
            # 检测连接的设备
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            devices = []
            lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行

            for line in lines:
                if '\t' in line:
                    serial, status = line.split('\t')
                    if status == 'device':
                        devices.append(serial)

            if not devices:
                return {"error": "未检测到连接的 Android 设备"}

            device_serial = devices[0]  # 使用第一个设备
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"instrumentation_report_{timestamp}.json"

            # 构建 instrumentation 命令
            cmd = ["adb", "-s", device_serial, "shell", "am", "instrument", "-w"]

            if test_runner:
                cmd.append(f"{package_name}/{test_runner}")
            else:
                # 默认使用 AndroidJUnitRunner
                cmd.append(f"{package_name}/androidx.test.runner.AndroidJUnitRunner")

            test_result = subprocess.run(cmd, capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析测试结果
            passed = test_output.count('PASS')
            failed = test_output.count('FAIL')
            total = passed + failed

            result = {
                "platform": "android",
                "type": "instrumentation",
                "device": device_serial,
                "package": package_name,
                "runner": test_runner or "androidx.test.runner.AndroidJUnitRunner",
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
            return {"error": f"运行 Instrumentation 测试失败: {str(e)}"}

    def run_uiautomator2_tests(self, project_path: str) -> Dict[str, Any]:
        """运行 UI Automator2 测试"""
        try:
            # 检测连接的设备
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            devices = []
            lines = result.stdout.strip().split('\n')[1:]

            for line in lines:
                if '\t' in line:
                    serial, status = line.split('\t')
                    if status == 'device':
                        devices.append(serial)

            if not devices:
                return {"error": "未检测到连接的 Android 设备"}

            device_serial = devices[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"uiautomator2_report_{timestamp}.json"

            # 确保 UI Automator 测试已构建
            # 如果提供了项目路径，尝试构建测试
            if Path(project_path).exists():
                gradle_wrapper = Path(project_path) / "gradlew"
                if gradle_wrapper.exists():
                    build_result = subprocess.run([
                        str(gradle_wrapper), "assembleAndroidTest"
                    ], cwd=project_path, capture_output=True, text=True)

                    if build_result.returncode != 0:
                        return {"error": f"构建 UI Automator 测试失败: {build_result.stderr}"}

            # 运行 UI Automator2 测试
            test_result = subprocess.run([
                "adb", "-s", device_serial, "shell",
                "uiautomator", "runtest", "all"
            ], capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析测试结果
            passed = test_output.count('PASS')
            failed = test_output.count('FAIL')
            total = passed + failed

            result = {
                "platform": "android",
                "type": "uiautomator2",
                "device": device_serial,
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
            return {"error": f"运行 UI Automator2 测试失败: {str(e)}"}


# 单例实例
_enhanced_android_tester_instance = None


def get_enhanced_android_tester() -> EnhancedAndroidTester:
    """获取增强 Android 测试器单例"""
    global _enhanced_android_tester_instance
    if _enhanced_android_tester_instance is None:
        _enhanced_android_tester_instance = EnhancedAndroidTester()
    return _enhanced_android_tester_instance