# -*- coding: utf-8 -*-
"""把这一轮（模块 F）的结论落回交接文档。

为什么要用脚本而不是十几个 edit 调用：每一处替换都要求**恰好命中一次**，
命中不了就报出来（不静默跳过）。文档改错字的代价比代码高——它是下一轮的入口。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (文件, 旧, 新)
EDITS = []


def edit(path, old, new):
    EDITS.append((path, old, new))


BRIEF = "DailySeed-交接简报.md"
CHECKLIST = "DailySeed-真机验收清单.md"
FEREADME = os.path.join("frontend", "README.md")

# ─────────────────────────── 交接简报 ───────────────────────────

edit(BRIEF,
     "> **上次更新**：2026-10-10 · **当前模块**：模块 E（并发正确性 + 运行期地基）🟡 **已交付并验证** · 上一模块：模块 D（身份退路 / 分享退路 / 启动护栏）✅",
     "> **上次更新**：2026-10-11 · **当前模块**：模块 F（界面重做 + 身份凭据加固）🟡 **代码已交付并全量复验**（记录在 **§0.6**）· 上一模块：模块 E（并发正确性 + 运行期地基）✅\n"
     "> **还差什么**：375px 真机逐页（§0 验收 ⑥）与阶段 0 手工发卡——**这两件只能人做**。")

edit(BRIEF,
     "① `mvn test` **54/54**、`npm run typecheck` + `npm run build` 全过 ✅",
     "① `mvn test` **57/57**（模块 F 加了 3 个）、`npm run typecheck` 过；`npm run build` 要在**普通终端**里跑"
     "（受限沙箱里 esbuild 会 `spawn EPERM`，见 §5）✅")

edit(BRIEF,
     "④ `verify_cookie.py` **17/17** ✅",
     "④ `verify_cookie.py` **19/19**（模块 F 加了两条「伪造令牌」攻击路径）✅")

edit(BRIEF,
     "**12 个接口 + 54 个单测全绿**",
     "**12 个接口 + 57 个单测全绿**")

edit(BRIEF,
     "| **「抽」的形式 ✅**       | 卡背 → 点「抽」**640ms 3D 翻面**揭晓",
     "| **「抽」的形式 ✅**（2026-10-11 改文案） | 卡背（植物插画 +「一件小事，也会慢慢发芽。」+ 一个**「打开今天这一粒」**按钮）→ **640ms 3D 翻面**揭晓")

edit(BRIEF,
     "| **身份退路（模块 D ✅）** | `SessionCookie`：HttpOnly 的 `dailyseed_uid`，**只在连 deviceId 都拿不出来时**参与认人；认出来后由服务端补发 `srv-` 前缀的 deviceId。`verify_cookie.py` **17/17** 守着它（含\"给了 deviceId 就不看 Cookie\"这条反例） |",
     "| **身份退路（模块 D ✅，模块 F 加固）** | `SessionCookie`：HttpOnly 的 `dailyseed_uid`，值是一串 **256 位随机恢复令牌**（库里只存 SHA-256 + 400 天到期，`V5__recovery_tokens.sql`），**只在连 deviceId 都拿不出来时**参与认人；认出来后由服务端补发 `srv-` 前缀的 deviceId。**2026-10-11 之前它存的是自增 `userId`——那是可枚举的凭据，猜一个数字就能读别人的花园**。`verify_cookie.py` **19/19** 守着它（含\"给了 deviceId 就不看 Cookie\"与\"伪造令牌认不出人\"两组反例） |")

edit(BRIEF,
     "把 PWA 那节里能机器判定的部分从\"眼睛看\"变成了\"跑一遍\" |",
     "把 PWA 那节里能机器判定的部分从\"眼睛看\"变成了\"跑一遍\"。**前提是 `frontend/dist` 真的构建过**：`verify_redlines.py` 现在会在 dist 空/缺 `index.html` 时直接红一条（以前是安静跳过，见 §5） |")

edit(BRIEF,
     "| 接口断言                | `tools/verify_api.py` **57/57 PASS**（编号的 A1–A13 与 C1–C28，另加 16 条早期身份/取卡断言）、`tools/verify_cookie.py` **17/17 PASS**、`tools/verify_health.py` **12/12 PASS**、`tools/verify_concurrency.py` **4/4 PASS**、`tools/verify_catchup.py` **4/4 PASS**、`tools/verify_pwa.py` **17/17 PASS**、`tools/verify_qa_fixtures.py` **43/43 PASS** |",
     "| 接口断言                | `tools/verify_api.py` **57/57 PASS**（编号的 A1–A13 与 C1–C28，另加 16 条早期身份/取卡断言）、`tools/verify_cookie.py` **19/19 PASS**、`tools/verify_health.py` **12/12 PASS**、`tools/verify_concurrency.py` **4/4 PASS**、`tools/verify_catchup.py` **4/4 PASS**、`tools/verify_pwa.py` **18/18 PASS**、`tools/verify_qa_fixtures.py` **43/43 PASS**、`tools/verify_redlines.py` **11/11 PASS（+8 自检）** |")

edit(BRIEF,
     "| 身份与同步码回归            | `frontend/qa-verify-bootstrap.mjs` **20/20 PASS**（纯 Node，无依赖）：401 → 重建身份 → 重试（含并发去重）+ 同步码整理 + 清缓存被 Cookie 认回 + 换发的新码不被 null 抹掉 + 四道源码守卫 |",
     "| 身份与同步码回归            | `frontend/qa-verify-bootstrap.mjs` **9 个场景 + 4 道源码守卫 + 1 条反例自检全过**（纯 Node，无依赖，**跑的是 `src/api/*.ts` 与 `src/lib/keepHint.ts` 的真源码**——用 TS 编译器转成 CJS 后塞进 `vm`，假 `localStorage`/`crypto`/`fetch`）：并发注册只建一次 · 断网/503 **不换身份**且可重试 · 清缓存被 Cookie 认回 · 401 先修再重试（串行与并发各一条）· 修复失败不被永久缓存 · 同步码整理与「空响应不抹码」 · 同步码提示只提一次且可永久关闭 · 四道源码守卫（含「守卫本身会不会报」的反例自检）。⚠️ 这一轮把它从「移植版 20 条」换成了「真源码 9+4+1 条」，**覆盖方向更真、条数更少**，旧版那四道守卫已补回 |")

edit(BRIEF,
     "python tools/verify_cookie.py            # 17 条：身份退路（cookiejar 模拟两台浏览器）",
     "python tools/verify_cookie.py            # 19 条：身份退路（cookiejar 模拟两台浏览器 + 两条伪造令牌）")

edit(BRIEF,
     "# 红线巡检（11 条 + 8 条自检）：产物+卡片库里\"能机器判定的那部分\"红线\npython tools/verify_redlines.py          # 加 --selftest 会额外验证\"检测器本身会不会报\"",
     "# 红线巡检（11 条 + 8 条自检）：产物+卡片库里\"能机器判定的那部分\"红线\npython tools/verify_redlines.py          # 加 --selftest 会额外验证\"检测器本身会不会报\"\n\n# 前端身份回归（9 场景 + 4 道源码守卫 + 1 条反例自检；纯 Node，不需要浏览器与后端）\ncd frontend; node qa-verify-bootstrap.mjs; cd ..")

edit(BRIEF,
     "- **⚠️ 无头浏览器在这台机器上跑不起来**（2026-10-10，别再花时间试）：",
     """- **⚠️ `frontend/dist` 可能"看着在、其实空了"**（2026-10-11 实测撞到，整轮交付被它卡住）：
  `dist/` 目录还在、里面**只剩 `icons/`**，`index.html` / `assets/` / `sw.js` / `manifest.webmanifest`
  全没了 —— 4173 预览、静态契约、375px 验收全部做不了（**Docker 那条路反而没事**，镜像里自己构建）。
  最可能是**预览服务器还在跑的时候又跑了 `npm run build`**（这个坑 README 里记过，还是踩了：
  Vite 先清空输出目录再写入，清到一半失败就留下半个 dist）。两条教训：
  ① **构建之后必须验产物**——`verify_redlines.py` 现在会在 dist 空/缺 `index.html` 时直接红一条
  （以前只打一行"共 0 字符"就安静跳过 3 条断言，总数从 11 变 8 而**看起来仍然全绿**，这就是假绿）；
  ② **讲过的坑要变成断言**，光写在文档里挡不住第二次
