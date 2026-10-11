# -*- coding: utf-8 -*-
"""第四批（--style 第一次跑出来的两处红）：

  ① 令牌之外的不透明色：把"阴影色 / 警示 toast 底"升成令牌，盆的陶土三色入白名单
  ② 裸的 12px 圆角 → var(--r-sm)（值相同，零像素变化）
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "frontend", "src", "styles", "base.css")
COMP = os.path.join(ROOT, "frontend", "src", "styles", "components.css")
TOOL = os.path.join(ROOT, "tools", "verify_redlines.py")

EDITS = [
    # ① 两个新令牌
    (BASE, "  --leaf-ink: #879777;",
     "  --leaf-ink: #879777;\n"
     "  --shadow-ink: #344c35;      /* 卡片的投影色：浅色底上用**带绿调的暗色**，不要用纯黑 */\n"
     "  --warn: #794438;             /* 警示 toast 的底（压白字用） */"),
    # ② 裸 12px 圆角
    (BASE, "  border-radius: 12px; color: var(--ink-3); font-size: 11px;",
     "  border-radius: var(--r-sm); color: var(--ink-3); font-size: 11px;"),
    # ③ 投影色并入令牌（两处卡片）
    (COMP, "box-shadow: 0 12px 28px -24px #384c35;", "box-shadow: 0 12px 28px -24px var(--shadow-ink);", 2),
    # ④ 警示 toast
    (BASE, ".toast--warn { background: #794438; }", ".toast--warn { background: var(--warn); }"),
    # ⑤ 盆的陶土三色：插画子调色板，写进白名单并说明理由
    (TOOL,
     'OPAQUE_ALLOWED = {\n    "#2c4438": "toast 底（比 --seed-deep 更深，压在白字下面才够）",\n}',
     'OPAQUE_ALLOWED = {\n'
     '    "#2c4438": "toast 底（比 --seed-deep 更深，压在白字下面才够）",\n'
     '    "#d69b79": "CSS 画的那盆：陶土亮面",\n'
     '    "#b57758": "CSS 画的那盆：陶土暗面",\n'
     '    "#d5cbb9": "CSS 画的那盆：碟子",\n'
     '    # 上面三个和 Icon.tsx 里 SVG 插画的陶土色（#bc775a / #ce8c6b / #dbd4c1）是有意分开的：\n'
     '    # 一个是 CSS 画的盆、一个是手绘插画，各自内部要一致，不必跨渲染方式对齐。\n'
     '}'),
]

problems = []
done = 0
for entry in EDITS:
    path, old, new = entry[0], entry[1], entry[2]
    times = entry[3] if len(entry) > 3 else 1
    text = io.open(path, encoding="utf-8").read()
    n = text.count(old)
    if n != times:
        problems.append("× 命中 %d 次（期望 %d）：%s" % (n, times, old[:60].replace("\n", " ")))
        continue
    io.open(path, "w", encoding="utf-8", newline="").write(text.replace(old, new))
    done += 1

print("完成 %d/%d 处" % (done, len(EDITS)))
for p in problems:
    print(p)
sys.exit(1 if problems else 0)
