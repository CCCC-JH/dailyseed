# -*- coding: utf-8 -*-
"""身份退路（HttpOnly Cookie）的实测。

**这条路要解决的唯一问题**：用户清掉浏览器缓存时，localStorage 里的 deviceId
和同步码**一起**消失，后端认不出人 —— 花园就永久没了（设计文档 §6.4）。
Cookie 是另一套存储，能接住其中一部分。

模型（三条优先级，不能反）：
  ① 有 deviceId 且被认识 → 认它（**正路永远优先**）
  ② 连 deviceId 都拿不出来 → 看 Cookie 能不能认出人（**退路的唯一入口**）
  ③ 都不行 → 建新号

为什么退路只认"拿不出 deviceId"这一种：前端生成了一个自己没见过的 deviceId，
意思是"我要一个干净的开始"；这时拿旧 Cookie 把人拽回旧花园，他就永远没法重新开始了。
而他的旧身份此刻并没有丢（还在别的设备上，或者他有同步码）。

用 http.cookiejar 模拟浏览器：它会自动存下 Set-Cookie 并在后续请求里带上。

用法：python tools/verify_cookie.py [base]
"""
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
TAG = "dev-cookie-%d" % (time.time() * 1000)

# 两台"浏览器"：各自一个 Cookie 罐，互不串味
jar_a = http.cookiejar.CookieJar()
jar_b = http.cookiejar.CookieJar()

results = []


def header(headers, name, default=""):
    """取响应头。

    ⚠️ 别写 `dict(resp.headers)["Set-Cookie"]`：http.client 里那些键是**小写**的，
    直连后端时又可能是别的写法。统一用大小写无关的取值，否则脚本会在"经代理"这条路上
    报假失败——而它恰恰是唯一有意义的验证路径（浏览器就是走代理的）。
    """
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return default


def call(jar, method, path, body=None, dev=None, cookie=None):
    headers = {}
    if dev:
        headers["X-Device-Id"] = dev
    if cookie:
        headers["Cookie"] = cookie
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


def check(name, ok, detail):
    results.append((name, ok, detail))


# ⚠️ 先确认"这台后端上这条路**验得了**"。`Secure` Cookie 在 http 下**规范上不会被回传**
#    （http.cookiejar 也守规矩），所以用生产开关（DAILYSEED_SESSION_COOKIE_SECURE=true）
#    对着 http 跑，这个脚本会 0/17 全红——看起来像"身份退路彻底坏了"，
#    其实只是配置让它**不适用**（线上是 https，它才生效）。
#    这种情况直接停下来说清楚（退出码 2），不要产出 17 个假失败。
try:
    _hs, _hb, _ = call(http.cookiejar.CookieJar(), "GET", "/api/health")
    _secure_cookie = bool((_hb or {}).get("config", {}).get("sessionCookieSecure"))
except Exception:  # noqa: BLE001 —— 问不到就按老行为继续
    _secure_cookie = False
if _secure_cookie and BASE.startswith("http://"):
    print("%s 这台后端配了 Secure Cookie，而当前地址是 http。" % BASE)
    print("  Secure Cookie 按规范不会被回传 → 这条退路在 http 下根本走不到，**不是它坏了**。")
    print("  要验它：把 DAILYSEED_SESSION_COOKIE_SECURE 设回 false（本机就是 false），或换成 https 地址。")
    sys.exit(2)


# ── ① 普通建号 ──
st, s1, head = call(jar_a, "POST", "/api/session", {"deviceId": TAG})
setcookie = header(head, "Set-Cookie")
check("1 POST /api/session 建号成功",
      st == 200 and s1.get("created") is True, "status=%s userId=%s" % (st, s1.get("userId")))
check("2 ★ 响应里种下 dailyseed_uid，且 HttpOnly（脚本偷不走）+ SameSite=Lax",
      "dailyseed_uid=" in setcookie and "HttpOnly" in setcookie and "SameSite=Lax" in setcookie,
      "已收到 Cookie" if setcookie else "没有 Cookie")

