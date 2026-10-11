# DailySeed · 新会话交接简报

> **怎么用**：每开一个**新模块**，先更新第 0 节，然后在新会话里把本文件贴成第一条消息，再开始干活。
> **会话名**：`DailySeed · <模块号> <内容词>`（如 `DailySeed · A 花园+毕业`）——**第一条消息第一行就写它**，界面自动取标题时也能认出来。
> **不贴也行**：只贴第 0、2、4 节（目标 / 红线 / 环境）通常就够开工了。
> **上次更新**：2026-10-11 · **当前模块**：模块 F（界面重做 + 身份凭据加固）🟡 **代码已交付并全量复验**（记录在 **§0.6**）· 上一模块：模块 E（并发正确性 + 运行期地基）✅
> **还差什么**：375px 真机逐页（§0 验收 ⑥）与阶段 0 手工发卡——**这两件只能人做**。

---

## 0. 本次模块：**E · 并发正确性 + 运行期地基** 🟡（2026-10-09）

> **下一模块开工前，把这一节整段换掉。** 模块 D 与 C 的记录已挪到 §0.8 / §0.9。

| 项 | 内容 |
| --- | --- |
| **模块** | **E · 并发正确性 + 运行期地基** 🟡 |
| **为什么做这个** | ① `verify_api.py` 当时那 53 条断言**全是串行的**，而真实用户会并发（双击「留住」、连点「再抽一张」、网络重试、PWA 切回来重新挂载）② 这套东西**起不来也发布不出去**——没有部署产物、没有健康检查、没有运行期可观测性，而那正是阶段 0（手工发卡）的前置条件 |
| **验收** | ① `mvn test` **57/57**（模块 F 加了 3 个）、`npm run typecheck` 过；`npm run build` 要在**普通终端**里跑（受限沙箱里 esbuild 会 `spawn EPERM`，见 §5）✅<br>② `verify_api.py` **57/57**（8080；经 4173 代理；容器经 nginx）——对着**生产开关**的后端（配额=1 + Secure Cookie）是 **56/56 + 1 SKIP**：C23 在 http 下按规范不适用，脚本会自己说明 ✅<br>③ `verify_health.py` **12/12**（本地口径）；`--prod` 在生产开关下 **15/15** ✅<br>④ `verify_cookie.py` **19/19**（模块 F 加了两条「伪造令牌」攻击路径）✅<br>⑤ `verify_concurrency.py` **4/4**（配额=1 的后端 + 无限配额的后端各一遍）✅<br>⑥ 375px 真机逐页（清单：`DailySeed-真机验收清单.md`）⬜ **待你点** |

### 0.1 这一轮抓到的两个真 bug（都不是报错型，串行测试完全无感）

| bug | 症状 | 为什么串行测试抓不到 | 修法 |
| --- | --- | --- | --- |
| **`addKept` 无条件自增** | 并发 8 次「留着」→ `kept_count` 变成 **5、6、7**。而它驱动**毕业小标记 ≥7**（§6.1）和放纵日门槛 —— 也就是说**手抖连点几次就能刷出毕业入口** | `verify_api.py` 的 A13 是串行的、本来就绿；Service 里的 `isKept()` 读检查在串行下永远成立 | 让 `markKept` 返回"是否真的改了行"，**只有返回 true 的请求去加计数**（`WHERE state <> 'KEPT'` 保证并发下只有一个） |
| **`redraw` 无条件更新** | N 次并发重抽，`draw_count` 只 **+1** —— 配额形同不存在；而且两次重抽会共用同一个选卡种子（种子里含 drawCount），抽到同一张 | 同上：串行下每次重抽都读到最新 count | 条件更新 `WHERE draw_count = :n`；失败就**重读重算**（有界，最多让 3 次） |

**通用教训**：**读检查挡不住并发，只有写条件挡得住**（`WHERE state <> 'KEPT'` / `WHERE draw_count = :n`），
而且**必须用返回行数决定下一步**——`update()` 的返回值不是装饰。

### 0.2 运行期地基（阶段 0 的前置条件）

| 交付 | 为什么 |
| --- | --- |
| `GET /api/health`（**不需要身份**） | 匿名、无推送、无账号的产品**没有任何用户会来报错**；出了事你只看到"没人用"，而"没人用"和"服务坏了"从外部一模一样。一条请求说清：迁移到位吗、库连得上吗、种子灌进去了吗、时区对得上吗、退路配得自洽吗 |
| 活动计数（**零 PII**，只看今天） | 把"没人用"和"服务坏了"分开。**只 +1，不记是谁、不累计、不持久化**——累计数会变成增长指标，那是红线 1 的另一面 |
| 优雅停机 + 20 秒收尾 | 每一次写请求都可能是一次「留着」，被硬杀在半路用户会看到"点了没反应" |
| `Dockerfile` × 2 + `docker-compose.yml` + `.env.example` + `tools/dev.ps1` + `tools/deploy.sh` | **上手就能跑**。⚠️ **Docker 没有实测过**（这台机器上 daemon 没起来），当草稿看待 |

### 0.3 健康检查的一条设计界（踩过才划清）

**ready（影响 200/503）** 和 **warnings（不影响）** 必须分开：

- `ok` 只管"能不能接流量"：库、迁移、种子、时钟、身份退路自洽
- 配置风险（无限重抽、非 secure Cookie）走**独立的 `warnings` 列表**

最初把两者混在一起，于是**本地开发机返回 503**（因为配额是 0、Cookie 没 secure）——
编排系统看到 503 会拒绝把流量打给一台其实完全正常的机器。**"该不该上线"和"能不能接流量"是两件事。**

### 0.4 仍然开着的（下一个模块或你拍板）

1. ✅ **Docker 产物已实测通过**（2026-10-10）：`docker compose --env-file backend/.env -f docker-compose.yml -f docker-compose.alt-ports.yml up -d --build` → 三个容器全部 healthy，`/api/health` 直连 **200**、经 nginx 也 **200**；`verify_api.py` 对着容器的栈跑 **57/57**，夹具 `verify_qa_fixtures.py` **43/43**。**顺带修掉一个真 bug**（nginx `add_header` 继承，见 §5）
2. **两个真机没确认的退路**：iOS Safari 的 `navigator.share({files})`（毕业卡、`.ics` 都走"先分享、退下载"）
3. **阶段 0（手工发卡）还没做**——唯一**不能跳过**的一步。代码再干净，没有人真的领过一粒、没人回过"留着"，就不知道卡片质量够不够
4. 卡片难度分布是否动态调整 · 放纵日门槛是否公示（当前不公示）· C 级卡是否显示「这张我也说不出根据」· 科普库是否继续扩
5. **留住之后要不要允许继续抽**：现在不允许（409）。要动之前先想清楚它和 `keptCount`、放纵门槛的关系（**并发那道闸门也在这条路上**）

### 0.5 为验收 ⑥ 铺的路：真机夹具重做（2026-10-10）

- **四台验收设备改成一条命令重建**：`python tools/seed_dev_user.py --qa`，夹具写在脚本的
  `QA_FIXTURES` 表里、**「今天」按运行时日期算**，`tools/verify_qa_fixtures.py`（43 条）守着"库里 = 清单"。
  为什么必须改：那三台以前是**手写 SQL** 塞的，而轮转选卡撞不出"今天正好是 25 号"；
  10-10 实测后果——三台的「今天那张」**还停在 10-09**，一打开页面就被后端换成别的卡，
  清单上 A/B/无依据的对照一条都点不出来，而清单自己看不出来。
- **顺带抓到造数脚本的两个真 bug**（原来那几台是手写 SQL 塞的，所以这两个坑一直没被踩到）：
  1. **`SELECT id INTO @uid FROM user_devices` 取错了列**——`user_devices` 有**自己的**自增主键 `id`，
     这句拿到的是"设备行的编号"，不是"这个人"。它**碰巧能用**：造一个用户配一台设备时两张表的自增
     是同步的。一旦错位（实测 users 到 701、user_devices 到 862），轻则外键报 **1452**，
     重则**安静地把数据写到别人的账号上**（那时脚本打印的摘要依然漂亮）。已全部改成 `SELECT user_id INTO`。
  2. **MySQL 的 `SELECT ... INTO @var` 在「零行」时\*\*不改动变量\*\***（实测：`@u` 先赋 42，
     再查一个不存在的设备，`@u` 还是 42）。于是**一次造多台**时，"新设备"会沿用上一台的 `@uid`
     → 两个 `device_id` 挂到同一个账号上、互相覆盖；一台一个进程时**完全看不出来**。
     `--clean` 那条最危险：它的最后一句是 `DELETE FROM users WHERE id = @uid`，会**删错人**。
     已在每个 `SELECT INTO` 前显式置 NULL。
  现在造数脚本**造完自己回读**（设备 → 账号 / 发放条数 / 花园行数），对不上就非零退出；
  夹具另有 `tools/verify_qa_fixtures.py` 从接口侧核 43 条。