- **⚠️ 中文 Windows 的控制台是 cp936，而 GB2312 只有 ①–⑩**（2026-10-11，用一次全量扫描扫出来的）：
  `verify_pwa.py` 跑到第 **⑪** 条就抛 `UnicodeEncodeError: 'gbk' codec can't encode '\\u246a'` 死掉，
  前面 10 条结论全白跑；`seed_dev_user.py --qa` 更阴——**四台设备全造好了、摘要也打印完了**，
  最后一行 `print("⚠️ …")` 崩在 U+26A0 上，退出码 1 + traceback，看着像"造数失败"。
  修法：打印文本里不用 GBK 编不出来的符号 · `sys.stdout.reconfigure(errors="replace")` 兜底 ·
  `verify_pwa.py` 按 `sys.stdout.encoding` 决定用 ⑪ 还是 `11.`。
  **通用教训：文档里让人照抄的命令，必须在这台机器的原始控制台上真跑一遍**——
  我这边一路是 UTF-8 控制台，所以这两条地雷从来没响过
- **⚠️ `mvn` 必须带 `-Dmaven.repo.local=.m2repo`**（2026-10-11 实测）：依赖装在 `backend/.m2repo` 里，
  直接 `mvn test` 会走默认的 `~/.m2`，然后报一串"依赖解析失败/offline"，看着像工程坏了。
  照 §4 那样 `cd backend` + 带参数就没问题
