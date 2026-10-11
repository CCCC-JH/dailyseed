# -*- coding: utf-8 -*-
"""补留窗口的边界验证：用两条真实 fixture 记录，验「2 天前能补、4 天前不能补」。

用法：python tools/verify_catchup.py <deviceId> <inWindowAssignmentId> <outOfWindowAssignmentId>
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8080"
DEV, IN_ID, OUT_ID = sys.argv[1], sys.argv[2], sys.argv[3]


def call(method, path):
    req = urllib.request.Request(
        BASE + path,
        data=b"" if method == "POST" else None,
        headers={"X-Device-Id": DEV},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


results = []


def check(name, ok, detail):
    results.append((name, ok, detail))


# 1) 窗口内（2 天前、没留过）→ 应该能补
s, r = call("POST", "/api/history/%s/keep" % IN_ID)
check("补留「2 天前、没留过」的卡 → 200 且 kept=true",
      s == 200 and r.get("kept") is True,
      "status=%s date=%s kept=%s text=%s" % (s, r.get("date"), r.get("kept"), r.get("text")))

# 2) 窗口外（4 天前）→ 应该拒绝，并给出原因
s2, r2 = call("POST", "/api/history/%s/keep" % OUT_ID)
check("补留「4 天前」的卡 → 409（超出 3 天窗口）",
      s2 == 409, "status=%s detail=%s" % (s2, r2.get("detail")))

# 3) 窗口外那张不应出现在 history 列表里
s3, r3 = call("GET", "/api/history?days=3")
ids = [x.get("assignmentId") for x in r3] if isinstance(r3, list) else []
check("history(3) 只含窗口内记录（4 天前那张不出现）",
      s3 == 200 and int(OUT_ID) not in ids,
      "status=%s ids=%s" % (s3, ids))

# 4) 补留后再看 history：那张应该变成 kept
kept_ids = [x.get("assignmentId") for x in r3 if x.get("kept")] if isinstance(r3, list) else []
hs, hr = call("GET", "/api/history?days=3")
check("补留成功后，该记录在列表里标记为已留",
      any(x.get("assignmentId") == int(IN_ID) and x.get("kept") for x in hr),
      "kept=%s" % [(x.get("assignmentId"), x.get("kept")) for x in hr])

print("=" * 68)
for name, ok, detail in results:
    print("%s  %s\n      %s" % ("PASS" if ok else "FAIL", name, detail))
print("=" * 68)
print("结论：%d/%d 通过" % (sum(1 for _, ok, _ in results if ok), len(results)))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
