# DailySeed 后端

Spring Boot 3 + Java 21 + **MySQL 8**（InnoDB / utf8mb4）。设计文档见上一层的《DailySeed-产品设计文档.md》。

## 包结构

```
com.dailyseed
├── assignment/   每日分配（选卡算法）+ 抽/留/补留（今天那一页的全部行为）
├── card/         卡片与依据（Evidence 一处拆四段，四个页面共用同一形状）
├── garden/       我的花园 + 毕业（只放习惯卡）
├── explored/     走过的（只放探索卡）
├── reminder/     日历提醒（.ics 生成 + 按用户时区）
├── user/         匿名身份、同步码、恢复、HttpOnly Cookie 退路
└── ops/          运行期地基：/api/health、活动计数（零 PII）
```

## 一条铁律：md 是唯一维护源

卡片内容（含依据、科普）**只改**《DailySeed-卡片库v2.md》，然后重新生成种子：

```powershell
python tools/gen_seed.py
```

它会重写 `src/main/resources/db/migration/V2__seed_cards.sql` 和 `src/main/resources/science-notes.json`，
并校验卡片数（100）、编号连续、依据/科普引用的卡是否存在。**不要手改这两个产物。**

## 本地跑起来

```powershell
# 1. 建库（utf8mb4，中文不这样建会乱码）
mysql -u root -p -e "CREATE DATABASE dailyseed CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"

# 2. 凭据：复制一份 backend/.env（已在 .gitignore 里）
#    DB_URL=jdbc:mysql://localhost:3306/dailyseed?characterEncoding=utf8&serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true
#    DB_USER=root
#    DB_PASSWORD=你的密码

# 3. 启动：Flyway 自动建表 + 灌 100 张卡
mvn spring-boot:run
```

## 接口（MVP 第一版）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/session` | body `{"deviceId":"xxx"}` → 首次创建匿名身份并返回 8 位同步码（只返回一次） |
| `GET` | `/api/today` | 今天的一粒种子（懒生成 + 幂等，同一天反复调返回同一张）。**未揭晓时 `revealed=false`，前端显示卡背** |
| `POST` | `/api/today/draw` | **抽**：第一次 = 揭晓当天那张（不换卡）；之后 = **换掉当天那张**。`?getView=true` 只读状态、不耗配额。已留住 / 配额用完 → 409 |
| `POST` | `/api/today/keep` | 留着（body `{"note":"..."}` 可选）；放纵卡会返回 409 |
| `POST` | `/api/today/indulge` | 今天想放纵：换成一张放纵卡（每天最多一次；不满足门槛返回 409） |
| `GET` | `/api/history?days=3` | 最近 3 天（含今天）的发放记录，供「补留」列表 |
| `POST` | `/api/history/{id}/keep` | 补留：只能补 **3 天内**、**没留过**、**非放纵卡**的；否则 409 |
| `GET` | `/api/garden` | 我的花园：窗台上的一排小盆（**只含习惯卡**）+ 已内化清单 |
| `POST` | `/api/garden/{cardId}/graduate` | 宣布毕业；**重复调用不报错**（幂等，`graduatedAt` 不覆盖） |
| `GET` | `/api/explored` | 走过的全部探索卡（新的在前，**同一张卡只出现一次**）+ `totalCount` + 日期区间 |
| `POST` | `/api/session/restore` | body `{"syncCode":"K7M2-P9QX","deviceId":"xxx"}` → 把设备绑到那个账号并**换发新码**。码长不对 400 / 查不到 404 / 本设备已被认识 409 |
| `POST` | `/api/session/reminder` | body `{"time":"08:00"}` → 存下用户自设的提醒时间（只收 `HH:mm`，否则 400） |
| `GET` | `/api/reminder.ics` | 生成日历提醒文件（`text/calendar` + `attachment`）。**每日重复、无终点、按用户时区** |
| `GET` | `/api/health` | **不需要身份**。200 = 可以接流量，503 = 别接。探测项 + 配置 warnings + 今天的活动计数（零 PII） |

除 `/api/session`、`/api/session/restore` 外都要带请求头 `X-Device-Id`。
（这两个是"建立身份"的入口，此时还没有身份可用；`/api/session/reminder` 与 `/api/reminder.ics` **要带**。）