- **⚠️ 无头浏览器在这台机器上跑不起来**（2026-10-10，别再花时间试）：""")

edit(BRIEF,
     "11. ✅ **Docker 产物已实测**（2026-10-10）：见 §0.4 第 1 条与 §3「部署产物」。剩下的只有**真机**那一半——iOS Safari 的 `navigator.share({files})` 与 `.ics` 落点（§8 第 1 条）",
     """11. ✅ **Docker 产物已实测**（2026-10-10）：见 §0.4 第 1 条与 §3「部署产物」。剩下的只有**真机**那一半——iOS Safari 的 `navigator.share({files})` 与 `.ics` 落点（§8 第 1 条）
12. **`recovery_tokens` 会随"不接受 Cookie 的客户端"无界增长**（2026-10-11 实测）：同一个 `deviceId`、不带任何 Cookie 连发 3 次 `POST /api/session` → 表里 **3 行**（正常浏览器会 `renew`，不新插）。清理只发生在**签发时**、且只清**该用户**的**已过期**行（400 天）。要么给每个 `user_id` 一个保留上限，要么加一个定期清理——量级不大，但它是目前唯一一张"只增不减"的表
13. **旧版"数字 Cookie"在升级后会一次性失效**（模块 F 的 `SessionCookie` 只认 64 位十六进制令牌）：受影响的只有"清过 localStorage、又只靠那条 Cookie 认人"的用户——他们升级后会落到一个新号上（旧数据没删，但再也认不回去）。本机与阶段 0 的量级可以接受；**要是上线时已经有真实用户，先补一段"把旧数字 Cookie 换成令牌"的兼容路径**""")

edit(BRIEF,
     "## 0.8 上一模块：**D · 上线前收尾** ✅（2026-10-09）",
     """### 0.6 2026-10-11 追加轮：**F · 界面重做 + 身份凭据加固** 🟡（不在原计划里）

> 这一轮的前后端由**另一个模型**动手改，交接时只留了 `frontend/README.md` 的一小节。
> 我这边做的是**全量复验 + 补齐交付面**：逐文件差异、每处的动机与实测证据都在
> `docs/review-20261011/优化记录.md`（同目录有两张截图）。

