#!/usr/bin/env bash
# DailySeed 上线前检查 + 起服务。
#
# 这个脚本的核心不是"把容器拉起来"，而是**在上线前把三个开关验掉**——
# 它们配错的后果都不是"报错"，而是"安静地按错的方式跑"：
#   ① 抽卡配额还是 0（无限重抽）→ 产品语义被推翻，而且没人会报错
#   ② 忘了 secure Cookie      → https 下浏览器直接丢掉它，"清缓存找回"静默失效
#   ③ 还承认着开发模式        → 上面两条的护栏全部失效
#
# 用法：
#   ./tools/deploy.sh check     # 只检查，不起服务
#   ./tools/deploy.sh up        # 检查通过就起（失败就停在这里）
#   ./tools/deploy.sh logs      # 跟日志
#   ./tools/deploy.sh down      # 停（保留数据卷）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
ylw()  { printf '\033[33m%s\033[0m\n' "$*"; }

fail=0
note() { [ "$1" = "0" ] && grn "  [ok]   $2" || { red "  [FAIL] $2"; fail=1; }; }

check() {
  echo
  echo "=== 上线前检查 ==="

  if [ ! -f backend/.env ]; then
    red "  [FAIL] backend/.env 不存在 —— cp backend/.env.example backend/.env 再改"
    exit 1
  fi
  # shellcheck disable=SC1091
  env_text="$(cat backend/.env)"

  get() { printf '%s\n' "$env_text" | grep -E "^[[:space:]]*$1[[:space:]]*=" | tail -n1 | cut -d= -f2- | tr -d '\r' | xargs || true; }

  draw="$(get DAILYSEED_DRAW_MAX_PER_DAY)"
  dev="$(get DAILYSEED_DEV_MODE)"
  secure="$(get DAILYSEED_SESSION_COOKIE_SECURE)"
  cookie="$(get DAILYSEED_SESSION_COOKIE_ENABLED)"
  pass="$(get DB_PASSWORD)"

  echo "  读到：draw=$draw dev=$dev cookie=$cookie secure=$secure"

  # ① 抽卡配额
  if [ -z "$draw" ]; then
    ylw "  [warn] 没写 DAILYSEED_DRAW_MAX_PER_DAY —— 会走默认 0（无限重抽）"
    fail=1
  elif [ "$draw" = "0" ]; then
    red "  [FAIL] 抽卡配额 = 0（无限重抽）：用户能一直重抽到满意为止，"
    red "         那会推翻「不确定性的味道」和放纵日门槛的意义。上线要设成 1"
    fail=1
  else
    note 0 "抽卡配额 = $draw"
  fi

  # ② 开发模式
  if [ "$dev" = "true" ]; then
    red "  [FAIL] DAILYSEED_DEV_MODE=true：这是本地开发的开关，上线必须去掉"
    fail=1
  else
    note 0 "未承认开发模式（护栏生效）"
  fi

  # ③ secure Cookie
  if [ "$cookie" != "false" ] && [ "$secure" != "true" ]; then
    red "  [FAIL] 身份 Cookie 没开 secure：https 下浏览器可能直接丢弃它，"
    red "         「清掉 localStorage 还能找回」这条退路会静默失效（不会有人报错）"
    fail=1
  else
    note 0 "身份 Cookie 配置可用（cookie=$cookie secure=$secure）"
  fi

  # ④ 数据库口令
  if [ -z "$pass" ] || [ "$pass" = "change-me" ] || [ "$pass" = "123456" ]; then
    red "  [FAIL] DB_PASSWORD 还是默认值 —— 必须换"
    fail=1
  else
    note 0 "DB_PASSWORD 已改"
  fi

  echo
  if [ "$fail" != "0" ]; then
    red "检查没过，不启动。改完 backend/.env 再来一次。"
    exit 1
  fi
  grn "检查通过。"
}

case "${1:-up}" in
  check) check ;;
  up)
    check
    echo
    echo "=== 起服务 ==="
    docker compose up -d --build
    echo
    echo "=== 等后端健康检查 ==="
    for i in $(seq 1 40); do
      sleep 3
      code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/health || true)"
      if [ "$code" = "200" ]; then
        grn "  [ok] /api/health → 200"
        curl -s http://localhost:8080/api/health | tr ',' '\n' | grep -i warning || true
        echo
        grn "前端 http://localhost:8088   后端 http://localhost:8080"
        exit 0
      fi
      if [ "$code" = "503" ]; then
        red "  [FAIL] /api/health → 503，探测项没过："
        curl -s http://localhost:8080/api/health || true
        echo
        exit 1
      fi
    done
    red "  120 秒内没就绪：docker compose logs api"
    exit 1
    ;;
  logs) docker compose logs -f --tail=200 ;;
  down) docker compose down ;;
  *) echo "用法：$0 {check|up|logs|down}"; exit 2 ;;
esac
