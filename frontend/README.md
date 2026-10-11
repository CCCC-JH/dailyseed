# DailySeed 前端（模块 B 起步 · C/D 补齐 · PWA）

React 18 + Vite 5 + TypeScript 严格模式。**没有路由库、没有 UI 框架、没有状态库、没有 axios**——
四个页面用状态切换，网络层一个文件，样式手写 CSS。少一个依赖就少一处以后要修的地方。

## 跑起来

```powershell
cd frontend
npm install --ignore-scripts --cache ".npm-cache"   # 见下面「沙箱坑」
npm run dev                                        # http://localhost:5173
```

**必须让后端先跑着**（8080）。前端一律请求相对路径 `/api/...`，由 `vite.config.mjs` 里的
proxy 转发到 `localhost:8080`。后端**没有任何 CORS 配置**，所以不要在前端写 `http://localhost:8080` 直连。

```powershell
npm run typecheck   # 两个 tsconfig 都检查（src + 配置文件）
npm run build       # typecheck + vite build → dist/
npm run preview     # 用 dist/ 起一个静态服务
```

改完 PWA / manifest / `sw.js`（或换过图标）之后，跑一遍**静态契约**那 18 条再点页面：
`python tools/verify_pwa.py`（默认对着 4173；容器那条路就 `python tools/verify_pwa.py http://127.0.0.1:18088`）。
它管的是"能机器判定的部分"：manifest 必填项、图标 192/512/maskable 都取得到、**产物名必须带内容哈希**
（nginx 给 `/assets/` 长缓存的前提）、页面里没有第三方源、**线上 `sw.js` 与源码逐字节一致**、
**SW 预缓存的每一项都真的存在**、SW 不碰 `/api/**`。
"安装到桌面 / 断网刷新 / iOS 分享"这些仍然只能人点。

## 想看"用了几天之后"的样子

新设备在同一天里怎么刷新都只有 1 盆（`POST /api/today/keep` 对同一天幂等），
所以花园的跨天视图、`readyToGraduate`（≥7 次）、放纵日入口在前端**看不到**。用 fixture：

```powershell
python tools/seed_dev_user.py --days 6      # 造一个用了 6 天的测试用户
```

然后在浏览器控制台粘它打印的那行 `localStorage.setItem(...)` 再刷新。
想变回真正的新用户：`localStorage.clear(); location.reload()`。

实测这个 fixture 的产出（6 天数据、设备 `dev-frontend-fixture`）：
窗台 **5 盆**（`#1×16`、`#2×9`、`#3×7` 带「可毕业」小标记，`#5×2`、`#6×1`）、
**`canIndulge: true`**（放纵入口出现）、`/api/history` 能看到跨天的补留列表。

> ⚠️ 它会写 **6 张** 卡的 `user_cards`，但花园只显示 5 盆——这是**对的**：
> 恰好有一张不是 `HABIT`/`EXPLORE`，被后端的 `visibleInGarden` 挡住了。
> 而那张仍然计入放纵门槛 `keptKinds`，所以入口照常出现。别把它当 bug 修。

`mysql.exe` 找不到时可以 `--mysql <路径>` 指定，或 `--sql` 只导出 SQL 自己跑。

## 接口契约（照真实响应写的，别照文档猜）

后端开了 `spring.jackson.default-property-inclusion: non_null`：**值为 null 的字段根本不出现在 JSON 里**。
`src/api/types.ts` 里因此全部是可选字段，判断只能用 `if (x)`，**不要写 `x === null`**。

