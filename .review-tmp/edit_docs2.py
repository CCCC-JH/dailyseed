# -*- coding: utf-8 -*-
"""第二批文档更新：会话纪要 + backend/README（同 edit_docs.py 的规矩：命中必须恰好一次）。"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITS = []


def edit(path, old, new):
    EDITS.append((path, old, new))


LOG = "DailySeed-会话纪要.md"
BRE = os.path.join("backend", "README.md")

edit(LOG,
     "| **当前进度** | 设计文档 **v1.8** · 卡片库 **v2.2**（100 张 + 依据库 A 6/B 27 + 科普库 8）· **后端**：**12 个接口 / 54 个单测 / 57 条接口断言 + 17 条身份退路断言**全绿 · **前端**：模块 B（四页 + 依据弹层 + 毕业 + Canvas 毕业卡 + PWA）+ 模块 C（走过的 / 找回 / 提醒）+ 模块 D（身份退路 / `.ics` 分享退路 / 启动护栏）+ 模块 E（健康检查 / 并发闸门 / Docker 产物已实测），构建与代理均已验证 |",
     "| **当前进度** | 设计文档 **v1.8** · 卡片库 **v2.2**（100 张 + 依据库 A 6/B 27 + 科普库 8）· **后端**：**12 个接口 / 57 个单测 / 57 条接口断言 + 19 条身份退路断言**全绿 · **前端**：模块 B（四页 + 依据弹层 + 毕业 + Canvas 毕业卡 + PWA）+ 模块 C（走过的 / 找回 / 提醒）+ 模块 D（身份退路 / `.ics` 分享退路 / 启动护栏）+ 模块 E（健康检查 / 并发闸门 / Docker 产物已实测）+ **模块 F（2026-10-11：界面重做 + Cookie 令牌化，见交接简报 §0.6）**，`npm run typecheck` 与静态契约 18 条均已验证 |")

edit(LOG,
     "| `tools/verify_{health,cookie,concurrency,qa_fixtures}.py` | 后续模块加的四个验证脚本：健康与配置 **12 条** · 身份退路 **17 条** · 并发不变量 **4 条** · 真机验收夹具 **43 条** |",
     """| `tools/verify_{health,cookie,concurrency,qa_fixtures}.py` | 后续模块加的四个验证脚本：健康与配置 **12 条** · 身份退路 **19 条**（模块 F 补了两条"伪造令牌"攻击路径） · 并发不变量 **4 条** · 真机验收夹具 **43 条** |
| `frontend/qa-verify-bootstrap.mjs` | **身份回归**（纯 Node，不需要浏览器与后端）：把**真实的** `src/api/client.ts` / `session.ts` / `lib/keepHint.ts` 用 TS 编译器转成 CJS、塞进 `vm` 跑（假 localStorage/crypto/fetch）——**9 个场景 + 4 道源码守卫 + 1 条反例自检**。它替代了原来那份"移植版"实现（移植版会验一个过时的模型） |""")

edit(LOG,
     "| 9   | ✅ 模块 D（2026-10-09）—— HttpOnly Cookie 身份退路 · `.ics` 先分享后退下载 · `StartupGuard` 拦住\"忘了改配额就上线\" | 已交付并验证 |",
     """| 9   | ✅ 模块 D（2026-10-09）—— HttpOnly Cookie 身份退路 · `.ics` 先分享后退下载 · `StartupGuard` 拦住"忘了改配额就上线" | 已交付并验证 |
| 10  | ✅ 模块 E（2026-10-10）—— 并发闸门（`WHERE state <> 'KEPT'` / `WHERE draw_count = :n`）· `/api/health` · Docker 产物实测 · PWA/红线两个静态巡检脚本 | 已交付并验证 |
| 11  | 🟡 模块 F（2026-10-11）—— 界面重做（米白纸张 / 插画 / 侧栏 / 弹层栈 / 44px 触控）· Cookie 换 256 位随机令牌（那之前它是可枚举的 userId）· N+1 批量化 · 前端 catch 收窄 | 代码已复验，**剩 375px 真机逐页** |""")

edit(BRE,
     "| **退路** | HttpOnly Cookie `dailyseed_uid` |",
     "| **退路** | HttpOnly Cookie `dailyseed_uid`（值 = 256 位随机令牌，库里只有 SHA-256） |")

report = []
for path, old, new in EDITS:
    full = os.path.join(ROOT, path)
    with io.open(full, encoding="utf-8") as fh:
        text = fh.read()
    n = text.count(old)
    if n != 1:
        report.append("× 跳过（命中 %d 次）：%s :: %s" % (n, path, old[:50].replace("\n", " ")))
        continue
    with io.open(full, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace(old, new))
    report.append("√ %s :: %s" % (path, old[:46].replace("\n", " ")))

print("\n".join(report))
ok = sum(1 for r in report if r.startswith("√"))
print("\n%d/%d 处替换成功" % (ok, len(EDITS)))
sys.exit(0 if ok == len(EDITS) else 1)
