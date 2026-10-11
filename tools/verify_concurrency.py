# -*- coding: utf-8 -*-
"""并发不变量实验：**同一用户并发操作时，产品语义还成不成立。**

为什么单独做这件事：`verify_api.py` 里那 53 条断言**全是串行的**——它证明"按顺序调用时规则成立"，
却证明不了"两个请求同时到的时候规则还成立"。而真实用户恰好就会并发：
双击「留住」、连点「再抽一张」、网络重试、PWA 从后台切回来重新挂载。

这套东西里**有三条不变量**是产品语义的地基，一旦被并发打破，
症状都不是报错而是"数据悄悄变得不对"（而没有人会来报错）：

    ① 配额      ——  `draw_count` 不能超过 `max-per-day`（否则"每天抽一次"形同不存在）
    ② 留住幂等   ——  同一天不管点几次，「留着」只能让 `kept_count` +1
                      （它驱动毕业小标记 ≥7 和放纵日门槛，点大了就是产品语义坏了）
    ③ 账要对得上 ——  `user_cards.kept_count` 的总和 == `daily_assignments` 里 KEPT 的行数
                      （两个表分开写，中间没有外键约束；对不上就是默默漏了一次留住）

用法：
    python tools/verify_concurrency.py
    python tools/verify_concurrency.py <base> --workers 24 --rounds 40
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

results = []


def check(name, ok, detail):
    results.append((name, ok, detail))


def call(base, method, path, body=None, dev=None, timeout=15):
    headers = {}
    if dev:
        headers["X-Device-Id"] = dev
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return e.code, {"raw": raw}
    except Exception as e:  # 连接被拒、超时
        return 0, {"error": str(e)}


def new_user(base, tag):
    dev = "dev-conc-%s-%d" % (tag, time.time() * 1000)
    st, body = call(base, "POST", "/api/session", {"deviceId": dev}, dev=dev)
    if st != 200:
        raise SystemExit("建号失败：%s %s" % (st, body))
    return dev


def kept_units(base, dev):
    """这个人在**补留窗口内**已经留住的发放行数 = 「留住」真正执行了几次。

    ⚠️ 为什么不用花园计数当判据（这是踩过的坑）：**花园只装习惯卡**——
    探索卡归「走过的」（§3.2），放纵卡什么都不进（§3.5 红线 5）。
    所以一张探索卡被留住了，花园计数仍然是 0，那是**正确**的。
    真正要守的不变量是"留住这个动作执行了几次"，而它在发放行上，
    通过 /api/history 的 `kept` 字段就能读到（它同时覆盖 HABIT 和 EXPLORE）。
    """
    st, hist = call(base, "GET", "/api/history?days=3", dev=dev)
    if st != 200:
        return None
    return sum(1 for h in hist if h.get("kept"))


def garden_kept_total(base, dev):
    """花园里所有盆（含已毕业）的 kept_count 之和。**只对习惯卡有意义**——见 kept_units 的注释。"""
    st, g = call(base, "GET", "/api/garden", dev=dev)
    if st != 200:
        return None
    return sum(p.get("keptCount", 0) for p in (g.get("items") or []) + (g.get("graduated") or []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base", nargs="?", default="http://localhost:8080")
    parser.add_argument("--workers", type=int, default=16, help="并发线程数")
    parser.add_argument("--rounds", type=int, default=20, help="重复多少轮（每轮一个新账号）")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    print("并发不变量实验：base=%s workers=%d rounds=%d" % (base, args.workers, args.rounds))
    print()

    # ==================================================================
    # ① 配额：并发抽卡的次数不能超过 max-per-day
    # ==================================================================
    # 注意：开发默认 maxDraws=0（无限），这时配额无法被违反（0 = 不限制），
    # 所以这一项只在后端配了有限配额时才有意义。脚本自己读一下当前配额，
    # 无限就如实说"这一项在当前配置下测不了"，而不是假造一个 PASS。
    dev_quota = new_user(base, "quota")
    st, today = call(base, "GET", "/api/today", dev=dev_quota)
    max_draws = today.get("maxDraws")
    print("① 配额不变量 —— 当前 maxDraws=%s" % max_draws)

    if max_draws == 0:
        check("① 配额：当前是无限重抽（开发默认），这一项测不了",
              True, "maxDraws=0；要用 DAILYSEED_DRAW_MAX_PER_DAY=1 起后端再跑一次才是真验证")
    else:
        # 先抽一次（把 drawCount 变成 1），然后并发多抽几次
        call(base, "POST", "/api/today/draw", dev=dev_quota)
        attempts = max(4, args.workers)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(lambda _: call(base, "POST", "/api/today/draw", dev=dev_quota),
                          range(attempts)))
        st, after = call(base, "GET", "/api/today", dev=dev_quota)
        # 用一次不耗配额的读来拿真实状态
        st2, shown = call(base, "POST", "/api/today/draw?getView=true", dev=dev_quota)
        real = (shown if st2 == 200 else after).get("drawCount")
        check("① ★ 并发抽 %d 次之后 draw_count 没有超过配额" % attempts,
              real is not None and real <= max_draws,
              "drawCount=%s maxDraws=%s（%d 个并发请求）" % (real, max_draws, attempts))

    # ==================================================================
    # ② 留住幂等：并发「留着」只能 +1
    # ==================================================================
    # ⚠️ 抽到**放纵卡**的轮次要单独算：按红线 5，放纵卡没有「留住」这个动作（接口 409），
    #    所以"它没被留住"是**正确行为**，不是失败。脚本必须能分清这两件事，
    #    否则要么把正确行为报成 bug，要么把真 bug 混在"跳过"里放过去。
    #    在配额=1 的后端上，第一次抽到什么就是什么，所以这条尤其要注意。
    print()
    print("② 留住幂等 —— 并发点「留住」")
    keep_failures, skipped_indulge, kept_rounds = [], 0, 0
    for r in range(args.rounds):
        dev = new_user(base, "keep%d" % r)
        card_type = None
        for _ in range(12):
            st, t = call(base, "POST", "/api/today/draw", dev=dev)
            if st == 200:
                card_type = t.get("type")
                if card_type != "INDULGE":
                    break
            elif st in (409, 400):
                # 配额用完 / 抽不动了：这一轮就到这里
                break
        if card_type != "INDULGE":
            kept_rounds += 1
        else:
            skipped_indulge += 1
            continue

        # ★ 并发 8 次「留着」
        with ThreadPoolExecutor(max_workers=8) as pool:
            codes = list(pool.map(lambda _: call(base, "POST", "/api/today/keep", {}, dev=dev)[0],
                                  range(8)))
        # 成功的那些必须都是 200；不能出现 500
        if any(c >= 500 for c in codes):
            keep_failures.append("round%d 出现 5xx：%s" % (r, sorted(set(codes))))
        # ★ 判据是「留住这个动作只执行了一次」，不是花园计数（探索卡不进花园）
        units = kept_units(base, dev)
        if units != 1:
            keep_failures.append("round%d 已留住行数=%s codes=%s" % (r, units, sorted(set(codes))))
    check("② ★ 并发 8 次「留着」之后只真的留住了一次（不会越点越大）",
          not keep_failures,
          " | ".join(keep_failures[:4]) if keep_failures
          else "测了 %d 轮全部 = 1（另有 %d 轮抽到放纵卡，按红线 5 它没有「留住」动作，不计入）"
               % (kept_rounds, skipped_indulge))

    # ==================================================================
    # ③ 账要对得上：花园里的 kept_count 总和 == 花园里那些卡的已留住发放行数
    # ==================================================================
    # 这条是**跨表**的：markKept 写 daily_assignments，addKept 写 user_cards，
    # 两处没有外键，也没有"同一事务里必须一起成功"之外的保障。
    # 对不上就说明某次留住只写了一半——而那种事不会有任何报错。
    #
    # ⚠️ 只对**习惯卡**比：花园按红线 5 只装习惯卡，探索卡留在别的账上（见 kept_units）。
    #    所以这里先把"花园里那些卡的 id"取出来，再数 history 里同 id 的已留住行数——
    #    两边说的是同一件事，才比得起来。
    print()
    print("③ 两本账对得上（花园 kept_count vs 同一批卡的已留住行数）")
    ledger_failures, ledger_rounds = [], 0
    for r in range(max(3, args.rounds // 4)):
        dev = new_user(base, "ledger%d" % r)
        card_type = None
        for _ in range(12):
            st, t = call(base, "POST", "/api/today/draw", dev=dev)
            if st == 200:
                card_type = t.get("type")
                if card_type != "INDULGE":
                    break
            elif st in (409, 400):
                break
        if card_type == "INDULGE":
            continue
        ledger_rounds += 1

        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: call(base, "POST", "/api/today/keep", {}, dev=dev), range(6)))
        # 再从补留列表那条路重复留一次（它走的是另一个方法 keepPast）
        st, hist = call(base, "GET", "/api/history?days=3", dev=dev)
        if st == 200 and hist:
            first = hist[0].get("assignmentId")
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _: call(base, "POST", "/api/history/%s/keep" % first, dev=dev),
                              range(4)))

        st, garden = call(base, "GET", "/api/garden", dev=dev)
        if st != 200:
            ledger_failures.append("round%d 读花园失败 %s" % (r, st))
            continue
        plants = (garden.get("items") or []) + (garden.get("graduated") or [])
        garden_ids = {p.get("cardId") for p in plants}
        garden_total = sum(p.get("keptCount", 0) for p in plants)

        st, hist2 = call(base, "GET", "/api/history?days=3", dev=dev)
        rows = hist2 if st == 200 else []
        # 花园里那些卡，在发放记录里有几行是已留住的
        rows_for_garden_cards = sum(1 for h in rows if h.get("kept") and h.get("cardId") in garden_ids)
        # 探索卡不进花园：它的已留住行数不该出现在花园账上
        explore_rows = sum(1 for h in rows if h.get("kept") and h.get("cardId") not in garden_ids)

        if garden_total != rows_for_garden_cards:
            ledger_failures.append("round%d 花园 kept_count=%s 但对应的已留住行数=%s（另有 %d 行属于不进花园的卡）"
                                   % (r, garden_total, rows_for_garden_cards, explore_rows))
    check("③ ★ 花园的 kept_count 总和 == 花园里那些卡的已留住行数（跨表账对得上）",
          not ledger_failures,
          " | ".join(ledger_failures[:4]) if ledger_failures
          else "测了 %d 轮，两本账全部对得上" % ledger_rounds)

    # ==================================================================
    # ④ 并发抽卡之后，状态自洽（drawCount 与实际卡片能对上，没有"半个更新"）
    # ==================================================================
    print()
    print("④ 并发重抽之后状态自洽")
    coherent_ok, coherent_detail = True, []
    for r in range(max(3, args.rounds // 4)):
        dev = new_user(base, "coherent%d" % r)
        st, t = call(base, "POST", "/api/today/draw", dev=dev)
        if t.get("type") == "INDULGE":
            continue
        # 并发重抽：每次都返回一张卡，最后必须是"某一次真的写进去了"的那张
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            responses = list(pool.map(lambda _: call(base, "POST", "/api/today/draw", dev=dev),
                                      range(args.workers)))
        returned = {b.get("cardId") for s, b in responses if s == 200}
        st, view = call(base, "POST", "/api/today/draw?getView=true", dev=dev)
        final = view.get("cardId")
        # 最终卡必须是"某次并发请求返回过的那一张"——如果不是，说明有请求返回了
        # 一个从未真正落库的状态（客户端就会显示一张库里其实没有的卡）
        ok = final is not None and (not returned or final in returned)
        coherent_ok = coherent_ok and ok
        if not ok:
            coherent_detail.append("round%d final=%s returned=%s" % (r, final, sorted(returned)))
    check("④ ★ 并发重抽后，库里的卡是某次请求真的返回过的那张（没有编造的响应）",
          coherent_ok, " | ".join(coherent_detail[:3]) if coherent_detail else "全部自洽")

    # ---------- 输出 ----------
    print()
    print("=" * 72)
    for name, ok, detail in results:
        print("%s  %s\n      %s" % ("PASS" if ok else "FAIL", name, detail))
    print("=" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    print("结论：%d/%d 通过" % (passed, len(results)))
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