### 身份有两条路（`dailyseed.session.cookie.*`）

| 路 | 载体 | 什么时候生效 |
| --- | --- | --- |
| **正路** | `X-Device-Id` 请求头（localStorage） | 永远优先 |
| **退路** | HttpOnly Cookie `dailyseed_uid`（值 = 256 位随机令牌，库里只有 SHA-256） | **只有连 deviceId 都拿不出来时**（= 浏览器缓存被清） |

退路的适用面**故意很窄**，这是实测纠正过的：一开始写成"deviceId 未被认识就用 Cookie 认"，
结果是用户清掉 localStorage 想重新开始，却被旧 Cookie 拽回旧花园——他就**永远没法重新开始**了。
现在的判定：**只要客户端给了 deviceId，Cookie 一律不生效。**

于是靠 Cookie 认人时，服务端会**补发一个 `srv-` 开头的 deviceId**（响应体里的 `deviceId` 字段）。
Cookie 为 HttpOnly，前端通过响应中的设备 ID 保存恢复后的身份。

**2026-10-11 安全修正（V5）**：Cookie 改为 256 位随机令牌，数据库 `recovery_tokens` 只存 SHA-256 哈希与到期时间。服务端查询并校验有效期后才确认用户身份，不再接受数字 userId。已有本地设备 ID 的用户下次打开时自动换发；只剩旧数字 Cookie 的设备需用同步码恢复。部署时让 Flyway 执行 V5，不要恢复旧 Cookie 解析代码。

```powershell
DAILYSEED_SESSION_COOKIE_ENABLED=false   # 关掉整条退路，退回只管 localStorage
DAILYSEED_SESSION_COOKIE_SECURE=true     # 生产（https）必须打开，否则 Cookie 明文传输
```

> ⚠️ `/api/reminder.ics` 前端**必须 fetch 后自己存文件**，不能写成 `<a href="/api/reminder.ics">`：
> 身份只靠请求头，点链接带不上它，后端会以 **400「缺少请求头」** 拒掉。

**抽卡配额**（`application.yml` → `dailyseed.draw.max-per-day`）：
`0` = **无限**（开发默认，方便连着抽看手感与分布）；**生产语义是 `1`**（只能抽一次、没有重抽）。
切换不必改代码：`DAILYSEED_DRAW_MAX_PER_DAY=1`。
重抽的种子带上抽卡轮次，所以同一轮重抽是**确定性**的（重试安全），不同轮会真的换卡。

> ⚠️ **`0` 必须显式承认开发模式，否则应用起不来**（`StartupGuard`）：
> ```powershell
> DAILYSEED_DEV_MODE=true      # 本地开发：承认「无限重抽」是故意的（backend/.env 里已有一份）
> DAILYSEED_DRAW_MAX_PER_DAY=1 # 生产：把配额改回 1，就不需要承认
> ```
> 这条护栏是为"**忘了改配置就上线**"准备的：无限重抽一旦上线，用户能一直重抽到满意为止，
> 那会推翻「不确定性的味道」（§3.2）和放纵日门槛的意义（§5.5）。
> 它**不吃掉配置**（不会悄悄把 0 当成 1），只是拒绝启动并把该设什么写在错误里。

```powershell
$dev = "dev-001"
curl.exe -s -X POST localhost:8080/api/session -H "Content-Type: application/json" -d "{\"deviceId\":\"$dev\"}"
curl.exe -s localhost:8080/api/today -H "X-Device-Id: $dev"
```

## 验证（每次改完算法或 SQL 都跑）

```powershell
mvn test                          # 57 个单测：幂等种子、6:3:1 占比、放纵日门槛、难度匹配、补留窗口边界、花园只见习惯卡、毕业幂等、抽卡配额与重抽种子、探索去重与只见探索卡、ics 折行与时区、同步码整理、Cookie 退路、启动护栏、并发计数
python tools/verify_api.py        # 57 条接口断言（**串行**：验业务规则对不对）
python tools/verify_health.py     # 12 条状态/配置断言（这台机器现在能不能见人）
python tools/verify_cookie.py     # 19 条身份退路断言（用 http.cookiejar 模拟两台浏览器）
python tools/verify_concurrency.py  # 并发不变量实验（见下）——① 需要单独起一个配额有限的后端
python tools/verify_catchup.py <deviceId> <窗口内id> <窗口外id>   # 补留窗口边界（需先插 fixture）
python tools/verify_pwa.py        # 18 条 PWA/静态契约（对着前端跑：默认 4173）
```