| 项 | 内容 |
| --- | --- |
| **后端** | ① Cookie 里的自增 `userId`（可枚举 → 可冒充）换成 **256 位随机恢复令牌**，库里只存 SHA-256 + 400 天到期（新增 `V5__recovery_tokens.sql` / `RecoveryTokenStore`）；②「走过的」列表的 N+1 查询改成一次 `IN (:ids)`；③ `createAnonymous` 加 `@Transactional`；④ `graduate` 返回"实际发生了没有"，失败时不再关弹层、不再拿过期数据开分享卡 |
| **前端** | 米白纸张底色（原深色）+ 植物 SVG 插画 + 统一线条图标；960px 起左侧栏、手机保留底部导航；**去掉 `user-scalable=no`**（恢复缩放）；底部弹层做成**栈**（只有顶层响应 Esc/Tab、焦点还给打开它的元素、body overflow 只在首尾处理）；触控目标补到 44px；`bootstrapDevice` 的 catch **收窄**（瞬时断网不再丢掉原账号）；花园/走过的各自独立错误态；一页一个 `<h1>` |
| **复验结果（2026-10-11）** | `mvn test` **57/57**（54 + 3）· `verify_api.py` **57/57** · `verify_cookie.py` **19/19**（17 + 2 条伪造令牌）· `verify_health.py` **12/12** · `verify_qa_fixtures.py` **43/43** · `verify_pwa.py` **18/18** · `verify_redlines.py` **11/11（+8 自检）** · `qa-verify-bootstrap.mjs` **9 场景 + 4 道源码守卫 + 1 条反例自检** · `npm run typecheck` 过 |
| **同轮补掉的交付缺口** | ① `frontend/dist` 当时是**空的**（只剩 `icons/`）→ 已重建并复验；② 交接文档还在描述旧界面（「抽」按钮、"点一下，看是什么"）→ 已按新界面改写（含验收清单）；③ `frontend/README.md` 引用的 `docs/review-20261011/优化记录.md` **不存在** → 已补写；④ 那两张截图其实是 JPEG 却命名 `.png` → 已改名 `.jpg`；⑤ `verify_pwa.py` / `seed_dev_user.py` 在 cp936 控制台上会崩 → 已修（见 §5） |
| **仍然待你点** | 375px 真机逐页（§0 验收 ⑥）· 阶段 0 手工发卡（§8 第 10 条） |

---

## 0.8 上一模块：**D · 上线前收尾** ✅（2026-10-09）""")

# ─────────────────────────── 真机验收清单 ───────────────────────────

edit(CHECKLIST,
     "#### 手动反复测「抽」这条路径（最常用）",
     "#### 手动反复测「打开今天这一粒」这条路径（最常用）")

edit(CHECKLIST,
     "| `python tools/seed_dev_user.py --reset-today` | **把今天那张复活**：未留住、回到卡背、抽卡次数归零 | 你刚点过「留住它」，按钮没了，想**再走一遍**「抽 → 揭晓 → 留住」 |",
     "| `python tools/seed_dev_user.py --reset-today` | **把今天那张复活**：未留住、回到卡背、抽卡次数归零 | 你刚点过「留住它」，按钮没了，想**再走一遍**「打开 → 揭晓 → 留住」 |")

edit(CHECKLIST,
     "- [ ] **卡背**：新身份（`localStorage.clear(); location.reload()`）打开 → 看到**卡背**（一颗呼吸的种子 + 「今天这一粒」+「点一下，看是什么」+ 一个「抽」按钮），**看不到卡面文案**",
     """- [ ] **页头**：英文眉标（`A LITTLE EVERY DAY`）+ **衬线体**大标题「给日常，一点新意。」+ 一句说明
- [ ] **卡背**：新身份（`localStorage.clear(); location.reload()`）打开 → 看到**卡背**（一株植物插画 + 「一件小事，也会慢慢发芽。」+「今天会遇见什么呢？」+ 一个**「打开今天这一粒」**按钮），**看不到卡面文案**
      > ⚠️ 老版本这里写的是「抽」按钮 +「点一下，看是什么」——2026-10-11 改了文案（"抽"是抽卡游戏的语言）""")

