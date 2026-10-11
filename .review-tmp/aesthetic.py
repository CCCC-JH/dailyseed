# -*- coding: utf-8 -*-
"""审美的"能测那部分"：把配色、字号、间距、动效从 CSS 里量出来。

审美本身不能量（那是 taste），但下面这些**能**：
  ① 对比度：谁在谁的底上、够不够 WCAG AA（正文 4.5:1 / 大字与 UI 3:1）
  ② 调色板纪律：到底定义了多少个颜色，其中有多少是"看起来一样却各写一遍"的近似色
  ③ 字号阶梯：是阶梯还是散点（散点会让页面"每块都不一样高"）
  ④ 间距与圆角/动效令牌的复用率

对照组：改动前那份深色主题（`_review_backup_20261011/frontend-src/styles/base.css`），
同一套判据量一遍 —— 换主题这种决策，至少该知道它的代价落在哪。
"""
import os
import re
import sys
import colorsys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = [os.path.join(ROOT, "frontend", "src", "styles", n) for n in ("base.css", "components.css")]
OLD = os.path.join(ROOT, "_review_backup_20261011", "frontend-src", "styles", "base.css")
OLD2 = os.path.join(ROOT, "_review_backup_20261011", "frontend-src", "styles", "components.css")

HEX = re.compile(r"#([0-9a-fA-F]{3,8})\b")
RULES = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;{}]+);")


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def tokens(text):
    return {m.group(1): m.group(2).strip() for m in RULES.finditer(text)}


def to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 8:  # 带 alpha：按白底合成（这些底基本都是浅色）
        a = int(h[6:8], 16) / 255
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return tuple(int(c * a + 255 * (1 - a)) for c in (r, g, b))
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


def ratio(a, b, label, size_note):
    r = contrast(a, b)
    need = 4.5 if "正文" in size_note or "小" in size_note else 3.0
    flag = "OK " if r >= need else "!! "
    return "  %s%-34s %s on %s = %5.2f:1（%s，需 %.1f）" % (flag, label, a, b, r, size_note, need)


out = []
new_text = "\n".join(read(p) for p in NEW)
old_text = read(OLD) + "\n" + (read(OLD2) if os.path.exists(OLD2) else "")
nt, ot = tokens(new_text), tokens(old_text)

out.append("=" * 78)
out.append("一、新主题的令牌（:root）")
for k, v in nt.items():
    out.append("  %-16s %s" % (k, v))

out.append("")
out.append("=" * 78)
out.append("二、对比度（WCAG AA：正文 4.5:1 / 大字或 UI 3:1）")
pairs = [
    ("--ink", "--bg", "正文/标题", "正文"),
    ("--ink-2", "--bg", "次级说明（.lede）", "正文"),
    ("--ink-3", "--bg", "三级信息（.muted/.kicker 10-13px）", "小字"),
    ("--ink-3", "--surface-1", "三级信息在卡片上", "小字"),
    ("--seed", "--surface-1", "链接色/盆的分类 11px", "小字"),
    ("--seed", "--bg", "强调色在页面底上", "UI"),
    ("--seed-ink", "--seed", "主按钮文字", "正文"),
    ("--harvest", "--harvest-glow", "chip--harvest（难度）", "小字"),
    ("--danger", "--bg", "危险动作文字", "正文"),
    ("--ink-3", "#fafaf5f5", "底部导航未选中 11px", "小字"),
    ("--ink-2", "--surface-2", "chip 文字", "小字"),
]
for fg, bg, label, note in pairs:
    if fg in nt and bg in nt:
        out.append(ratio(nt[fg], nt[bg], label, note))
    elif bg.startswith("#"):
        out.append(ratio(nt.get(fg, "#000"), bg, label, note))

out.append("")
out.append("  —— 对照：改动前的深色主题 ——")
old_pairs = [
    ("--ink", "--bg", "正文/标题"),
    ("--ink-2", "--bg", "次级说明"),
    ("--ink-3", "--bg", "三级信息（10-13px）"),
]
for fg, bg, label in old_pairs:
    if fg in ot and bg in ot:
        out.append("  %-34s %s on %s = %5.2f:1" % (label, ot[fg], ot[bg], contrast(ot[fg], ot[bg])))

out.append("")
out.append("=" * 78)
out.append("三、调色板纪律：文件里一共出现多少个不同的颜色字面量")
for name, text in (("新（base+components）", new_text), ("旧（base+components）", old_text)):
    cols = Counter("#" + m.group(1).lower() for m in HEX.finditer(text))
    out.append("  %s：%d 处、%d 个不同颜色" % (name, sum(cols.values()), len(cols)))

out.append("")
out.append("四、近似色簇（RGB 距离 < 24 —— 肉眼看不出差别，却各写一遍）")
seen = sorted({m.group(1).lower() for m in HEX.finditer(new_text)})
groups = []
for c in seen:
    rgb = to_rgb(c)
    for g in groups:
        if max(abs(a - b) for a, b in zip(rgb, to_rgb(g[0]))) < 24:
            g.append(c)
            break
    else:
        groups.append([c])
multi = [g for g in groups if len(g) > 1]
for g in multi:
    uses = []
    for c in g:
        uses.append("#%s×%d" % (c, len(re.findall(re.escape("#" + c), new_text, re.I))))
    out.append("  " + "  ".join(uses))

out.append("")
out.append("=" * 78)
out.append("五、字号阶梯（散点 = 每块都不一样大）")
sizes = Counter()
for m in re.finditer(r"font-size:\s*([0-9.]+)px", new_text):
    sizes[float(m.group(1))] += 1
for m in re.finditer(r"font-size:\s*clamp\(([^)]+)\)", new_text):
    sizes["clamp(%s)" % m.group(1)] += 1
for m in re.finditer(r"font:\s*([0-9.]+)px", new_text):
    sizes[float(m.group(1))] += 1
numeric = sorted((k for k in sizes if isinstance(k, float)))
out.append("  数值字号：%s（%d 个不同值）" % (", ".join("%g" % s for s in numeric), len(numeric)))
out.append("  clamp：%s" % ", ".join("%s" % k for k in sizes if not isinstance(k, float)))
out.append("  出现次数：" + " ".join("%g×%d" % (s, sizes[s]) for s in numeric))

out.append("")
out.append("六、间距 / 圆角 / 动效令牌的复用")
for key in ("--r-sm", "--r-md", "--r-lg", "--r-pill", "--pad", "--tabbar", "--t-fast", "--t-base", "--t-slow", "--ease"):
    if key in nt:
        n = len(re.findall(r"var\(%s\)" % re.escape(key), new_text))
        out.append("  %-12s = %-34s 被 var() 引用 %d 次" % (key, nt[key], n))
radii = Counter(re.findall(r"border-radius:\s*([^;]+);", new_text))
out.append("  硬编码 border-radius（没走令牌）：%d 处 → %s" % (sum(radii.values()),
                                                          ", ".join(sorted(radii)[:10])))

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aesthetic.txt")
with open(path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
print("written", path)