- **清单里「三台设备 `canIndulge` 都是 false」那条是错的**：门槛是"累计留住过 ≥5 种"，
  而这几台的花园正好 5 盆 → 门槛当天就满足。已改成"两条都看"（门槛满足时**会**画出来，
  点它验放纵卡不进花园；门槛没到用全新设备验"完全不画"）。

---

## 0.6 2026-10-11 追加轮：**F · 界面重做 + 身份凭据加固** 🟡（不在原计划里）

> ⚠️ **本节比 §0.8 / §0.9 新**：上面那一段（§0 与 §0.1–§0.5）仍是模块 **E（2026-10-09）** 的记录。
> 界面 / 文案 / 身份凭据以本节为准——**§0 里凡是提到「抽」按钮、深色底、Cookie 存 `userId` 的地方都已被本轮改掉**。
> 这一轮的前后端由**另一个模型**动手改，交接时只留了 `frontend/README.md` 的一小节。
> 我这边做的是**全量复验 + 补齐交付面**：逐文件差异、每处的动机与实测证据都在
> `docs/review-20261011/优化记录.md`（同目录有两张截图）。

| 项 | 内容 |
| --- | --- |
| **后端** | ① Cookie 里的自增 `userId`（可枚举 → 可冒充）换成 **256 位随机恢复令牌**，库里只存 SHA-256 + 400 天到期（新增 `V5__recovery_tokens.sql` / `RecoveryTokenStore`）；②「走过的」列表的 N+1 查询改成一次 `IN (:ids)`；③ `createAnonymous` 加 `@Transactional`；④ `graduate` 返回"实际发生了没有"，失败时不再关弹层、不再拿过期数据开分享卡 |
| **前端** | 米白纸张底色（原深色）+ 植物 SVG 插画 + 统一线条图标；960px 起左侧栏、手机保留底部导航；**去掉 `user-scalable=no`**（恢复缩放）；底部弹层做成**栈**（只有顶层响应 Esc/Tab、焦点还给打开它的元素、body overflow 只在首尾处理）；触控目标补到 44px；`bootstrapDevice` 的 catch **收窄**（瞬时断网不再丢掉原账号）；花园/走过的各自独立错误态；一页一个 `<h1>` |
| **复验结果（2026-10-11）** | `mvn test` **57/57**（54 + 3）· `verify_api.py` **57/57** · `verify_cookie.py` **19/19**（17 + 2 条伪造令牌）· `verify_health.py` **12/12** · `verify_qa_fixtures.py` **43/43** · `verify_pwa.py` **18/18** · `verify_redlines.py` **11/11（+8 自检）**、**`--style --selftest` 35/35**（11 红线 + 9 样式 + 15 自检） · `qa-verify-bootstrap.mjs` **9 场景 + 4 道源码守卫 + 1 条反例自检** · `npm run typecheck` 过 |
| **同轮补掉的交付缺口** | ① `frontend/dist` 当时是**空的**（只剩 `icons/`）→ 已重建并复验；② 交接文档还在描述旧界面（「抽」按钮、"点一下，看是什么"）→ 已按新界面改写（含验收清单）；③ `frontend/README.md` 引用的 `docs/review-20261011/优化记录.md` **不存在** → 已补写；④ 那两张截图其实是 JPEG 却命名 `.png` → 已改名 `.jpg`；⑤ `verify_pwa.py` / `seed_dev_user.py` 在 cp936 控制台上会崩 → 已修（见 §5）；⑥ **界面里三处小字低于 WCAG AA、侧栏那句被 `<br/>` 挤断、桌面卡片"只变宽没变构图"、调色板漂到 40 个色 / 字号 20 档** → 全部**先算数再改**（`--ink-3`、`--harvest` 换成刚好达标的取值；半像素字号整数化到 15 档；插画 230→300px、两面 400→440px），并把判据写成 `--style` 断言、立了 `docs/review-20261011/视觉规范.md` |
| **仍然待你点** | 375px 真机逐页（§0 验收 ⑥）· 阶段 0 手工发卡（§8 第 10 条） |

---

## 0.8 上一模块：**D · 上线前收尾** ✅（2026-10-09）

| 项 | 内容 |
| --- | --- |
| **模块** | **D · 上线前收尾**（身份退路 / `.ics` 分享退路 / 启动护栏）✅ |
| **目标** | 把三件"会真出事但我一直拖着"的事做完：① 清缓存再也找不回来 ② iOS 上 `.ics` 点不下去 ③ 忘了改配置就上线，把无限重抽带上生产 |
| **实际交付** | **后端**：`SessionCookie`（HttpOnly `dailyseed_uid`）· `/api/session` 改成「认设备 → 认 Cookie → 建新号」并补发 `srv-` 前缀的 deviceId · `StartupGuard`；**仍然零迁移**<br>**前端**：`bootstrapDevice` 改用 `readDeviceId()`（不生成新 ID，把路让给 Cookie 退路）· 存下服务端补发的 deviceId · `shareOrDownloadFile()`（先分享、退下载）· 一次性提示「认出你了」 |
| **决策** | **退路的适用面故意很窄**：只有**连 deviceId 都拿不出来**时才认 Cookie。**只要前端给了 deviceId，Cookie 一律不生效**——实测发现，否则用户清掉 localStorage 想重新开始，会被旧 Cookie 拽回旧花园，**永远没法重新开始** |

---

## 0.9 上一模块：**C · 探索记录 / 同步码恢复 / `.ics` 提醒** ✅（2026-10-09）

| 项 | 内容 |
| --- | --- |
| **模块** | **C · 探索记录 / 同步码恢复 / `.ics` 提醒**（三个后端接口 + 三个前端落点）✅ |
| **实际交付** | **后端**：`GET /api/explored`（`explored/` 新包）· `POST /api/session/restore`（`RestoreService`）· `GET /api/reminder.ics` + `POST /api/session/reminder`（`reminder/` 新包）；**零迁移**<br>**前端**：TabBar 三页 → **四页**（今天 / 花园 / 走过的 / 设置）· `pages/Explored.tsx`（一条带时间点的竖线，不是格子）· `components/RestoreSheet.tsx` / `ReminderSheet.tsx` |
| **决策** | 先做后端再动前端 · 允许换发新码但**拒绝「给自己恢复」**（409）· 「走过的」显示**全部走过的**、保留住的标一下 · 提醒时间 = 三个预设 + 原生输入 |

### 0.9.1 模块 C 的三条教训（§5 有详细版）

1. **凭据的"规范形态"必须和落库时那一串逐字一致**：`RestoreService` 把码抹成 8 位裸码去查哈希，
   而库里哈希的是**带连字符**的 `K7M2-P9QX` → 恒定 404。纯函数测试只断言"长度是 8"抓不住它
2. **别用 `replaceAll("[^0-9A-Za-z]", "")` 剥分隔符**：Unicode 语义下**全角空格**会被当成字母数字躲过去
3. **跨"页面重载"的状态变更要专门问一句「重载之后跑的那段代码会不会把它覆盖掉」**：
   恢复成功后 reload 会再调一次 `/api/session`，那次 `syncCode` 是 null，`saveSession` 照写就抹掉了刚换发的码


---

## 1. 一句话背景

**DailySeed（每日一粒）**：每天给你一个很小的约定。想做就做，觉得好就**留着**它；留久了它自己长成你的习惯。PWA、无推送、匿名 8 位同步码、毕业由用户自己宣布。

**用户**：Java 后端方向的学生，每天能投入 3-4 小时，不擅长前端，最想听到的评价是「你怎么想到的」——**巧思优先于技术深度**。

---

## 2. 红线（违反任何一条都要停下来重做）

