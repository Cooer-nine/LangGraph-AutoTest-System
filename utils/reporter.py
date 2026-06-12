"""测试报告生成器 — V1 版

生成自包含的 HTML 报告，截图以 base64 嵌入，无需外部依赖即可查看。
"""
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import REPORT_DIR, SCREENSHOT_DIR
from utils.logger import logger


def _img_to_base64(path: Path) -> Optional[str]:
    """将图片转为 base64 内嵌字符串"""
    if not path or not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def generate_html_report(
    title: str,
    step_results: list[dict],
    passed: bool,
    duration_s: float = 0,
) -> Path:
    """生成自包含 HTML 测试报告

    Args:
        title: 测试用例标题
        step_results: 每个步骤的 {description, tool, passed, result, screenshot}
        passed: 整体是否通过
        duration_s: 执行耗时（秒）

    Returns:
        报告文件路径
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in "_-" else "_" for c in title)[:40]
    report_path = REPORT_DIR / f"report_{safe_title}_{timestamp}.html"

    total = len(step_results)
    passed_count = sum(1 for s in step_results if s.get("passed"))

    # 构建步骤 HTML
    steps_html = ""
    for i, step in enumerate(step_results, 1):
        ok = step.get("passed", False)
        desc = step.get("description", step.get("tool", "?"))
        tool = step.get("tool", "")
        result_text = step.get("result", "")
        screenshot_path = step.get("screenshot")

        status_class = "pass" if ok else "fail"
        status_text = "✓ 通过" if ok else "✗ 失败"

        # 截图嵌入
        screenshot_html = ""
        if screenshot_path:
            sp = Path(screenshot_path)
            b64 = _img_to_base64(sp)
            if b64:
                screenshot_html = f"""
                <div class="screenshot">
                    <div class="screenshot-label">📸 截图: {sp.name}</div>
                    <img src="data:image/png;base64,{b64}" alt="步骤{i}截图" />
                </div>"""
            else:
                screenshot_html = f'<div class="screenshot-missing">⚠ 截图不可用: {screenshot_path}</div>'

        steps_html += f"""
        <div class="step {status_class}">
            <div class="step-header">
                <span class="step-num">步骤 {i}</span>
                <span class="step-status">{status_text}</span>
                <span class="step-tool">[{tool}]</span>
            </div>
            <div class="step-desc">{desc}</div>
            <div class="step-result">{result_text}</div>
            {screenshot_html}
        </div>"""

    summary_class = "pass" if passed else "fail"
    summary_text = "✅ 全部通过" if passed else "❌ 存在失败"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - 测试报告</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #f5f6fa; color: #333; padding: 20px; }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    .header {{ background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .header h1 {{ font-size: 20px; margin-bottom: 12px; }}
    .header .meta {{ color: #888; font-size: 13px; display: flex; gap: 24px; flex-wrap: wrap; }}
    .summary {{ display: inline-block; padding: 4px 16px; border-radius: 20px; font-size: 14px; font-weight: 600; }}
    .summary.pass {{ background: #e8f5e9; color: #2e7d32; }}
    .summary.fail {{ background: #fbe9e7; color: #c62828; }}
    .stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
    .stat {{ background: #fff; border-radius: 8px; padding: 16px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; flex: 1; }}
    .stat .num {{ font-size: 28px; font-weight: 700; }}
    .stat .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
    .stat.pass .num {{ color: #2e7d32; }}
    .stat.fail .num {{ color: #c62828; }}
    .step {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #e0e0e0; }}
    .step.pass {{ border-left-color: #4caf50; }}
    .step.fail {{ border-left-color: #f44336; }}
    .step-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
    .step-num {{ font-weight: 700; font-size: 14px; }}
    .step-status {{ font-size: 13px; }}
    .step.pass .step-status {{ color: #2e7d32; }}
    .step.fail .step-status {{ color: #c62828; }}
    .step-tool {{ color: #888; font-size: 12px; background: #f0f0f0; padding: 2px 8px; border-radius: 4px; }}
    .step-desc {{ font-size: 14px; margin-bottom: 6px; }}
    .step-result {{ color: #666; font-size: 13px; }}
    .screenshot {{ margin-top: 12px; }}
    .screenshot-label {{ font-size: 12px; color: #888; margin-bottom: 6px; }}
    .screenshot img {{ max-width: 100%; border: 1px solid #e0e0e0; border-radius: 4px; }}
    .screenshot-missing {{ color: #e65100; font-size: 12px; }}
    .footer {{ text-align: center; margin-top: 20px; color: #aaa; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{title}</h1>
        <div class="meta">
            <span>🕐 {now}</span>
            <span>⏱ 耗时: {duration_s:.1f}s</span>
            <span class="summary {summary_class}">{summary_text}</span>
        </div>
    </div>

    <div class="stats">
        <div class="stat">
            <div class="num">{total}</div>
            <div class="label">总步骤</div>
        </div>
        <div class="stat pass">
            <div class="num">{passed_count}</div>
            <div class="label">通过</div>
        </div>
        <div class="stat fail">
            <div class="num">{total - passed_count}</div>
            <div class="label">失败</div>
        </div>
    </div>

    {steps_html}

    <div class="footer">
        IoT NAC 自动化测试系统 · 报告自动生成于 {now}
    </div>
</div>
</body>
</html>"""

    report_path.write_text(html, encoding="utf-8")
    logger.info(f"📄 测试报告已生成: {report_path}")
    return report_path


def print_console_summary(title: str, step_results: list[dict], passed: bool, duration_s: float = 0):
    """控制台打印测试摘要"""
    total = len(step_results)
    passed_count = sum(1 for s in step_results if s.get("passed"))

    border = "=" * 56
    logger.info("")
    logger.info(border)
    logger.info(f"  测试用例: {title}")
    logger.info(f"  结    果: {'✓ 通过' if passed else '✗ 失败'}")
    logger.info(f"  步    骤: {passed_count}/{total} 通过")
    logger.info(f"  耗    时: {duration_s:.1f}s")
    logger.info(border)

    for i, step in enumerate(step_results, 1):
        ok = step.get("passed", False)
        status = "✓" if ok else "✗"
        desc = step.get("description", step.get("tool", "?"))
        result = step.get("result", "")
        logger.info(f"  {status} 步骤{i}: {desc}")
        if not ok and result:
            logger.info(f"       原因: {result}")
        ss = step.get("screenshot")
        if ss:
            logger.info(f"       截图: {ss}")

    logger.info(border)
