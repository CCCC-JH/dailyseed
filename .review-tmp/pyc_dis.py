# -*- coding: utf-8 -*-
"""把旧 pyc 与新源码的**指令流**都规范化（去掉行号），再逐行对照，定位那处逻辑改动。

verify_pwa.py 的字符串常量一个都没变，但字节码不同 —— 说明改的是判断方式而不是文案。
"""
import dis
import difflib
import io
import marshal
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "tools", "__pycache__")


def old_code(pyc):
    with open(pyc, "rb") as fh:
        fh.read(16)
        return marshal.load(fh)


def norm(code):
    out = []
    for ins in dis.get_instructions(code):
        if ins.opname in ("RESUME", "NOP", "CACHE", "PRECACHE", "EXTENDED_ARG", "RETURN_GENERATOR"):
            continue
        out.append("%-24s %s" % (ins.opname, ins.argrepr))
    return out


def walk(code, path="<module>"):
    """按（名字）递归给出每层代码对象的规范化指令。"""
    yield path, norm(code)
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from walk(const, "%s/%s" % (path, const.co_name))


for name in ("verify_pwa",):
    pyc = os.path.join(CACHE, name + ".cpython-313.pyc")
    src = os.path.join(ROOT, "tools", name + ".py")
    old = dict(walk(old_code(pyc)))
    new = dict(walk(compile(open(src, encoding="utf-8").read(), src, "exec")))
    lines = []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if a == b:
            lines.append("==" * 30)
            lines.append("%s：指令流一致" % key)
            continue
        lines.append("!!" * 30)
        lines.append("%s：指令流不同" % key)
        a = a or []
        b = b or []
        for line in difflib.unified_diff(a, b, "old", "new", lineterm="", n=3):
            lines.append(line)
    out = os.path.join(HERE, "pwa_dis_diff.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("written", out)