| #   | 红线                                    | 原因                                |
| --- | ------------------------------------- | --------------------------------- |
| 1   | **不做监工**：不打卡、不连续天数、不红点、不催促、不问"做了没有"    | 第一原则。只问"这张还要吗"                    |
| 2   | **不劝服**：依据只陈述"谁发现了什么"，不写"你应该"          | 「?」是防"儿戏"的，不是营销文案                 |
| 3   | **没有依据就不显示「?」入口**（C 级卡）               | 诚实是信任资产；没依据就承认                    |
| 4   | **有争议 / 复制失败的研究一律不用**                 | 已列排除清单，见卡片库 **10.1**——补依据前先查那张表   |
| 5   | **放纵卡不进花园、不可毕业、不计入"留住"**              | 放纵是允许，不是收集                        |
| 6   | **放纵日门槛不公示**                          | 一公示，用户就会为攒放纵而表演自律                 |
| 7   | **花钱的卡不写金额**，写「按你自己的预算」               | 自己定的数天然不会后悔                       |
| 8   | **只改 `.md`**；`.docx`/`.pdf` 是冻结快照，不维护 | 用户明确要求                            |
| 9   | **每步先讨论方案再动手**                        | 用户明确要求                            |

> **其中能机器判定的部分由 `tools/verify_redlines.py` 守着（11 条 + 8 条自检）**：产物里没有任何
> "还剩/已抽/进度"文案、监工与催促的词**只允许出现在否定句里**（"留着不是打卡"是好文案，
> 一刀切的词表会把好文案判成违规）、没有可加载的第三方源、「?」入口与放纵分支的结构守卫、
> 放纵卡金额与难度、§10.1 排除清单还在。**语气、卡片质量、'巧思'仍然只能人看。**

---

## 3. 已完成且已验证的资产（不用重做）

| 资产                  | 状态与证据                                                              |
| ------------------- | ------------------------------------------------------------------ |
| 产品设计文档              | **v1.8**（v1.8 = 毕业卡分享改为第一版就做），`DailySeed-产品设计文档.md` **唯一维护源** |
| 卡片库                 | **v2.2**，100 张（HABIT 42 / EXPLORE 38 / INDULGE 20）+ 依据库 A 6 / B 27 + 科普 8 |
| 数据库                 | **MySQL 8.0.37** `dailyseed`（InnoDB / utf8mb4），5 张业务表 + Flyway 历史表（4 个迁移全 success） |
| 后端                  | Spring Boot 3.3.5 / Java 21 / Maven，**12 个接口 + 57 个单测全绿** |
| 花园 + 毕业（模块 A ✅） | `GET /api/garden`（只含习惯卡）+ `POST /api/garden/{id}/graduate`（幂等）；重启后数据仍在 |
| **接口契约**            | **以真实响应为准的长表在 `frontend/README.md`**（含 `non_null` 导致字段会整键消失这件坑） |
| **前端（模块 B + C 🟡）** | `frontend/`：React 18 + Vite 5 + TS；**四页**（今天 / 花园 / 走过的 / 设置）；`npm run typecheck` / `npm run build` 全过；页面 + manifest + 图标 + SW 均 200；`/api` 代理转发正常 |
| **「抽」的形式 ✅**（2026-10-11 改文案） | 卡背（植物插画 +「一件小事，也会慢慢发芽。」+ 一个**「打开今天这一粒」**按钮）→ **640ms 3D 翻面**揭晓 → 可重抽（`POST /api/today/draw`）。`V3__draw.sql`（`revealed_at` / `draw_count`）+ `V4__backfill_revealed.sql`（回填历史）。配额 `dailyseed.draw.max-per-day`，**`0 = 无限`（开发默认）**，`DAILYSEED_DRAW_MAX_PER_DAY=1` 切回生产语义。留住后不能再抽（409）；揭晓状态存服务端，刷新不回卡背 |
| **探索记录（模块 C ✅）**   | `GET /api/explored` + `pages/Explored.tsx`。只含探索卡（`ExploredService.visibleInExplored` 纯函数守着），同卡按**最后一次**遇见去重，查询**不带天数上限** |
| **同步码恢复（模块 C ✅）** | `POST /api/session/restore` + `RestoreService` + `RestoreSheet.tsx`。码本身就是凭据（库里只有 SHA-256 哈希）；成功即**换发新码**、旧码作废；本设备已被认识 → 409；码长不对 400；查不到 404。**零迁移** |
| **`.ics` 提醒（模块 C ✅）** | `POST /api/session/reminder`（存时间）+ `GET /api/reminder.ics`（生成文件）+ `ReminderSheet.tsx`。**零迁移**（`users.remind_at` 一直就在库里）。`RRULE:FREQ=DAILY` 无 `UNTIL`、按用户时区、折行按 UTF-8 字节 |
| **身份退路（模块 D ✅，模块 F 加固）** | `SessionCookie`：HttpOnly 的 `dailyseed_uid`，值是一串 **256 位随机恢复令牌**（库里只存 SHA-256 + 400 天到期，`V5__recovery_tokens.sql`），**只在连 deviceId 都拿不出来时**参与认人；认出来后由服务端补发 `srv-` 前缀的 deviceId。**2026-10-11 之前它存的是自增 `userId`——那是可枚举的凭据，猜一个数字就能读别人的花园**。`verify_cookie.py` **19/19** 守着它（含"给了 deviceId 就不看 Cookie"与"伪造令牌认不出人"两组反例） |
| **启动护栏（模块 D ✅）** | `StartupGuard`：`draw.max-per-day=0` 却没承认开发模式 → **拒绝启动**。实测过（`APPLICATION FAILED TO START`）。它**永不改配置**，只把该设什么写在错误里 |
| **文件分享退路（模块 D ✅）** | `lib/format.ts` 的 `shareOrDownloadFile()`：先 `navigator.share({files})`、不支持才退回下载；用户取消时不再补一次下载。`.ics` 与毕业卡共用这套判断 |
| **运行期地基（模块 E ✅）** | `GET /api/health`（不需要身份；200 = 可接流量 / 503 = 别接；探测项 + 配置 warnings + 今天的活动计数）· `ops/ActivityCounters`（零 PII，只 +1，跨零点整体 CAS 翻页）· 优雅停机 20s · `tools/verify_health.py`（`--prod` 按上线标准判配置） |
| **并发闸门（模块 E ✅）** | `markKept` 的 `WHERE state <> 'KEPT'` + `redraw` 的 `WHERE draw_count = :n`，**都靠返回行数决定下一步**。`tools/verify_concurrency.py` 4/4（抓出过两个真 bug，见 §0.1） |
| **部署产物（模块 E ✅ 已实测 2026-10-10）** | `backend/Dockerfile`（两段构建、非 root、`/api/health` 做 HEALTHCHECK）· `frontend/Dockerfile` + `frontend/deploy/templates/default.conf.template`（nginx：SW 与 index.html 不缓存、哈希产物长缓存、同域反代 /api、CSP）· `docker-compose.yml`（MySQL 带 healthcheck 让后端等它真能连）· `docker-compose.alt-ports.yml`（本机已有开发环境时的端口覆盖）· `backend/.env.example` · `tools/dev.ps1` · `tools/deploy.sh`。**实测结果**：三容器 healthy；`/api/health` 直连与经 nginx 均 **200**；`verify_api.py` 对容器 **57/57**；夹具 **43/43** |
| **PWA 静态契约（2026-10-10 新增）** | `tools/verify_pwa.py` **18/18**：manifest 必填项与图标（192/512/maskable 都取得到）、**index.html 里 rel=icon / apple-touch-icon 的链接都取得到**、产物名带内容哈希、页面无第三方源、SW 与源码逐字节一致、**SW 预缓存的每一项都存在**、SW 明确不碰 `/api/**`。把 PWA 那节里能机器判定的部分从"眼睛看"变成了"跑一遍"。**前提是 `frontend/dist` 真的构建过**：`verify_redlines.py` 现在会在 dist 空/缺 `index.html` 时直接红一条（以前是安静跳过，见 §5） |
| **红线巡检（2026-10-10 新增）** | `tools/verify_redlines.py` **11/11（+8 条自检）**、**加 `--style` 另 9 条样式断言（对比度 / 调色板 / 字号 / 圆角 / 产物同步）+7 条自检**（判据与实测数见 `docs/review-20261011/视觉规范.md`）：产物里没有任何「次数/进度」文案、监工与催促的词**只允许出现在否定句里**、没有可加载的第三方源、「?」入口与放纵卡分支的结构守卫、放纵卡不写金额且难度恒 0、§10.1 排除清单还在。⚠️ 三个判据都是踩过假阳性才定的（词表会把"留着不是打卡"判成违规、`元|块` 会把"时间块"判成金额、`http` 会把 w3.org 命名空间判成第三方） |
| **毕业卡分享图**          | 纯前端 Canvas（1080×1440），`frontend/src/lib/shareCard.ts`；不放二维码与号召语 |
| **前端测试数据**          | `tools/seed_dev_user.py`：造「用了 N 天」的用户（否则花园跨天视图 / 毕业小标记 / 放纵入口都看不到）。**实测产出**：6 天数据 → 花园 **5 盆**（16/9/7/2/1 次，前三个带「可毕业」标记）+ `canIndulge:true` + 跨天补留列表。手动反复验「抽」用 `--reset-today`（今天那张复活）/ `--fresh`（换新设备名） |
| **真机验收夹具（模块 E 收尾新增）** | `tools/seed_dev_user.py --qa`：四台验收设备（`-a` A 级 / `-b` B 级 / `-none` 无依据 / `dev-c-owner` 恢复来源）**按运行时日期重建**，同步码写死（`A4R7-M2QX` / `B6T3-N9KP` / `C2W5-P8JZ` / `D7X4-Q3MN`）。原来那三台是手写 SQL 塞的，**日期一过就失效**（10-10 实测：还停在 10-09 那张）。守着它的是 `tools/verify_qa_fixtures.py`（43 条，期望值从夹具表推出来） |
| 接口断言                | `tools/verify_api.py` **57/57 PASS**（编号的 A1–A13 与 C1–C28，另加 16 条早期身份/取卡断言）、`tools/verify_cookie.py` **19/19 PASS**、`tools/verify_health.py` **12/12 PASS**、`tools/verify_concurrency.py` **4/4 PASS**、`tools/verify_catchup.py` **4/4 PASS**、`tools/verify_pwa.py` **18/18 PASS**、`tools/verify_qa_fixtures.py` **43/43 PASS**、`tools/verify_redlines.py` **11/11 PASS（+8 自检）** |
| 身份与同步码回归            | `frontend/qa-verify-bootstrap.mjs` **9 个场景 + 4 道源码守卫 + 1 条反例自检全过**（纯 Node，无依赖，**跑的是 `src/api/*.ts` 与 `src/lib/keepHint.ts` 的真源码**——用 TS 编译器转成 CJS 后塞进 `vm`，假 `localStorage`/`crypto`/`fetch`）：并发注册只建一次 · 断网/503 **不换身份**且可重试 · 清缓存被 Cookie 认回 · 401 先修再重试（串行与并发各一条）· 修复失败不被永久缓存 · 同步码整理与「空响应不抹码」 · 同步码提示只提一次且可永久关闭 · 四道源码守卫（含「守卫本身会不会报」的反例自检）。⚠️ 这一轮把它从「移植版 20 条」换成了「真源码 9+4+1 条」，**覆盖方向更真、条数更少**，旧版那四道守卫已补回 |
| 种子生成                | `tools/gen_seed.py`：卡片库 md → SQL 种子 + 科普 JSON（**md 是唯一源**）            |
| 表结构导出               | `docs/db-schema.sql`（真实 `mysqldump`，86 行）                          |

