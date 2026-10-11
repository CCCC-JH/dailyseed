# -*- coding: utf-8 -*-
"""列出每个 font-size 声明属于哪个选择器 —— 判断"改 0.5px 会不会挤破布局"要看着这个决定。"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for name in ("base.css", "components.css"):
    path = os.path.join(ROOT, "frontend", "src", "styles", name)
    text = open(path, encoding="utf-8").read()
    print("=" * 70)
    print(name)
    selector = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith("{") and not stripped.startswith("@"):
            selector = stripped[:-1].strip()
        for m in re.finditer(r"font-size:\s*([0-9.]+)px", line):
            size = float(m.group(1))
            mark = "  ← 半像素" if size % 1 else ""
            print("  %5.1fpx  %-46s%s" % (size, selector[:46], mark))
        # 同一行里也可能有选择器
        for m in re.finditer(r"([.#][\w-]+[^{};]*)\{[^}]*font-size:\s*([0-9.]+)px", line):
            print("  %5.1fpx  %-46s  ← 行内规则" % (float(m.group(2)), m.group(1)[:46]))