> **前三个脚本都收一个 base 参数**，所以可以对着**代理**跑一遍——那才是浏览器的真实路径：
> ```powershell
> python tools/verify_api.py http://localhost:5173       # 经 Vite 代理
> python tools/verify_cookie.py http://localhost:4173    # 经 preview 代理
> ```
> 这一步抓出过一个**假失败**：脚本里写 `dict(resp.headers)["Set-Cookie"]`，
> 而 http.client 给的键是**小写**的——直连时靠内容匹配偶然过了，经代理就报错。
> 现在统一走 `header(headers, name)` 做大小写无关取值。

### 并发不变量（`verify_concurrency.py`）—— 串行测试永远抓不到的那一类

`verify_api.py` 那 57 条**全是串行的**：它证明"按顺序调用时规则成立"，证明不了"两个请求同时到的时候"。
而真实用户恰好会并发：双击「留住」、连点「再抽一张」、网络重试、PWA 从后台切回来重新挂载。

三条不变量是产品语义的地基，一旦被并发打破，症状都不是报错而是**数据悄悄变得不对**：

| 不变量 | 守它的闸门 |
| --- | --- |
| ① `draw_count` 不超过配额 | `AssignmentStore.redraw` 的 `WHERE draw_count = :n`（条件更新 + 失败后重读重算） |
| ②「留住」只真的发生一次 | `AssignmentStore.markKept` 的 `WHERE state <> 'KEPT'`，**返回值决定要不要加计数** |
| ③ 花园 `kept_count` 与发放行对得上 | 上面两道闸 + 同一个事务 |

跑法（① 需要**有限配额**的后端，开发默认的 0 是无限、测不出来）：

```powershell
# 另起一个后端，不影响正在用的 8080
$env:DAILYSEED_DRAW_MAX_PER_DAY="1"; $env:DAILYSEED_DEV_MODE="true"
mvn "-Dmaven.repo.local=.m2repo" spring-boot:run "-Dspring-boot.run.arguments=--server.port=8081"
python tools/verify_concurrency.py http://localhost:8081 --workers 12 --rounds 16
python tools/verify_concurrency.py http://localhost:8080      # 无限配额那个也能跑 ②③④
```

> ⚠️ **改了抽卡或留住的写路径之后一定要跑它。** 这轮就是靠它抓到两个真 bug——
> `addKept` 无条件自增（并发 8 次「留着」把 `kept_count` 加到 **5~7**，而它驱动毕业小标记 ≥7：
> 等于**手抖连点几次就能刷出毕业入口**）、以及 `redraw` 无条件更新（N 次并发重抽只 +1 次计数，
> 配额形同不存在）。两个都**不报错**，串行断言也全绿。

### `verify_health.py` 与 `GET /api/health`

一条不需要身份的请求，说清"这台服务现在能不能见人"。用在**每次发布前后**——
它和 `verify_api.py` 的分工是：一个验**行为**（CI 里跑），一个验**状态与配置**（发布时跑）。
混在一起的结果通常是 CI 因为环境不对而红，于是没人再认真看行为那部分。

状态码就是结论：**200 = 可以接流量，503 = 别接**。探测项（都影响 ok）：
Flyway 迁移到位、库连得上、卡片种子灌进去了、JVM/MySQL/用户时区能对上、身份退路配得自洽。
配置风险（无限重抽、非 secure Cookie）走**独立的 `warnings` 列表，不影响 ok**——
它是"该不该上线"而不是"能不能接流量"。这条界是踩过一次才划清的：
最初把两者混在一起，于是**本地开发机返回 503**，编排系统会拒绝把流量打给一台其实正常的机器。

```powershell
python tools/verify_health.py                  # 本机口径
python tools/verify_health.py --prod           # 生产口径（本地会 FAIL，那是故意的）
python tools/verify_health.py https://你的域名 --prod   # 上线前对着线上跑，必须全绿
```

