# -*- coding: utf-8 -*-
"""同上，但不过滤长度，把差异写成 UTF-8 文件（控制台编码会吃中文）。"""
import marshal
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "tools", "__pycache__")


def strings_of(code, out):
    for const in code.co_consts:
        if isinstance(const, str):
            out.append(const)
        elif isinstance(const, types.CodeType):
            strings_of(const, out)
    return out


def old_strings(pyc):
    with open(pyc, "rb") as fh:
        fh.read(16)
        return strings_of(marshal.load(fh), [])


def new_strings(src):
    return strings_of(compile(open(src, encoding="utf-8").read(), src, "exec"), [])


lines = []
for name in ("verify_cookie", "verify_pwa"):
    pyc = os.path.join(CACHE, name + ".cpython-313.pyc")
    src = os.path.join(ROOT, "tools", name + ".py")
    old, new = old_strings(pyc), new_strings(src)
    osc, nsc = set(old), set(new)
    lines.append("=" * 70)
    lines.append("%s：旧 %d / 新 %d" % (name, len(old), len(new)))
    for s in sorted(osc - nsc):
        lines.append("  [不在新版里] %r" % s)
    for s in sorted(nsc - osc):
        lines.append("  [新版新增]   %r" % s)

out = os.path.join(HERE, "pyc_diff.txt")
with open(out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print("written", out)