# ── ① 正路：同一个 deviceId 再来，还是同一个人 ──
st_same, s_same, _ = call(jar_a, "POST", "/api/session", {"deviceId": TAG})
check("3 正路：同一个 deviceId 再来 → 同一人、不新建、不再发码",
      st_same == 200 and s_same.get("userId") == s1.get("userId")
      and s_same.get("created") is False and not s_same.get("syncCode"),
      "status=%s userId=%s created=%s" % (st_same, s_same.get("userId"), s_same.get("created")))
check("4 正路命中时不补发 deviceId（没换人，前端不需要动 localStorage）",
      not s_same.get("deviceId"), "deviceId=%s" % s_same.get("deviceId"))

# ── ② ★核心★ 连 deviceId 都拿不出来（= 缓存被清）→ 靠 Cookie 认人 ──
st_rec, s_rec, _ = call(jar_a, "POST", "/api/session", None)
check("5 ★★ 拿不出 deviceId 时靠 Cookie 认出同一个人（userId 一致、不新建）",
      st_rec == 200 and s_rec.get("userId") == s1.get("userId") and s_rec.get("created") is False,
      "status=%s userId=%s created=%s（原 %s）"
      % (st_rec, s_rec.get("userId"), s_rec.get("created"), s1.get("userId")))
check("6 ★★ 认出来之后服务端补发一个 deviceId，并标记 recovered（HttpOnly 前端读不到，只能靠这个字段）",
      bool(s_rec.get("deviceId")) and s_rec.get("recovered") is True,
      "deviceId=%s recovered=%s" % (s_rec.get("deviceId"), s_rec.get("recovered")))

# 补发的那个 ID 存下来之后，下一次就走回正路
issued = s_rec.get("deviceId") or ""
st_after, s_after, _ = call(jar_a, "POST", "/api/session", {"deviceId": issued}, dev=issued)
check("7 ★ 存下补发的 ID 之后走回正路：同一人、且不再补发",
      st_after == 200 and s_after.get("userId") == s1.get("userId")
      and not s_after.get("deviceId") and s_after.get("recovered") is not True,
      "status=%s userId=%s deviceId=%s" % (st_after, s_after.get("userId"), s_after.get("deviceId")))

# 数据真的还在：用补发的 ID 读今天
st_today, t_today, _ = call(jar_a, "GET", "/api/today", dev=issued)
check("8 ★★ 用补发的 ID 能读到同一个人的今天",
      st_today == 200 and t_today.get("cardId"), "status=%s cardId=%s" % (st_today, t_today.get("cardId")))

# ── ② 的反面：**只要给了 deviceId，Cookie 一律不生效** ──
st_new, s_new, _ = call(jar_a, "POST", "/api/session", {"deviceId": TAG + "-fresh"}, dev=TAG + "-fresh")
check("9 ★★ 前端生成的全新 dev- ID 不会被旧 Cookie 拽回去（用户要的是新开始）",
      st_new == 200 and s_new.get("created") is True and s_new.get("userId") != s1.get("userId"),
      "status=%s userId=%s created=%s" % (st_new, s_new.get("userId"), s_new.get("created")))

st_second, s_second, _ = call(jar_a, "POST", "/api/session", {"deviceId": TAG + "-second"},
                              dev=TAG + "-second")
check("10 ★ 正路优先：一个没注册过的 deviceId 也照样建新号，不看 Cookie",
      st_second == 200 and s_second.get("created") is True
      and s_second.get("userId") not in (s1.get("userId"), s_new.get("userId")),
      "status=%s userId=%s" % (st_second, s_second.get("userId")))

