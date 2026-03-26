"""
Android UI 自动化 - 基于 ADB 的简单方案
无需 Appium，直接使用 adb shell 命令
"""

import subprocess
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import tempfile
import time


class AndroidUIAutomation:
    """Android UI 自动化 (ADB 方案)"""

    def __init__(self, device_serial: str = None):
        self.device_serial = device_serial or self._get_first_device()
        self.temp_dir = Path(tempfile.gettempdir())

    def _get_first_device(self) -> str:
        """获取第一个连接的设备"""
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        for line in result.stdout.strip().split('\n')[1:]:
            if '\tdevice' in line:
                return line.split('\t')[0]
        raise RuntimeError("未检测到连接的 Android 设备")

    def _adb(self, *args) -> str:
        """执行 adb 命令"""
        cmd = ["adb", "-s", self.device_serial] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.stdout.strip()

    def _adb_shell(self, *args) -> str:
        """执行 adb shell 命令"""
        return self._adb("shell", *args)

    # ========== 基础操作 ==========

    def tap(self, x: int, y: int) -> bool:
        """点击屏幕坐标"""
        result = self._adb_shell("input", "tap", str(x), str(y))
        return result == ""

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """滑动"""
        result = self._adb_shell("input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration))
        return result == ""

    def input_text(self, text: str) -> bool:
        """输入文本 (需先点击输入框)"""
        # 转义特殊字符
        text = text.replace(" ", "%s").replace("&", "\\&")
        result = self._adb_shell("input", "text", text)
        return result == ""

    def press_key(self, keycode: str) -> bool:
        """按键事件"""
        # 常用: KEYCODE_HOME=3, KEYCODE_BACK=4, KEYCODE_ENTER=66
        result = self._adb_shell("input", "keyevent", keycode)
        return result == ""

    def back(self) -> bool:
        """返回"""
        return self.press_key("KEYCODE_BACK")

    def home(self) -> bool:
        """回到桌面"""
        return self.press_key("KEYCODE_HOME")

    # ========== 元素定位 ==========

    def dump_ui(self) -> Dict[str, Any]:
        """获取当前界面的 UI 层级"""
        # 导出 UI dump
        self._adb_shell("uiautomator", "dump", "/sdcard/ui.xml")
        # 拉取到本地
        local_path = self.temp_dir / "ui.xml"
        subprocess.run(
            ["adb", "-s", self.device_serial, "pull", "/sdcard/ui.xml", str(local_path)],
            capture_output=True
        )

        if not local_path.exists():
            return {"error": "无法获取 UI dump"}

        # 解析 XML
        tree = ET.parse(local_path)
        root = tree.getroot()

        elements = []
        for node in root.iter():
            if node.tag == "node":
                attrs = node.attrib
                elements.append({
                    "text": attrs.get("text", ""),
                    "content_desc": attrs.get("content-desc", ""),
                    "resource_id": attrs.get("resource-id", ""),
                    "class": attrs.get("class", ""),
                    "package": attrs.get("package", ""),
                    "bounds": attrs.get("bounds", ""),
                    "clickable": attrs.get("clickable", "") == "true",
                    "enabled": attrs.get("enabled", "") == "true",
                    "displayed": attrs.get("displayed", "") == "true",
                })

        return {
            "device": self.device_serial,
            "element_count": len(elements),
            "elements": elements
        }

    def find_element(self, text: str = None, resource_id: str = None,
                     content_desc: str = None, class_name: str = None) -> Optional[Dict]:
        """查找元素"""
        ui = self.dump_ui()
        if "error" in ui:
            return None

        for elem in ui["elements"]:
            match = True
            if text and text not in elem.get("text", ""):
                match = False
            if resource_id and resource_id not in elem.get("resource_id", ""):
                match = False
            if content_desc and content_desc not in elem.get("content_desc", ""):
                match = False
            if class_name and class_name not in elem.get("class", ""):
                match = False
            if match:
                return elem

        return None

    def find_elements(self, text: str = None, resource_id: str = None,
                      content_desc: str = None, class_name: str = None) -> List[Dict]:
        """查找多个元素"""
        ui = self.dump_ui()
        if "error" in ui:
            return []

        results = []
        for elem in ui["elements"]:
            match = True
            if text and text not in elem.get("text", ""):
                match = False
            if resource_id and resource_id not in elem.get("resource_id", ""):
                match = False
            if content_desc and content_desc not in elem.get("content_desc", ""):
                match = False
            if class_name and class_name not in elem.get("class", ""):
                match = False
            if match:
                results.append(elem)

        return results

    def get_element_center(self, bounds: str) -> Tuple[int, int]:
        """从 bounds 字符串提取中心坐标"""
        # bounds 格式: [x1,y1][x2,y2]
        match = re.findall(r'\[(\d+),(\d+)\]', bounds)
        if len(match) >= 2:
            x1, y1 = int(match[0][0]), int(match[0][1])
            x2, y2 = int(match[1][0]), int(match[1][1])
            return ((x1 + x2) // 2, (y1 + y2) // 2)
        return (0, 0)

    # ========== 高级操作 ==========

    def tap_element(self, text: str = None, resource_id: str = None,
                    content_desc: str = None, class_name: str = None) -> bool:
        """点击元素 (通过属性定位)"""
        elem = self.find_element(text, resource_id, content_desc, class_name)
        if not elem:
            print(f"未找到元素: text={text}, id={resource_id}")
            return False

        bounds = elem.get("bounds", "")
        x, y = self.get_element_center(bounds)
        print(f"点击元素: {elem.get('text') or elem.get('resource_id')} at ({x}, {y})")
        return self.tap(x, y)

    def screenshot(self, save_path: str = None) -> str:
        """截图"""
        if save_path is None:
            save_path = str(self.temp_dir / "android_screenshot.png")

        # 截图到设备
        self._adb_shell("screencap", "-p", "/sdcard/screenshot.png")
        # 拉取到本地
        subprocess.run(
            ["adb", "-s", self.device_serial, "pull", "/sdcard/screenshot.png", save_path],
            capture_output=True
        )

        return save_path

    def get_current_activity(self) -> str:
        """获取当前 Activity"""
        result = self._adb_shell("dumpsys", "activity", "activities", "|", "grep", "mResumedActivity")
        # 格式: mResumedActivity: ActivityRecord{xxx u0 com.package/.ActivityName}
        match = re.search(r'([a-z]+\.[a-z]+/[.\w]+)', result)
        if match:
            return match.group(1)
        return result

    def get_current_package(self) -> str:
        """获取当前包名"""
        result = self._adb_shell("dumpsys", "window", "|", "grep", "mCurrentFocus")
        match = re.search(r'([a-z]+\.[a-z]+)', result)
        if match:
            return match.group(1)
        return result

    def start_app(self, package: str, activity: str = None) -> bool:
        """启动应用"""
        if activity:
            cmd = f"am start -n {package}/{activity}"
        else:
            cmd = f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        result = self._adb_shell(cmd)
        return "Error" not in result

    def force_stop(self, package: str) -> bool:
        """强制停止应用"""
        self._adb_shell("am", "force-stop", package)
        return True

    # ========== 测试流程 ==========

    def run_test_sequence(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        运行测试序列

        Args:
            steps: 测试步骤列表
                [{"action": "tap", "element": {"text": "登录"}},
                 {"action": "input", "text": "username"},
                 {"action": "screenshot", "save_path": "/tmp/step1.png"}]

        Returns:
            测试结果
        """
        results = []
        passed = 0
        failed = 0

        for i, step in enumerate(steps):
            action = step.get("action")
            step_result = {"step": i + 1, "action": action, "success": False}

            try:
                if action == "tap":
                    elem = step.get("element", {})
                    success = self.tap_element(**elem)
                    step_result["success"] = success
                    step_result["element"] = elem

                elif action == "tap_coords":
                    x, y = step.get("x"), step.get("y")
                    success = self.tap(x, y)
                    step_result["success"] = success
                    step_result["coords"] = (x, y)

                elif action == "input":
                    text = step.get("text", "")
                    success = self.input_text(text)
                    step_result["success"] = success

                elif action == "swipe":
                    x1, y1 = step.get("x1"), step.get("y1")
                    x2, y2 = step.get("x2"), step.get("y2")
                    success = self.swipe(x1, y1, x2, y2)
                    step_result["success"] = success

                elif action == "back":
                    success = self.back()
                    step_result["success"] = success

                elif action == "screenshot":
                    path = self.screenshot(step.get("save_path"))
                    step_result["success"] = True
                    step_result["screenshot"] = path

                elif action == "wait":
                    time.sleep(step.get("seconds", 1))
                    step_result["success"] = True

                elif action == "assert_element":
                    elem = step.get("element", {})
                    found = self.find_element(**elem) is not None
                    step_result["success"] = found
                    step_result["element"] = elem

                elif action == "start_app":
                    package = step.get("package")
                    activity = step.get("activity")
                    success = self.start_app(package, activity)
                    step_result["success"] = success

                else:
                    step_result["error"] = f"未知操作: {action}"

                # 等待界面稳定
                if step.get("wait_after", 0) > 0:
                    time.sleep(step["wait_after"])
                elif action in ["tap", "tap_coords", "input", "back"]:
                    time.sleep(0.5)  # 默认等待

            except Exception as e:
                step_result["error"] = str(e)

            if step_result["success"]:
                passed += 1
            else:
                failed += 1

            results.append(step_result)

        return {
            "device": self.device_serial,
            "total": len(steps),
            "passed": passed,
            "failed": failed,
            "steps": results
        }

    def interactive_test(self):
        """交互式测试模式"""
        print(f"📱 Android UI 自动化测试 (设备: {self.device_serial})")
        print("命令: tap <text|id>, swipe, input <text>, back, screenshot, dump, quit")

        while True:
            try:
                cmd = input("\n> ").strip().split(maxsplit=1)
                if not cmd:
                    continue

                action = cmd[0].lower()

                if action == "quit":
                    break

                elif action == "tap":
                    if len(cmd) > 1:
                        target = cmd[1]
                        # 尝试作为 text 或 resource_id
                        if target.startswith("id:"):
                            self.tap_element(resource_id=target[3:])
                        else:
                            self.tap_element(text=target)
                    else:
                        print("用法: tap <text> 或 tap id:<resource_id>")

                elif action == "dump":
                    ui = self.dump_ui()
                    print(f"UI 元素数量: {ui.get('element_count', 0)}")
                    # 显示可点击元素
                    clickable = [e for e in ui.get("elements", []) if e.get("clickable") and e.get("text")]
                    for e in clickable[:10]:
                        print(f"  - {e.get('text')} ({e.get('resource_id')})")

                elif action == "screenshot":
                    path = self.screenshot()
                    print(f"截图保存: {path}")

                elif action == "input":
                    if len(cmd) > 1:
                        self.input_text(cmd[1])
                    else:
                        print("用法: input <text>")

                elif action == "back":
                    self.back()
                    print("已返回")

                elif action == "activity":
                    activity = self.get_current_activity()
                    print(f"当前 Activity: {activity}")

                else:
                    print(f"未知命令: {action}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")

        print("\n测试结束")


# CLI 入口
if __name__ == "__main__":
    import sys

    automation = AndroidUIAutomation()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "dump":
            ui = automation.dump_ui()
            print(json.dumps(ui, ensure_ascii=False, indent=2))

        elif cmd == "screenshot":
            path = automation.screenshot(sys.argv[2] if len(sys.argv) > 2 else None)
            print(f"截图: {path}")

        elif cmd == "tap":
            if len(sys.argv) > 2:
                target = sys.argv[2]
                if target.startswith("id:"):
                    automation.tap_element(resource_id=target[3:])
                else:
                    automation.tap_element(text=target)

        elif cmd == "activity":
            print(automation.get_current_activity())

        else:
            print(f"未知命令: {cmd}")
    else:
        automation.interactive_test()