**行数实测**（2026-10-09，跑过几轮验证脚本之后）：`cards=100` · `daily_assignments=149` · `user_cards=74` · `users=178` · `flyway_schema_history=4`

> 验证脚本每跑一次就开一批新设备，所以后三个数字只会涨——它们是测试数据，不是健康指标。
> 只有 `cards=100` 是硬约束（`gen_seed.py` 会校验）。

---

## 4. 环境与命令

```
JDK 21 · Maven 3.9.11 · MySQL 8.0.37（D:\MySQL\MySQL Server 8.0）
库：dailyseed（utf8mb4）· 用户 root · 口令在 backend/.env（已 gitignore，不要提交）
```

```powershell
# ⚠️ mvn 都在 **backend/** 里跑：仓库根没有 pom.xml，`.m2repo` 也在 backend/ 底下。
#    （`.env` 也是按**进程工作目录**找的，所以在根下跑会读不到库口令。）
cd backend

# 跑单测（-D 的引号必须有，否则 PowerShell 会拆参数）
mvn "-Dmaven.repo.local=.m2repo" test

# 起服务（后台跑，端口 8080）
mvn "-Dmaven.repo.local=.m2repo" spring-boot:run
```

```powershell
# 验证（服务在跑时执行）——下面这些脚本都在**仓库根**的 tools/ 下，所以先回根目录：
cd ..

python tools/verify_api.py               # 57 条：业务行为（串行）
python tools/verify_health.py            # 12 条：状态与配置（能不能见人）
python tools/verify_cookie.py            # 19 条：身份退路（cookiejar 模拟两台浏览器 + 两条伪造令牌）
python tools/verify_concurrency.py       # 并发不变量（① 需要配额有限的后端，见下）
python tools/verify_catchup.py <deviceId> <inWindowId> <outWindowId>

# 真机验收那四台设备（★ 点清单之前先跑这两条，见《真机验收清单》§1）
python tools/seed_dev_user.py --qa       # 按**运行时日期**重建四台（A 级 / B 级 / 无依据 / 恢复来源）
python tools/verify_qa_fixtures.py       # 43 条：核这四台是不是真长成清单说的样子

# PWA / 静态契约（18 条：manifest+图标、index.html 的图标链接、产物名带哈希、SW 与源码一致、预缓存都存在、SW 不碰 /api）
python tools/verify_pwa.py               # 默认对着 4173 预览页；也可以 python tools/verify_pwa.py http://127.0.0.1:18088

# 红线巡检（11 条 + 8 条自检）：产物+卡片库里"能机器判定的那部分"红线
python tools/verify_redlines.py          # 加 --selftest 会额外验证"检测器本身会不会报"
# 样式契约（对比度/调色板/字号/圆角）：改了 src/styles/** 或 Icon.tsx 就跑它
python tools/verify_redlines.py --style --selftest   # 35 条 = 11 红线 + 9 样式 + 15 自检

# 前端身份回归（9 场景 + 4 道源码守卫 + 1 条反例自检；纯 Node，不需要浏览器与后端）
cd frontend; node qa-verify-bootstrap.mjs; cd ..

# ★ 再对着代理跑一遍——那才是浏览器的真实路径（见 §5「验证脚本经代理会假失败」）
python tools/verify_api.py http://localhost:5173
python tools/verify_cookie.py http://localhost:4173

# 并发实验：另起一个配额=1 的后端（不动 8080 上正在用的那个；★ 记得先 cd backend）
$env:DAILYSEED_DRAW_MAX_PER_DAY="1"; $env:DAILYSEED_DEV_MODE="true"
mvn "-Dmaven.repo.local=.m2repo" spring-boot:run "-Dspring-boot.run.arguments=--server.port=8081"
cd ..      # 下面这条是根目录下的脚本
python tools/verify_concurrency.py http://localhost:8081 --workers 12 --rounds 16

# 重新生成种子（改了卡片库 md 之后）
python tools/gen_seed.py
```

**开发/生产的几个开关**（都有默认值，本地靠 `backend/.env`；完整样例见 `backend/.env.example`）：

| 变量 | 默认 | 本地 | 生产 |
| --- | --- | --- | --- |
| `DAILYSEED_DRAW_MAX_PER_DAY` | `0`（无限） | `0`，连着抽看手感 | **`1`** |
| `DAILYSEED_DEV_MODE` | `false` | **`true`**（承认无限重抽，`.env` 里已有一份） | **不设** |
| `DAILYSEED_SESSION_COOKIE_ENABLED` | `true` | `true` | `true`（身份退路） |
| `DAILYSEED_SESSION_COOKIE_SECURE` | `false` | `false`（http） | **`true`**（https） |

> 前两行是**连在一起**的：`0` + 没承认开发模式 = **应用拒绝启动**（`StartupGuard`）。
> 所以"忘了改配置就上线"会当场炸掉，而不是安静地把无限重抽带上生产。