```
POST /api/session                      → { userId, created, [syncCode], [deviceId], recovered }
                                         **deviceId 只有"服务端补发"时才有**（见下面身份退路一节）；
                                         设备已被认识时没有 syncCode（`non_null` 下整键消失）
GET  /api/today                        → { date, assignmentId, cardId, text, type, category,
                                           difficulty, kept, canIndulge, revealed, drawCount,
                                           maxDraws, canRedraw, [indulgenceKind], [evidence], [science] }
POST /api/today/draw                   → 同 today。第一次抽 = 揭晓并返回当天那张（不换卡）；
                                         之后 = 换掉当天那张。`?getView=true` 只读状态、不耗配额
                                         已留住 / 配额用完 → 409
POST /api/today/keep                   → 同 today（幂等：重复调用 keptCount 不涨）
POST /api/today/indulge                → 同 today；门槛不满足 → 409，且入口不出现
GET  /api/history?days=3               → 裸数组，字段同上但无 canIndulge / revealed / drawCount
POST /api/history/{assignmentId}/keep  → 单条；超 3 天 / 已留过 / 放纵卡 → 409
GET  /api/garden                       → { plantedCount, graduatedCount, items[], graduated[] }
POST /api/garden/{cardId}/graduate     → 一盆；幂等（graduatedAt 不覆盖）；非法 → 409
GET  /api/explored                     → { totalCount, from, to, items[] }；每条 { cardId, category,
                                          text, difficulty, date, kept, [evidence], [science] }
                                         **同一张卡只出现一次**，新的在前；一次都没走过时 items=[] 且无 from/to
POST /api/session/restore              → { syncCode }（**换发的新码**）。
                                         body `{ syncCode, deviceId }`，**设备必须没注册过**；
                                         码长不对 400 / 查不到 404 / 本设备已被认识 409
POST /api/session/reminder             → { time }。body `{"time":"08:00"}`；只收 HH:mm，否则 400
GET  /api/reminder.ics                 → text/calendar 正文（**不是 JSON**），每日重复、无终点
```

> ⚠️ `/api/reminder.ics` 与别的接口不一样：它返回**纯文本**（`request(..., 'text')`），
> 而且**必须用 fetch 取回来自己存文件**——写成 `<a href="/api/reminder.ics">` 的话，
> 浏览器点链接带不上 `X-Device-Id`，后端会以 **400「缺少请求头」** 拒掉。

## 「抽」：卡背 → 揭晓 → 可重抽

「今天」这一页不再直接把卡摊开：`revealed === false` 时画**卡背**，点「抽」调
`POST /api/today/draw` 揭晓（CSS 3D 翻面，640ms，`prefers-reduced-motion` 下自动降级）。

- **揭晓状态存在服务端**（`daily_assignments.revealed_at`）：刷新、换设备都保持翻开，不会重复揭晓
- **重抽 = 换掉当天那张**（没留的直接丢）。`daily_assignments` 仍然**一天一行**，
  幂等前提没变，重抽只是换掉那一行的 `card_id`
- **入口只看 `canRedraw`**：后端已算好「没留住 + 配额没用完」。`maxDraws === 0` 是无限（开发默认），
  这种时刻意**不写任何次数文案**（红线 1：不做监工）
- **留住之后不能再抽**（409）——否则一天能攒下好几张，把花园与放纵门槛的数据弄脏
- 配额由后端 `dailyseed.draw.max-per-day` 控制，生产语义是 `1`：
  `DAILYSEED_DRAW_MAX_PER_DAY=1` 即可关掉重抽

> ⚠️ `keep`（留住）**不要求先揭晓**：补留列表里的历史卡本来就没揭晓过，
> 加了这道限制会把「补留」弄坏。别顺手补这个"检查"。


依据分三级，前端据此决定画什么：

| 级别 | 拿到的字段 | 界面 |
| --- | --- | --- |
| A | `{level:'A', benefit, basis, source}` | ① 好处 ② 依据 ③ 出处 |
| B | `{level:'B', benefit, basis}` | ①②，并固定加一句「这是机制，不是研究结论」 |
| C | **连 `evidence` 键都没有** | **不显示「?」入口**（红线 3） |

> ⚠️ **「C 级」这个说法要小心**：卡片库里 `evidence_level='C'` 的卡**一张都没有**（实测 0 张）。
> 那 67 张是 `evidence_level IS NULL`，前端拿到的是**根本没有 `evidence` 这个键**。
> 所以判定只能写 `if (today.evidence)`，**绝不能写 `x === null`**——说了「C 级」，心里要清楚
> 它指的是"无依据 / 无 evidence 键"这一档。

## 模块 C 的三个落点（走过的 / 找回 / 提醒）

### 「走过的」= 探索卡的家

三类卡各进各的家，这条线是**产品结构本身**，不是排版偏好：
习惯卡 → 花园 · 探索卡 → **走过的** · 放纵卡 → 什么都不进。
后端用纯函数 `ExploredService.visibleInExplored` 守着（和 `visibleInGarden` 同一个套路）。

这一页刻意**不是成就册**：没有进度条、没有「你已探索 23/100」、没有徽章、没有连续天数。
唯一的计数是一句叙述——「这些是你走过的 23 条路」，那是回看，不是分数（红线 1）。
版式也照这个意思来：**一条带时间点的竖线**，不是一排格子。

