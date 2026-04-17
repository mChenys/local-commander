"""
Android 混合自动化 - uiautomator2 + VL 视觉模型协同
处理 uiautomator2 无法解决的场景
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import tempfile

# 尝试导入依赖
try:
    import uiautomator2 as u2
    HAS_U2 = True
except ImportError:
    HAS_U2 = False


class AndroidHybridAutomation:
    """Android 混合自动化 - u2 + VL 协同"""

    def __init__(self, device_serial: str = None, vl_service=None):
        self.device_serial = device_serial
        self.temp_dir = Path(tempfile.gettempdir())
        self._d = None
        self._vl_service = vl_service

    @property
    def d(self):
        """懒加载 uiautomator2"""
        if self._d is None:
            if not HAS_U2:
                raise RuntimeError("uiautomator2 未安装")
            self._d = u2.connect(self.device_serial) if self.device_serial else u2.connect()
        return self._d

    def set_vl_service(self, vl_service):
        """设置 VL 视觉服务"""
        self._vl_service = vl_service

    # ========== 协同定位：u2 优先，VL 降级 ==========

    def hybrid_tap(self, keyword: str, timeout: int = 5, use_vl_fallback: bool = True) -> Dict:
        """
        混合点击：优先 u2 定位，失败时降级到 VL 视觉定位

        Args:
            keyword: 搜索关键词
            timeout: u2 等待超时
            use_vl_fallback: 是否使用 VL 降级
        """
        d = self.d

        # 1. 尝试 u2 定位
        selectors = [
            lambda: d(text=keyword),
            lambda: d(textContains=keyword),
            lambda: d(description=keyword),
            lambda: d(descriptionContains=keyword),
            lambda: d(resourceIdContains=keyword),
        ]

        for selector in selectors:
            try:
                elem = selector()
                if elem.wait(timeout=timeout):
                    elem.click()
                    return {"success": True, "method": "u2", "keyword": keyword}
            except:
                continue

        # 2. u2 定位失败，尝试 VL 视觉定位
        if use_vl_fallback and self._vl_service:
            return self._vl_tap(keyword)

        return {"success": False, "method": None, "keyword": keyword, "error": "元素未找到"}

    def _vl_tap(self, keyword: str) -> Dict:
        """使用 VL 视觉模型定位并点击"""
        # 截图
        screenshot_path = str(self.temp_dir / "vl_locate.png")
        self.d.screenshot(screenshot_path)

        # 调用 VL 服务定位
        try:
            result = self._vl_service.detect_element(screenshot_path, keyword)
            if result.get("success") and result.get("center"):
                x, y = result["center"]
                self.d.click(x, y)
                return {"success": True, "method": "vl", "keyword": keyword, "coords": (x, y)}
        except Exception as e:
            return {"success": False, "method": "vl", "keyword": keyword, "error": str(e)}

        return {"success": False, "method": "vl", "keyword": keyword}

    # ========== UI 验证：VL 视觉分析 ==========

    def verify_ui(self, prompt: str, screenshot_path: str = None) -> Dict:
        """
        使用 VL 视觉模型验证 UI

        Args:
            prompt: 验证提示词，如 "页面顶部是否有断网提示"
            screenshot_path: 截图保存路径（可选）

        Returns:
            验证结果
        """
        if not self._vl_service:
            return {"success": False, "error": "VL 服务未配置"}

        # 截图
        if screenshot_path is None:
            screenshot_path = str(self.temp_dir / "verify_ui.png")
        self.d.screenshot(screenshot_path)

        # VL 分析
        try:
            result = self._vl_service.detect_element(screenshot_path, prompt)
            return {
                "success": True,
                "screenshot": screenshot_path,
                "analysis": result.get("description", ""),
                "found": result.get("success", False)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_network_status(self) -> Dict:
        """检查网络状态提示"""
        return self.verify_ui(
            "页面顶部是否有断网提示、网络异常提示、'等待网络'等文字？如果有，描述具体内容。"
        )

    def check_error_dialog(self) -> Dict:
        """检查是否有错误弹窗"""
        return self.verify_ui(
            "页面是否有错误弹窗、警告对话框？如果有，描述弹窗内容和按钮。"
        )

    # ========== OCR：VL 文字识别 ==========

    def ocr_extract(self, region: Tuple[int, int, int, int] = None) -> Dict:
        """
        使用 VL 模型进行 OCR 文字提取

        Args:
            region: 截取区域 (x1, y1, x2, y2)，None 表示全屏
        """
        if not self._vl_service:
            return {"success": False, "error": "VL 服务未配置"}

        # 截图
        screenshot_path = str(self.temp_dir / "ocr.png")
        self.d.screenshot(screenshot_path)

        # VL OCR
        try:
            prompt = "提取这张图片中的所有文字内容，按行排列。"
            if region:
                prompt += f" 只关注区域 {region} 内的文字。"

            result = self._vl_service.detect_element(screenshot_path, prompt)
            return {
                "success": True,
                "text": result.get("description", ""),
                "screenshot": screenshot_path
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== 完整测试流程 ==========

    def run_hybrid_test(self, steps: List[Dict], auto_handle_permissions: bool = True) -> Dict:
        """
        运行混合自动化测试

        Args:
            steps: 测试步骤，支持 hybrid_tap、verify_ui、ocr 等
            auto_handle_permissions: 自动处理权限弹窗
        """
        results = []
        passed = 0
        failed = 0

        for i, step in enumerate(steps):
            action = step.get("action")
            step_result = {"step": i + 1, "action": action, "success": False}

            try:
                # 自动处理权限弹窗
                if auto_handle_permissions:
                    self._handle_permission_if_exists()

                if action == "hybrid_tap":
                    keyword = step.get("keyword", "")
                    result = self.hybrid_tap(keyword, step.get("timeout", 5), step.get("use_vl_fallback", True))
                    step_result["success"] = result["success"]
                    step_result["method"] = result.get("method")

                elif action == "verify_ui":
                    prompt = step.get("prompt", "")
                    result = self.verify_ui(prompt)
                    step_result["success"] = result.get("found", False)
                    step_result["analysis"] = result.get("analysis", "")

                elif action == "check_network":
                    result = self.check_network_status()
                    step_result["success"] = not result.get("found", True)  # 没有断网提示才算成功
                    step_result["analysis"] = result.get("analysis", "")

                elif action == "check_error":
                    result = self.check_error_dialog()
                    step_result["success"] = not result.get("found", True)  # 没有错误弹窗才算成功

                elif action == "ocr":
                    result = self.ocr_extract(step.get("region"))
                    step_result["success"] = result["success"]
                    step_result["text"] = result.get("text", "")

                elif action == "u2_tap":
                    # 纯 u2 操作
                    keyword = step.get("keyword", "")
                    timeout = step.get("timeout", 5)
                    if self.d(text=keyword).wait(timeout=timeout):
                        self.d(text=keyword).click()
                        step_result["success"] = True
                    elif self.d(textContains=keyword).wait(timeout=1):
                        self.d(textContains=keyword).click()
                        step_result["success"] = True

                elif action == "screenshot":
                    path = self.d.screenshot(step.get("save_path", str(self.temp_dir / "step.png")))
                    step_result["success"] = True
                    step_result["path"] = path

                elif action == "wait":
                    time.sleep(step.get("seconds", 1))
                    step_result["success"] = True

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

    def _handle_permission_if_exists(self):
        """自动处理权限弹窗"""
        d = self.d
        allow_texts = ["允许", "Allow", "始终允许", "仅在使用中允许"]

        for text in allow_texts:
            if d(text=text).exists:
                d(text=text).click()
                time.sleep(0.5)
                return True

        # Android 原生权限对话框
        if d(resourceId="com.android.packageinstaller:id/permission_allow_button").exists:
            d(resourceId="com.android.packageinstaller:id/permission_allow_button").click()
            return True

        return False


# CLI 测试
if __name__ == "__main__":
    import sys

    auto = AndroidHybridAutomation()

    print("=== Android 混合自动化测试 ===")
    print("命令: hybrid_tap <keyword>, verify_ui <prompt>, check_network, screenshot, quit")

    while True:
        try:
            cmd = input("\n> ").strip().split(maxsplit=1)
            if not cmd:
                continue

            action = cmd[0].lower()

            if action == "quit":
                break
            elif action == "hybrid_tap":
                result = auto.hybrid_tap(cmd[1] if len(cmd) > 1 else "")
                print(f"结果: {result}")
            elif action == "verify_ui":
                result = auto.verify_ui(cmd[1] if len(cmd) > 1 else "分析页面内容")
                print(f"结果: {result}")
            elif action == "check_network":
                result = auto.check_network_status()
                print(f"网络状态: {result}")
            elif action == "screenshot":
                path = auto.d.screenshot()
                print(f"截图: {path}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"错误: {e}")

    print("\n测试结束")
