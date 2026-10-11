# -*- coding: utf-8 -*-
"""交叉核对：TSX 里用到的 className，CSS 里到底有没有对应的选择器。

为什么要这条：class 名写错（或 CSS 改名后漏改 TSX）在浏览器里**不报错**，
只是那一段样式悄悄不生效 —— 恰好属于"只能靠眼睛看"的那一类。
而 375px 逐页验收眼下点不了，先用机器把"孤儿 class"筛出来。

不做的事：不判断样式好不好看，也不要求 CSS 里每个选择器都被用到
（有些是给状态用的，比如 .is-revealed）。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "frontend", "src")

tsx_classes = {}   # class -> 出现位置
for base, _dirs, files in os.walk(SRC):
    for name in files:
        if not name.endswith((".tsx", ".ts")):
            continue
        path = os.path.join(base, name)
        rel = os.path.relpath(path, ROOT)
        text = open(path, encoding="utf-8").read()
        for m in re.finditer(r'className=(?:"([^"]*)"|\{`([^`]*)`\})', text):
            raw = m.group(1) or m.group(2) or ""
            # 模板串里的 ${...} 是动态拼接，逐个 token 拆出来
            for token in re.split(r"\s+", re.sub(r"\$\{[^}]*\}", " ", raw)):
                token = token.strip()
                if token and re.fullmatch(r"[A-Za-z][\w-]*", token):
                    tsx_classes.setdefault(token, set()).add(rel)

css_text = ""
for name in ("base.css", "components.css"):
    css_text += open(os.path.join(SRC, "styles", name), encoding="utf-8").read()
css_classes = set(re.findall(r"\.([A-Za-z][\w-]*)", css_text))

orphans = {c: sorted(v) for c, v in sorted(tsx_classes.items()) if c not in css_classes}
print("TSX 里用了 %d 个 class（含动态拼接的 token）" % len(tsx_classes))
print("CSS 里定义了 %d 个 class" % len(css_classes))
print("=" * 68)
if orphans:
    print("没有对应 CSS 规则的 class（要么是白写的，要么是名字写错了）：")
    for c, where in orphans.items():
        print("  %-26s %s" % (c, ", ".join(where)))
else:
    print("没有孤儿 class：TSX 里用到的每个 class 都能在 CSS 里找到。")

# 反向看一眼：CSS 定义了但这次改动后再没人用的 class（可能是重写留下的残骸）
used = set(tsx_classes)
unused = sorted(c for c in css_classes if c not in used and not c.startswith(("is-", "has-")))
print("=" * 68)
print("CSS 里定义、但 TSX 里没出现的 class（%d 个，含伪类/状态类，仅供扫一眼残骸）：" % len(unused))
print("  " + ", ".join(unused))
sys.exit(1 if orphans else 0)