```powershell
# ── 前端（模块 B）─────────────────────────────
cd frontend
npm install --ignore-scripts --cache ".npm-cache"   # 必须 --ignore-scripts，见 §5
npm run dev            # http://localhost:5173（需后端在 8080 跑着）
npm run typecheck      # 两个 tsconfig 都查
npm run build          # typecheck + vite build

# 造一个"用了几天"的测试用户（否则花园跨天视图 / 毕业小标记 / 放纵入口都看不到）
python tools/seed_dev_user.py --days 6
```

> 前端细节（接口契约 / 沙箱坑 / 红线落点）都在 **`frontend/README.md`**，改前端前先读它。

**接口**（共 **12** 个）：`POST /api/session` · **`POST /api/session/restore`** · **`POST /api/session/reminder`** · `GET /api/today` · `POST /api/today/draw`（抽：第一次揭晓、之后重抽；`?getView=true` 只读不耗配额） · `POST /api/today/keep` · `POST /api/today/indulge` · `GET /api/history` · `POST /api/history/{id}/keep` · `GET /api/garden` · `POST /api/garden/{cardId}/graduate` · **`GET /api/explored`** · **`GET /api/reminder.ics`**

> 要说"12 个"就别把 `/api/reminder.ics` 数漏——它的路径不带 `session` 前缀，容易在盘点时被忘掉。
> ⚠️ 旧版本这里写的是 `POST /api/today/swap` 和 `GET /api/cards/{id}/why`——**两个都不存在**（换卡是 `indulge`；依据不单开接口，直接跟在 `today` / `history` / `garden` / `explored` 的响应里）。
> ⚠️ **`/api/session/restore` 不需要 `X-Device-Id`**（它就是在建立身份），但 **`/api/session/reminder` 和 `/api/reminder.ics` 需要**。

> **新会话第一步：先探服务是否还活着。** 后台任务绑在**旧会话**上，新会话里通常已经不在了。
> `Invoke-WebRequest http://localhost:8080/api/history -Headers @{"X-Device-Id"="probe"} -UseBasicParsing` 返回 **401 就是活着的**（401 是服务端真实回应，不是连不上）；
> **但这条判据有盲区，别只靠它**——还要证明这是 DailySeed 而不是别的服务：用
> `POST /api/session` 传一个随机 `deviceId`，**应返回 200 + 新同步码**（只有我们的 SessionController 有这个接口）。
> 两条判据与「找/停占用进程」的沙箱坑都记在 §5 的「探针 401 有盲区」那一条里。连不上再按上面命令重启。
>
> ⚠️ **别把不带请求头的那次 400 当成服务坏了**：`/api/history` 不带 `X-Device-Id` 返回的是 **400**（缺必需请求头），空串或假设备才是 **401**。两种都不是"连不上"。
> ⚠️ 不要用 `Get-NetTCPConnection -LocalPort 8080` 判断——实测它在服务正常时会误报"没监听"。

---

## 5. 已知坑（踩过一次，别再踩）

- **MySQL 方言**：没有 `RETURNING`（用 `KeyHolder`）；`ON DUPLICATE KEY UPDATE` 而非 `ON CONFLICT`；`DATETIME(6)` / `CURRENT_TIMESTAMP(6)`；`text` 是保留字必须加反引号；用 `BOOLEAN` 而非 `TINYINT(1)`（后者触发弃用告警）
- **⚠️ 别把 `user_devices.id` 当成 `users.id`**（2026-10-10，造数脚本踩的）：
  `seed_dev_user.py` 里一直是 `SELECT id INTO @uid FROM user_devices WHERE device_id = @dev` ——
  `user_devices` 有它**自己的**自增主键 `id`，所以这句拿的是"设备行的编号"，不是"这个人"。
  它**碰巧能用**（造一个用户配一台设备时两张表的自增同步）；错位之后轻则外键 1452，
  重则把夹具数据**安静地写到别人的账号上**。修法：`SELECT user_id INTO @uid ...`。
  **通用教训：跨表取外键时永远写清楚列名——"看起来对"是这类 bug 唯一的伪装**
- **⚠️ MySQL 的 `SELECT ... INTO @var` 在「零行」时\*\*不改动变量\*\***（2026-10-10 实测）：
  先 `SET @u := 42`，再 `SELECT id INTO @u FROM user_devices WHERE device_id='不存在的'`，`@u` **还是 42**。
  后果很具体：脚本里 `SELECT id INTO @uid ...` 后面跟着 `INSERT ... WHERE @uid IS NULL`（建新账号）
  和 `DELETE ... WHERE user_id = @uid`（清旧数据）时，**零行并不等于"没有这个人"**，
  于是"新设备"会沿用**上一台设备**的 `@uid` —— 两个 `device_id` 挂到同一个账号上互相覆盖。
  **一台设备一个进程时完全看不出来**（`@uid` 本来就是 NULL），一次造多台就必踩；
  `--clean` 那条尤其危险，它的最后一句是 `DELETE FROM users WHERE id = @uid`，会**删错人**。
  修法：每个 `SELECT INTO` 之前显式 `SET @uid := NULL;`。用 `SELECT 1 INTO @flag ... HAVING COUNT(*)=1`
  做"存在性判断"时同理——**先给 @flag 一个默认值**，零行时它就保持那个默认值（这个特性反过来很好用）
- **卡片 id 不按类型连续**：HABIT 是 1–79、EXPLORE 是 4–80 **交错**的，只有 INDULGE（81–100）是一整段。**别假设 1–42 都是习惯卡**（单测里那个 1–42 的池子是构造出来的假数据）
- **`keep` 曾经不幂等**：同一天连点 3 次 `keptCount` 就是 3，而它驱动「毕业小标记 ≥7」和放纵日门槛。已修（留过就原样返回），`verify_api.py` 的 **A13** 守着它——改 `keep()` 前先想清楚这一点
- **沙箱下 `Get-CimInstance Win32_Process` 会「拒绝访问」**：找后端进程用 `Get-Process java` + `netstat -ano | Select-String ":8080"`；`mvn spring-boot:run` 是 Maven 一个 java 进程 + 被 fork 的应用一个 java 进程，**两个都停**才算停干净
- **`mysql.exe` 在 PowerShell 里写反引号**（列名 `` `text` ``）要用**单引号**包 SQL，双引号里的反引号会被 PowerShell 当转义符吃掉
- **服务存活探针**：`/api/history` 或 `/api/garden` 带个**假设备**返回 **401** 就说明活着（401 是服务端真实回应）；**不带请求头是 400**，别搞混；启动到能用大约 5 秒
- **⚠️ 探针「401 = 活着」有盲区**（2026-10-09 实测踩到）：**只有当 8080 上跑的确实是 DailySeed 时才成立**。那次 8080 被**另一个服务**（同一 PID 还占着 4873）占用，我们的 `mvn spring-boot:run` 早已被杀，而假设备探针**照样返回 401**，把已死的后端判成"活着"。
  **可靠判据是两条一起看**：① `POST /api/session` 传随机 `deviceId` → **200 + 新同步码**（只有我们的 SessionController 有这个接口）；② 错误体是 Spring 格式且带 `path`（`{"timestamp":...,"status":401,"error":"Unauthorized","path":"/api/today"}`）。
  另外**别假设上次那个 PID 还活着**：`netstat` 里的 PID 可能已经换了一个进程。停占用者时若 `Get-Process <pid>` 说"不存在"而端口仍在监听，就是进程不在你的沙箱视图里（`node.exe`/`java.exe` 都这样，`python.exe` 反而可见），提权重试一次即可
- **⚠️ 前端「设备自愈」路径曾经是死循环**（2026-10-09 修，改身份逻辑前先读 `frontend/README.md` 的对应段）：症状是页面**永远停在「每日一粒 + 绿点」的引导屏**，控制台只有一行 401。四个缺陷叠在一起——`App.tsx` 的 `registering` ref 守卫**永不重置**（401 后想重新注册被它挡掉）、`client.ts` 只清 deviceId 不负责重建、注册与首屏取数**并行**（可能抢在注册前发出）、注册失败被 `catch {}` **静默吞掉**。
  现在的做法：注册全局单飞（`bootstrapDevice`）、401 时按**这次真正发出去的 deviceId** 去重修复（`repairDevice`，同步登记进 `repairing` map，否则并发两个请求会各注册一次、建出两个用户）、自愈**只做一次**、失败落到可重试的错误态。回归脚本 `frontend/qa-verify-bootstrap.mjs`（9 个场景）守着它