### 「用同步码找回」= 换手机那条路

- **入口在设置页**，动作在 `components/RestoreSheet.tsx`
- **这一步刻意不走 `request()`**（`restoreSession` 直接 fetch）：`request()` 会在 401 时
  自作主张把设备重新注册一遍，而恢复的前提恰恰是**这台设备还没被认识**（已经被认识的会 409）
- 成功之后**换发新码**，`restoreSession` 内部立刻 `saveSyncCode()` 覆盖本地那一份——
  旧码在那时已经作废，不覆盖就会让用户拿着一串废码
- 成功后 `location.reload()` 走一遍干净的首屏：身份换了，today / history / garden 全得重拉
- **⚠️ `saveSession()` 在 `syncCode` 为 null 时绝不写盘**。恢复成功后那一轮 reload 会再调一次
  `POST /api/session`，而那时设备已注册、返回的 `syncCode` 是 **null**；
  照写不误的话，**刚换发到手的码会在同一次刷新里被抹掉**，设置页从此显示"还没拿到"。
  `qa-verify-bootstrap.mjs` 里有一条场景专门守它（跑的是真实的 `session.ts`）
- **连字符必须补回去**：`session.ts` 的 `canonicalSyncCode` 整理成 `K7M2-P9QX`。
  服务端哈希的是**带连字符**的那串原码，抹成 8 位裸码去查会恒定查不到——
  症状是"码明明对着，恢复却永远说没有这个码"（这条真踩过，后端同名函数那里也立了碑）

### 「每天提醒我一下」

`components/ReminderSheet.tsx`：三个预设钟点（早 8:00 / 中午 12:30 / 晚 21:00）+ 原生时间输入。
点「放进我的日历」会**先存时间、再取 .ics、然后先试分享、不行才退回下载**。

这是产品里唯一一个召回手段，而且刻意**不是我们推送**（§8.1）：到点响的是用户自己的日历。
所以这一屏不写"别忘了"、不写"坚持一下"——只问他几点想看一眼。文案改动前先读 §8.1。

> **为什么要"先分享再下载"**（`lib/format.ts` 的 `shareOrDownloadFile`）：iOS Safari 上的"下载"
> 经常只是把文件丢给某个 App，用户不知道该点哪个；而系统分享面板里"存储到文件 / 用日历打开"
> 是现成的两条路。顺序不能反——下载会立刻触发，用户就没机会看到分享面板了。
> 用户取消分享面板时返回 `'cancelled'`，**不**顺手再给他下载一遍。

## 设备身份的自愈路径（改 `client.ts` / `App.tsx` 前必读）

这一段曾经是**坏的**，而且坏得很隐蔽：页面只是**永远停在「每日一粒 + 绿点」的引导屏**
（`App.tsx` 里 `phase === 'loading' && !today`），控制台只有一行 401。四个缺陷叠在一起：

| 缺陷 | 后果 |
| --- | --- |
| `App.tsx` 的 `registering` ref 守卫**永不重置** | 401 后 `setRegisterKey` 想让 effect 重跑，被它直接 `return` 挡掉 → **永远不再注册** |
| 旧 `request()` 只清 deviceId、不负责重建 | 拿着一个未注册的新 ID 反复撞 401 |
| 注册 effect 与首屏取数 effect **并行** | `/api/today` 可能抢在 `POST /api/session` 之前发出 |
| 注册失败被 `catch {}` **静默吞掉** | 界面上毫无痕迹 |

现在的约定（**改之前先读完这段，别退回旧形状**）：

- `bootstrapDevice()`：注册**全局单飞**，注册与落盘都在这里，同一个 deviceId 不会注册两次
- `repairDevice(badId)`：401 时按**这次真正发出去的 deviceId** 去重修复。
  `repairing` 是**同步**写进去的（在第一个 await 之前）——首屏两个请求在同 tick 都撞上同一个 401，
  若等到 await 之后才登记，两个请求会**各注册一次、建出两个用户**
- `request()` 发送时**逐次记录 `sentId`**，401 后用它去修，而不是重读 localStorage
  （并发的另一个请求可能已经把它修好了，重读会把刚建好的新 ID 当成坏的再修一次）
