"""
iOS 自动化测试器 - 集成 XCUITest/Simulator
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class IOSTester:
    """iOS 自动化测试器"""

    def __init__(self):
        self.platform = "ios"
        self.test_reports_dir = Path.home() / ".local-commander" / "test-reports" / "ios"
        self.test_reports_dir.mkdir(parents=True, exist_ok=True)

    def detect_simulators(self) -> List[Dict[str, str]]:
        """检测可用的 iOS 模拟器"""
        try:
            result = subprocess.run([
                "xcrun", "simctl", "list", "devices", "available"
            ], capture_output=True, text=True)

            simulators = []
            lines = result.stdout.strip().split('\n')

            for line in lines:
                if '(' in line and ')' in line:
                    # 解析模拟器信息
                    # 格式: iPhone 14 (ABCDEF12-1234-ABCD-EFGH-123456789ABC) (Booted)
                    line = line.strip()
                    if line.startswith('iPhone') or line.startswith('iPad') or line.startswith('Apple Watch') or line.startswith('Apple TV'):
                        name_and_udid = line.split('(')
                        if len(name_and_udid) >= 2:
                            name = name_and_udid[0].strip()
                            udid_part = name_and_udid[1].split(')')
                            if len(udid_part) >= 1:
                                udid = udid_part[0].strip()
                                status = "Shutdown"
                                if "(Booted)" in line:
                                    status = "Booted"

                                simulators.append({
                                    "name": name,
                                    "udid": udid,
                                    "status": status
                                })

            return simulators
        except Exception as e:
            print(f"检测模拟器失败: {e}")
            return []

    def detect_real_devices(self) -> List[Dict[str, str]]:
        """检测连接的真实 iOS 设备"""
        try:
            result = subprocess.run([
                "idevice_id", "-l"
            ], capture_output=True, text=True)

            devices = []
            udids = result.stdout.strip().split('\n')

            for udid in udids:
                if udid.strip():
                    # 获取设备信息
                    try:
                        name_result = subprocess.run([
                            "ideviceinfo", "-u", udid.strip(), "-k", "DeviceName"
                        ], capture_output=True, text=True)

                        model_result = subprocess.run([
                            "ideviceinfo", "-u", udid.strip(), "-k", "ProductType"
                        ], capture_output=True, text=True)

                        devices.append({
                            "udid": udid.strip(),
                            "name": name_result.stdout.strip() if name_result.stdout else "Unknown",
                            "model": model_result.stdout.strip() if model_result.stdout else "Unknown Device",
                            "type": "real"
                        })
                    except:
                        devices.append({
                            "udid": udid.strip(),
                            "name": "Unknown",
                            "model": "Unknown Device",
                            "type": "real"
                        })

            return devices
        except:
            # idevice_id 未安装的情况
            return []

    def run_xctest(self, app_bundle_path: str, test_bundle_path: str) -> Dict[str, Any]:
        """运行 XCUnitTest"""
        try:
            # 检测设备（优先使用模拟器）
            simulators = self.detect_simulators()
            devices = self.detect_real_devices()

            target_device = None
            device_udid = None

            if simulators:
                # 选择第一个可用模拟器
                target_device = simulators[0]
                device_udid = target_device["udid"]
            elif devices:
                # 使用第一个真实设备
                target_device = devices[0]
                device_udid = target_device["udid"]
            else:
                return {"error": "未检测到可用的 iOS 模拟器或设备"}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"xctest_report_{timestamp}.json"

            # 构建测试命令
            if target_device.get("type") == "real":
                # 真实设备测试
                test_result = subprocess.run([
                    "xcodebuild", "test-without-building",
                    "-destination", f"id={device_udid}",
                    "-xctestrun", test_bundle_path
                ], capture_output=True, text=True)
            else:
                # 模拟器测试
                # 启动模拟器
                subprocess.run([
                    "xcrun", "simctl", "boot", device_udid
                ], capture_output=True)

                test_result = subprocess.run([
                    "xcodebuild", "test-without-building",
                    "-destination", f"platform=iOS Simulator,id={device_udid}",
                    "-xctestrun", test_bundle_path
                ], capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析测试结果
            passed = test_output.count('PASS')
            failed = test_output.count('FAIL')
            total = passed + failed

            result = {
                "platform": "ios",
                "type": "xctest",
                "device": target_device,
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
            return {"error": f"运行 XCUnitTest 失败: {str(e)}"}

    def run_xcuitest(self, app_path: str, test_target: str, test_class: str = None) -> Dict[str, Any]:
        """运行 XCUITest"""
        try:
            simulators = self.detect_simulators()
            devices = self.detect_real_devices()

            target_device = None
            device_udid = None

            if simulators:
                target_device = simulators[0]
                device_udid = target_device["udid"]
            elif devices:
                target_device = devices[0]
                device_udid = target_device["udid"]
            else:
                return {"error": "未检测到可用的 iOS 模拟器或设备"}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"xcuitest_report_{timestamp}.json"

            # 启动模拟器
            if target_device.get("type") != "real":
                subprocess.run([
                    "xcrun", "simctl", "boot", device_udid
                ], capture_output=True)

            # 构建测试命令
            cmd = [
                "xcodebuild", "test",
                "-project", app_path,
                "-scheme", test_target,
                "-destination", f"platform=iOS Simulator,id={device_udid}"
            ]

            if test_class:
                cmd.extend(["-only-testing", test_class])

            test_result = subprocess.run(cmd, capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析测试结果
            passed = test_output.count('PASS')
            failed = test_output.count('FAIL')
            total = passed + failed

            result = {
                "platform": "ios",
                "type": "xcuitest",
                "device": target_device,
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
            return {"error": f"运行 XCUITest 失败: {str(e)}"}

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
设备: {test_results.get('device', {}).get('name', 'Unknown')}
总测试: {total} | 通过: {passed} | 失败: {failed}
报告路径: {test_results.get('report_path', 'N/A')}
        """.strip()

        return report


# 单例实例
_ios_tester_instance = None


def get_ios_tester() -> IOSTester:
    """获取 iOS 测试器单例"""
    global _ios_tester_instance
    if _ios_tester_instance is None:
        _ios_tester_instance = IOSTester()
    return _ios_tester_instance