- **⚠️ 加列迁移一定要回填**（V3 的教训）：`V3__draw.sql` 给 `daily_assignments` 加了 `revealed_at`（NULL = 还没揭晓），**但没有回填**——而 V3 之前的旧代码是把卡面直接摊开的，「没揭晓」这个状态对历史数据从来不存在。于是所有**已留住**的行成了 `state='KEPT'` + `revealed_at IS NULL`，前端画出一个**没有任何按钮的空白卡背**（`!revealed` 画卡背、`revealed` 才画动作区），用户既翻不开也留不了。已用 `V4__backfill_revealed.sql` 回填，并在前后端各加一道 `kept ⇒ revealed` 护栏。
  **通用规则：任何时候给既有表加一个"新语义"的列，都要问一句「老数据这一列该是什么值」，并写进迁移里**
- **⚠️ 凭据的"规范形态"必须和落库时那一串逐字一致**（模块 C 真踩过，症状迷惑性极强）：
  `users.sync_code_hash` 哈希的是 `newSyncCode()` 生成的 **`K7M2-P9QX`（带连字符）**，
  而 `RestoreService` 一开始把用户抄回来的码**抹掉连字符**成 8 位裸码再去查 —— 于是**恒定 404**，
  日志里 `canonical` 看起来完全正确、用户也完全抄对了。查了四轮才定位到"哈希的输入少了一个字符"。
  **教训**：纯函数测试只断言"整理后长度是 8"，它就抓不住这个 bug；要断言的是
  **「整理出来的字符串必须等于落库时那一串」**。现在前后端各有一份同名整理函数 + 一条专门的断言（`verify_api.py` 的 **C7**）
- **⚠️ 别用 `replaceAll("[^0-9A-Za-z]", "")` 去剥分隔符**（同一个函数里的第二个坑）：
  在 Unicode 感知的字符类语义下，隐式 `\w` 会把**全角空格 `\u3000` 当成字母数字**，它躲过剥离、
  让长度多出一位，用户明明抄对了却被判"位数不对"。**逐个字符白名单判断**（收 ASCII 字母数字，其余一律丢）
- **⚠️ `.ics` 是按字节折行的**：RFC 5545 要求每行 ≤ 75 **八位组**，续行以空格开头。
  中文一个字三个字节，**按字符数折会折出 200 多字节的非法行**，严格的日历客户端直接拒收。
  另外 `DTSTAMP` 是"这份对象什么时候生成的"（UTC，带 `Z`），**不是提醒时刻**——写成提醒时刻，
  日历里会出现一个从没发生过的创建时间
- **⚠️「C 级卡」这个说法不准**：卡片库里 `evidence_level='C'` 的卡**一张都没有**（实测 0 张）。那 67 张是 `evidence_level IS NULL` —— 前端拿到的是**根本没有 `evidence` 这个键**（后端开了 `non_null`）。所以判定只能写 `if (today.evidence)`，**绝不能写 `x === null`**；说「C 级」时心里要清楚它指的是"无依据/无 evidence 键"这一档
- **⚠️ `mvn spring-boot:run` 说 "Nothing to compile - all classes are up to date" 不等于你跑的是新代码**（2026-10-09 踩到）：
  它只比对 class 与源文件的时间戳。**改了代码先 `mvn test`（会真编译）再重启**，
  或者干脆看启动日志里有没有 `Recompiling the module because of changed source code`。
  现象是"改了却没生效"，很容易被误判成逻辑错——**本次为了排除这一项，白跑了两轮重启**
- **⚠️ 恢复成功后"换发的新码被抹掉"的坑**（模块 C 交付前最后一步抓到，值得单独记一条）：
  恢复流程是 `restoreSession()` 换发新码 → 落盘 → `location.reload()`。而 reload 之后
  `App` 会再调一次 `POST /api/session`，那时设备**已经注册过**，后端返回的 `syncCode` 是 **null**
  （这是"设备已用过、不必再弹码"的既定语义）。原来的 `saveSession()` 照写不误，
  于是**刚换到手的码在同一次刷新里被抹成 null**，设置页显示"还没拿到"，
  用户拿着已经作废的旧码 —— 而且**接口层全绿、单测全绿都发现不了它**，因为坏的是前端落盘时机。
  修法：`saveSession` 只在 `info.syncCode` 非空时写；`qa-verify-bootstrap.mjs` 加一条断言 + 一道源码守卫。
  **通用教训：跨"页面重载"的状态变更，要专门问一句「重载之后跑的那段代码会不会把它覆盖掉」**
- **⚠️「身份退路」的适用范围必须收窄，否则用户永远没法重新开始**（模块 D 实测纠正）：
  最初的写法是"deviceId 没被认识就用 Cookie 认人"。结果是用户清掉 localStorage 想要一个干净的开始，
  却被旧 Cookie 拽回旧花园——**他永远回不到"新用户"状态了**。而他的旧身份此刻并没丢
  （还在别的设备上，或者他有同步码）。
  现在的规则：**只要客户端给了 deviceId，Cookie 一律不生效**；退路唯一的入口是"连 deviceId 都拿不出来"
  （= 浏览器缓存被清，前端生成不出 ID）。
  教训：**加一条"自愈"路径时，先问清楚它会不会抢走用户主动表达的意图**
- **⚠️ HttpOnly Cookie 是前端读不到的，所以"我换了个人"必须由服务端说出来**：
  靠 Cookie 认人时后端会补发一个 `srv-` 前缀的 deviceId 放在响应体里。前端不存下它，
  下次刷新又回到"没有身份"（Cookie 救得了一次，救不了第二次）。
  前端这边还有一条同样关键的配合：`bootstrapDevice()` 必须用 `readDeviceId()`（**不生成**），
  一发新 ID，后端只能当成新用户，退路就永远走不到
- **⚠️ 测恢复接口时，`deviceId` 必须是"没注册过"的**：已经被认识的设备会走 409「不用恢复」那条分支。
  验证脚本里如果顺手用 `new_device()` 先建号，再调 restore，就会一路 409 而看不出真正的原因
- **⚠️ 恢复成功会立刻换发新码**：任何"连测几种写法"的脚本都不能串成一条链——
  第一次成功后旧码就废了，后面的变体自然 404。**每种写法用一套独立账号**
- **⚠️ `POST /api/session` 的优先级是「请求头 → body」**（模块 D 改的）：验证脚本只往 body 里塞新
  deviceId、而请求头还带着主设备时，拿回来的会是**主设备**（已注册、没有 `syncCode`）。
  症状是后续断言全崩、但崩得莫名其妙。测这个接口时**请求头要和 body 里那个一致**
- **⚠️ 验证脚本必须对着代理再跑一遍，否则会漏掉真路径上的假失败**（模块 D 踩到）：
  `verify_api.py` / `verify_cookie.py` 里一度写成 `dict(resp.headers)["Set-Cookie"]`，
  而 `http.client` 给的响应头键是**小写**的。直连后端时靠"内容里有没有 `dailyseed_uid=`"偶然过了，
  **经 Vite 代理**（= 浏览器唯一走的路径）就报失败——差一点把它当成 Cookie 没种上。
  两个脚本现在都收 `base` 参数，`python tools/verify_api.py http://localhost:5173` 即可；
  取响应头统一用 `header(headers, name)` 做大小写无关查找
- **⚠️ `Secure` Cookie + http = 那条断言**不适用**，不是 bug**（2026-10-10 实测撞到）：
  用生产开关（`DAILYSEED_SESSION_COOKIE_SECURE=true`）起一台后端、再用 http 地址跑验证脚本时，
  **`verify_api.py` 的 C23「拿不出 deviceId 时靠 Cookie 认人」会 FAIL**、**`verify_cookie.py` 会全红**
  —— 一眼看过去都像"身份退路坏了"。真相是：**`Secure` Cookie 按规范就不会被客户端回传**
  （Python 的 cookiejar 也守规矩），所以那条在 http 下**根本没资格成立**（线上是 https，它才生效）。
  现在两个脚本都会先读 `/api/health` 的 `config.sessionCookieSecure`：
  `verify_api.py` 打印 **SKIP + 原因**（其余照验，退出码 0），`verify_cookie.py` **直接停下来说明**（退出码 2）；
  本机（secure=false）分别照旧 57/57 与 19/19。
  **通用教训：拿"生产口径"的配置跑"开发口径"的脚本前，先问一句"这条断言在当前配置下成立吗"**