edit(CHECKLIST,
     "- [ ] **抽 → 揭晓**：点「抽」→ 卡片**翻面**露出卡面（约 0.64s 的 3D 翻转，有轻微节奏感、不晃眼）",
     "- [ ] **打开 → 揭晓**：点「打开今天这一粒」→ 卡片**翻面**露出卡面（约 0.64s 的 3D 翻转，有轻微节奏感、不晃眼）")

edit(CHECKLIST,
     "- [ ] **揭晓后 UI 正确**：卡背的「抽」按钮消失，出现「留住它」；「?」入口**这时才出现**（A/B 级）",
     """- [ ] **揭晓后 UI 正确**：卡背那个按钮消失（它只在未揭晓时才渲染），出现「留住它」；「?」入口**这时才出现**（A/B 级）
- [ ] **卡面排版**：文案是**衬线体**、明显比正文大；卡面下部一行「一点点，也很好。」带叶子图标
- [ ] **页面底部那句**：有「想做就做，觉得好就留下。／今天不想做，也没关系。」（红线 1/2 的落点）
- [ ] **窄屏（≤420px，375px 重点看这条）**：卡背与卡面高度降到 **370px**、按钮不贴边、卡片不溢出、底部导航不挡内容""")

edit(CHECKLIST,
     "- [ ] 留到 ≥7 次的那几盆（16 / 9 / 7 次，`-a` 是 #2/#3/#5）带「可毕业」小标记；2 次和 1 次的不带",
     """- [ ] 留到 ≥7 次的那几盆（16 / 9 / 7 次，`-a` 是 #2/#3/#5）带「可毕业」小标记；2 次和 1 次的不带
- [ ] **每盆显示**：分类 + 卡片原文 + 「留住 N 次」（`-a` 那台的 #2 应显示「留住 16 次」）
- [ ] **两列排布**：手机上每行 2 盆；文案长的盆不会把格子撑坏、不会互相压到""")

edit(CHECKLIST,
     "- [ ] Application → Cookies：能看到 **`dailyseed_uid`**，且 **HttpOnly 打勾**、SameSite 是 `Lax`",
     """- [ ] Application → Cookies：能看到 **`dailyseed_uid`**，值是**一长串 64 位十六进制**（2026-10-11 起不再是数字），且 **HttpOnly 打勾**、SameSite 是 `Lax`
- [ ] **★ 伪造凭据不管用**（新增）：把这个 Cookie 的值改成**纯数字的 userId**、刷新 → **不是**你的花园，而是一个新号；再改成一串随便编的 64 位十六进制 → 同样认不出来（接口侧由 `verify_cookie.py` 第 18/19 条守着）""")

# ─────────────────────────── frontend/README ───────────────────────────

edit(FEREADME,
     "  `qa-verify-bootstrap.mjs` 里有一条专门守它（移植版 + 源码守卫各一道）",
     "  `qa-verify-bootstrap.mjs` 里有一条场景专门守它（跑的是真实的 `session.ts`）")

edit(FEREADME,
     """- 回归脚本：`node qa-verify-bootstrap.mjs`（20 个场景，纯 Node 无依赖）。
  **改身份逻辑时要同步改里面那份移植版本**，否则它会验一个过时的模型。
  它现在也覆盖同步码整理、清缓存被 Cookie 认回、以及三道**源码守卫**（`session.ts` 是否还导出那两个函数、
  `client.ts` 的恢复接口有没有退回会自作主张重注册的 `request()`、`bootstrapDevice` 有没有用 `readDeviceId`）""",
     """- 回归脚本：`node qa-verify-bootstrap.mjs`（**9 个场景 + 4 道源码守卫 + 1 条反例自检**，纯 Node 无依赖）。
  它用 `typescript` 把**真实的** `src/api/client.ts` / `session.ts` / `src/lib/keepHint.ts` 转成 CJS，
  再塞进 `vm` 跑（假的 `window.localStorage` / `sessionStorage` / `crypto` / `fetch`）——
  **不再维护一份移植实现**（移植版的问题是：源码改了它没改，测试照样绿，于是它验的是一个过时的模型）。
  覆盖：并发注册只建一次 · 断网/503 **不换身份**且可重试 · 清缓存被 Cookie 认回 ·
  401 先修再重试（串行 + 并发）· 修复失败不被永久缓存 · 同步码整理与"空响应不抹码" ·
  同步码提示只提一次且可永久关闭。
  外加四道**源码守卫**（`session.ts` 的 readDeviceId/canonicalSyncCode/saveSession 还在 ·
  `restoreSession` 没退回会自作主张重注册的 `request()` · `bootstrapDevice` 用 `readDeviceId` 而不是 `ensureDeviceId` ·
  `main.tsx` 不套 StrictMode），以及**反例自检**：拿"人造旧形状"喂进同一套判据，必须被判为不合格
  （只会通过的守卫等于没有守卫）""")

