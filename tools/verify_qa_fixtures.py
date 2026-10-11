# -*- coding: utf-8 -*-
"""跑完 `seed_dev_user.py --qa` 之后，用**真接口**核对四台夹具确实长成了清单说的样子。

**为什么要有它**：`QA_FIXTURES`（夹具）和《真机验收清单》是两份会各自漂移的东西。
上一轮的现场就是这样——清单写着「`dev-qa-why-a` 今天 #25、`-b` #13、`-none` #30」，
库里那三台的「今天那张」却停在**前一天**；等日期一过，一打开页面就是另一张卡，
而清单看不出来。这个脚本把清单里**能机器判定的部分**钉住：

  · 今天那张是几号、是不是"已揭晓未留住可重抽"
  · 「?」的三种形态（A 级有 ③出处 / B 级没有 / 无依据连 `evidence` 键都没有）
  · 花园几盆、留住次数分档、「可毕业」小标记落在哪几盆、已内化的是哪张
  · 「走过的」几条、「补留」按钮画在哪几条（今天 + 昨天那张）
  · 红线 5 的两条：花园与「走过的」里**不许**出现放纵卡

期望值**从 `QA_FIXTURES` 推出来**，不在这份文件里再抄一遍——否则就是第三个会漂的副本。

用法（后端要跑着；造数和核对是两步）：
    python tools/seed_dev_user.py --qa
    python tools/verify_qa_fixtures.py                          # 直连 8080
    python tools/verify_qa_fixtures.py http://localhost:5173     # 对着代理再跑一遍（浏览器的真路径）
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seed_dev_user import QA_FIXTURES, canonical_sync_code  # noqa: E402

# 「?」的三种形态是**产品决定**，推不出来，只能写在这里（清单 §1 那张表也是这么写的）：
#   设备 → (evidence 级别 或 None, 第④段科普的 key 或 None)
WHY_FORMS = {
    "dev-qa-why-a": ("A", "sample-size"),
    "dev-qa-why-b": ("B", "21-days"),
    "dev-qa-why-none": (None, None),
    "dev-c-owner": (None, None),
}

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
results = []


def call(method, path, device=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if device:
        req.add_header("X-Device-Id", device)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "null")


def check(label, ok, detail=""):
    results.append((ok, label, detail))
    print("%s %s%s" % ("PASS" if ok else "FAIL", label, ("  ← " + detail) if detail else ""))


def card_types(card_ids):
    """卡号 → 类型。要判「探索卡」只能问库（接口在「走过的」里刻意不回 type）。"""
    try:
        from seed_dev_user import read_env, parse_db_url, find_mysql, Mysql
    except ImportError:
        return None
    exe = find_mysql()
    if not exe:
        return None
    cfg = read_env()
    dbc, dbname = parse_db_url(cfg.get("DB_URL") or "jdbc:mysql://localhost:3306/dailyseed")
    creds = {"host": dbc["host"], "port": dbc["port"],
             "user": cfg.get("DB_USER", "root"), "password": cfg.get("DB_PASSWORD", "")}
    out = Mysql(exe, creds, dbname).run(
        "SELECT id, type FROM cards WHERE id IN (%s);"
        % ",".join(str(i) for i in sorted(card_ids)))
    types = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip().isdigit():
            types[int(parts[0])] = parts[1].strip()
    return types


all_ids = set()
for spec in QA_FIXTURES:
    all_ids.add(spec["today"])
    all_ids.update(cid for _, cid, _ in spec["past"])
    all_ids.update(cid for cid, _ in spec["pots"])
    all_ids.update(cid for cid, _ in spec["graduated"])
TYPES = card_types(all_ids)
if TYPES is None:
    print("!! 找不到 mysql.exe / .env，探索记录那条只能弱判（子集而不是相等）\n")

print("base = %s" % BASE)
print("=" * 72)

for spec in QA_FIXTURES:
    device = spec["device"]
    level, science_key = WHY_FORMS[device]
    print("\n### %s" % device)

    status, sess = call("POST", "/api/session", device=device, body={"deviceId": device})
    check("  POST /api/session 认识这台设备（created=false、不再发码）",
          status == 200 and sess.get("created") is False and "syncCode" not in sess,
          "status=%s created=%s syncCode=%s" % (status, sess.get("created"), sess.get("syncCode")))
    print("     固定同步码 %s（造数写死的；设置页不会显示它，要用恢复接口验）"
          % canonical_sync_code(spec["code"]))

    _, today = call("GET", "/api/today", device)
    check("  今天 #%d 已揭晓 · 未留住 · 可重抽" % spec["today"],
          today.get("cardId") == spec["today"] and today.get("revealed") is True
          and today.get("kept") is False and today.get("canRedraw") is True
          and today.get("drawCount") == 1 and today.get("maxDraws") == 0,
          "cardId=%s revealed=%s kept=%s canRedraw=%s drawCount=%s maxDraws=%s"
          % (today.get("cardId"), today.get("revealed"), today.get("kept"),
             today.get("canRedraw"), today.get("drawCount"), today.get("maxDraws")))

    ev, sci = today.get("evidence"), today.get("science")
    if level is None:
        check("  无依据：响应里**没有** evidence 键（红线 3）", "evidence" not in today,
              "keys=%s" % sorted(today.keys()))
    else:
        check("  ? 形态 = %s 级" % level, bool(ev) and ev.get("level") == level, "evidence=%s" % ev)
        check("  ③ 出处（source）%s" % ("有" if level == "A" else "没有"),
              ("source" in (ev or {})) is (level == "A"), "evidence=%s" % ev)
    check("  ④ 多知道一点 = %s" % (science_key or "无"),
          (sci or {}).get("key") == science_key, "science=%s" % (sci or None))

    _, garden = call("GET", "/api/garden", device)
    pot_counts = sorted((c for _, c in spec["pots"]), reverse=True)
    counts = [p["keptCount"] for p in garden.get("items", [])]
    check("  花园 %d 盆 + %d 盆已内化" % (len(spec["pots"]), len(spec["graduated"])),
          garden.get("plantedCount") == len(spec["pots"])
          and garden.get("graduatedCount") == len(spec["graduated"]) and counts == pot_counts,
          "planted=%s graduated=%s counts=%s（期望 %s）"
          % (garden.get("plantedCount"), garden.get("graduatedCount"), counts, pot_counts))
    ready = [p["readyToGraduate"] for p in garden.get("items", [])]
    check("  「可毕业」小标记只落在 ≥7 次的那几盆",
          ready == [c >= 7 for c in pot_counts], "readyToGraduate=%s" % ready)
    if spec["graduated"]:
        check("  已内化的是 %s" % sorted(cid for cid, _ in spec["graduated"]),
              {p["cardId"] for p in garden.get("graduated", [])}
              == {cid for cid, _ in spec["graduated"]})
    check("  红线 5：花园里没有放纵卡",
          all(p.get("type") != "INDULGE" for p in garden.get("items", [])
              + garden.get("graduated", [])),
          "types=%s" % [p.get("type") for p in garden.get("items", [])])

    _, explored = call("GET", "/api/explored", device)
    eids = {i["cardId"] for i in explored.get("items", [])}
    past_ids = {cid for _, cid, _ in spec["past"]}
    if TYPES is None:
        check("  探索记录只来自 past 里的卡", eids <= past_ids,
              "ids=%s past=%s（拿不到卡类型，只能弱判）" % (sorted(eids), sorted(past_ids)))
    else:
        want = {cid for cid in past_ids if TYPES.get(cid) == "EXPLORE"}
        check("  走过的 %d 条（%s）" % (len(want), sorted(want)),
              explored.get("totalCount") == len(want) and eids == want,
              "totalCount=%s ids=%s" % (explored.get("totalCount"), sorted(eids)))
        check("  红线 5：走过的里全是探索卡（没有习惯卡、没有放纵卡）",
              all(TYPES.get(cid) == "EXPLORE" for cid in eids)
              and all(i.get("kept") in (True, False) for i in explored.get("items", [])),
              "ids=%s types=%s" % (sorted(eids), [TYPES.get(cid) for cid in sorted(eids)]))

    _, history = call("GET", "/api/history?days=3", device)
    # 补留窗口是 3 天（含今天）：今天 + 昨天 + 前天。画「补留」按钮的就是其中"未留住"的那几条
    want_unkept = {spec["today"]} | {cid for offset, cid, state in spec["past"]
                                    if offset <= 2 and state == "PENDING"}
    unkept = {h["cardId"] for h in history if not h["kept"]}
    check("  补留列表里未留住的是 %s（今天 + 昨天那张）" % sorted(want_unkept),
          unkept == want_unkept,
          "列表=%s 未留住=%s" % (sorted(h["cardId"] for h in history), sorted(unkept)))
    print("     canIndulge = %s（门槛：累计留住过 ≥5 种；`--qa` 那几台都是满足的）"
          % today.get("canIndulge"))

print("\n" + "=" * 72)
failed = [r for r in results if not r[0]]
print("合计 %d 条断言：%d PASS / %d FAIL" % (len(results), len(results) - len(failed), len(failed)))
for _, label, detail in failed:
    print("  FAIL %s  ← %s" % (label, detail))
raise SystemExit(1 if failed else 0)
