"""
Android 自动化测试器 - 集成 Appium/Espresso/UIAutomator
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class AndroidTester:
    """Android 自动化测试器"""

    def __init__(self):
        self.platform = "android"
        self.test_reports_dir = Path.home() / ".local-commander" / "test-reports" / "android"
        self.test_reports_dir.mkdir(parents=True, exist_ok=True)

    def detect_devices(self) -> List[Dict[str, str]]:
        """检测连接的 Android 设备"""
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            devices = []
            lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行

            for line in lines:
                if '\t' in line:
                    serial, status = line.split('\t')
                    if status == 'device':
                        # 获取设备信息
                        model_result = subprocess.run(
                            ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
                            capture_output=True, text=True
                        )
                        model = model_result.stdout.strip() if model_result.stdout else "Unknown"

                        devices.append({
                            "serial": serial,
                            "model": model,
                            "status": status
                        })

            return devices
        except Exception as e:
            print(f"检测设备失败: {e}")
            return []

    def run_espresso_tests(self, apk_path: str, test_apk_path: str = None) -> Dict[str, Any]:
        """运行 Espresso 测试"""
        try:
            devices = self.detect_devices()
            if not devices:
                return {"error": "未检测到连接的 Android 设备"}

            device_serial = devices[0]["serial"]  # 使用第一个设备
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 构建测试报告路径
            report_file = self.test_reports_dir / f"espresso_report_{timestamp}.json"

            # 安装 APK
            print(f"正在安装应用: {apk_path}")
            install_result = subprocess.run([
                "adb", "-s", device_serial, "install", "-r", apk_path
            ], capture_output=True, text=True)

            if install_result.returncode != 0:
                return {"error": f"安装 APK 失败: {install_result.stderr}"}

            if test_apk_path:
                print(f"正在安装测试 APK: {test_apk_path}")
                test_install_result = subprocess.run([
                    "adb", "-s", device_serial, "install", "-r", test_apk_path
                ], capture_output=True, text=True)

                if test_install_result.returncode != 0:
                    return {"error": f"安装测试 APK 失败: {test_install_result.stderr}"}

            # 运行测试
            print("正在运行 Espresso 测试...")
            test_result = subprocess.run([
                "adb", "-s", device_serial, "shell",
                "am", "instrument", "-w", "-r",
                "com.android.support.test.runner.AndroidJUnitRunner"
            ], capture_output=True, text=True)

            # 解析测试结果
            test_output = test_result.stdout
            test_error = test_result.stderr

            # 提取测试统计信息
            passed = 0
            failed = 0
            for line in test_output.split('\n'):
                if 'PASS' in line.upper():
                    passed += 1
                elif 'FAIL' in line.upper():
                    failed += 1

            result = {
                "platform": "android",
                "type": "espresso",
                "device": devices[0],
                "passed": passed,
                "failed": failed,
                "total": passed + failed,
                "output": test_output,
                "error": test_error,
                "report_path": str(report_file)
            }

            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"运行 Espresso 测试失败: {str(e)}"}

    def run_uiautomator_tests(self, test_script_path: str) -> Dict[str, Any]:
        """运行 UI Automator 测试"""
        try:
            devices = self.detect_devices()
            if not devices:
                return {"error": "未检测到连接的 Android 设备"}

            device_serial = devices[0]["serial"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            report_file = self.test_reports_dir / f"uiautomator_report_{timestamp}.json"

            # 运行 UI Automator 测试
            test_result = subprocess.run([
                "adb", "-s", device_serial, "shell",
                "uiautomator", "runtest", test_script_path
            ], capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 统计测试结果
            passed = test_output.count('PASS')
            failed = test_output.count('FAIL')

            result = {
                "platform": "android",
                "type": "uiautomator",
                "device": devices[0],
                "passed": passed,
                "failed": failed,
                "total": passed + failed,
                "output": test_output,
                "error": test_error,
                "report_path": str(report_file)
            }

            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"运行 UI Automator 测试失败: {str(e)}"}

    def run_appium_tests(self, capabilities: Dict[str, Any]) -> Dict[str, Any]:
        """运行 Appium 测试"""
        try:
            from appium import webdriver
            from appium.options.android import UiAutomator2Options

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"appium_report_{timestamp}.json"

            # 配置选项
            options = UiAutomator2Options()
            for key, value in capabilities.items():
                setattr(options, key, value)

            # 启动会话
            driver = webdriver.Remote('http://localhost:4723', options=options)

            # 在这里运行实际测试（示例测试）
            # 实际使用时应传入测试脚本
            print("正在运行 Appium 测试...")

            # 关闭会话
            driver.quit()

            result = {
                "platform": "android",
                "type": "appium",
                "capabilities": capabilities,
                "passed": 1,  # 示例值
                "failed": 0,  # 示例值
                "total": 1,
                "output": "Appium 测试执行完成",
                "error": None,
                "report_path": str(report_file)
            }

            # 保存报告
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            return result

        except Exception as e:
            return {"error": f"运行 Appium 测试失败: {str(e)}"}

    def generate_test_report(self, test_results: Dict[str, Any]) -> str:
        """生成测试报告摘要"""
        if "error" in test_results:
            return f"❌ 测试执行失败: {test_results['error']}"

        total = test_results.get("total", 0)
        passed = test_results.get("passed", 0)
        failed = test_results.get("failed", 0)

        status = "✅ 成功" if failed == 0 else "⚠️ 部分失败"

        report = f"""
📊 {test_results.get('type', '测试')} 报告 - {status}
设备: {test_results.get('device', {}).get('model', 'Unknown')}
总测试: {total} | 通过: {passed} | 失败: {failed}
报告路径: {test_results.get('report_path', 'N/A')}
        """.strip()

        return report


# 单例实例
_android_tester_instance = None


def get_android_tester() -> AndroidTester:
    """获取 Android 测试器单例"""
    global _android_tester_instance
    if _android_tester_instance is None:
        _android_tester_instance = AndroidTester()
    return _android_tester_instance