- **⚠️ 读检查挡不住并发，只有写条件挡得住**（模块 E，本轮抓到两个真 bug）：
  - `addKept` 无条件自增 → 并发 8 次「留着」把 `kept_count` 加到 **5~7**，
    而它驱动毕业小标记 ≥7：**手抖连点几次就能刷出毕业入口**
  - `redraw` 无条件更新 → N 次并发重抽 `draw_count` 只 +1，**配额形同不存在**；
    而且种子里含 drawCount，两次并发会抽到同一张

  两处都改成了「条件更新 + **用返回行数决定下一步**」：
  `WHERE state <> 'KEPT'` 与 `WHERE draw_count = :n`。
  **串行测试对这两个 bug 完全无感**——`verify_api.py` 当时那 53 条全绿（现在 57 条），
  只有 `tools/verify_concurrency.py`（并发实验）能抓到。改抽卡/留住的写路径之后一定要跑它
- **⚠️ "该不该上线"和"能不能接流量"必须分成两条判据**（模块 E 踩到）：
  `/api/health` 最初把配置风险（无限重抽、非 secure Cookie）也算进失败，
  于是**本地开发机返回 503**——编排系统看到 503 会拒绝把流量打给一台其实完全正常的机器。
  现在 `ok` 只管存活必需项（库/迁移/种子/时钟/退路自洽），配置风险走独立的 `warnings` 列表
- **⚠️ nginx 的 `add_header` 是「全有或全无」**（2026-10-10 实测，修掉一个静默 bug）：
  **只要某个 `location` 自己写了任何一条 `add_header`，`server` 块里的*所有* `add_header`
  在这个 location 内就全部失效**（官方文档：inherited … **if and only if** there are no
  add_header directives defined on the current level）。
  原来的 `default.conf.template` 在 `/index.html`、`/assets/`、`/sw.js`、`/icons/`、
  `/manifest.webmanifest` 里各写了一条 `Cache-Control` → 于是 **CSP / X-Frame-Options /
  nosniff / Referrer-Policy 在这些响应上一条都不发**，恰恰包括最需要 CSP 的 `index.html`。
  它不报错、日志干净，只有 `curl -I` 才看得出来（**实测对照**：拿老配置单独起一个 nginx 容器，
  `/` 与 `/assets/…` 的 `CSP=没有`、`nosniff=没有`，而 `Cache-Control` 正常）。
  修法：把缓存策略收进一张 `map $uri $dailyseed_cache_control`，`server` 层统一
  `add_header Cache-Control $...`，**location 里一条 add_header 都不写**。
  **通用教训：nginx 里"我在 server 层加了安全头"不等于"每个响应都有它"——验证要 curl 每类路径。**
- **⚠️ 读产物/源码做"词表扫描"时必须显式按 UTF-8 读**（2026-10-10，差点得出一个完全相反的结论）：
  用 `Get-Content -Raw` 读 `frontend/dist/assets/*.js`，**每一个中文词都数出 0**——
  于是"产物里没有任何监工词"这个结论看起来漂亮极了，其实是编码读错了。
  改用 `[System.IO.File]::ReadAllText($p, [Text.Encoding]::UTF8)` 之后，`打卡` 出现 3 次、`连续` 1 次。
  **通用教训：词表扫描这类"零命中"结论，先用一个**必然存在**的控制词（如 `今天`/`deviceId`）
  验一下扫描器本身**——否则你验的是编码，不是红线
- **⚠️ 红线不能靠"违禁词表"来守**（同一天踩出三个假阳性，判据都是这么定下来的）：
  ① 这个产品**故意**把"打卡/连续"写在界面上，而且是在**否定它们**（"留着不是打卡"、"它不打卡、不算连续天数"）
  → 词表会把好文案判成违规；正确判据是「这些词只允许出现在**否定句**里」（词前 4 字内有 不/没/别/非/无/否）。
  ② `元|块` 这种宽匹配会把 98 号卡的"时间**块**"判成金额 → 只认"数字+单位"或"货币符号+数字"。
  ③ "产物里不许出现 http"会把 React 的 `https://reactjs.org/docs/error-decoder.html`
  和 SVG/MathML 的 `http://www.w3.org/...` **命名空间**判成第三方源（实测 13 处全是这类）
  → 只查**可加载**的形态（`src=` / `href=` / `import(` / `url(` / `fetch(` 后面紧跟 http）。
  **判据要能从"文案意图"上站得住，不能凭手感拉清单**——这三条现在都写在 `verify_redlines.py` 里
- **⚠️ `frontend/dist` 可能"看着在、其实空了"**（2026-10-11 实测撞到，整轮交付被它卡住）：
  `dist/` 目录还在、里面**只剩 `icons/`**，`index.html` / `assets/` / `sw.js` / `manifest.webmanifest`
  全没了 —— 4173 预览、静态契约、375px 验收全部做不了（**Docker 那条路反而没事**，镜像里自己构建）。
  最可能是**预览服务器还在跑的时候又跑了 `npm run build`**（这个坑 README 里记过，还是踩了：
  Vite 先清空输出目录再写入，清到一半失败就留下半个 dist）。两条教训：
  ① **构建之后必须验产物**——`verify_redlines.py` 现在会在 dist 空/缺 `index.html` 时直接红一条
  （以前只打一行"共 0 字符"就安静跳过 3 条断言，总数从 11 变 8 而**看起来仍然全绿**，这就是假绿）；
  ② **讲过的坑要变成断言**，光写在文档里挡不住第二次
- **⚠️ 中文 Windows 的控制台是 cp936，而 GB2312 只有 ①–⑩**（2026-10-11，用一次全量扫描扫出来的）：
  `verify_pwa.py` 跑到第 **⑪** 条就抛 `UnicodeEncodeError: 'gbk' codec can't encode '\u246a'` 死掉，
  前面 10 条结论全白跑；`seed_dev_user.py --qa` 更阴——**四台设备全造好了、摘要也打印完了**，
  最后一行 `print("⚠️ …")` 崩在 U+26A0 上，退出码 1 + traceback，看着像"造数失败"。
  修法：打印文本里不用 GBK 编不出来的符号 · `sys.stdout.reconfigure(errors="replace")` 兜底 ·
  `verify_pwa.py` 按 `sys.stdout.encoding` 决定用 ⑪ 还是 `11.`。
  **通用教训：文档里让人照抄的命令，必须在这台机器的原始控制台上真跑一遍**——
  我这边一路是 UTF-8 控制台，所以这两条地雷从来没响过
- **⚠️ `mvn` 必须带 `-Dmaven.repo.local=.m2repo`**（2026-10-11 实测）：依赖装在 `backend/.m2repo` 里，
  直接 `mvn test` 会走默认的 `~/.m2`，然后报一串"依赖解析失败/offline"，看着像工程坏了。
  照 §4 那样 `cd backend` + 带参数就没问题
- **⚠️ 无头浏览器在这台机器上跑不起来**（2026-10-10，别再花时间试）：
  Chrome 155 与 Edge 155 都挂在
  `crashpad ... OpenProcess: 拒绝访问` 与 `FATAL:mojo\publ…`——它们要子进程与**命名管道**，
  而这正是受限模式封掉的东西（提权也没用，与 Docker 那次不同）。
  所以 **UI 那一层只能人点**：`--dump-dom` 拿不到一行输出，别把"页面到底渲染出来没有"寄托在无头浏览器上
- **⚠️ compose 里 `env_file:` 和 `${VAR}` 是两套机制，不是一回事**（2026-10-10）：
  `env_file:` 把文件里的键**原样交给容器**；`${DB_PASSWORD}` 这种替换**只从 shell 或
  `--env-file` / 根 `.env` 取**，**不会**读 `env_file:` 那份。少了 `--env-file backend/.env`，
  mysql 容器拿到默认 `123456`、api 容器拿到 `.env` 里的真密码 → "库起来了、api 起不来"。
  本地两边恰好都是 `123456`，所以**只有换了密码之后才会咬人**。
  现在 `docker-compose.yml` 文件头把命令写成 `docker compose --env-file backend/.env up -d --build`