- 自愈**只做一次**，失败就抛给上层显示**可重试的错误态**，绝不在注册/取数之间无限打转
- 回归脚本：`node qa-verify-bootstrap.mjs`（**9 个场景 + 4 道源码守卫 + 1 条反例自检**，纯 Node 无依赖）。
  它用 `typescript` 把**真实的** `src/api/client.ts` / `session.ts` / `src/lib/keepHint.ts` 转成 CJS，
  再塞进 `vm` 跑（假的 `window.localStorage` / `sessionStorage` / `crypto` / `fetch`）——
  **不再维护一份移植实现**（移植版的问题是：源码改了它没改，测试照样绿，于是它验的是一个过时的模型）。
  覆盖：并发注册只建一次 · 断网/503 **不换身份**且可重试 · 清缓存被 Cookie 认回 ·
  401 先修再重试（串行 + 并发）· 修复失败不被永久缓存 · 同步码整理与"空响应不抹码" ·
  同步码提示只提一次且可永久关闭。
  外加四道**源码守卫**（`session.ts` 的 readDeviceId/canonicalSyncCode/saveSession 还在 ·
  `restoreSession` 没退回会自作主张重注册的 `request()` · `bootstrapDevice` 用 `readDeviceId` 而不是 `ensureDeviceId` ·
  `main.tsx` 不套 StrictMode），以及**反例自检**：拿"人造旧形状"喂进同一套判据，必须被判为不合格
  （只会通过的守卫等于没有守卫）

### 身份退路：清掉 localStorage 之后还能被认出来

这是模块 D 加的，为的是填上 §6.4 那个死角——**缓存被清时 deviceId 和同步码一起消失，
后端认不出你是谁，任何"服务端保管、以后补发"都物理上送不到**。
后端多了一条 HttpOnly Cookie（`dailyseed_uid`），前端这条配合规则只有两条，但**两条都不能省**：

1. **`bootstrapDevice()` 用 `readDeviceId()`，不是 `ensureDeviceId()`**
   本地没有 ID 时**什么都不发**。一发新 ID，后端只能当成新用户建号，
   那条 Cookie 退路就永远走不到了（这也是为什么它不能走 `request()`——那个会现场生成一个 ID）。
2. **服务端补发的 `deviceId` 必须存下来**
   Cookie 是 HttpOnly 的，前端**读不到**里面的 userId；唯一能察觉"我换了个人"的途径
   就是响应体里多出来的 `deviceId`。不存的话，下一次刷新又回到"没有身份"。

> 后端那边还有一条同样重要的规则：**只要前端给了 deviceId，Cookie 一律不生效**。
> 否则用户清掉 localStorage 想重新开始，会被旧 Cookie 拽回旧花园——**永远没法重新开始**。
> 这条是实测纠正过的，`tools/verify_cookie.py` 的第 9 条守着它。

## 红线在前端的落点

改这个目录里的任何东西之前先读一遍：

- **不做监工**：不出现连续天数、打卡、红点、进度条、"你还没做"。
  **「走过的」那页的唯一计数是一句叙述**（"这些是你走过的 23 条路"），
  写成「已探索 23/100」或加个徽章就是踩线。
- **不劝服**：依据只陈述谁发现了什么；不写"你应该"。日历提醒里也一样（不写"别忘了"）。
- **C 级不给入口**：`evidence` 为空就不渲染「?」。
- **放纵门槛不公示**：`canIndulge === false` 时**连入口都不画**，不灰显、不解释。
- **花园里不出现放纵卡**：由后端 `visibleInGarden` 守，前端只照实画。
  **「走过的」同理只出现探索卡**，由 `visibleInExplored` 守。
- **`readyToGraduate` 只是"这个选项现在有意义了"**：不写任何"你该毕业了"的文案。

## 沙箱坑（在这台机器上踩过）

- **`npm install` 要加 `--ignore-scripts`**：npm 的 rebuild 阶段会 spawn 子进程，
  受限沙箱直接 `spawn EPERM`。跳过 postinstall 不影响 esbuild——它用平台专属可选包，不走脚本下载。
- **`vite.config` 必须是 `.mjs`**：Vite 加载 `.ts` 配置时也要起 esbuild 子进程编译它，同样 EPERM。
  用 `.mjs` 能让它跳过这一步；配置文件仍被 `tsconfig.node.json` 类型检查。
- **`npm run build` / `npm run dev` 在受限沙箱里会失败**（esbuild 服务进程被拒），
  在普通终端里跑没问题。DSH 里若必须跑，只能把那条命令升级为更宽权限重试一次。