edit(FEREADME,
     "├── components/   Sheet / EvidenceSheet / Pot / GraduateConfirm / ShareSheet / SyncCodeSheet /\n│                 RestoreSheet / ReminderSheet / TabBar / Toast / Tappable / CardMeta / AsyncArea",
     "├── components/   Sheet / EvidenceSheet / Pot / GraduateConfirm / ShareSheet / SyncCodeSheet /\n│                 RestoreSheet / ReminderSheet / TabBar / Toast / Tappable / CardMeta / AsyncArea /\n│                 Icon（线条图标 + 植物插画，纯内联 SVG）· PageHeading（眉标 + h1 + 说明）")

edit(FEREADME,
     "## 2026-10-11 界面与稳定性更新\n\n米白纸张底色、植物 SVG 插画与统一线条图标。960px 起使用侧栏导航，手机保留底部导航；支持页面缩放和减少动态效果。没有增加运行时依赖，也没有外部字体或图片请求。\n\n`node qa-verify-bootstrap.mjs` 现在会转译并执行真实的 `src/api/client.ts` / `session.ts`，覆盖并发注册、离线后重试、Cookie 恢复、401 修复与同步码保留，不再维护一份移植实现。\n\n完整记录见 `../docs/review-20261011/优化记录.md`，同目录有桌面与手机截图。",
     """## 2026-10-11 界面与稳定性更新

米白纸张底色、植物 SVG 插画与统一线条图标。960px 起使用侧栏导航，手机保留底部导航；支持页面缩放和减少动态效果。没有增加运行时依赖，也没有外部字体或图片请求。

`node qa-verify-bootstrap.mjs` 现在会转译并执行真实的 `src/api/client.ts` / `session.ts`，覆盖并发注册、离线后重试、Cookie 恢复、401 修复与同步码保留，不再维护一份移植实现。

> **复验与交付缺口（2026-10-11 补齐）**：`npm run typecheck` 过；`verify_pwa.py` **18/18**、`verify_redlines.py` **11/11**。
> 当时留下的 `frontend/dist` 其实是**空的**（只剩 `icons/`，见交接简报 §5），已重建。
> 完整的逐文件改动、动机与实测证据见 `../docs/review-20261011/优化记录.md`，同目录有桌面（1264px）与手机（360px）截图（`.jpg`）。
>
> ⚠️ 这两张截图是 **360px** 宽，而验收清单要的是 **375px** —— 375px 那一轮仍然只能人点。""")

# ─────────────────────────── 执行 ───────────────────────────

report = []
for path, old, new in EDITS:
    full = os.path.join(ROOT, path)
    with io.open(full, encoding="utf-8") as fh:
        text = fh.read()
    n = text.count(old)
    if n != 1:
        report.append("× 跳过（命中 %d 次）：%s :: %s" % (n, path, old[:60].replace("\n", " ")))
        continue
    with io.open(full, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace(old, new))
    report.append("√ %s :: %s" % (path, old[:48].replace("\n", " ")))

print("\n".join(report))
ok = sum(1 for r in report if r.startswith("√"))
print("\n%d/%d 处替换成功" % (ok, len(EDITS)))
sys.exit(0 if ok == len(EDITS) else 1)
