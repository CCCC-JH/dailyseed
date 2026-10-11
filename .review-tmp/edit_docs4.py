# -*- coding: utf-8 -*-
"""样式断言从 8 条变 9 条（补了"产物同步"），把文档里的数字改对。"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITS = [
    ("DailySeed-交接简报.md",
     "**加 `--style` 另 8 条样式断言（对比度 / 调色板 / 字号 / 圆角）+7 条自检**",
     "**加 `--style` 另 9 条样式断言（对比度 / 调色板 / 字号 / 圆角 / 产物同步）+7 条自检**"),
    ("DailySeed-交接简报.md",
     "python tools/verify_redlines.py --style --selftest   # 34 条 = 11 红线 + 8 样式 + 15 自检",
     "python tools/verify_redlines.py --style --selftest   # 35 条 = 11 红线 + 9 样式 + 15 自检"),
    ("DailySeed-交接简报.md",
     "**`--style --selftest` 34/34**（11 红线 + 8 样式 + 15 自检）",
     "**`--style --selftest` 35/35**（11 红线 + 9 样式 + 15 自检）"),
    (os.path.join("frontend", "README.md"),
     "python tools/verify_redlines.py --style --selftest   # 34 条 = 11 红线 + 8 样式 + 15 自检",
     "python tools/verify_redlines.py --style --selftest   # 35 条 = 11 红线 + 9 样式 + 15 自检"),
    (os.path.join("frontend", "README.md"),
     "**圆角**（要么 `var(--r-*)`，要么白名单里的有机形状）。",
     "**圆角**（要么 `var(--r-*)`，要么白名单里的有机形状）、"
     "**产物同步**（dist 的 CSS 里读不到当前令牌 = 改了样式忘了 `npm run build`）。"),
    ("DailySeed-会话纪要.md",
     "**加 `--style` 再 8 条样式断言（对比度/调色板/字号/圆角）+7 条自检**",
     "**加 `--style` 再 9 条样式断言（对比度/调色板/字号/圆角/产物同步）+7 条自检**"),
    (os.path.join("docs", "review-20261011", "视觉规范.md"),
     "同一套判据在 `tools/verify_redlines.py --style` 里，8 条断言 + 7 条自检：",
     "同一套判据在 `tools/verify_redlines.py --style` 里，9 条断言 + 7 条自检："),
    (os.path.join("docs", "review-20261011", "视觉规范.md"),
     "| 圆角 ×1 | 要么 `var(--r-*)`，要么在 `RADIUS_ALLOWED` 里 |",
     "| 圆角 ×1 | 要么 `var(--r-*)`，要么在 `RADIUS_ALLOWED` 里 |\n"
     "| 产物同步 ×1 | dist 的 CSS 里能读到当前令牌值（改了样式忘了 build 会被抓到） |"),
    (os.path.join("docs", "review-20261011", "优化记录.md"),
     "- `tools/verify_redlines.py --style`：8 条样式断言 + 7 条自检（含正反例：黑/白必须 21:1、同色必须 1:1、差 1/255 要报、差 40/255 要放过）。",
     "- `tools/verify_redlines.py --style`：9 条样式断言 + 7 条自检（含正反例：黑/白必须 21:1、同色必须 1:1、差 1/255 要报、差 40/255 要放过）。\n"
     "  第 9 条是**产物同步**（dist 的 CSS 里读不到当前令牌 = 改了样式忘了 build）——**它本身也做过反例测试**：\n"
     "  故意把 dist 里那个色改回旧值，它立刻报红；还原后转绿。"),
]

report = []
for path, old, new in EDITS:
    full = os.path.join(ROOT, path)
    text = io.open(full, encoding="utf-8").read()
    n = text.count(old)
    if n != 1:
        report.append("× 命中 %d 次：%s :: %s" % (n, path, old[:50]))
        continue
    io.open(full, "w", encoding="utf-8", newline="").write(text.replace(old, new))
    report.append("√ %s" % path)

print("\n".join(report))
ok = sum(1 for r in report if r.startswith("√"))
print("\n%d/%d" % (ok, len(EDITS)))
sys.exit(0 if ok == len(EDITS) else 1)
