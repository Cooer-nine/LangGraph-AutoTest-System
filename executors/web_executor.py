"""
Web 执行器 — 基于 Playwright 封装浏览器操作，支持多策略元素定位
"""
import os
import time as _time
from pathlib import Path
from typing import Optional, Tuple

from playwright.sync_api import sync_playwright, Page, Browser, Locator, TimeoutError as PwTimeout

from utils.logger import logger
from config.settings import SCREENSHOT_DIR

_VISUAL_LOCATE_TIMEOUT = 10


class WebExecutor:
    """Playwright 浏览器执行器

    定位策略（优先级降级）：
      1. Playwright 语义定位（get_by_role / get_by_text / get_by_placeholder）
      2. DOM 爬取 + 关键词模糊匹配（快速，无需 API）
      3. 视觉模型坐标识别（最慢，仅兜底）
    """

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._base_url: str = ""

    # ── 生命周期 ─────────────────────────────────

    def _ensure_started(self) -> bool:
        if self._page is not None:
            return True
        base_url = os.environ.get("WEB_BASE_URL") or os.environ.get("WEB_CONSOLE_URL", "")
        logger.info("[WebExecutor] 自动启动浏览器...")
        return self.start(base_url=base_url, headless=False)

    def start(self, base_url: str = "", headless: bool = False) -> bool:
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=headless,
                args=["--start-maximized"]
            )
            self._page = self._browser.new_page(viewport={"width": 1920, "height": 1080})
            self._base_url = base_url
            logger.info(f"浏览器已启动 (headless={headless}, base_url={base_url})")
            return True
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            return False

    def stop(self):
        if self._browser:
            self._browser.close()
            logger.info("浏览器已关闭")
        if self._playwright:
            self._playwright.stop()

    @property
    def page(self) -> Optional[Page]:
        return self._page

    # ── 视觉定位兜底 ─────────────────────────────

    def _visual_locate(self, description: str) -> Optional[Tuple[float, float]]:
        if not self._page:
            return None
        try:
            from agent.tools.vision_tool import _vision_analyze
            viewport = self._page.viewport_size or {"width": 1920, "height": 1080}
            vw = viewport["width"]
            vh = viewport["height"]
            from datetime import datetime
            tmp_name = f"_visual_locate_{datetime.now().strftime('%H%M%S_%f')}"
            filepath = SCREENSHOT_DIR / f"{tmp_name}.png"
            filepath.parent.mkdir(parents=True, exist_ok=True)
            self._page.screenshot(path=str(filepath))

            question = (
                f"请在这张网页截图中找到描述为「{description}」的交互元素（输入框、按钮、复选框等）。\n"
                f"截图分辨率：{vw}x{vh} 像素。\n"
                f'请严格按JSON格式回答: {{"found": true/false, "x": 数字, "y": 数字, "width": 数字, "height": 数字}}\n'
                f"(x,y)是元素左上角像素坐标(x范围0~{vw}, y范围0~{vh}), width/height是元素宽高。\n"
                f"找不到返回{{\"found\": false}}"
            )
            logger.info(f"[视觉定位] 询问: {description}")
            result = _vision_analyze(str(filepath), question)
            logger.debug(f"[视觉定位] 返回: {result[:200]}")

            import json
            json_str = result
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                parts = json_str.split("```")
                if len(parts) >= 2:
                    json_str = parts[1]
            data = json.loads(json_str.strip())

            try:
                filepath.unlink()
            except Exception:
                pass

            if not data.get("found"):
                logger.warning(f"[视觉定位] 未找到: {description}")
                return None

            x = float(data["x"]) + float(data["width"]) / 2
            y = float(data["y"]) + float(data["height"]) / 2
            logger.info(f"[视觉定位] 成功: {description} -> ({x:.0f}, {y:.0f})")
            return (x, y)
        except Exception as e:
            logger.warning(f"[视觉定位] 失败: {e}")
            return None

    # ── 元素定位（多策略降级） ────────────────────

    def _locate(self, description: str, timeout: int = 5000) -> Optional[Locator]:
        if not self._page:
            return None
        # 策略1: Playwright 语义定位
        strategies = [
            lambda: self._page.get_by_role("button", name=description),
            lambda: self._page.get_by_role("link", name=description),
            lambda: self._page.get_by_role("textbox", name=description),
            lambda: self._page.get_by_role("combobox", name=description),
            lambda: self._page.get_by_role("checkbox", name=description),
            lambda: self._page.get_by_text(description, exact=True),
            lambda: self._page.get_by_text(description, exact=False),
            lambda: self._page.get_by_placeholder(description),
            lambda: self._page.get_by_label(description),
        ]
        for strategy in strategies:
            try:
                locator = strategy()
                if locator and locator.count() > 0:
                    logger.debug(f"元素定位成功(语义): {description}")
                    return locator
            except Exception:
                continue
        # 策略2: DOM 爬取 + 关键词模糊匹配
        dom_result = self._dom_locate(description)
        if dom_result:
            css = dom_result["css"]
            try:
                locator = self._page.locator(css)
                if locator.count() > 0:
                    logger.info(f"元素定位成功(DOM): {description} -> {css}")
                    return locator
            except Exception:
                pass
        logger.warning(f"元素定位失败: {description}")
        return None

    def _extract_page_elements(self) -> list[dict]:
        """从页面 DOM 提取所有可交互元素及其属性（瞬时，无需 API）"""
        if not self._page:
            return []
        try:
            return self._page.evaluate("""
                () => {
                    const elements = [];
                    const nodes = document.querySelectorAll(
                        'input, textarea, select, button, a, [role="button"], [role="checkbox"], [role="combobox"]'
                    );
                    for (const el of nodes) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        let labelText = '';
                        if (el.labels && el.labels.length > 0)
                            labelText = el.labels[0].textContent.trim();
                        if (!labelText) {
                            const prev = el.previousElementSibling;
                            if (prev && prev.tagName === 'LABEL')
                                labelText = prev.textContent.trim();
                        }
                        if (!labelText) {
                            const next = el.nextElementSibling;
                            if (next && next.tagName === 'LABEL')
                                labelText = next.textContent.trim();
                        }
                        if (!labelText) {
                            // 组件式复选框: 文本在父级的兄弟节点中
                            const parentEl = el.parentElement;
                            if (parentEl) {
                                const parentNext = parentEl.nextElementSibling;
                                if (parentNext)
                                    labelText = parentNext.textContent.trim();
                                if (!labelText) {
                                    const parentPrev = parentEl.previousElementSibling;
                                    if (parentPrev)
                                        labelText = parentPrev.textContent.trim();
                                }
                                // 或是祖辈就是 label
                                if (!labelText) {
                                    const grandParent = parentEl.parentElement;
                                    if (grandParent && grandParent.tagName === 'LABEL')
                                        labelText = grandParent.textContent.trim();
                                }
                            }
                        }
                        // 合并父级+祖辈文本, 确保组件式复选框的文本也能被关键词匹配到
                        const parentOwnText = (el.parentElement?.textContent || '').trim();
                        const grandText = (el.parentElement?.parentElement?.textContent || '').trim();
                        const parentText = (parentOwnText + ' ' + grandText).trim().slice(0, 200);
                        // 提取父级首class, 用于生成组件式复选框/按钮的精确点击选择器
                        let parentClass = '';
                        if (el.parentElement && el.parentElement.className) {
                            parentClass = String(el.parentElement.className).trim().split(/\s+/)[0];
                        }
                        let css = '';
                        if (el.id)
                            css = '#' + CSS.escape(el.id);
                        else if (el.name)
                            css = el.tagName.toLowerCase() + '[name="' + el.name.replace(/"/g, '\\"') + '"]';
                        else if (el.placeholder)
                            css = el.tagName.toLowerCase() + '[placeholder="' + el.placeholder.replace(/"/g, '\\"') + '"]';
                        else if (el.getAttribute('aria-label'))
                            css = el.tagName.toLowerCase() + '[aria-label="' + el.getAttribute('aria-label').replace(/"/g, '\\"') + '"]';
                        else {
                            // 兜底: 基于文本内容生成 Playwright 选择器
                            const elTag = el.tagName.toLowerCase();
                            const ownText = (el.textContent || '').trim().slice(0, 50).replace(/"/g, '\\"');
                            // void 元素 (input/img/br/hr) 不能包含文本, 改用关联 label
                            const isVoid = (elTag === 'input' || elTag === 'img' || elTag === 'br' || elTag === 'hr');
                            if (isVoid && labelText) {
                                // 优先点击父级wrapper, 避免label内链接(如"用户服务协议")拦截点击
                                if (parentClass) {
                                    css = 'span.' + CSS.escape(parentClass);
                                } else {
                                    css = 'label:has-text("' + labelText.replace(/"/g, '\\"').slice(0, 50) + '")';
                                }
                            } else if (ownText) {
                                css = elTag + ':has-text("' + ownText + '")';
                            } else if (labelText) {
                                css = elTag + ':has-text("' + labelText.replace(/"/g, '\\"').slice(0, 50) + '")';
                            }
                        }
                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            type: el.type || '',
                            name: el.name || '',
                            id: el.id || '',
                            placeholder: el.placeholder || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            text: (el.textContent || '').trim().slice(0, 100),
                            label: labelText,
                            parentText: parentText,
                            css: css,
                            className: (el.className?.toString?.() || ''),
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                        });
                    }
                    return elements;
                }
            """)
        except Exception as e:
            logger.warning(f"[DOM爬取] 失败: {e}")
            return []

    def _dom_locate(self, description: str) -> Optional[dict]:
        """通过关键词模糊匹配 DOM 元素属性

        例如 "用户名输入框" → 匹配 placeholder="请输入用户名" / id="username"
        """
        elements = self._extract_page_elements()
        if not elements:
            return None

        # 去掉常见后缀，提取核心关键词
        suffixes = ["输入框", "按钮", "复选框", "下拉框", "选择框", "链接", "文本域"]
        keywords = description
        for s in suffixes:
            keywords = keywords.replace(s, "")
        keywords = keywords.strip()

        # 判断目标元素类型偏好
        is_input = "输入" in description or "密码" in description
        is_button = "按钮" in description
        is_checkbox = "复选框" in description or "勾选" in description or "协议" in description

        best_score = 0
        best_match = None

        for el in elements:
            score = 0
            search_text = " ".join([
                el["placeholder"], el["name"], el["id"], el["ariaLabel"],
                el["label"], el["text"], el["parentText"], el["className"],
            ]).lower()

            kw_lower = keywords.lower()
            if kw_lower in search_text:
                score += 10

            import re
            words = re.split(r"[\s\-_/：:]+", kw_lower)
            for w in words:
                if not w:
                    continue
                if w in search_text:
                    score += 3

            if is_input and el["tag"] in ("input", "textarea"):
                if "密码" in description and el["type"] == "password":
                    score += 20
                if ("验证码" in description or "captcha" in kw_lower) and \
                   ("captcha" in search_text or "验证码" in search_text):
                    score += 20
                score += 5
            if is_button and (el["tag"] in ("button", "a") or el["type"] == "submit"):
                score += 5
            if is_checkbox and el["type"] == "checkbox":
                score += 50  # 复选框操作强优先, 确保不误匹配到label内的链接

            if score > best_score:
                best_score = score
                best_match = el

        if best_match and best_score >= 5 and best_match.get("css"):
            logger.info(f"[DOM匹配] {description} -> {best_match['css']} (score={best_score})")
            return best_match

        return None

    # ── 基础操作 ─────────────────────────────────

    def navigate(self, url: str = "") -> bool:
        if not self._ensure_started() or not self._page:
            return False
        target = url if url.startswith("http") else f"{self._base_url}{url}"
        try:
            self._page.goto(target, wait_until="domcontentloaded")
            logger.info(f"导航到: {target}")
            return True
        except Exception as e:
            logger.error(f"导航失败: {target}, {e}")
            return False

    def click(self, description: str, timeout: int = 3000) -> bool:
        if not self._ensure_started():
            return False
        # 检测是否为复选框/勾选操作
        is_checkbox_op = "复选框" in description or "勾选" in description
        locator = self._locate(description, timeout)
        if locator:
            # 复选框: JS 直接设置 checked=true, 先读状态避免取反已勾选的
            if is_checkbox_op:
                try:
                    result = locator.evaluate("""
                        el => {
                            let cb = el.querySelector('input[type="checkbox"]');
                            if (!cb) {
                                const label = el.closest('label');
                                if (label) cb = label.querySelector('input[type="checkbox"]');
                            }
                            if (!cb) {
                                const all = document.querySelectorAll('input[type="checkbox"]');
                                if (all.length === 1) cb = all[0];
                            }
                            if (!cb || cb.tagName !== 'INPUT' || cb.type !== 'checkbox') return 'not_found';
                            if (cb.checked) return 'already_checked';
                            cb.checked = true;
                            cb.dispatchEvent(new Event('change', {bubbles: true}));
                            cb.dispatchEvent(new Event('input', {bubbles: true}));
                            // 二次确认是否勾选成功
                            return cb.checked ? 'checked' : 'check_failed';
                        }
                    """)
                    if result == 'checked':
                        logger.info(f"勾选(JS): {description}")
                        return True
                    elif result == 'already_checked':
                        logger.info(f"复选框已处于勾选状态, 无需操作: {description}")
                        return True
                    elif result == 'check_failed':
                        logger.warning(f"勾选后状态异常(仍为未勾选): {description}")
                        return False
                    else:
                        logger.warning(f"未找到复选框元素: {description}")
                except Exception as e:
                    logger.warning(f"JS勾选失败, 降级点击: {e}")
            try:
                locator.click(timeout=timeout)
                logger.info(f"点击: {description}")
                return True
            except Exception as e:
                logger.warning(f"语义点击失败: {description}")
        coords = self._visual_locate(description)
        if coords:
            try:
                self._page.mouse.click(coords[0], coords[1])
                logger.info(f"点击(视觉): {description}")
                return True
            except Exception as e:
                logger.error(f"点击失败(视觉): {e}")
        return False

    def input(self, description: str, text: str, timeout: int = 3000) -> bool:
        if not self._ensure_started():
            return False
        locator = self._locate(description, timeout)
        if locator:
            try:
                locator.click(timeout=timeout)
                locator.fill(text, timeout=timeout)
                logger.info(f"输入: {description} <- {text}")
                return True
            except Exception as e:
                logger.warning(f"语义输入失败: {description}")
        coords = self._visual_locate(description)
        if coords:
            try:
                x, y = coords[0], coords[1]
                import json as _json
                text_js = _json.dumps(text)
                js_result = self._page.evaluate(f"""
                    (() => {{
                        const el = document.elementFromPoint({x}, {y});
                        if (!el) return 'no_element';
                        let input = el;
                        if (input.tagName !== 'INPUT' && input.tagName !== 'TEXTAREA') {{
                            input = el.closest('input, textarea');
                        }}
                        if (!input) return 'no_input';
                        input.focus();
                        input.value = {text_js};
                        input.dispatchEvent(new Event('input', {{bubbles: true}}));
                        input.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return 'ok';
                    }})()
                """)
                ok = (js_result == 'ok')
                logger.info(f"输入(视觉JS): {description} <- {text}, js={js_result}")
                return ok
            except Exception as e:
                logger.error(f"输入失败(视觉): {e}")
        return False

    def get_text(self, description: str, timeout: int = 5000) -> tuple[bool, str]:
        locator = self._locate(description, timeout)
        if not locator:
            return False, ""
        try:
            text = locator.text_content() or ""
            return True, text
        except Exception as e:
            return False, str(e)

    def wait(self, description: str, timeout: int = 10000) -> bool:
        if not self._ensure_started():
            return False
        locator = self._locate(description, timeout)
        return locator is not None

    def select(self, description: str, value: str, timeout: int = 5000) -> bool:
        locator = self._locate(description, timeout)
        if not locator:
            return False
        try:
            locator.select_option(value)
            return True
        except Exception as e:
            logger.error(f"选择失败: {e}")
            return False

    def check(self, description: str, expected: str, timeout: int = 5000) -> tuple[bool, str]:
        ok, text = self.get_text(description, timeout)
        if not ok:
            return False, f"元素未找到: {description}"
        return expected in text, text

    def screenshot(self, name: str = None) -> Optional[Path]:
        if not self._ensure_started() or not self._page:
            return None
        from datetime import datetime
        if name is None:
            name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filepath = SCREENSHOT_DIR / f"{name}.png"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._page.screenshot(path=str(filepath))
            return filepath
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None

    def dump_checkbox_dom(self) -> str:
        """诊断工具: 输出页面上所有 checkbox 的外层 DOM 结构"""
        if not self._page:
            return "浏览器未启动"
        try:
            result = self._page.evaluate("""
                () => {
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    const out = [];
                    out.push('=== 页面 checkbox 外层 DOM 结构 ===');
                    out.push('共找到 ' + checkboxes.length + ' 个 checkbox\\n');
                    checkboxes.forEach((cb, i) => {
                        out.push('--- checkbox #' + (i + 1) + ' ---');
                        // input 自身
                        out.push('[input] ' + cb.outerHTML);
                        // 父级
                        if (cb.parentElement)
                            out.push('[parent] ' + cb.parentElement.outerHTML.slice(0, 300));
                        // 祖辈
                        if (cb.parentElement?.parentElement)
                            out.push('[grand] ' + cb.parentElement.parentElement.outerHTML.slice(0, 500));
                        // 曾祖辈
                        if (cb.parentElement?.parentElement?.parentElement)
                            out.push('[great] ' + cb.parentElement.parentElement.parentElement.outerHTML.slice(0, 600));
                        out.push('');
                    });
                    return out.join('\\n');
                }
            """)
            logger.info("[诊断]\n" + result)
            return result
        except Exception as e:
            logger.error(f"诊断失败: {e}")
            return str(e)


web_executor = WebExecutor()
