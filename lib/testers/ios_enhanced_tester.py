"""
iOS 增强测试器 - 集成 KIF、EarlGrey 等更多测试框架
"""
import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class EnhancedIOSTester:
    """iOS 增强测试器，支持更多测试框架"""

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

    def run_kif_tests(self, project_path: str, scheme: str, destination: str = None) -> Dict[str, Any]:
        """运行 KIF 测试"""
        try:
            # 检测设备
            simulators = self.detect_simulators()
            devices = self.detect_real_devices()

            target_device = None
            device_destination = None

            if simulators:
                # 选择第一个可用模拟器
                target_device = simulators[0]
                device_destination = f"platform=iOS Simulator,id={target_device['udid']}"
            elif devices:
                # 使用第一个真实设备
                target_device = devices[0]
                device_destination = f"platform=iOS,id={target_device['udid']}"
            else:
                return {"error": "未检测到可用的 iOS 模拟器或设备"}

            # 如果提供了目标，则使用提供的目标
            if destination:
                device_destination = destination

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"kif_report_{timestamp}.json"

            # 运行 KIF 测试
            # 通常使用 xcodebuild 来运行测试
            cmd = [
                "xcodebuild", "test",
                "-project", project_path,
                "-scheme", scheme,
                "-destination", device_destination,
                "-enableCodeCoverage", "YES"
            ]

            test_result = subprocess.run(cmd, capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析测试结果
            passed = test_output.count('PASS') + test_output.count('TEST PASSED')
            failed = test_output.count('FAIL') + test_output.count('TEST FAILED')
            total = passed + failed

            result = {
                "platform": "ios",
                "type": "kif",
                "device": target_device,
                "project": project_path,
                "scheme": scheme,
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
            return {"error": f"运行 KIF 测试失败: {str(e)}"}

    def run_earlgrey_tests(self, project_path: str, scheme: str, destination: str = None) -> Dict[str, Any]:
        """运行 EarlGrey 测试"""
        try:
            # 检测设备
            simulators = self.detect_simulators()
            devices = self.detect_real_devices()

            target_device = None
            device_destination = None

            if simulators:
                # 选择第一个可用模拟器
                target_device = simulators[0]
                device_destination = f"platform=iOS Simulator,id={target_device['udid']}"
            elif devices:
                # 使用第一个真实设备
                target_device = devices[0]
                device_destination = f"platform=iOS,id={target_device['udid']}"
            else:
                return {"error": "未检测到可用的 iOS 模拟器或设备"}

            # 如果提供了目标，则使用提供的目标
            if destination:
                device_destination = destination

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"earlgrey_report_{timestamp}.json"

            # 运行 EarlGrey 测试
            # EarlGrey 使用标准的 Xcode 测试命令
            cmd = [
                "xcodebuild", "test",
                "-project", project_path,
                "-scheme", scheme,
                "-destination", device_destination,
                "-enableCodeCoverage", "YES"
            ]

            test_result = subprocess.run(cmd, capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析测试结果
            passed = test_output.count('PASSED') + test_output.count('EXECUTED')
            failed = test_output.count('FAILED')
            total = passed + failed

            result = {
                "platform": "ios",
                "type": "earlgrey",
                "device": target_device,
                "project": project_path,
                "scheme": scheme,
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
            return {"error": f"运行 EarlGrey 测试失败: {str(e)}"}

    def run_perf_tests(self, project_path: str, scheme: str, destination: str = None) -> Dict[str, Any]:
        """运行性能测试"""
        try:
            # 检测设备
            simulators = self.detect_simulators()
            devices = self.detect_real_devices()

            target_device = None
            device_destination = None

            if simulators:
                # 选择第一个可用模拟器
                target_device = simulators[0]
                device_destination = f"platform=iOS Simulator,id={target_device['udid']}"
            elif devices:
                # 使用第一个真实设备
                target_device = devices[0]
                device_destination = f"platform=iOS,id={target_device['udid']}"
            else:
                return {"error": "未检测到可用的 iOS 模拟器或设备"}

            # 如果提供了目标，则使用提供的目标
            if destination:
                device_destination = destination

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.test_reports_dir / f"perf_report_{timestamp}.json"

            # 运行性能测试
            cmd = [
                "xcodebuild", "test",
                "-project", project_path,
                "-scheme", scheme,
                "-destination", device_destination,
                "-enableCodeCoverage", "NO"
            ]

            test_result = subprocess.run(cmd, capture_output=True, text=True)

            test_output = test_result.stdout
            test_error = test_result.stderr

            # 解析性能测试结果
            # 查找性能测试相关的标记
            perf_tests = test_output.count('measured')
            passed = test_output.count('measured')  # 性能测试通常以 measured 为标记
            failed = test_output.count('regressed')  # 性能回退
            total = perf_tests

            result = {
                "platform": "ios",
                "type": "performance",
                "device": target_device,
                "project": project_path,
                "scheme": scheme,
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
            return {"error": f"运行性能测试失败: {str(e)}"}


# 单例实例
_enhanced_ios_tester_instance = None


def get_enhanced_ios_tester() -> EnhancedIOSTester:
    """获取增强 iOS 测试器单例"""
    global _enhanced_ios_tester_instance
    if _enhanced_ios_tester_instance is None:
        _enhanced_ios_tester_instance = EnhancedIOSTester()
    return _enhanced_ios_tester_instance