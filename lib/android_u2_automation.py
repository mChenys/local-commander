"""
Android UI 自动化 - 基于 uiautomator2 的增强方案
支持系统权限弹窗、Compose UI、智能等待

安装: pip install uiautomator2
初始化: python -m uiautomator2 init  # 在手机上安装 ATX agent
"""

import subprocess
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import tempfile

# 尝试导入 uiautomator2
try:
    import uiautomator2 as u2
    HAS_U2 = True
except ImportError:
    HAS_U2 = False
    print("[WARN] uiautomator2 未安装，部分功能不可用。安装: pip install uiautomator2")


class AndroidU2Automation:
    """Android UI 自动化 (uiautomator2 方案) - 增强版"""

    def __init__(self, device_serial: str = None):
        self.device_serial = device_serial
        self.temp_dir = Path(tempfile.gettempdir())
        self._d = None

    @property
    def d(self):
        """懒加载 uiautomator2 设备"""
        if self._d is None:
            if not HAS_U2:
                raise RuntimeError("uiautomator2 未安装，请先安装: pip install uiautomator2")
            if self.device_serial:
                self._d = u2.connect(self.device_serial)
            else:
                self._d = u2.connect()
            # 获取设备信息
            self._device_info = self._d.info
        return self._d

    def ensure_u2_installed(self) -> bool:
        """确保手机上安装了 ATX agent"""
        if not HAS_U2:
            return False
        try:
            # uiautomator2 会在连接时自动检查并安装
            _ = self.d.info
            return True
        except Exception as e:
            print(f"[ERROR] uiautomator2 初始化失败: {e}")
            print("请手动执行: python -m uiautomator2 init")
            return False

    # ========== 系统权限弹窗处理 ==========

    def handle_permission_dialog(self, action: str = "allow") -> bool:
        """
        处理系统权限弹窗

        Args:
            action: "allow" 允许 | "deny" 拒绝 | "dismiss" 忽略

        Returns:
            是否成功处理
        """
        d = self.d

        # 常见权限弹窗文本
        allow_texts = ["允许", "Allow", "ALLOW", "始终允许", "仅在使用中允许"]
        deny_texts = ["拒绝", "Deny", "DENY", "不允许"]

        try:
            # 检测权限弹窗是否存在
            if d(text="要允许").exists or d(textContains="允许").exists:
                if action == "allow":
                    for text in allow_texts:
                        if d(text=text).exists:
                            d(text=text).click()
                            return True
                    # 尝试点击右侧按钮（通常是允许）
                    bounds = d(textContains="允许").get().info['bounds']
                    d.click(bounds['right'] - 100, (bounds['top'] + bounds['bottom']) // 2)
                    return True
                elif action == "deny":
                    for text in deny_texts:
                        if d(text=text).exists:
                            d(text=text).click()
                            return True

            # 尝试通过 resource-id 定位（Android 原生权限对话框）
            if d(resourceId="com.android.packageinstaller:id/permission_allow_button").exists:
                if action == "allow":
                    d(resourceId="com.android.packageinstaller:id/permission_allow_button").click()
                else:
                    d(resourceId="com.android.packageinstaller:id/permission_deny_button").click()
                return True

            # MIUI / 其他厂商的权限弹窗
            if d(resourceId="com.miui.securitycenter:id/permission_allow_button").exists:
                if action == "allow":
                    d(resourceId="com.miui.securitycenter:id/permission_allow_button").click()
                else:
                    d(resourceId="com.miui.securitycenter:id/permission_deny_button").click()
                return True

        except Exception as e:
            print(f"[WARN] 处理权限弹窗失败: {e}")

        return False

    def wait_and_handle_permission(self, timeout: int = 5, action: str = "allow") -> bool:
        """
        等待并处理权限弹窗

        Args:
            timeout: 等待超时（秒）
            action: "allow" | "deny"
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.handle_permission_dialog(action):
                return True
            time.sleep(0.3)
        return False

    # ========== 增强的元素定位 ==========

    def smart_find(self, keyword: str, timeout: int = 5) -> Optional[object]:
        """
        智能查找元素 - 支持多种选择器

        Args:
            keyword: 搜索关键词
            timeout: 超时时间
        """
        d = self.d

        # 1. 精确文本匹配
        if d(text=keyword).wait(timeout=timeout):
            return d(text=keyword)

        # 2. 包含文本
        if d(textContains=keyword).wait(timeout=1):
            return d(textContains=keyword)

        # 3. content-desc 匹配
        if d(description=keyword).wait(timeout=1):
            return d(description=keyword)

        # 4. descriptionContains
        if d(descriptionContains=keyword).wait(timeout=1):
            return d(descriptionContains=keyword)

        # 5. resource-id 匹配
        if d(resourceIdContains=keyword).wait(timeout=1):
            return d(resourceIdContains=keyword)

        return None

    def smart_tap(self, keyword: str, timeout: int = 5) -> bool:
        """智能点击元素"""
        elem = self.smart_find(keyword, timeout)
        if elem:
            elem.click()
            return True
        return False

    def wait_for_element(self, keyword: str, timeout: int = 10) -> bool:
        """等待元素出现"""
        return self.smart_find(keyword, timeout) is not None

    def wait_for_element_gone(self, keyword: str, timeout: int = 10) -> bool:
        """等待元素消失"""
        d = self.d
        start = time.time()
        while time.time() - start < timeout:
            if not (d(text=keyword).exists or d(textContains=keyword).exists or
                    d(description=keyword).exists or d(descriptionContains=keyword).exists):
                return True
            time.sleep(0.3)
        return False

    # ========== 输入增强 ==========

    def input_text(self, element_keyword: str, text: str, clear_first: bool = True) -> bool:
        """
        在指定元素中输入文本

        Args:
            element_keyword: 元素定位关键词
            text: 要输入的文本
            clear_first: 是否先清空
        """
        elem = self.smart_find(element_keyword)
        if not elem:
            return False

        try:
            if clear_first:
                elem.clear_text()
            elem.set_text(text)
            return True
        except Exception as e:
            # 降级方案：点击后使用 ADB input
            elem.click()
            time.sleep(0.3)
            subprocess.run(["adb", "shell", "input", "text", text.replace(" ", "%s")])
            return True

    # ========== 滚动增强 ==========

    def scroll_to_find(self, keyword: str, direction: str = "down",
                       max_scrolls: int = 5, scrollable: str = None) -> Optional[object]:
        """
        滚动查找元素

        Args:
            keyword: 搜索关键词
            direction: "up" | "down"
            max_scrolls: 最大滚动次数
            scrollable: 可滚动容器定位（可选）
        """
        d = self.d

        # 先检查当前屏幕
        elem = self.smart_find(keyword, timeout=1)
        if elem:
            return elem

        # 获取屏幕尺寸
        info = d.info
        width = info['displayWidth']
        height = info['displayHeight']

        # 滚动参数
        if direction == "down":
            start_y = height * 0.7
            end_y = height * 0.3
        else:
            start_y = height * 0.3
            end_y = height * 0.7

        for i in range(max_scrolls):
            d.swipe(width // 2, start_y, width // 2, end_y, 0.3)
            time.sleep(0.5)

            elem = self.smart_find(keyword, timeout=1)
            if elem:
                return elem

        return None

    def scroll_and_tap(self, keyword: str, direction: str = "down",
                       max_scrolls: int = 5) -> bool:
        """滚动查找并点击元素"""
        elem = self.scroll_to_find(keyword, direction, max_scrolls)
        if elem:
            elem.click()
            return True
        return False

    # ========== 截图和视觉 ==========

    def screenshot(self, save_path: str = None, quality: int = 10) -> str:
        """
        截图

        Args:
            save_path: 保存路径
            quality: 图片质量 1-100
        """
        if save_path is None:
            save_path = str(self.temp_dir / "android_screenshot.png")

        d = self.d
        img = d.screenshot(quality=quality)
        img.save(save_path)
        return save_path

    def get_screen_text(self) -> List[str]:
        """获取当前屏幕所有文本元素"""
        d = self.d
        texts = []

        # 获取所有元素
        for elem in d.dump_hierarchy():
            text = elem.attrib.get('text', '')
            desc = elem.attrib.get('content-desc', '')
            if text:
                texts.append(text)
            if desc and desc != text:
                texts.append(desc)

        return texts

    # ========== 应用管理 ==========

    def start_app(self, package: str, activity: str = None) -> bool:
        """启动应用"""
        d = self.d
        try:
            if activity:
                d.app_start(f"{package}/{activity}")
            else:
                d.app_start(package)
            return True
        except Exception as e:
            # 降级方案
            subprocess.run(["adb", "shell", "monkey", "-p", package,
                          "-c", "android.intent.category.LAUNCHER", "1"])
            return True

    def stop_app(self, package: str) -> bool:
        """停止应用"""
        d = self.d
        d.app_stop(package)
        return True

    def clear_app(self, package: str) -> bool:
        """清除应用数据"""
        d = self.d
        d.app_clear(package)
        return True

    def current_app(self) -> Tuple[str, str]:
        """获取当前运行的应用"""
        d = self.d
        info = d.app_current()
        return info['package'], info.get('activity', '')

    # ========== 增强的测试流程 ==========

    def run_test_sequence(self, steps: List[Dict[str, Any]],
                          auto_handle_permissions: bool = True) -> Dict[str, Any]:
        """
        运行测试序列（带权限自动处理）

        Args:
            steps: 测试步骤
            auto_handle_permissions: 是否自动处理权限弹窗
        """
        results = []
        passed = 0
        failed = 0

        for i, step in enumerate(steps):
            action = step.get("action")
            step_result = {"step": i + 1, "action": action, "success": False}

            try:
                # 处理可能的权限弹窗
                if auto_handle_permissions:
                    self.wait_and_handle_permission(timeout=1)

                if action == "tap":
                    keyword = step.get("keyword", "")
                    success = self.smart_tap(keyword, timeout=step.get("timeout", 5))
                    step_result["success"] = success

                elif action == "scroll_and_tap":
                    keyword = step.get("keyword", "")
                    success = self.scroll_and_tap(keyword, step.get("direction", "down"),
                                                  step.get("max_scrolls", 5))
                    step_result["success"] = success

                elif action == "input":
                    element = step.get("element", "")
                    text = step.get("text", "")
                    success = self.input_text(element, text)
                    step_result["success"] = success

                elif action == "wait":
                    time.sleep(step.get("seconds", 1))
                    step_result["success"] = True

                elif action == "wait_for":
                    keyword = step.get("keyword", "")
                    timeout = step.get("timeout", 10)
                    success = self.wait_for_element(keyword, timeout)
                    step_result["success"] = success

                elif action == "assert_text":
                    keyword = step.get("keyword", "")
                    success = self.wait_for_element(keyword, step.get("timeout", 5))
                    step_result["success"] = success

                elif action == "handle_permission":
                    action_type = step.get("permission_action", "allow")
                    success = self.handle_permission_dialog(action_type)
                    step_result["success"] = success

                elif action == "screenshot":
                    path = self.screenshot(step.get("save_path"))
                    step_result["success"] = True
                    step_result["path"] = path

                elif action == "back":
                    self.d.press("back")
                    step_result["success"] = True

            except Exception as e:
                step_result["error"] = str(e)

            if step_result["success"]:
                passed += 1
            else:
                failed += 1

            results.append(step_result)

        return {
            "total": len(steps),
            "passed": passed,
            "failed": failed,
            "steps": results
        }

    # ========== 调试工具 ==========

    def dump_ui_xml(self, save_path: str = None) -> str:
        """导出 UI XML"""
        if save_path is None:
            save_path = str(self.temp_dir / "ui_dump.xml")

        xml = self.d.dump_hierarchy(pretty=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(xml)

        return save_path

    def interactive_shell(self):
        """交互式测试"""
        print("📱 Android U2 自动化测试")
        print("命令: tap <keyword>, scroll <keyword>, input <text>, screenshot, dump, quit")

        while True:
            try:
                cmd = input("\n> ").strip().split(maxsplit=1)
                if not cmd:
                    continue

                action = cmd[0].lower()

                if action == "quit":
                    break
                elif action == "tap":
                    self.smart_tap(cmd[1] if len(cmd) > 1 else "")
                elif action == "scroll":
                    self.scroll_and_tap(cmd[1] if len(cmd) > 1 else "")
                elif action == "input":
                    self.d.send_keys(cmd[1] if len(cmd) > 1 else "")
                elif action == "screenshot":
                    print(f"截图: {self.screenshot()}")
                elif action == "dump":
                    print(f"UI XML: {self.dump_ui_xml()}")
                elif action == "permission":
                    self.handle_permission_dialog()

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")

        print("\n测试结束")


# CLI 入口
if __name__ == "__main__":
    import sys

    if not HAS_U2:
        print("请先安装 uiautomator2: pip install uiautomator2")
        sys.exit(1)

    auto = AndroidU2Automation()

    # 初始化
    if not auto.ensure_u2_installed():
        print("ATX agent 未安装，正在安装...")
        subprocess.run([sys.executable, "-m", "uiautomator2", "init"])

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "dump":
            print(auto.dump_ui_xml())
        elif cmd == "screenshot":
            print(f"截图: {auto.screenshot(sys.argv[2] if len(sys.argv) > 2 else None)}")
        elif cmd == "tap":
            auto.smart_tap(sys.argv[2] if len(sys.argv) > 2 else "")
        elif cmd == "permission":
            auto.handle_permission_dialog(sys.argv[2] if len(sys.argv) > 2 else "allow")
    else:
        auto.interactive_shell()