`verify_api.py` 验的是：匿名身份只创建一次、同一天两次调用拿到同一张卡（**幂等**）、
**首屏返回卡背（`revealed=false`）**、**抽卡揭晓且第一次不换卡**、**`getView` 不耗配额**、
**留住后 `canRedraw=false` 且再抽 → 409**、
留着成功、放纵日门槛 409、依据该有则有该空则空、补留已经留过的卡 409，
**花园那一段**（A1–A13）：空花园、留着后出现在窗台、留过的探索卡不进花园、
毕业后从窗台移入「已内化」、**重复毕业不覆盖毕业时间**、没留过/探索卡/不存在的卡毕业一律 409、
**连点 3 次「留着」keptCount 仍是 1**，
以及**模块 C 那一段**（C1–C21）：探索记录只含探索卡 / 计数自洽 / 同卡去重 / 空记录不炸、
**同步码的哈希口径**、恢复后 `assignmentId` 与老设备一致、**旧码立即失效**、
三种失败状态码（400/404/409）各归各位、**四种抄码笔误都认**、
提醒只收 `HH:mm`、**ics 的时区/每日重复/无终点**、**RFC 5545 的 CRLF 与 75 字节折行**、
以及「不带请求头是 400」。
`verify_catchup.py` 用真实数据验窗口：2 天前能补、4 天前拒绝、且被拒的那张不会进 history 列表。

> 花园那一段会自己开新设备：今天抽到习惯卡还是探索卡由服务端按 6:3:1 决定，
> 所以它循环开设备直到同时拿到两种卡（预期 3-4 次，上限 30）。
> 循环里开过的设备 id 写在 `backend/target/verify-api.json` 的 `gardenDevices` 里——
> 想验「重启后花园还在」就拿里面的 `habit` 设备再查一次。

## 已经实现的规则

- **幂等**：种子 = `hash(userId, date)`（`SplittableRandom`，相邻种子也均匀），
  同时靠 `UNIQUE KEY (user_id, assigned_date)` + `ON DUPLICATE KEY UPDATE id = id` 兜底；并发不会发出两张
- **加权**：留过的卡更容易再出现；太久没见的略微加权；难度按近期留着率匹配
- **类型占比 6:3:1**：按类型归一化，避免被卡片张数（42:38:20）带偏
- **放纵日门槛**：累计留住 ≥5 种 + 冷却 7 天 + 不连抽 + 每天最多换一次；**门槛不公示**，接口只回 `canIndulge`
- **「?」**：`evidence` 为空就不给依据（C 级不显示入口）；`science_key` 指向科普第 ④ 段
  （`com.dailyseed.card.Evidence` 一处拆四段，今天那张 / 补留列表 / 花园共用同一个形状）
- **花园只放习惯卡**：探索卡属「探索记录」（§3.2），**放纵卡什么都不进**（§3.5 红线 5）。
  这条规则故意写成纯函数 `GardenService.visibleInGarden`，不藏在 SQL 的 WHERE 里——那样才有人守得住
- **毕业幂等**：已是 `GRADUATED` 就原样返回、不覆盖 `graduated_at`（Service 一道闸 + SQL 的
  `AND state <> 'GRADUATED'` 一道闸）；`readyToGraduate`（留到 7 次）只是给前端画小标记，**不是"该毕业了"的判定**
- **留着也是幂等的**：同一天重复 POST `/api/today/keep` 返回当前状态、**keptCount 不涨**
  （它驱动毕业小标记和放纵日门槛，点大了产品语义就坏了；补留那条路仍然是 409）
- **抽（V3）**：`revealed_at` 为 NULL = 卡背；`draw_count` 记今天抽了几次。
  重抽 = **换掉当天那一行的 card_id**（没留的直接丢），**仍然一天一行**，幂等前提没变。
  **留住之后不能再抽**（否则一天能攒下好几张，把花园与放纵门槛的数据弄脏）。
  留住的卡一律视为已揭晓（`view()` 里 `revealed = isRevealed() || isKept()`，防 V3 那类迁移疏漏）
