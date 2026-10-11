# -*- coding: utf-8 -*-
"""把 gbk_check 的结论写进 UTF-8 文件（打印到控制台会自己踩同一个坑）。"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
HERE = os.path.dirname(os.path.abspath(__file__))


def encodable(ch, encoding):
    try:
        ch.encode(encoding)
        return True
    except UnicodeEncodeError:
        return False


lines = []
for encoding in ("cp936", "utf-8"):
    lines.append("### 目标编码 %s" % encoding)
    hit = 0
    for name in sorted(os.listdir(TOOLS)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(TOOLS, name)
        tree = ast.parse(open(path, encoding="utf-8").read(), path)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print"):
                continue
            for arg in node.args:
                for sub in ast.walk(arg):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        bad = sorted({c for c in sub.value if not encodable(c, encoding)})
                        if bad:
                            hit += 1
                            lines.append("  %s 第 %d 行  编不过的字符=%s  文本=%s"
                                         % (name, node.lineno, " ".join("U+%04X" % ord(c) for c in bad),
                                            sub.value[:60].replace("\n", " ")))
    if not hit:
        lines.append("  没有地雷。")

out = os.path.join(HERE, "gbk.txt")
with open(out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print("written", out)
