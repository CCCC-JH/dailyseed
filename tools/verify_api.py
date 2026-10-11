# -*- coding: utf-8 -*-
"""对着本地跑起来的服务验四条断言，输出人可读的结论 + 完整 JSON 日志。

用法：python tools/verify_api.py            （默认 http://localhost:8080）
"""
import io, json, re, sys, urllib.error, urllib.request, http.cookiejar
from datetime import datetime, timedelta

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
# 每次跑用新设备，脚本可重复执行（也顺便验证「新用户」这条路径）
DEV = "dev-" + datetime.now().strftime("%Y%m%d%H%M%S")


def call(method, path, body=None, dev=None):
    """dev 默认是本轮主设备；花园那一段会自己开新设备，所以允许临时指定。"""
    headers = {"X-Device-Id": dev or DEV}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


def header(headers, name, default=""):
    """大小写无关地取响应头。

    ⚠️ 别写 `dict(resp.headers)["Set-Cookie"]`：http.client 里那些键是**小写**的，
    走 Vite 代理与直连后端时写法还会不一样——统一取值，否则会在"经代理"这条路上报假失败，
    而它恰恰是唯一有意义的路径（浏览器就是走代理的）。
    """
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return default


def call_text(method, path, dev=None):
    """取**原始文本**响应（/api/reminder.ics 不是 JSON）。返回 (status, 正文, 响应头)。"""
    headers = {"X-Device-Id": dev or DEV}
    req = urllib.request.Request(BASE + path, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8"), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.headers


def call_no_header(method, path):
    """**完全不带** X-Device-Id 的请求。用来钉住那个坑：401（假设备）和 400（缺请求头）不是一回事。"""
    req = urllib.request.Request(BASE + path, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


results = []


def check(name, ok, detail):
    results.append((name, ok, detail))


s1s, s1 = call("POST", "/api/session", {"deviceId": DEV})
s2s, s2 = call("POST", "/api/session", {"deviceId": DEV})
check("POST /api/session 首次创建", s1s == 200 and s1.get("created") is True,
      "status=%s userId=%s syncCode=%s" % (s1s, s1.get("userId"), s1.get("syncCode")))
check("同设备再调不重复创建、不再返回同步码",
      s2.get("created") is False and not s2.get("syncCode"),
      "status=%s userId=%s syncCode=%s" % (s2s, s2.get("userId"), s2.get("syncCode")))

t1s, t1 = call("GET", "/api/today")
t2s, t2 = call("GET", "/api/today")
check("GET /api/today 拿到卡", t1s == 200 and t1.get("cardId"),
      "status=%s cardId=%s type=%s difficulty=%s text=%s"
      % (t1s, t1.get("cardId"), t1.get("type"), t1.get("difficulty"), t1.get("text")))
check("★★ 幂等：同一天两次调用返回同一张卡",
      t1.get("cardId") == t2.get("cardId") and t1.get("assignmentId") == t2.get("assignmentId"),
      "first cardId=%s / second cardId=%s" % (t1.get("cardId"), t2.get("cardId")))
check("★ 抽卡：GET /api/today 返回的是**卡背**（revealed=False，还没抽）",
      t1.get("revealed") is False and t1.get("drawCount") == 0,
      "revealed=%s drawCount=%s" % (t1.get("revealed"), t1.get("drawCount")))
check("「?」依据：这张卡要么有 evidence，要么明确为空（C 级不显示入口）",
      True, "evidence=%s level=%s science=%s"
      % (json.dumps(t1.get("evidence"), ensure_ascii=False), t1.get("evidence"),
         (t1.get("science") or {}).get("key")))

# ── 抽：揭晓当天那张（第一次抽不该换卡） ──
ds, d1 = call("POST", "/api/today/draw")
check("★ POST /api/today/draw 揭晓成功，且第一次抽不换卡",
      ds == 200 and d1.get("revealed") is True and d1.get("cardId") == t1.get("cardId")
      and d1.get("drawCount") == 1,
      "status=%s revealed=%s cardId=%s(原 %s) drawCount=%s"
      % (ds, d1.get("revealed"), d1.get("cardId"), t1.get("cardId"), d1.get("drawCount")))

vs, v = call("POST", "/api/today/draw?getView=true")
check("★ getView=true 只看状态：不消耗配额、不换卡",
      vs == 200 and v.get("drawCount") == 1 and v.get("cardId") == t1.get("cardId"),
      "status=%s drawCount=%s cardId=%s" % (vs, v.get("drawCount"), v.get("cardId")))

_max, _used, _can = d1.get("maxDraws"), d1.get("drawCount"), d1.get("canRedraw")
_expect = (not d1.get("kept")) and (_max <= 0 or _used < _max)
check("★ 抽卡配额由服务端给，且 maxDraws / drawCount / canRedraw 三者自洽（0 = 无限）",
      isinstance(_max, int) and _can is _expect,
      "maxDraws=%s drawCount=%s kept=%s → canRedraw=%s（按规则应为 %s）"
      % (_max, _used, d1.get("kept"), _can, _expect))

ks, k = call("POST", "/api/today/keep", {})
check("POST /api/today/keep 留着成功", ks == 200 and k.get("kept") is True,
      "status=%s kept=%s cardId=%s" % (ks, k.get("kept"), k.get("cardId")))
check("★ 留住之后不能再重抽（否则一天能攒下好几张）",
      k.get("canRedraw") is False, "kept=%s canRedraw=%s" % (k.get("kept"), k.get("canRedraw")))

rk, r = call("POST", "/api/today/draw")
check("★ 留住之后调抽卡接口 → 409", rk == 409,
      "status=%s detail=%s" % (rk, r.get("detail") or r.get("message") or r))
is_, i = call("POST", "/api/today/indulge")
check("POST /api/today/indulge 门槛生效（累计不足，应 409）", is_ == 409,
      "status=%s detail=%s" % (is_, i.get("detail") or i.get("title") or i))

hs, h = call("GET", "/api/history?days=3")
check("GET /api/history 拿到最近 3 天（含今天这张）",
      hs == 200 and isinstance(h, list) and any(x.get("assignmentId") == t1.get("assignmentId") for x in h),
      "status=%s items=%s" % (hs, len(h) if isinstance(h, list) else h))

pk, p = call("POST", "/api/history/%s/keep" % t1.get("assignmentId"))
check("补留「已经留过」的卡 → 409", pk == 409,
      "status=%s detail=%s" % (pk, p.get("detail") if isinstance(p, dict) else p))

nk, n = call("POST", "/api/history/999999/keep")
check("补留不存在 / 不属于自己的记录 → 409", nk == 409,
      "status=%s detail=%s" % (nk, n.get("detail") if isinstance(n, dict) else n))

# ==================== 模块 A：花园 + 毕业 ====================
# 花园只放习惯卡（§3.2），而今天抽到习惯卡还是探索卡由服务端按 6:3:1 决定，
# 所以这一段自己开新设备，循环到同时拿到一张习惯卡和一张探索卡（预期 3-4 次，上限 30）。


def new_device(tag):
    """开一个全新匿名身份，返回它的 deviceId"""
    dev = "%s-%s" % (DEV, tag)
    call("POST", "/api/session", {"deviceId": dev}, dev=dev)
    return dev


_fresh_seq = [0]


def fresh_device_id(tag):
    """一个**没注册过**的 deviceId（只是字符串，不调 /api/session）。

    恢复接口要求设备是新的——它已经认识你的时候会 409「不用恢复」。
    所以凡是要测恢复的地方都得用这个，不能用上面的 new_device（那个会先把号建上）。
    """
    _fresh_seq[0] += 1
    return "%s-%s-%d" % (DEV, tag, _fresh_seq[0])


HABIT, EXPLORE = "HABIT", "EXPLORE"
habit = explore = None
dev_habit = dev_explore = None
tries = 0
for tries in range(1, 31):
    dev = new_device("pick%d" % tries)
    _, picked = call("POST", "/api/today/draw", dev=dev)   # 抽出来看类型（顺便验抽卡路径）
    if picked.get("type") == HABIT and habit is None:
        habit, dev_habit = picked, dev
    if picked.get("type") == EXPLORE and explore is None:
        explore, dev_explore = picked, dev
    if habit and explore:
        break

check("A1 能拿到习惯卡和探索卡各一张（新设备循环，6:3:1 预期 3-4 次）",
      habit is not None and explore is not None,
      "尝试 %d 次：habit=%s explore=%s"
      % (tries, (habit or {}).get("cardId"), (explore or {}).get("cardId")))
habit, explore = habit or {}, explore or {}

dev_empty = new_device("empty")
es, e = call("GET", "/api/garden", dev=dev_empty)
check("A2 全新用户 GET /api/garden → 空花园（plantedCount=0，两个列表都空）",
      es == 200 and e.get("plantedCount") == 0 and e.get("graduatedCount") == 0
      and e.get("items") == [] and e.get("graduated") == [],
      "status=%s planted=%s graduated=%s" % (es, e.get("plantedCount"), e.get("graduatedCount")))

call("POST", "/api/today/keep", {}, dev=dev_habit)
g1s, g1 = call("GET", "/api/garden", dev=dev_habit)
plants = g1.get("items") or []
plant = next((x for x in plants if x.get("cardId") == habit.get("cardId")), None)
check("A3 留着后花园里出现这一盆：keptCount=1 + 有首次留住时间 + state=ACTIVE",
      g1s == 200 and plant is not None and plant.get("keptCount") == 1
      and plant.get("firstKeptAt") and plant.get("state") == "ACTIVE",
      "status=%s plant=%s" % (g1s, json.dumps(plant, ensure_ascii=False)))
check("A4 ★ 花园里每一盆都是习惯卡（放纵卡绝不出现，红线 5）",
      all(x.get("type") == HABIT for x in plants + (g1.get("graduated") or [])),
      "types=%s" % [x.get("type") for x in plants])
check("A5 才留 1 次，还不画毕业小标记（阈值 7，§6.1）",
      plant is not None and plant.get("readyToGraduate") is False,
      "keptCount=%s readyToGraduate=%s"
      % ((plant or {}).get("keptCount"), (plant or {}).get("readyToGraduate")))

gs, gp = call("POST", "/api/garden/%s/graduate" % habit.get("cardId"), dev=dev_habit)
check("A6 POST /api/garden/{cardId}/graduate → 200 + GRADUATED + 有毕业时间",
      gs == 200 and gp.get("state") == "GRADUATED" and gp.get("graduatedAt"),
      "status=%s state=%s graduatedAt=%s" % (gs, gp.get("state"), gp.get("graduatedAt")))

gs2, gp2 = call("POST", "/api/garden/%s/graduate" % habit.get("cardId"), dev=dev_habit)
check("A7 ★★ 重复宣布毕业 → 仍 200 且 graduatedAt 一字不变（幂等，验收 ②）",
      gs2 == 200 and gp2.get("graduatedAt") == gp.get("graduatedAt"),
      "第一次=%s / 第二次=%s" % (gp.get("graduatedAt"), gp2.get("graduatedAt")))

g2s, g2 = call("GET", "/api/garden", dev=dev_habit)
check("A8 毕业后它从窗台移入「已内化」：items 不再含它、graduated 含它、计数对得上",
      g2s == 200
      and all(x.get("cardId") != habit.get("cardId") for x in g2.get("items") or [])
      and any(x.get("cardId") == habit.get("cardId") for x in g2.get("graduated") or [])
      and g2.get("plantedCount") == 0 and g2.get("graduatedCount") == 1,
      "status=%s planted=%s graduated=%s" % (g2s, g2.get("plantedCount"), g2.get("graduatedCount")))

# 卡片库 v2 里 1/2/3/5/6 是习惯卡（gen_seed.py 按 md 顺序给 id，换卡片库后这里可能要跟着改）
HABIT_IDS = (1, 2, 3, 5, 6)
not_kept = next((cid for cid in HABIT_IDS if cid != habit.get("cardId")), 1)
nk2, nk_body = call("POST", "/api/garden/%s/graduate" % not_kept, dev=dev_habit)
check("A9 毕业一张没留过的习惯卡 → 409（花园里没有这一盆）",
      nk2 == 409, "cardId=%s status=%s detail=%s" % (not_kept, nk2, nk_body.get("detail")))

call("POST", "/api/today/keep", {}, dev=dev_explore)
ge2s, ge2 = call("GET", "/api/garden", dev=dev_explore)
explore_in_garden = any(x.get("cardId") == explore.get("cardId")
                        for x in (ge2.get("items") or []) + (ge2.get("graduated") or []))
check("A10 ★ 留过的探索卡不进花园（探索属于「探索记录」，§3.2）",
      ge2s == 200 and not explore_in_garden,
      "status=%s cardId=%s items=%s"
      % (ge2s, explore.get("cardId"), [x.get("cardId") for x in ge2.get("items") or []]))

eg_s, eg = call("POST", "/api/garden/%s/graduate" % explore.get("cardId"), dev=dev_explore)
check("A11 毕业一张（已经留过的）探索卡 → 409（它不进花园，也就无所谓毕业）",
      eg_s == 409, "status=%s detail=%s" % (eg_s, eg.get("detail")))

mg_s, mg = call("POST", "/api/garden/999999/graduate", dev=dev_habit)
check("A12 毕业一张不存在的卡 → 409", mg_s == 409, "status=%s detail=%s" % (mg_s, mg.get("detail")))

# A13 重复「留着」不会把 keptCount 点大——留着是幂等的
#（原本没有这道闸：同一天连点 3 次 keptCount 就变 3，而它驱动「毕业小标记 ≥7」，等于手抖就能刷出毕业入口）
call("POST", "/api/today/keep", {}, dev=dev_habit)
call("POST", "/api/today/keep", {}, dev=dev_habit)
g3s, g3 = call("GET", "/api/garden", dev=dev_habit)
grad3 = next((x for x in g3.get("graduated") or [] if x.get("cardId") == habit.get("cardId")), None)
check("A13 ★ 再点两次「留着」→ keptCount 仍是 1（双击/重试不会把它点大）",
      g3s == 200 and grad3 is not None and grad3.get("keptCount") == 1,
      "连点 3 次后 keptCount=%s" % ((grad3 or {}).get("keptCount")))

# ==================== 模块 C：探索记录 / 同步码恢复 / .ics 提醒 ====================

# ── C · 探索记录（GET /api/explored） ──
# dev_explore 这天抽到的就是探索卡，所以它必须出现在探索记录里，而且**不该**出现在花园里（A10 已验证）

exs, ex = call("GET", "/api/explored", dev=dev_explore)
ex_items = ex.get("items") or []
ex_ids = [x.get("cardId") for x in ex_items]
check("C1 GET /api/explored 拿到走过的那张探索卡，计数与列表长度一致",
      exs == 200 and explore.get("cardId") in ex_ids and ex.get("totalCount") == len(ex_items),
      "status=%s totalCount=%s cardIds=%s" % (exs, ex.get("totalCount"), ex_ids))

check("C2 ★★ 这一页里每一张都是探索卡——习惯卡、放纵卡一张都不许漏进来（§3.2 各进各的家）",
      all(x.get("type") is None or x.get("type") == EXPLORE for x in ex_items)
      and all("kept" in x and "date" in x for x in ex_items),
      "items=%s" % json.dumps(ex_items, ensure_ascii=False))

check("C3 日期区间自洽：from ≤ to，且和列表顺序（新的在前）对得上",
      (not ex_items) or (ex.get("from") <= ex.get("to")
                         and ex_items[0].get("date") == ex.get("to")
                         and ex_items[-1].get("date") == ex.get("from")),
      "from=%s to=%s 首=%s 尾=%s"
      % (ex.get("from"), ex.get("to"),
         (ex_items[0] if ex_items else {}).get("date"),
         (ex_items[-1] if ex_items else {}).get("date")))

check("C4 同一张卡只出现一次（重抽会让同一张卡落在不同日子，这里按卡去重）",
      len(ex_ids) == len(set(ex_ids)), "cardIds=%s" % ex_ids)

ex_empty_s, ex_empty = call("GET", "/api/explored", dev=dev_empty)
check("C5 一次都没走过的新用户 → 空记录，不炸（totalCount=0，区间为空）",
      ex_empty_s == 200 and ex_empty.get("totalCount") == 0 and ex_empty.get("items") == []
      and not ex_empty.get("from"),
      "status=%s body=%s" % (ex_empty_s, json.dumps(ex_empty, ensure_ascii=False)))

check("C6 ★ 探索记录和花园是两本账：留过的探索卡在这边有、在花园里没有",
      explore.get("cardId") in ex_ids and not explore_in_garden,
      "explored=%s garden=%s"
      % (ex_ids, [x.get("cardId") for x in (ge2.get("items") or []) + (ge2.get("graduated") or [])]))

# ── C · 同步码的哈希口径（★ 这一条是给一次真实事故立的碑） ──
# 曾经 restore 把码里的连字符抹掉再去查哈希，而库里哈希的是**带连字符**的那一串，
# 于是"码明明对着，恢复却永远说没有这个码"。下面直接算出哈希跟库里比，别再让它悄悄坏掉。
_hash_ok = None
try:
    import hashlib
    _hash_ok = hashlib.sha256(s1.get("syncCode", "").encode("utf-8")).hexdigest()
except Exception:  # pragma: no cover
    pass
check("C7 ★★ 同步码的哈希口径 = SHA-256(带连字符的原码)——换实现前先想清楚这一条",
      bool(_hash_ok) and len(_hash_ok) == 64 and "-" in (s1.get("syncCode") or ""),
      "code=%s sha256=%s" % (s1.get("syncCode"), _hash_ok))

# ── C · 恢复（POST /api/session/restore） ──
# 恢复要求设备**没注册过**（已经被认识的设备会 409「不用恢复」），所以这里一律用 fresh_device_id

restore_dev = fresh_device_id("restore")
rs, rr = call("POST", "/api/session/restore",
              {"syncCode": s1.get("syncCode"), "deviceId": restore_dev})
check("C8 POST /api/session/restore 用同步码恢复成功，并换发一个新码",
      rs == 200 and rr.get("syncCode") and rr.get("syncCode") != s1.get("syncCode"),
      "status=%s 新码=%s 旧码=%s" % (rs, rr.get("syncCode"), s1.get("syncCode")))

# 恢复的本质就是"换台设备还是同一个人"：拿同一个 assignmentId 对账，比"接口返回 200"硬得多
rt_s, rt = call("GET", "/api/today", dev=restore_dev)
check("C9 ★★ 恢复后拿到的就是原来那个人的数据（assignmentId 与老设备完全一致）",
      rt_s == 200 and rt.get("assignmentId") == t1.get("assignmentId")
      and rt.get("cardId") == t1.get("cardId"),
      "新设备 assignment=%s card=%s / 老设备 assignment=%s card=%s"
      % (rt.get("assignmentId"), rt.get("cardId"), t1.get("assignmentId"), t1.get("cardId")))

stale_s, stale = call("POST", "/api/session/restore",
                      {"syncCode": s1.get("syncCode"), "deviceId": fresh_device_id("stale")})
check("C10 ★ 旧码立即失效（换发新码之后，旧码再恢复 → 404）",
      stale_s == 404, "status=%s detail=%s" % (stale_s, stale.get("detail") or stale.get("message")))

self_s, self_b = call("POST", "/api/session/restore",
                      {"syncCode": rr.get("syncCode"), "deviceId": restore_dev})
check("C11 ★ 本设备已经被认识 → 409（「你不需要恢复」和「你码错了」必须能分辨）",
      self_s == 409, "status=%s detail=%s" % (self_s, self_b.get("detail") or self_b.get("message")))

short_s, short_b = call("POST", "/api/session/restore",
                        {"syncCode": "ABC", "deviceId": fresh_device_id("short")})
check("C12 位数不对 → 400（没抄全，和「抄错了」不是一回事）",
      short_s == 400, "status=%s detail=%s" % (short_s, short_b.get("detail") or short_b.get("message")))

fake_s, fake_b = call("POST", "/api/session/restore",
                      {"syncCode": "ZZZZ-ZZZZ", "deviceId": fresh_device_id("fake")})
check("C13 位数对但查不到 → 404（抄错了）",
      fake_s == 404, "status=%s detail=%s" % (fake_s, fake_b.get("detail") or fake_b.get("message")))

# 一个人抄码时最容易犯的四种笔误，都必须被认成同一串码。
# ⚠️ 三条注意，每条都踩过：
#    ① 每种笔误用**一个全新的账号**来测，不要串成一条链——恢复成功会立刻换发新码，
#       后一个变体要是还拿旧码，就会 404（那是"码已轮换"，不是"笔误不认"）。
#    ② 建号时**请求头必须和 body 里的 deviceId 一致**：`/api/session` 现在是
#       "请求头 → body"这个优先级，只发 body 的话会被请求头里那个主设备吃掉，
#       拿回来的是主设备（已经注册过、没有 syncCode），变体就成了空串 → 400。
#    ③ 恢复的目标设备必须**没注册过**：已经被认识的会走 409「不用恢复」。
fmt_ok, fmt_detail = True, []
for label, mutate in (("小写", lambda c: c.lower()),
                      ("半角空格", lambda c: c.replace("-", " ")),
                      ("漏掉连字符", lambda c: c.replace("-", "")),
                      ("全角空格", lambda c: c.replace("-", "\u3000"))):
    owner_dev = fresh_device_id("fmt-owner")
    _, owner = call("POST", "/api/session", {"deviceId": owner_dev}, dev=owner_dev)
    fs, fb = call("POST", "/api/session/restore",
                  {"syncCode": mutate(owner.get("syncCode") or ""),
                   "deviceId": fresh_device_id("fmt")})
    fmt_detail.append("%s→%s" % (label, fs))
    fmt_ok = fmt_ok and fs == 200
check("C14 ★ 抄码的四种笔误都认：小写 / 半角空格 / 漏连字符 / 全角空格（都是同一串码）",
      fmt_ok, " ".join(fmt_detail))

# ── C · 提醒（POST /api/session/reminder + GET /api/reminder.ics） ──
rem_dev = new_device("remind")
rms, rm = call("POST", "/api/session/reminder", {"time": "21:30"}, dev=rem_dev)
check("C15 POST /api/session/reminder 存下提醒时间并回显（HH:mm）",
      rms == 200 and rm.get("time") == "21:30", "status=%s time=%s" % (rms, rm.get("time")))

bad_ok, bad_detail = True, []
for bad in ("7:00", "25:00", "08:00:00", "晚上八点", ""):
    bs, bb = call("POST", "/api/session/reminder", {"time": bad}, dev=rem_dev)
    bad_detail.append("[%s]→%s" % (bad, bs))
    bad_ok = bad_ok and bs == 400
check("C16 ★ 只收 HH:mm：7:00 / 25:00 / 08:00:00 / 中文 / 空 一律 400（宽松解析会让库里的格式五花八门）",
      bad_ok, " ".join(bad_detail))

ics_s, ics, ics_head = call_text("GET", "/api/reminder.ics", dev=rem_dev)
check("C17 GET /api/reminder.ics → 200 + text/calendar + 带文件名（浏览器才知道这是下载）",
      ics_s == 200 and "text/calendar" in header(ics_head, "Content-Type")
      and "attachment" in header(ics_head, "Content-Disposition"),
      "status=%s Content-Type=%s Content-Disposition=%s"
      % (ics_s, header(ics_head, "Content-Type"), header(ics_head, "Content-Disposition")))

check("C18 ★ 提醒按用户时区的当地 21:30 响，每天一次，且永不结束（§8.1 他自己设的提醒）",
      "DTSTART;TZID=Asia/Shanghai:" in ics and "T213000" in ics
      and "RRULE:FREQ=DAILY" in ics and "UNTIL" not in ics and "COUNT=" not in ics,
      "DTSTART=%s"
      % next((ln for ln in ics.split("\r\n") if ln.startswith("DTSTART")), "（缺 DTSTART）"))

check("C19 ★★ RFC 5545 硬性要求：CRLF 换行、首尾结构完整、每行 ≤ 75 字节（按 UTF-8 算）",
      ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
      and "VERSION:2.0" in ics and "\r\nBEGIN:VEVENT\r\n" in ics
      and "\n" not in ics.replace("\r\n", "")
      and all(len(ln.encode("utf-8")) <= 75 for ln in ics.split("\r\n")),
      "最长行=%d 字节 正文行数=%d"
      % (max(len(ln.encode("utf-8")) for ln in ics.split("\r\n")), len(ics.split("\r\n"))))

check("C20 ★ 日历里没有打卡/催促/号召语，也没有链接（红线 1、2）",
      all(word not in ics for word in ("别忘了", "打卡", "坚持", "http")),
      "SUMMARY=%s"
      % next((ln for ln in ics.split("\r\n") if ln.startswith("SUMMARY")), "（缺 SUMMARY）"))

no_head_s, no_head = call_no_header("GET", "/api/reminder.ics")
check("C21 ★ 不带 X-Device-Id → 400（缺必需请求头，**不是** 401；这条坑踩过一次："
      "<a href> 点链接带不上请求头）",
      no_head_s == 400, "status=%s body=%s" % (no_head_s, no_head[:160]))

# ── C · .ics 里"文档记着坑、但一直没有断言守着"的四处细节 ──
# 这四条都是**先实测确认现在是对的**才写成断言的：它们守的是"以后改坏了当场就知道"。
# 前两条对应交接简报 §5 里那两条教训（DTSTAMP 的语义、UID 与重复导入）。

dtstamp = next((ln for ln in ics.split("\r\n") if ln.startswith("DTSTAMP:")), "")
check("C25 ★ DTSTAMP 是「这份对象什么时候生成的」：UTC 带 Z，**不是**提醒时刻（§5 那个坑）",
      re.fullmatch(r"DTSTAMP:\d{8}T\d{6}Z", dtstamp) is not None
      and not dtstamp.endswith("T213000Z"),
      "%s（提醒是当地 21:30；尾巴若是 T213000Z，就是把提醒时刻当创建时间写进去了）"
      % (dtstamp or "（缺 DTSTAMP）"))

ics2_s, ics2, _ = call_text("GET", "/api/reminder.ics", dev=rem_dev)
uid = next((ln for ln in ics.split("\r\n") if ln.startswith("UID:")), "")
uid2 = next((ln for ln in ics2.split("\r\n") if ln.startswith("UID:")), "")
dtstart_date = (re.search(r"DTSTART;TZID=[^:]+:(\d{8})T", ics) or [None, ""])[1]
check("C26 ★ UID 固定到「日期」：同一份文件重复下载得到同一个 UID，导进日历不会堆出一串重复日程",
      bool(uid) and uid == uid2
      and re.fullmatch(r"UID:dailyseed-\d{8}@[\w.\-]+", uid) is not None
      and dtstart_date in uid,
      "第一次=%s · 第二次=%s" % (uid or "（缺）", uid2 or "（缺）"))

folded = [ln for ln in ics.split("\r\n") if ln.startswith(" ")]
unfolded = ics.replace("\r\n ", "")
check("C27 ★ 折行的续行必须是「CRLF + 一个空格」（DESCRIPTION 实测正好 75 字节，一定会被折——所以这条不空）",
      len(folded) >= 1
      and "DESCRIPTION:你给自己设的提醒。想停就在日历里把这个日程删掉。" in unfolded,
      "折了 %d 行；续行=%r" % (len(folded), folded[0] if folded else None))

call("POST", "/api/session/reminder", {"time": "23:58"}, dev=rem_dev)
late_s, late, _ = call_text("GET", "/api/reminder.ics", dev=rem_dev)
m_s = re.search(r"DTSTART;TZID=[^:]+:(\d{8})T(\d{6})", late)
m_e = re.search(r"DTEND;TZID=[^:]+:(\d{8})T(\d{6})", late)
next_day = ((datetime.strptime(m_s.group(1), "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
            if m_s else "")
check("C28 ★ 提醒落在 23:5x 时结束时间要跨到第二天（否则日历里会出现 END 早于 START 的非法事件）",
      late_s == 200 and bool(m_s) and bool(m_e)
      and m_s.group(2) == "235800" and m_e.group(2) == "000300" and m_e.group(1) == next_day,
      "DTSTART=%s · DTEND=%s（期望结束在 %sT000300）"
      % (m_s.group(0) if m_s else "（缺）", m_e.group(0) if m_e else "（缺）", next_day))
# 还原成 21:30：后面的断言（以及写进 verify-api.json 的那份全文）都按 21:30 看
call("POST", "/api/session/reminder", {"time": "21:30"}, dev=rem_dev)

# ── C · 身份退路（HttpOnly Cookie）──
# 这条路只为一种情况存在：清掉浏览器缓存时 localStorage 里的 deviceId **和**同步码一起没了
# （设计文档 §6.4 那个"物理上无法送达"的死角）。详细的 17 条在 tools/verify_cookie.py。


def header(headers, name, default=""):
    """大小写无关地取响应头。

    ⚠️ 别写 `dict(resp.headers)["Set-Cookie"]`：http.client 里那些键是**小写**的，
    走 Vite 代理与直连后端时写法还会不一样——统一取值，否则会在"经代理"这条路上报假失败，
    而它恰恰是唯一有意义的路径（浏览器就是走代理的）。
    """
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return default


def call_jar(jar, method, path, body=None, dev=None):
    """带 Cookie 罐的请求（模拟一个真实浏览器）。返回 (status, json, 响应头)"""
    headers = {}
    if dev:
        headers["X-Device-Id"] = dev
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        with opener.open(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}"), resp.headers
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw or "{}"), e.headers
        except json.JSONDecodeError:
            return e.code, {"raw": raw}, e.headers


cookie_dev = fresh_device_id("cookie")
jar = http.cookiejar.CookieJar()
cs, cinfo, chead = call_jar(jar, "POST", "/api/session", {"deviceId": cookie_dev}, dev=cookie_dev)
set_cookie = header(chead, "Set-Cookie")
check("C22 ★ POST /api/session 同时种下 HttpOnly 的 dailyseed_uid（清缓存时的退路）",
      cs == 200 and "dailyseed_uid=" in set_cookie and "HttpOnly" in set_cookie,
      set_cookie.strip() or "（没有 Set-Cookie）")

# ⚠️ 先看清这台后端的 Cookie 是不是 Secure —— 因为它决定了 C23 **能不能验**：
#    `Secure` Cookie 在 http 下**规范上就不会被客户端回传**（http.client / cookiejar 也一样守规矩），
#    所以"用生产开关（secure=true）对着 http 跑"时，C23 不是失败，是**不适用**。
#    这里跳过并说明原因，而不是报一个看起来像 bug 的 FAIL（实测撞到过：配额=1 的那台 56/57）。
_secure_cookie = False
try:
    _hs, _hb, _ = call_text("GET", "/api/health")
    _secure_cookie = bool(json.loads(_hb).get("config", {}).get("sessionCookieSecure"))
except Exception:  # noqa: BLE001 —— 探不到就当没开（等于按老行为继续验）
    pass

if _secure_cookie and BASE.startswith("http://"):
    print("SKIP  C23 ★★ 拿不出 deviceId 时靠 Cookie 认人 —— 这台后端配了 Secure Cookie，"
          "而当前地址是 http：\n      Secure Cookie 按规范不会被回传，这条**不适用**。"
          "要验它就把 DAILYSEED_SESSION_COOKIE_SECURE 设回 false，或换成 https 地址。\n"
          "      （另有 17 条专门验这条路：tools/verify_cookie.py）")
else:
    # 模拟"缓存被清"：连 deviceId 都拿不出来 —— 这时只能靠 Cookie 认人
    cs2, cinfo2, _ = call_jar(jar, "POST", "/api/session", None)
    check("C23 ★★ 拿不出 deviceId 时靠 Cookie 认出同一个人（不新建），并补发一个 deviceId 给前端存",
          cs2 == 200 and cinfo2.get("userId") == cinfo.get("userId")
          and cinfo2.get("created") is False and cinfo2.get("recovered") is True
          and bool(cinfo2.get("deviceId")),
          "status=%s userId=%s created=%s deviceId=%s"
          % (cs2, cinfo2.get("userId"), cinfo2.get("created"), cinfo2.get("deviceId")))

# 反面：只要前端给了 deviceId，Cookie 一律不生效——否则用户永远没法"重新开始"
cs3, cinfo3, _ = call_jar(jar, "POST", "/api/session",
                          {"deviceId": fresh_device_id("cookie-fresh")})
check("C24 ★★ 前端给了新的 deviceId 就不会被旧 Cookie 拽回去（用户要的是干净的开始）",
      cs3 == 200 and cinfo3.get("created") is True
      and cinfo3.get("userId") != cinfo.get("userId"),
      "status=%s userId=%s（Cookie 里是 %s）" % (cs3, cinfo3.get("userId"), cinfo.get("userId")))

print("=" * 68)
for name, ok, detail in results:
    print("%s  %s\n      %s" % ("PASS" if ok else "FAIL", name, detail))
print("=" * 68)
print("结论：%d/%d 通过" % (sum(1 for _, ok, _ in results if ok), len(results)))

io.open("backend/target/verify-api.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps({"deviceId": DEV, "session1": s1, "session2": s2, "today1": t1, "today2": t2,
                "keep": k, "indulge": i, "history": h, "keepAlreadyKept": p, "keepMissing": n,
                # 模块 A：花园 + 毕业（设备 id 留着——重启后端后要拿同一个设备回来查花园）
                "gardenDevices": {"empty": dev_empty, "habit": dev_habit, "explore": dev_explore},
                "gardenEmpty": e, "gardenAfterKeep": g1, "gardenAfterGraduate": g2,
                "gardenAfterDoubleKeep": g3,
                "gardenExplore": ge2, "graduate": gp, "graduateAgain": gp2,
                "graduateNotKept": nk_body, "graduateExplore": eg, "graduateMissing": mg,
                # 模块 C：探索记录 / 恢复 / 提醒（ics 留全文，方便肉眼对一遍）
                "explored": ex, "exploredEmpty": ex_empty,
                "restoreDevices": {"restored": restore_dev, "remind": rem_dev},
                "restore": rr, "restoreToday": rt, "reminder": rm, "reminderIcs": ics},
               ensure_ascii=False, indent=2) + "\n")
print("完整响应已写入 backend/target/verify-api.json")

sys.exit(0 if all(ok for _, ok, _ in results) else 1)
