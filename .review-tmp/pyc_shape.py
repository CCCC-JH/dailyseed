# -*- coding: utf-8 -*-
"""更硬一点的对照：逐层比较旧 pyc 与新源码编译出来的**字节码**。

字符串常量相同还不足以说明"逻辑没动"（条件表达式可以变）。
这里逐层比对 co_code / co_names / co_varnames / 非 code 常量，
完全忽略行号表 —— 于是"只改了注释/换行"会判定为相同，任何逻辑改动都会现形。

verify_api.py 这次没人动，一起跑当控制组。
"""
import marshal
import os
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "tools", "__pycache__")


def old_code(pyc):
    with open(pyc, "rb") as fh:
        fh.read(16)
        return marshal.load(fh)


def new_code(src):
    return compile(open(src, encoding="utf-8").read(), src, "exec")


def shape(code):
    """把一个 code 对象压成"与行号无关"的形状。"""
    return (
        code.co_code,
        code.co_names,
        code.co_varnames,
        tuple(c for c in code.co_consts if not isinstance(c, types.CodeType)),
        tuple(shape(c) for c in code.co_consts if isinstance(c, types.CodeType)),
    )


for name in ("verify_pwa", "verify_cookie", "verify_api", "verify_redlines"):
    pyc = os.path.join(CACHE, name + ".cpython-313.pyc")
    src = os.path.join(ROOT, "tools", name + ".py")
    if not (os.path.exists(pyc) and os.path.exists(src)):
        print("SKIP %s" % name)
        continue
    a, b = shape(old_code(pyc)), shape(new_code(src))
    print("%-16s 字节码层面：%s" % (name, "完全一致（只有注释/排版/行号变了）" if a == b else "有逻辑差异"))