- **⚠️ 沙箱里 `docker` 命令一律连不上 daemon**（2026-10-10）：daemon 是走**命名管道**
  （`npipe:////./pipe/dockerDesktopLinuxEngine`）的，受限模式不允许开命名管道，
  症状是 `docker info` 报"找不到这个管道"、`Docker Desktop.exe` 起了立刻消失、
  `wsl --status` 报 `Wsl/E_ACCESSDENIED`。**这不是 Docker 坏了**——把那条命令提权重试即可
  （实测提权后 Server 29.8.0 正常）。另外别被这条误导：**HTTP 检查（curl/Invoke-WebRequest）
  在沙箱里是好的**，所以"起容器"要提权、"验容器"不用
- **拉镜像可能卡在 IPv6**（2026-10-10）：`docker compose up --build` 报
  `failed to fetch oauth token … dial tcp [2a03:2880:...]:443: connectex: … timeout`，
  而同一批里的 `mysql:8.0` 却拉下来了——是这台机器双栈解析到没有路由的 IPv6 地址。
  **重试就好**（实测 `docker pull` 循环重试 4 次全部成功），不用改 daemon 配置
- **`java.util.Random` 相邻种子的首个 `nextDouble()` 相关** → 已换 `SplittableRandom`，别换回去
- **补留的陈旧 DTO**：返回体里的 `kept` 必须从数据库**重读**，不能用 `markKept` 之前那个对象
- **沙箱**：受限模式下 python 改不了已存在的文件 → 用编辑器工具；Maven 必须 `-Dmaven.repo.local=.m2repo`（在 workspace 内）
- **前端也吃沙箱这一套**（详见 `frontend/README.md`）：`npm install` 必须加 `--ignore-scripts`（postinstall 会 spawn 子进程 → `spawn EPERM`）；`vite.config` 必须是 **`.mjs`**（`.ts` 会再起一个 esbuild 子进程）；`npm run build` / `npm run dev` 在受限沙箱里本身就跑不起来（esbuild 服务进程被拒），**在普通终端里没问题**，实在要在沙箱里跑只能把那条命令升级权限重试一次
- **⚠️ 起过 `npm run preview` 之后，`npm run build` 会失败**（2026-10-09 踩到）：报 `ENOTEMPTY: directory not empty, rmdir ...\dist\assets`。原因是**预览服务器占着 `dist` 里文件的句柄**，Vite 清不空输出目录。**先停 preview 再 build**（或改用 `vite build --emptyOutDir=false`，但不建议——会留下旧哈希产物）
- **⚠️ 沙箱里看不到 `node.exe` / `java.exe` 进程**：`Get-Process <pid>` 会说"不存在"，而 `netstat` 明确显示该 PID 在监听（`python.exe` 反而可见）。**这是沙箱视图限制，不是进程真没了**——需要按端口找占用者并停止时，提权重试一次即可（`netstat -ano | Select-String ":8080.*LISTENING"` 拿 PID）
- **`GET /api/history` 只有 3 天窗口**：`days` 参数上限就是 3（`Math.min(days, 3)`），别以为能拉 30 天
- **同一个新设备在同一天只能有 1 盆**：`keep` 幂等 → 花园跨天视图、`readyToGraduate`、放纵入口在本地**看不到**，要用 `tools/seed_dev_user.py` 造数据
- **IDE 看不到表**：数据源 URL 若只到 `localhost:3306`，要先 Refresh；必要时改成 `jdbc:mysql://localhost:3306/dailyseed`
- **DOCX/PDF 已停维护**，md 才是源；重生 PDF 需要提权，配方在《会话纪要》§五

---

## 6. 必读文件（按需读，别全读）

| 文件                        | 什么时候读                        |
| ------------------------- | ---------------------------- |
| `DailySeed-会话纪要.md`      | **开工前读一次**（已定决策 / 否决方向 / 待决事项） |
| `DailySeed-产品设计文档.md`    | 改产品行为时，查对应章节                 |
| `DailySeed-卡片库v2.md`      | 加/改卡片、补依据时（**先看 10.1 排除清单**）  |
| **`DailySeed-阶段0执行表.md`** | **要真去发卡的时候**（发哪张 / 话术 / 记录表 / 计分板；阶段 0 是唯一不能跳过的一步） |
| **`DailySeed-真机验收清单.md`** | **要动手点的时候**（含造数命令、身份退路的手工验法与"不是 bug"清单） |
| **`frontend/README.md`**  | **改前端时先读**（接口契约 / 红线落点 / 前端沙箱坑） |
| **`docs/review-20261011/视觉规范.md`** | **改样式前先读**（颜色语义与达标对比度 / 15 档字号阶梯 / 断点 / 触控尺寸 / 图标与插画约定；配套 `verify_redlines.py --style`） |
| `backend/README.md`       | 改后端时（接口 + MySQL 方言备忘）         |
| `docs/db-schema.sql`      | 需要表结构时                       |
| `生活维护产品调研与创新点.md`         | 只在需要竞品数据时（第十节后已不适用）          |

---

## 7. 不要再讨论的（已否决，重提是浪费时间）

家庭维护提醒中枢 · 通知聚合中台 · 告警降噪中台 · Wasm 插件沙箱 · Bot 竞技场 · 并发 Bug 猎人 · 模拟器/光追/音频合成 · 全世界共用一件事 · 视角反转器 · 绑定已有动作（habit stacking）

**完整否决理由见《会话纪要》§二**（含通用判据 7 条硬标准）。

---

## 8. 当前待决事项（开工前先扫一眼）

1. ✅ **已定：毕业卡分享 = 纯前端 Canvas 生成一张图**（2026-10-09，推翻设计文档原「第一版不做」；设计文档已升 v1.8）。**待真机确认**：iOS Safari 对 `navigator.share({files})` 支持不一，代码里已有"不支持就复制文字"的退路
2. 卡片难度分布是否需要动态调整
3. 放纵日门槛是否公示（当前：不公示）
4. C 级卡是否改为显示「这张我也说不出根据」（当前：不显示入口）
5. 科普库首批 8 条是否继续扩
6. ✅ **同步码丢失的残余风险已大幅降低**（模块 D）：后端种 HttpOnly 的 `dailyseed_uid`，
   清掉 localStorage 之后还能被认回来。但它**不是万无一失**——用户清"网站数据 / 全部 Cookie"时
   两者会一起没；那时唯一的退路还是同步码。所以 §6.4 那句"趁他还不在乎时先塞给他一次"依然成立
7. ✅ **模块 C 三件事已交付**，模块 D 的三处收尾、模块 E 的并发修复与运行期地基也都已完成
8. ✅ **抽卡配额这条已经加了护栏**：`0`（无限）却没承认 `DAILYSEED_DEV_MODE=true` 时
   **应用拒绝启动**；上线只需设 `DAILYSEED_DRAW_MAX_PER_DAY=1`，护栏自动放行
9. **留住之后要不要允许继续抽**：现在是**不允许**（留住后 `canRedraw=false`，接口 409），刻意挡住"一天攒好几张"。手动反复测试靠 `tools/seed_dev_user.py --reset-today`（今天那张复活）绕开。**如果哪天觉得太紧，先想清楚它和花园 `keptCount`、放纵门槛的关系再动**（并发那道闸门也在这条路上）
10. **阶段 0（手工发卡）还没做**——这是唯一**不能跳过**的一步（《会话纪要》§五）。代码再干净，
    没有人真的领过一粒、没有人回过"留着"，就不知道卡片质量够不够
11. ✅ **Docker 产物已实测**（2026-10-10）：见 §0.4 第 1 条与 §3「部署产物」。剩下的只有**真机**那一半——iOS Safari 的 `navigator.share({files})` 与 `.ics` 落点（§8 第 1 条）
12. **`recovery_tokens` 会随"不接受 Cookie 的客户端"无界增长**（2026-10-11 实测）：同一个 `deviceId`、不带任何 Cookie 连发 3 次 `POST /api/session` → 表里 **3 行**（正常浏览器会 `renew`，不新插）。清理只发生在**签发时**、且只清**该用户**的**已过期**行（400 天）。要么给每个 `user_id` 一个保留上限，要么加一个定期清理——量级不大，但它是目前唯一一张"只增不减"的表
13. **旧版"数字 Cookie"在升级后会一次性失效**（模块 F 的 `SessionCookie` 只认 64 位十六进制令牌）：受影响的只有"清过 localStorage、又只靠那条 Cookie 认人"的用户——他们升级后会落到一个新号上（旧数据没删，但再也认不回去）。本机与阶段 0 的量级可以接受；**要是上线时已经有真实用户，先补一段"把旧数字 Cookie 换成令牌"的兼容路径**