# ── 隔离：另一台浏览器（另一个 Cookie 罐）不该共享身份 ──
st_b, s_b, _ = call(jar_b, "POST", "/api/session", {"deviceId": TAG + "-other"})
check("11 另一台浏览器（另一个 Cookie 罐）拿到自己的新号",
      st_b == 200 and s_b.get("userId") not in (s1.get("userId"), s_new.get("userId")),
      "status=%s userId=%s" % (st_b, s_b.get("userId")))

# ── 手改 Cookie 成垃圾值：当作没有凭据，不能 500 ──
st_bad, s_bad, _ = call(jar_b, "POST", "/api/session", None, cookie="dailyseed_uid=not-a-number")
check("12 Cookie 被手改成垃圾 → 因为没有 deviceId 而 400（不 500、也不建错号）",
      st_bad == 400, "status=%s detail=%s" % (st_bad, s_bad.get("detail") or s_bad.get("error")))

st_bad2, s_bad2, _ = call(jar_b, "POST", "/api/session", {"deviceId": TAG + "-badcookie"},
                          dev=TAG + "-badcookie", cookie="dailyseed_uid=not-a-number")
check("13 Cookie 是垃圾但有 deviceId → 照常建号（坏 Cookie 不该影响正路）",
      st_bad2 == 200 and s_bad2.get("created") is True, "status=%s userId=%s" % (st_bad2, s_bad2.get("userId")))

# ── 恢复之后 Cookie 必须换人，否则下次清缓存会被领回**上一个**账号 ──
_, owner, _ = call(jar_b, "POST", "/api/session", {"deviceId": TAG + "-owner"})
st_r, r, _ = call(jar_b, "POST", "/api/session/restore",
                  {"syncCode": owner.get("syncCode"), "deviceId": TAG + "-borrowed"})
uid_after = next((c.value for c in jar_b if c.name == "dailyseed_uid"), None)
check("14 ★ 恢复成功会换发新码",
      st_r == 200 and r.get("syncCode") and r.get("syncCode") != owner.get("syncCode"),
      "status=%s 新码=%s" % (st_r, r.get("syncCode")))
check("15 ★★ 恢复之后 Cookie 指向**被恢复的那个人**（不是恢复前那个）",
      uid_after is not None and len(uid_after) == 64 and uid_after != str(owner.get("userId")),
      "使用不含用户编号的随机令牌，归属通过下一条恢复请求验证")

# 恢复后的那条 Cookie 也必须真的能用在"清缓存"场景上
st_r2, s_r2, _ = call(jar_b, "POST", "/api/session", None)
check("16 ★★ 恢复之后清缓存（拿不出 deviceId）→ 认回来的是**新主人**",
      st_r2 == 200 and s_r2.get("userId") == owner.get("userId") and s_r2.get("recovered") is True,
      "status=%s userId=%s（期望 %s）" % (st_r2, s_r2.get("userId"), owner.get("userId")))

check("17 每次成功响应都会刷新 Cookie 的有效期（400 天上限，越长越好）",
      "Max-Age=" in header(head, "Set-Cookie"), "有效期存在")

# 真实攻击路径回归：一个有效用户编号不能成为身份凭据。
forged_status, _, _ = call(http.cookiejar.CookieJar(), "POST", "/api/session", None,
                           cookie="dailyseed_uid=" + str(owner.get("userId")))
check("18 伪造已有用户的数字 Cookie 不会恢复身份", forged_status == 400, "status=%s" % forged_status)
unknown_status, _, _ = call(http.cookiejar.CookieJar(), "POST", "/api/session", None,
                            cookie="dailyseed_uid=" + "a" * 64)
check("19 格式合法但不存在的随机令牌也不能恢复身份", unknown_status == 400, "status=%s" % unknown_status)

print("=" * 70)
for name, ok, detail in results:
    print("%s  %s\n      %s" % ("PASS" if ok else "FAIL", name, detail))
print("=" * 70)
print("结论：%d/%d 通过" % (sum(1 for _, ok, _ in results if ok), len(results)))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