- **探索记录（模块 C）**：只放**探索卡**（`ExploredService.visibleInExplored`，也是纯函数守着，
  和花园那条线同一个套路），同一张卡按**最后一次**遇见它的日期去重（重抽会让同一张卡落在不同日子），
  查询**不带天数上限**——这一页是"我走过的路"，砍掉三个月前的记录等于把路抹了
- **同步码恢复（模块 C）**：`users.sync_code_hash` 里是 **SHA-256 十六进制**（`UserStore.sha256`），
  所以"查得到"就等于"码对"。成功即**换发新码**、旧码立即作废（§7.2「可重置」）。
  ⚠️ **整理用户抄回来的码时，连字符必须按 `newSyncCode()` 的排法补回去**——
  库里哈希的是 `K7M2-P9QX` 这一串，把连字符抹成 8 位裸码去查会**恒定查不到**（真踩过）
- **`.ics`（模块 C）**：`DTSTART;TZID=<用户时区>` + `RRULE:FREQ=DAILY` **无 `UNTIL`**（不给提醒设终点），
  `DTSTAMP` 是真正的生成时刻（UTC），**折行按 UTF-8 字节算**
  （中文一字三字节，按字符数折会折出 200 多字节的非法行，严格客户端直接拒收）
- **身份退路（模块 D）**：Cookie 是经过服务端校验的随机恢复凭据，不能直接信任客户端提供的用户编号。`/api/session` 的优先级是「认设备 → 认 Cookie → 建新号」，
  而且**只要客户端给了 deviceId，Cookie 就不参与**（那条规则见上面「身份有两条路」）
- **启动护栏（模块 D）**：`StartupGuard` 只拦一种配置（无限重抽却没承认开发模式），
  其余是 WARN。它**永不改配置**——那就变成"应用偷偷改了用户设过的值"，比提示更坏
- **并发下的两条闸门（模块 E）**：写路径都不靠"先读再判"，靠**条件更新 + 用返回行数决定下一步**：
  - `markKept`：`WHERE state <> 'KEPT'`。返回 1 的那个请求才是"真正完成这次留住"的，
    **只有它去加 `kept_count`**（不加这道闸时并发 8 次会加到 5~7）
  - `redraw`：`WHERE draw_count = :n`（n 是读到的那个值，它同时是选卡种子的输入）。
    失败就重读重算——否则 N 次并发重抽只 +1 次计数，配额形同不存在
  两条都是"读检查挡不住并发，只有写条件挡得住"。串行测试对它们完全无感，跑 `verify_concurrency.py`
- **优雅停机**：`server.shutdown=graceful` + 20 秒收尾。每一次写请求都可能是一次「留着」，
  被硬杀在半路上用户会看到"点了没反应"——而那种体验对习惯养成产品是致命的（他会以为数据丢了）

## MySQL 方言备忘（换库时踩过的）

| Postgres 写法 | MySQL 写法 |
| --- | --- |
| `INSERT … RETURNING id` | `KeyHolder` + `getGeneratedKeys()`（MySQL 没有 RETURNING） |
| `ON CONFLICT DO NOTHING` | `ON DUPLICATE KEY UPDATE id = id`（**别用 `INSERT IGNORE`**，它会吞掉外键错误） |
| `ON CONFLICT … DO UPDATE` | `ON DUPLICATE KEY UPDATE col = col + 1` |
| `TIMESTAMPTZ` / `now()` | `DATETIME(6)` / `CURRENT_TIMESTAMP(6)` |
| `BIGSERIAL` | `BIGINT AUTO_INCREMENT` |
| `TINYINT(1)` | `BOOLEAN`（8.0.37 已弃用整数显示宽度，会告警） |
| 列名 `text` | 要写 `` `text` `` |

## 还没做（下一步）

> 模块 C（三个接口）与模块 D 的收尾（身份退路 / `.ics` 分享退路 / 启动护栏）**都已落地**，
> 剩下的都是前端的落点与真机确认。

- 375px 真机逐页验收（清单在上一层 `DailySeed-真机验收清单.md`）
- 上线时确认三件事：`DAILYSEED_DRAW_MAX_PER_DAY=1`、`DAILYSEED_DEV_MODE` 不设、
  `DAILYSEED_SESSION_COOKIE_SECURE=true`
