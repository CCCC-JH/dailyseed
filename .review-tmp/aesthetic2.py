# -*- coding: utf-8 -*-
"""把上面那几条"感觉"落到具体数值上：替换色要算过、近似色只数不透明色、圆角要分清 var()。"""
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = [os.path.join(ROOT, "frontend", "src", "styles", n) for n in ("base.css", "components.css")]
text = "\n".join(open(p, encoding="utf-8").read() for p in NEW)
out = []


def to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = lum(to_rgb(a)), lum(to_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def darken_until(hex_color, bg, target):
    """只调暗、保持色相：找出刚好达标的那个值（这样就不用在"审美"和"达标"之间猜）。"""
    r, g, b = to_rgb(hex_color)
    best = None
    for k in range(0, 60):
        cand = "#%02x%02x%02x" % (max(0, r - k), max(0, g - k), max(0, b - k))
        if contrast(cand, bg) >= target:
            best = cand
            break
    return best


out.append("一、把不达标的三处算到刚好达标（只调暗、保持色相）")
for name, fg, bg in (("--ink-3", "#73776b", "#f8f7f2"),
                     ("底部导航未选中（--ink-3 在 tabbar 底上）", "#73776b", "#fafaf5"),
                     ("--harvest（难度 chip）", "#956638", "#f3e8d8")):
    now = contrast(fg, bg)
    fix = darken_until(fg, bg, 4.5)
    out.append("  %-34s 现在 #%s = %.2f:1 → 改 %s = %.2f:1"
               % (name, fg.lstrip("#"), now, fix, contrast(fix, bg)))
out.append("  （--harvest 也可以直接用现有的 --ink-2 #5c695e：%.2f:1，但那会丢掉「难度=棕色」的语义）"
           % contrast("#5c695e", "#f3e8d8"))

out.append("")
out.append("二、近似色簇（只数**不透明**色，α 值如 #293f3424 是阴影/光晕，本来就该独立）")
opaque = Counter("#" + m.group(1).lower() for m in re.finditer(r"#([0-9a-fA-F]{6})\b", text))
groups = []
for c in sorted(opaque):
    rgb = to_rgb(c)
    for g in groups:
        if max(abs(a - b) for a, b in zip(rgb, to_rgb(g[0]))) < 24:
            g.append(c)
            break
    else:
        groups.append([c])
light_bg = [g for g in groups if len(g) > 1 and lum(to_rgb(g[0])) > 0.72]
dark_ink = [g for g in groups if len(g) > 1 and lum(to_rgb(g[0])) <= 0.72]
out.append("  A. 浅色底/描边一族（肉眼看不出差别，却各写一遍）—— %d 组、共 %d 个色："
           % (len(light_bg), sum(len(g) for g in light_bg)))
for g in light_bg:
    out.append("     " + "  ".join(g))
out.append("  B. 深色文字/绿色一族 —— %d 组、共 %d 个色：" % (len(dark_ink), sum(len(g) for g in dark_ink)))
for g in dark_ink:
    out.append("     " + "  ".join(g))
out.append("  合计：不透明色 %d 个，其中 %d 个落在近似簇里（= 可合并）"
           % (len(opaque), sum(len(g) for g in light_bg + dark_ink)))

out.append("")
out.append("三、圆角：走令牌 vs 硬写")
all_radius = re.findall(r"border-radius:\s*([^;]+);", text)
via_var = [r for r in all_radius if "var(" in r]
hard = [r for r in all_radius if "var(" not in r]
out.append("  共 %d 处：走 var(--r-*) %d 处、硬写 %d 处" % (len(all_radius), len(via_var), len(hard)))
for v, n in Counter(hard).most_common():
    out.append("     %-40s ×%d" % (v.strip(), n))

out.append("")
out.append("四、侧栏那句为什么会断成「生活会长出自己的样／子。」")
out.append("  .navigation 宽 240px，左右各 padding 26px；.navigation__note 再 padding 0 12px")
out.append("  → 可用宽度 = 240 − 26×2 − 12×2 = %dpx" % (240 - 52 - 24))
out.append("  那句话是手写 <br/> 断的：第二行「生活会长出自己的样子。」共 10 个汉字")
out.append("  … 16px 字号下正好 %dpx —— 只余 %dpx。字体回退一变（Windows 上落宋体）就断行。" % (10 * 16, 164 - 160))

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aesthetic2.txt")
with open(path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
print("written", path)