- **⚠️ 起过 `npm run preview` 之后，`npm run build` 会报 `ENOTEMPTY: rmdir ...\dist\assets`**：
  预览服务器占着 `dist` 里文件的句柄，Vite 清不空输出目录。**先停 preview 再 build**。
- **开发模式不注册 Service Worker**（见 `src/main.tsx`）：SW 会让热更新看起来"没生效"。
  只有 `npm run build` 的产物才注册。
- **`main.tsx` 故意不用 StrictMode**：注册设备的 effect 只能跑一次，StrictMode 会跑两遍、多建一个用户。

## 目录

```
src/
├── api/          client.ts（唯一的网络层）· types.ts（对齐真实响应）· session.ts（deviceId / 同步码整理 / 一次性标记）
├── components/   Sheet / EvidenceSheet / Pot / GraduateConfirm / ShareSheet / SyncCodeSheet /
│                 RestoreSheet / ReminderSheet / TabBar / Toast / Tappable / CardMeta / AsyncArea /
│                 Icon（线条图标 + 植物插画，纯内联 SVG）· PageHeading（眉标 + h1 + 说明）
├── lib/          format.ts（含"分享或下载文件"的退路）· shareCard.ts（Canvas 画毕业卡）· useToast.ts · keepHint.ts
├── pages/        Today.tsx · Garden.tsx · Explored.tsx · Settings.tsx
└── styles/       base.css（设计令牌 + 外壳）· components.css（组件与页面）
public/           manifest.webmanifest · sw.js · icons/（由 tools/make_icons.py 生成）
```

毕业卡的图**完全在前端画**（`lib/shareCard.ts`）：1080×1440、Canvas、不引第三方库、不需要后端接口。


## 2026-10-11 界面与稳定性更新

米白纸张底色、植物 SVG 插画与统一线条图标。960px 起使用侧栏导航，手机保留底部导航；支持页面缩放和减少动态效果。没有增加运行时依赖，也没有外部字体或图片请求。

`node qa-verify-bootstrap.mjs` 现在会转译并执行真实的 `src/api/client.ts` / `session.ts`，覆盖并发注册、离线后重试、Cookie 恢复、401 修复与同步码保留，不再维护一份移植实现。

> **复验与交付缺口（2026-10-11 补齐）**：`npm run typecheck` 过；`verify_pwa.py` **18/18**、`verify_redlines.py` **11/11**。
> 当时留下的 `frontend/dist` 其实是**空的**（只剩 `icons/`，见交接简报 §5），已重建。
> 完整的逐文件改动、动机与实测证据见 `../docs/review-20261011/优化记录.md`，同目录有桌面（1264px）与手机（360px）截图（`.jpg`）。
>
> ⚠️ 这两张截图是 **360px** 宽，而验收清单要的是 **375px** —— 375px 那一轮仍然只能人点。

### 样式契约：改 `src/styles/**` 或 `components/Icon.tsx` 之前先读这个

```powershell
python tools/verify_redlines.py --style --selftest   # 35 条 = 11 红线 + 9 样式 + 15 自检
```

它量四件事：**对比度**（正文/次级/三级/按钮/难度 chip 都要 ≥4.5:1，且三级信息要压在**最暗的那块底**上也达标）、
**调色板**（不许出现「和某个令牌只差 ≤2/255」的一次性色；令牌外的不透明色必须白名单里且写了理由）、
**字号**（只许用 `FONT_SCALE` 里的 15 档，半像素会被拦下）、**圆角**（要么 `var(--r-*)`，要么白名单里的有机形状）、**产物同步**（dist 的 CSS 里读不到当前令牌 = 改了样式忘了 `npm run build`）。

语义、取值理由与「机器不管什么」的边界都写在 **`../docs/review-20261011/视觉规范.md`**（2026-10-11 定稿）。
这一轮据它改掉的东西：`--ink-3` `#73776b`→`#6a6e62`（4.27→4.87，最暗的侧栏底 4.53）、`--harvest` `#956638`→`#8e5f31`（4.10→4.53）、
半像素字号整数化（20→15 档）、侧栏那句的 padding 12→8px（原来只余 4px 余量，会被挤断）、
桌面端插画 230→300px 且两面 `min-height` 同步 400→440px（**必须成对改**，否则翻面会跳高）。
