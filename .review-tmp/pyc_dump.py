# -*- coding: utf-8 -*-
"""从 __pycache__ 里的旧 .pyc 还原"改动前"的字符串常量，用来对照改动后的 .py。

用途：这次的评审对象改过我的两份验证脚本（verify_cookie.py / verify_pwa.py），
但没留下改动前的副本。pyc 是 10/10 22:16 编出来的，正好是改动前的版本 —— 它自带
每条断言的标签文本，于是"哪几条被动了"可以直接列出来，不用靠记忆。

verify_redlines.py 这次没人动，拿它当**控制组**：如果它也报出差异，说明这个方法本身不可信。
"""
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
        fh.read(16)  # magic + flags + mtime + size
        code = marshal.load(fh)
    return strings_of(code, [])


def new_strings(src):
    code = compile(open(src, encoding="utf-8").read(), src, "exec")
    return strings_of(code, [])


for name in ("verify_cookie", "verify_pwa", "verify_redlines", "verify_api"):
    pyc = os.path.join(CACHE, name + ".cpython-313.pyc")
    src = os.path.join(ROOT, "tools", name + ".py")
    if not (os.path.exists(pyc) and os.path.exists(src)):
        print("SKIP %s（缺 pyc 或 py）" % name)
        continue
    old, new = set(old_strings(pyc)), set(new_strings(src))
    gone = sorted(s for s in old - new if len(s.strip()) > 12)
    added = sorted(s for s in new - old if len(s.strip()) > 12)
    print("=" * 70)
    print("%s：旧 %d 个字符串 / 新 %d 个；只有旧的 %d 条，只有新的 %d 条"
          % (name, len(old), len(new), len(old - new), len(new - old)))
    for s in gone:
        print("  [删/改] %s" % s.replace("\n", " / ")[:150])
    for s in added:
        print("  [新增] %s" % s.replace("\n", " / ")[:150])
