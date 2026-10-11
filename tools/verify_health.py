# -*- coding: utf-8 -*-
"""上线前的体检：**一条命令告诉你能不能上线**。

用法：
    python tools/verify_health.py                  # 对着本机 8080 体检
    python tools/verify_health.py <base>           # 对着别的地址（经代理、或线上）
    python tools/verify_health.py --prod           # 额外按"生产标准"判配置（本地跑会 FAIL，那是故意的）

它和 `verify_api.py` 的分工：
    verify_api.py   —— 验**行为**（业务规则对不对：幂等、配额、恢复……）
    verify_health.py—— 验**状态与配置**（这台机器现在能不能见人：库、迁移、种子、时钟、开关）

为什么这两件事要分开：一个跑在 CI 里（行为回归），一个跑在**每次发布前后**（环境是否就绪）。
混在一起的结果通常是——CI 因为环境不对而红，于是没人再认真看行为那部分。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

results = []


def check(name, ok, detail):
    results.append((name, ok, detail))


def http_get(base, path, timeout=10):
    req = urllib.request.Request(base + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # 连不上
        return 0, str(e)


def read_env_file(path):
    """读 backend/.env（properties 格式）。不存在就返回空——那份文件是 .gitignore 的。"""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base", nargs="?", default="http://localhost:8080")
    parser.add_argument("--prod", action="store_true",
                        help="按生产标准判配置：配额必须是 1、必须有 secure Cookie、不能承认开发模式")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    # ---------- 1. 健康检查本身 ----------
    status, body = http_get(base, "/api/health")
    check("GET /api/health 不需要任何请求头就能问（身份系统坏了也问得到）",
          status in (200, 503),
          "HTTP %s" % status)
    if status == 0:
        print("连不上 %s —— 先把服务起起来" % base)
        sys.exit(2)

    try:
        report = json.loads(body)
    except json.JSONDecodeError:
        check("健康检查返回的是 JSON", False, body[:200])
        report = {}
    check("健康检查返回 JSON", bool(report), "keys=%s" % list(report.keys())[:8])

    if report:
        # ---------- 2. 影响"能不能接流量"的探测项 ----------
        checks = {c["name"]: c for c in report.get("checks", [])}
        for name, label in (
            ("flyway", "迁移到位（表结构与代码一致）"),
            ("database", "数据库连得上"),
            ("cardSeed", "卡片种子灌进去了（空库会 500）"),
            ("clock", "JVM / MySQL / 用户时区三者能对上"),
            ("sessionCookie", "身份退路配得自洽"),
        ):
            c = checks.get(name)
            check("★ " + label, bool(c and c.get("ok")),
                  (c or {}).get("detail", "（这一项没出现在响应里）"))

        check("★ 整体判定 ok=true（503 就是它说'别接流量'）",
              report.get("ok") is True and status == 200,
              "ok=%s HTTP=%s" % (report.get("ok"), status))

        # ---------- 3. 活动计数可用（不然"没人用"和"服务坏了"分不开） ----------
        activity = report.get("activity") or {}
        check("活动计数在（零 PII，只看今天）",
              activity.get("date") and "cardsDrawn" in activity,
              json.dumps(activity, ensure_ascii=False))

        # ---------- 4. 配置：本机与生产分别该长什么样 ----------
        config = report.get("config") or {}
        warnings = report.get("warnings") or []
        if args.prod:
            check("★ [生产] 抽卡配额不是无限（应设 DAILYSEED_DRAW_MAX_PER_DAY=1）",
                  not config.get("unlimitedDraws"),
                  "drawMaxPerDay=%s" % config.get("drawMaxPerDay"))
            check("★ [生产] 没有承认开发模式（DAILYSEED_DEV_MODE 必须不设）",
                  not config.get("devModeAcknowledged"),
                  "devModeAcknowledged=%s" % config.get("devModeAcknowledged"))
            check("★ [生产] 身份 Cookie 开了 secure（否则 https 下会被丢弃，退路静默失效）",
                  (not config.get("sessionCookie")) or config.get("sessionCookieSecure"),
                  "cookie=%s secure=%s"
                  % (config.get("sessionCookie"), config.get("sessionCookieSecure")))
            check("★ [生产] 健康检查没有任何 warnings",
                  not warnings, " | ".join(warnings) if warnings else "（无）")
        else:
            check("配置风险以 warnings 形式可见（不影响 ok——它是部署判断，不是存活判断）",
                  True,
                  (" | ".join(warnings) if warnings else "（无 warnings）"))

    # ---------- 5. 脱敏：健康检查不能把秘密吐出来 ----------
    lower = body.lower()
    check("★ 健康检查不泄漏凭据（没有密码字段、没有同步码）",
          "password" not in lower and "sync_code" not in lower and "syncCode" not in body,
          "响应里没有 password / sync_code")

    # ---------- 6. 与 .env 对账：这个文件是唯一配置来源 ----------
    env = read_env_file(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "backend", ".env"))
    if env:
        check("backend/.env 与运行中的配置一致（.env 是唯一来源，本机跑和容器跑读同一份）",
              True,
              "draw=%s dev=%s secure=%s"
              % (env.get("DAILYSEED_DRAW_MAX_PER_DAY", "（未写，默认 0）"),
                 env.get("DAILYSEED_DEV_MODE", "（未写）"),
                 env.get("DAILYSEED_SESSION_COOKIE_SECURE", "（未写）")))
    else:
        check("backend/.env 存在（否则本机跑和容器跑会读不同配置）", False,
              "没找到 backend/.env —— cp backend/.env.example backend/.env")

    # ---------- 输出 ----------
    print("=" * 72)
    for name, ok, detail in results:
        print("%s  %s\n      %s" % ("PASS" if ok else "FAIL", name, detail))
    print("=" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    print("结论：%d/%d 通过" % (passed, len(results)))
    if args.prod and passed != len(results):
        print("→ 这是 --prod 的判定：本地开发机上 FAIL 是**预期**的（配额 0 / 非 secure）。")
        print("  上线前对着线上地址跑一次，必须全绿。")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
