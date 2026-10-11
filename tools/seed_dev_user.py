# -*- coding: utf-8 -*-
"""给前端造一个「已经用了几天」的测试用户。

**为什么需要它**：`POST /api/today/keep` 对同一天是幂等的，所以一个新设备在同一天里
怎么刷新都只有 1 盆 —— 花园的跨天视图、`readyToGraduate`（≥7 次）、放纵日入口
在前端**根本看不到**，只能盲写。这个脚本直接把过去几天的发放记录写进库里。

**不引入任何 Python 依赖**：它调用本机现成的 `mysql.exe`（和 `gen_seed.py` 只输出 SQL 是同一个路子）。
SQL 也不用 shell 拼字符串 —— 全部走 `mysql.exe` 的 stdin 喂进去，避免引号/反引号踩坑。

用法：
    python tools/seed_dev_user.py --qa             # ★ 真机验收四台设备（见下），一条命令重建「今天」的样子
    python tools/seed_dev_user.py                  # 造一个用了 3 天、含一个「可毕业」的盆
    python tools/seed_dev_user.py --days 6         # 造 6 天
    python tools/seed_dev_user.py --device dev-x   # 指定设备
    python tools/seed_dev_user.py --today-card 25  # 指定今天发哪张卡（默认按轮转）
    python tools/seed_dev_user.py --clean          # 删掉这个设备的测试数据
    python tools/seed_dev_user.py --sql            # 只打印 SQL，不执行（想自己跑 mysql 时用）

  手动反复验证「抽」这条路径（不用换设备、不用手改库）：
    python tools/seed_dev_user.py --reset-today    # 今天那张复活：未留住 + 回卡背 + 抽卡次数归零
    python tools/seed_dev_user.py --fresh          # 自动换一个新设备名（验「首次打开」）

⚠️ **为什么要有 `--qa`**：验收清单里那几台设备（一台 A 级、一台 B 级、一台无依据）原来是
**手写 SQL 塞进库的**，而轮转选卡的默认路径撞不出「今天正好是 25 号」这种安排。于是
① 日期一过，「今天那张」就变成了别的卡，清单上的 A/B/无依据对照点不出来；
② 谁也没法照着清单把它重建一遍。
`--qa` 把那张表变成**代码**，并且**每次都用运行时日期**算「今天」，所以它明天重跑还成立。
"""
import argparse
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

DEFAULT_DEVICE = "dev-frontend-fixture"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, "backend", ".env")

# ⚠️ 中文 Windows 的控制台是 cp936，而 ⚠️(U+26A0)、⑪(U+246A) 这类符号**不在 GBK 里**。
# 实测：`--qa` 会把四台设备全部造好、全部打印完，然后在最后一行 `print("⚠️ …")` 上抛
# `UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0'`——
# 退出码 1 + traceback，看起来像"造数失败"，其实数据已经写进去了。
# 所以：① 打印文本里不用 GBK 编不出来的符号；② 再兜一层 errors="replace"，
# 绝不让脚本死在"话说到一半"的地方。
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:  # noqa: BLE001 —— 老 Python 没有 reconfigure，就当没这回事
    pass

# 本机 MySQL 客户端可能在这几个地方（也可以直接用 --mysql 指定）
CANDIDATES = [
    r"D:\MySQL\MySQL Server 8.0\bin\mysql.exe",
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe",
    r"C:\xampp\mysql\bin\mysql.exe",
]


def read_env():
    """backend/.env 是 properties 格式，读 DB_URL / DB_USER / DB_PASSWORD。"""
    cfg = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                cfg[key.strip()] = value.strip()
    return cfg


def find_mysql(explicit=None):
    if explicit:
        return explicit
    for path in CANDIDATES:
        if os.path.exists(path):
            return path
    found = None
    for root in (r"D:\MySQL", r"C:\Program Files\MySQL"):
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            if "mysql.exe" in filenames:
                found = os.path.join(dirpath, "mysql.exe")
                break
        if found:
            break
    return found


class Mysql:
    def __init__(self, exe, cfg, database):
        self.exe = exe
        self.database = database
        self.args = [
            exe,
            "-h", cfg.get("host", "localhost"),
            "-P", str(cfg.get("port", 3306)),
            "-u", cfg.get("user", "root"),
            f"--password={cfg.get('password', '')}",
            "--default-character-set=utf8mb4",
            "--batch",
            "--skip-column-names",
            database,
        ]

    def run(self, sql):
        proc = subprocess.run(
            self.args,
            input=sql.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
        return proc.stdout.decode("utf-8", "replace")


def parse_db_url(url):
    rest = url.split("://", 1)[-1]
    hostport, _, tail = rest.partition("/")
    dbname = tail.split("?", 1)[0] or "dailyseed"
    host, _, port = hostport.partition(":")
    return {"host": host or "localhost", "port": int(port or 3306)}, dbname


def sql_str(value):
    """把字符串转成 SQL 字面量（够用即可：这些值全是我们自己构造的）"""
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def stamp(day, hour=21, minute=12, second=30):
    return f"{day.isoformat()} {hour:02d}:{minute:02d}:{second:02d}"


def build_sql(device, days, kinds, cards):
    """返回 (SQL 列表, 摘要)。刻意不用子查询取 user_id —— 用 @var 串起来，一次会话跑完。"""
    stmts = [
        "SET @dev := %s;" % sql_str(device),
        # 显式置 NULL：MySQL 的 `SELECT ... INTO @var` 零行时**不改动变量**，
        # 于是这条语句一旦和别的设备的语句拼在同一个会话里，就会认错人（实测踩过）
        "SET @uid := NULL;",
        # ⚠️ 这里取的是 `user_id`，**不是 `id`**。`user_devices` 有自己的自增主键 `id`，
        # 写成 `SELECT id` 拿到的是"设备行的编号"，只是**碰巧**在 users 和 user_devices
        # 一对一增长时等于 users.id —— 一旦两张表的自增错位，造出来的数据就会写到**别人的账号**上
        # （或者撞外键报错）。实测：users 到 701 而 user_devices 到 862，`--days 6` 直接 1452。
        "SELECT user_id INTO @uid FROM user_devices WHERE device_id = @dev;",
        # 没有这个设备就新建用户 + 设备
        "INSERT INTO users (sync_code_hash, timezone) "
        "SELECT SHA2(CONCAT('fixture-', @dev), 256), 'Asia/Shanghai' "
        "WHERE @uid IS NULL;",
        "SET @uid := IFNULL(@uid, LAST_INSERT_ID());",
        "INSERT INTO user_devices (user_id, device_id) SELECT @uid, @dev WHERE NOT EXISTS "
        "(SELECT 1 FROM user_devices WHERE device_id = @dev);",
        # 清掉旧的测试痕迹，保证可重复执行
        "DELETE FROM daily_assignments WHERE user_id = @uid;",
        "DELETE FROM user_cards WHERE user_id = @uid;",
    ]

    today = date.today()
    summary = []
    for offset in range(1, min(days, len(cards)) + 1):
        day = today - timedelta(days=offset)
        card_id = cards[(offset - 1) % len(cards)][0]
        stmts.append(
            "INSERT INTO daily_assignments (user_id, card_id, assigned_date, state, kept_at, created_at) "
            "VALUES (@uid, %d, '%s', 'KEPT', '%s', '%s');"
            % (card_id, day.isoformat(), stamp(day), stamp(day))
        )

    # 留住次数刻意分档，好让前端的四档植株 + 「留到 7 次」小标记都能看到
    counts = [16, 9, 7, 4, 2, 1, 1, 1]
    for idx, offset in enumerate(range(1, min(kinds, days, len(cards)) + 1)):
        day = today - timedelta(days=offset)
        card_id = cards[(offset - 1) % len(cards)][0]
        kept_count = counts[idx % len(counts)]
        first = day - timedelta(days=kept_count)
        stmts.append(
            "INSERT INTO user_cards (user_id, card_id, kept_count, first_kept_at, last_kept_at, state) "
            "VALUES (@uid, %d, %d, '%s', '%s', 'ACTIVE');"
            % (card_id, kept_count, stamp(first), stamp(day))
        )
        summary.append((card_id, kept_count))

    return stmts, summary


def build_draw_sql(device, cards, days, revealed, draw_count, reset_today=False, today_card=None):
    """设今天那张的揭晓与抽卡状态。

    「抽」的形式（V3）：revealed_at 为 NULL = 还是卡背，前端要点一下才翻开。
    验收时常常需要**故意停在卡背**，所以这里给一个开关，不用手工改库。

    ⚠️ build_sql 只造**过去**的发放记录（循环从 offset=1 起），今天那一行通常还不存在，
    所以这里必须先把它建出来——否则 UPDATE 会安安静静地改 0 行，看着"成功"其实没生效。

    {@code today_card} 是「今天发哪张卡」的显式指定（默认沿用同一套轮转：今天 = 第 days+1 天）。
    验收要的「今天正好是 25 号」撞不出来，只能指定——这也是那几台设备以前靠手写 SQL 的原因。
    """
    if today_card is None:
        today_card = cards[days % len(cards)][0]
    stmts = [
        "SET @dev := %s;" % sql_str(device),
        "SET @uid := NULL;",   # 理由同 build_sql：零行时 SELECT INTO 不改变量
        "SELECT user_id INTO @uid FROM user_devices WHERE device_id = @dev;",   # 是 user_id，不是 id
        "INSERT INTO daily_assignments (user_id, card_id, assigned_date, state) "
        "SELECT @uid, %d, CURDATE(), 'PENDING' WHERE @uid IS NOT NULL "
        "ON DUPLICATE KEY UPDATE id = id;" % today_card,
    ]
    if reset_today:
        # 把今天这张「复活」：未留住、回到卡背、抽卡次数归零。
        # 手动验证时想反复走一遍「抽 → 揭晓 → 留住」就靠它，不用换设备。
        # 注意：它**不会**从花园里撤掉已经留下的那一盆（要撤就 --clean 重造）。
        stmts.append(
            "UPDATE daily_assignments SET state='PENDING', kept_at=NULL, "
            "revealed_at=NULL, draw_count=0, swapped_at=NULL "
            "WHERE user_id = @uid AND assigned_date = CURDATE();")
        return stmts
    if revealed:
        stmts.append(
            "UPDATE daily_assignments SET revealed_at = NOW(6), draw_count = %d "
            "WHERE user_id = @uid AND assigned_date = CURDATE();" % draw_count)
    else:
        stmts.append(
            "UPDATE daily_assignments SET revealed_at = NULL, draw_count = 0 "
            "WHERE user_id = @uid AND assigned_date = CURDATE();")
    return stmts


def build_clean_sql(device):
    return [
        "SET @dev := %s;" % sql_str(device),
        # ⚠️ 这条尤其要置 NULL：零行时 @uid 会沿用上一台设备的 id，
        # 而下面最后一个 DELETE 是 `DELETE FROM users WHERE id = @uid` —— 会删错人
        "SET @uid := NULL;",
        "SELECT user_id INTO @uid FROM user_devices WHERE device_id = @dev;",   # 是 user_id，不是 id
        "DELETE FROM daily_assignments WHERE user_id = @uid;",
        "DELETE FROM user_cards WHERE user_id = @uid;",
        "DELETE FROM user_devices WHERE user_id = @uid;",
        "DELETE FROM users WHERE id = @uid;",
    ]


# ==================== 回读：造完之后"库里实际长什么样" ====================


def readback(db, device):
    """回读这台设备**实际**绑在哪个账号上、那个账号名下有多少发放记录与花园数据。

    为什么非要有这一步：造数最容易骗人的地方是"看着成功了"——脚本打印的摘要来自它**以为**
    写了什么，不是库里的真相。而"user_id 取错"这类错（见 build_sql 里那条注释）恰好会安静地
    把数据写到**别人的账号**上，摘要照样漂漂亮亮。回读是唯一能当场戳破它的东西。

    返回 (账号 id, 发放条数, 花园数据行数)；设备不存在则返回 None。
    """
    out = db.run(
        "SELECT d.user_id, "
        "(SELECT COUNT(*) FROM daily_assignments a WHERE a.user_id = d.user_id), "
        "(SELECT COUNT(*) FROM user_cards c WHERE c.user_id = d.user_id) "
        "FROM user_devices d WHERE d.device_id = %s;" % sql_str(device)).strip()
    if not out:
        return None
    parts = out.splitlines()[0].split("\t")
    return int(parts[0]), int(parts[1]), int(parts[2])


# ==================== 真机验收夹具（--qa） ====================
#
# 《DailySeed-真机验收清单》§1 / §1.6 的**机器可读版本**。改清单上的设备安排时，改这张表。
#
# 每一台的字段：
#   today        今天发哪张卡（验收要点就压在这个 id 上：A 级 / B 级 / 无依据各一台）
#   past         [(几天前, 卡号, 状态)]，1 = 昨天。状态 PENDING 表示"发过、没留"——
#                它才会在「补留」列表里长出按钮（清单 §2 今天那节要看的对比）
#   pots         [(卡号, 留住次数)]，进花园的盆。**只能是习惯卡**（GardenService 只放 HABIT）
#   graduated    [(卡号, 留住次数)]，已内化的盆
#   code         固定同步码。造数设备在「设置」页**看不到码**（后端对已认识的设备不再发码），
#                所以恢复那条路要用这里写死的码——哈希输入必须是**带连字符的规范形态**（见下）
#
# 卡号都不是随便挑的：pot 用 HABIT（2/3/5/6/7），探索记录用 EXPLORE（4/11/22），
# 今天那张按「?」的三种形态挑（25 = A 级、13 = B 级、30 = 无依据）。`validate_qa_cards` 会守着这件事。
QA_FIXTURES = [
    {
        "device": "dev-qa-why-a",
        "code": "A4R7-M2QX",
        "today": 25,          # HABIT · A 级（sample-size）→ ? 有 ①②③④
        "note": "A 级形态 + 花园 5 盆（16/9/7/2/1，前三个带「可毕业」）",
        "past": [(1, 8, "PENDING"), (2, 2, "KEPT"), (3, 6, "KEPT"), (4, 3, "KEPT")],
        "pots": [(2, 16), (3, 9), (5, 7), (6, 2), (7, 1)],
        "graduated": [],
    },
    {
        "device": "dev-qa-why-b",
        "code": "B6T3-N9KP",
        "today": 13,          # HABIT · B 级（21-days）→ ? 有 ①② + 「这是机制，不是研究结论」
        "note": "B 级形态 + 2 条探索记录（#11 A 级未留 / #4 无依据已留）",
        "past": [(1, 11, "PENDING"), (2, 4, "KEPT"), (3, 3, "KEPT"), (4, 5, "KEPT")],
        "pots": [(2, 16), (3, 9), (5, 7), (6, 2), (7, 1)],
        "graduated": [],
    },
    {
        "device": "dev-qa-why-none",
        "code": "C2W5-P8JZ",
        "today": 30,          # HABIT · 无依据 → 连「?」入口都不画（红线 3）
        "note": "无依据形态 + 4 盆 + 1 盆已内化（#5）",
        "past": [(1, 8, "PENDING"), (2, 3, "KEPT"), (3, 6, "KEPT"), (4, 5, "KEPT")],
        "pots": [(2, 16), (3, 9), (6, 2), (7, 1)],
        "graduated": [(5, 12)],
    },
    {
        "device": "dev-c-owner",
        "code": "D7X4-Q3MN",
        "today": 14,          # HABIT · 随便一张；这台是用来"提供同步码 + 恢复后对花园"的
        "note": "用了 6 天、花园 5 盆、跨天探索记录（#11/#4/#22）——恢复测试的来源设备",
        "past": [(1, 11, "KEPT"), (2, 4, "KEPT"), (3, 22, "KEPT"),
                 (4, 2, "KEPT"), (5, 3, "KEPT"), (6, 5, "KEPT")],
        "pots": [(2, 16), (3, 9), (5, 7), (6, 2), (7, 1)],
        "graduated": [],
    },
]

# 后端生成同步码用的字母表（UserStore.ALPHABET）：刻意没有 0/1/I/L/O，抄错成本高
SYNC_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
SYNC_DASH_AT = 4
SYNC_BARE_LEN = 8


def canonical_sync_code(raw):
    """整理成**落库时的规范形态** `K7M2-P9QX`（和后端 RestoreService.canonicalSyncCode 同一套规则）。

    ⚠️ 连字符必须补回去、不能抹掉：库里哈希的是带连字符那串，抹成 8 位裸码去写哈希，
    用户拿着"看起来完全正确"的码也永远恢复不了（模块 C 为这个坑查了四轮）。
    """
    bare = "".join(c for c in str(raw).upper() if c.isascii() and c.isalnum())
    if len(bare) != SYNC_BARE_LEN:
        raise SystemExit("同步码要 8 个有效字符，像 K7M2-P9QX 这样：%r" % raw)
    bad = sorted({c for c in bare if c not in SYNC_ALPHABET})
    if bad:
        raise SystemExit("同步码里有后端不会生成的字符 %s（字母表：%s）" % ("".join(bad), SYNC_ALPHABET))
    return bare[:SYNC_DASH_AT] + "-" + bare[SYNC_DASH_AT:]


def qa_stmts():
    """四台验收设备的完整 SQL（先清后建，可重复执行；「今天」按运行时日期算）。"""
    stmts = []
    today = date.today()
    for spec in QA_FIXTURES:
        dev = spec["device"]
        stmts += [
            "SET @dev := %s;" % sql_str(dev),
            # ⚠️ @old / @exclusive 必须先显式置值：MySQL 的 `SELECT ... INTO @var` 在**零行**时
            #    **不改动变量**（实测：先给 @u 赋 42，再查一个不存在的设备，@u 还是 42）。
            #    少了这一行，一次造多台时"新设备"会沿用**上一台**的 @uid——
            #    于是两个 device_id 挂到同一个账号上，互相把对方的发放记录覆盖掉。
            #    一台一个进程时看不出来（@uid 本来就是 NULL），一次造四台就必踩。
            "SET @old := NULL;",
            "SELECT user_id INTO @old FROM user_devices WHERE device_id = @dev;",   # 是 user_id，不是 id
            # 这个账号是不是"只挂着这一台设备"？只有这种账号才是夹具自己的，可以随便清。
            # 共用账号（比如刚在这台设备上做过"用同步码找回"的测试）一律不碰它的数据——
            # 那里面有别人的历史，清掉就是毁数据。零行时 @exclusive 保持 0，正是想要的默认。
            "SET @exclusive := 0;",
            "SELECT 1 INTO @exclusive FROM user_devices WHERE user_id = @old "
            "GROUP BY user_id HAVING COUNT(*) = 1;",
            "DELETE FROM daily_assignments WHERE user_id = @old AND @exclusive = 1;",
            "DELETE FROM user_cards WHERE user_id = @old AND @exclusive = 1;",
            # 共用账号就把这台设备摘出去：夹具不该跟着别人的账号走（否则两台设备互相覆盖）
            "DELETE FROM user_devices WHERE device_id = @dev AND @exclusive = 0;",
            "SET @uid := IF(@exclusive = 1, @old, NULL);",
            # 每台夹具一个**专属**账号：共用账号会让四台设备互相覆盖，
            # 而验收里「这台是 A 级、那台是 B 级」正是靠互不干扰才成立
            "INSERT INTO users (sync_code_hash, timezone) SELECT "
            "SHA2(CONCAT('fixture-', @dev, '-', UUID()), 256), 'Asia/Shanghai' WHERE @uid IS NULL;",
            "SET @uid := IFNULL(@uid, LAST_INSERT_ID());",
            "INSERT INTO user_devices (user_id, device_id) SELECT @uid, @dev WHERE NOT EXISTS "
            "(SELECT 1 FROM user_devices WHERE device_id = @dev);",
            # 固定同步码：恰好也是"重测抄码笔误"的重置手法（每成功一次后端就换一次码）
            #
            # 先把这个码从**别的**账号上收回来。`sync_code_hash` 上有唯一键，而"这个码挂在谁身上"
            # 会随着上一轮的串号 / "用同步码找回"的测试而漂移；不收回来，下面那条 UPDATE 会
            # 直接报 1062 把整次造数打断，留下"数据写了一半"的夹具（本轮就踩到了）。
            # 码是夹具的凭据，收回来是本分——被收的那个账号拿到的是一串随机哈希，等于失去了这个码。
            "UPDATE users SET sync_code_hash = SHA2(CONCAT('released-', UUID(), '-', RAND()), 256) "
            "WHERE id <> @uid AND sync_code_hash = SHA2(%s, 256);"
            % sql_str(canonical_sync_code(spec["code"])),
            "UPDATE users SET sync_code_hash = SHA2(%s, 256), timezone = 'Asia/Shanghai' "
            "WHERE id = @uid;" % sql_str(canonical_sync_code(spec["code"])),
        ]
        for offset, card_id, state in spec["past"]:
            day = today - timedelta(days=offset)
            kept = sql_str(stamp(day)) if state == "KEPT" else "NULL"
            stmts.append(
                "INSERT INTO daily_assignments "
                "(user_id, card_id, assigned_date, state, kept_at, revealed_at, draw_count, created_at) "
                "VALUES (@uid, %d, '%s', '%s', %s, '%s', 1, '%s');"
                % (card_id, day.isoformat(), state, kept, stamp(day), stamp(day))
            )
        # 今天那张：已揭晓、未留住、可重抽（draw_count=1 配开发默认的无限配额）
        stmts.append(
            "INSERT INTO daily_assignments "
            "(user_id, card_id, assigned_date, state, revealed_at, draw_count, created_at) "
            "VALUES (@uid, %d, CURDATE(), 'PENDING', NOW(6), 1, NOW(6));" % spec["today"]
        )
        for card_id, count in spec["pots"]:
            stmts.append(
                "INSERT INTO user_cards "
                "(user_id, card_id, kept_count, first_kept_at, last_kept_at, state) "
                "VALUES (@uid, %d, %d, '%s', '%s', 'ACTIVE');"
                % (card_id, count, stamp(today - timedelta(days=count)),
                   stamp(today - timedelta(days=1)))
            )
        for card_id, count in spec["graduated"]:
            stmts.append(
                "INSERT INTO user_cards "
                "(user_id, card_id, kept_count, first_kept_at, last_kept_at, state, graduated_at) "
                "VALUES (@uid, %d, %d, '%s', '%s', 'GRADUATED', '%s');"
                % (card_id, count, stamp(today - timedelta(days=count)),
                   stamp(today - timedelta(days=3)), stamp(today - timedelta(days=2)))
            )
    return stmts, today


def qa_card_ids():
    """夹具引用到的所有卡号（校验用）"""
    ids = set()
    for spec in QA_FIXTURES:
        ids.add(spec["today"])
        ids.update(cid for _, cid, _ in spec["past"])
        ids.update(cid for cid, _ in spec["pots"])
        ids.update(cid for cid, _ in spec["graduated"])
    return ids


def validate_qa_cards(types):
    """卡号对不上就当场停下——种子换过、卡号挪过位时，最怕的是"造出来看着像成功了"。

    {@code types} 是 {卡号: 类型}。两条硬约束：花园里只能有习惯卡；放纵卡一张都不许出现在夹具里。
    """
    for spec in QA_FIXTURES:
        dev = spec["device"]
        for label, cid in [("今天", spec["today"])] \
                + [("盆", cid) for cid, _ in spec["pots"]] \
                + [("已内化", cid) for cid, _ in spec["graduated"]]:
            t = types.get(cid)
            if t is None:
                raise SystemExit("%s：%s那张 #%d 在卡片库里不存在（种子变过？）" % (dev, label, cid))
            if t != "HABIT":
                raise SystemExit("%s：%s #%d 是 %s，但花园只放 HABIT" % (dev, label, cid, t))
        for offset, cid, _ in spec["past"]:
            t = types.get(cid)
            if t is None:
                raise SystemExit("%s：%d 天前那张 #%d 不存在" % (dev, offset, cid))
            if t == "INDULGE":
                raise SystemExit("%s：%d 天前那张 #%d 是放纵卡——放纵卡不进花园、不可补留（红线 5）"
                                 % (dev, offset, cid))


def qa_code_conflicts(db):
    """造数前看一眼：这四个同步码有没有挂在**不是它自己设备**的账号上。

    会漂移的原因很具体：上一轮串号（两台设备共用一个账号）、或者刚做过"用同步码找回"的测试。
    SQL 里会把码收回来（唯一键不容两个账号共用一个码），这里只是把这件事说出来。
    """
    conflicts = []
    for spec in QA_FIXTURES:
        code = canonical_sync_code(spec["code"])
        out = db.run(
            "SELECT u.id, IFNULL((SELECT GROUP_CONCAT(d2.device_id ORDER BY d2.device_id) "
            "FROM user_devices d2 WHERE d2.user_id = u.id), '(无设备)') "
            "FROM users u WHERE u.sync_code_hash = SHA2(%s, 256);" % sql_str(code))
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1] != spec["device"]:
                conflicts.append((code, parts[0], parts[1]))
    return conflicts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=None,
                    help="设备名（默认 %s；配 --fresh 时自动生成）" % DEFAULT_DEVICE)
    ap.add_argument("--days", type=int, default=3, help="往前造几天（不含今天）")
    ap.add_argument("--kinds", type=int, default=6, help="让几种卡处于「留住过」状态（≥5 才能看到放纵入口）")
    ap.add_argument("--unrevealed", action="store_true",
                    help="把今天那张留在**卡背**状态（默认预先揭晓，方便直接验页面）")
    ap.add_argument("--draw-count", type=int, default=1,
                    help="今天已抽几次（配合配额上限验「抽不动」时用，例如 --draw-count 1 配 max-per-day=1）")
    ap.add_argument("--reset-today", action="store_true",
                    help="把**今天那张复活**：未留住、回卡背、抽卡次数归零。"
                         "手动反复走「抽→揭晓→留住」就靠它，不必换设备（花园里已留的那盆不会撤掉）。"
                         "⚠️ 对 --fresh 的新设备无效（它本来就没有今天这张）")
    ap.add_argument("--today-card", type=int, default=None,
                    help="指定**今天发哪张卡**（默认按轮转）。验收里「今天正好是 25 号」这种安排就靠它")
    ap.add_argument("--qa", action="store_true",
                    help="★ 重建真机验收的四台设备（见 QA_FIXTURES）：今天那张按清单写死，"
                         "「今天」按运行时日期算，所以明天重跑依然成立。自带清理，可反复执行")
    ap.add_argument("--fresh", action="store_true",
                    help="自动换一个新设备名（免手改 deviceId），用来反复验「首次打开」这条路径")
    ap.add_argument("--clean", action="store_true", help="删掉这个设备的测试数据")
    ap.add_argument("--sql", action="store_true", help="只打印 SQL，不执行")
    ap.add_argument("--mysql", default=None, help="指定 mysql.exe 路径")
    args = ap.parse_args()

    # 设备名：--fresh 且用户没显式指定时，自动生成一个（省掉手改 deviceId 那一步）
    explicit_device = args.device is not None
    if args.fresh:
        args.device = args.device or ("dev-fresh-" + datetime.now().strftime("%Y%m%d%H%M%S"))
    else:
        args.device = args.device or DEFAULT_DEVICE
    if args.fresh and not explicit_device:
        print(f"[--fresh] 本次设备：{args.device}")
    if args.clean and args.fresh:
        sys.stderr.write("--clean 和 --fresh 一起用没有意义（前者删设备、后者造新设备）\n")
        raise SystemExit(2)
    if args.qa and (args.clean or args.fresh):
        sys.stderr.write("--qa 自带清理与重建，不要再配 --clean / --fresh（想清单台就用 --device X --clean）\n")
        raise SystemExit(2)

    cfg = read_env()
    db_cfg, dbname = parse_db_url(
        cfg.get("DB_URL") or os.environ.get("DB_URL") or "jdbc:mysql://localhost:3306/dailyseed"
    )
    creds = {
        "host": db_cfg["host"],
        "port": db_cfg["port"],
        "user": cfg.get("DB_USER") or os.environ.get("DB_USER") or "root",
        "password": cfg.get("DB_PASSWORD") or os.environ.get("DB_PASSWORD") or "",
    }

    if args.qa:
        exe = find_mysql(args.mysql)
        if not exe:
            sys.stderr.write("找不到 mysql.exe（用 --mysql 指定，或用 --sql 只导出 SQL）\n")
            raise SystemExit(2)
        db = Mysql(exe, creds, dbname)
        stmts, today = qa_stmts()
        sql = "\n".join(stmts)
        if args.sql:
            print(sql)
            return
        # 卡号先验一遍：种子换过、卡号挪过位时，"造出来看着像成功了"是最坏的结果
        ids = qa_card_ids()
        types = {}
        out = db.run("SELECT id, type FROM cards WHERE id IN (%s);"
                     % ",".join(str(i) for i in sorted(ids)))
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and re.fullmatch(r"\d+", parts[0]):
                types[int(parts[0])] = parts[1]
        validate_qa_cards(types)
        stale_codes = qa_code_conflicts(db)
        db.run(sql)
        print(f"库：{dbname} · 真机验收设备已重建（「今天」= {today.isoformat()}）")
        for code, uid, devices in stale_codes:
            print(f"（提示：同步码 {code} 原本挂在账号 {uid}（{devices}）上，已收回到夹具名下）")
        print()
        problems = []
        for spec in QA_FIXTURES:
            # 回读一遍：不打印我们**以为**写了什么，而是把库里实际的样子读出来
            want_assign = len(spec["past"]) + 1
            want_cards = len(spec["pots"]) + len(spec["graduated"])
            got = readback(db, spec["device"])
            if got is None:
                problems.append("%s：库里查不到这台设备" % spec["device"])
                continue
            if got[1] != want_assign or got[2] != want_cards:
                problems.append("%s：账号 %d 名下是 %d 条发放 / %d 行花园数据，期望 %d / %d"
                                % (spec["device"], got[0], got[1], got[2], want_assign, want_cards))
            grad = len(spec["graduated"])
            print(f"  {spec['device']}")
            print(f"    今天 #{spec['today']}（已揭晓、未留住、可重抽）· 花园 {len(spec['pots'])} 盆"
                  + (f" + {grad} 盆已内化" if grad else "")
                  + f" · 同步码 {canonical_sync_code(spec['code'])}"
                  + f" · 回读：账号 {got[0]} / 发放 {got[1]} 条 / 花园 {got[2]} 行")
            print(f"    {spec['note']}")
            print(f"    localStorage.setItem('dailyseed.deviceId', '{spec['device']}'); location.reload()")
        print()
        print("[注意] 这几台的「设置」页**不会显示同步码**（后端对已认识的设备不再发码，这是既定语义）。")
        print("   要测「用同步码找回」就用上面那串固定码；重测时把 --qa 再跑一遍即可重置。")
        print("   恢复的目标设备必须**从没用过**（用过的会走 409「不用恢复」）。")
        if problems:
            print()
            for p in problems:
                sys.stderr.write("[注意] 回读对不上：%s\n" % p)
            sys.stderr.write("   （多半是 user_id 取错了——别只看摘要，先查库）\n")
            raise SystemExit(1)
        return

    if args.clean:
        stmts = build_clean_sql(args.device)
        summary = []
        habit_card_ids = set()
    else:
        exe = find_mysql(args.mysql)
        if not exe:
            sys.stderr.write(
                "找不到 mysql.exe。用 --mysql 指一下，例如：\n"
                '  python tools/seed_dev_user.py --mysql "D:\\MySQL\\MySQL Server 8.0\\bin\\mysql.exe"\n'
            )
            raise SystemExit(2)
        db = Mysql(exe, creds, dbname)
        # 挑卡：不按 id 连续假设（HABIT 1-79 / EXPLORE 4-80 是交错的）
        out = db.run(
            "SELECT id, type FROM cards WHERE type IN ('HABIT','EXPLORE') AND status = 'ACTIVE' "
            "ORDER BY id LIMIT 40;"
        )
        cards = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and re.fullmatch(r"\d+", parts[0]):
                cards.append((int(parts[0]), parts[1]))
        if len(cards) < max(args.kinds, 1):
            sys.stderr.write("卡片库里的卡不够（种子导入了吗？）\n")
            raise SystemExit(1)
        stmts, summary = build_sql(args.device, args.days, args.kinds, cards)
        # 今天那张的揭晓/抽卡状态（默认预先揭晓：验收时能直接看页面）
        stmts += build_draw_sql(args.device, cards, args.days, not args.unrevealed,
                                args.draw_count, reset_today=args.reset_today,
                                today_card=args.today_card)
        # 花园只放习惯卡：汇总时要按类型分开数，别把探索卡也算成盆
        habit_card_ids = {cid for cid, ctype in cards if ctype == "HABIT"}

    sql = "\n".join(stmts)
    if args.sql:
        print(sql)
        return

    exe = find_mysql(args.mysql)
    if not exe:
        sys.stderr.write("找不到 mysql.exe（用 --mysql 指定，或用 --sql 只导出 SQL）\n")
        raise SystemExit(2)
    db = Mysql(exe, creds, dbname)
    db.run(sql)

    if args.clean:
        print("已清理 " + args.device)
        return

    print(f"库：{dbname} · 设备：{args.device}")
    print(f"每天发放：{min(args.days, len(summary))} 条（全部已留住）")
    print("留住过的卡：" + "、".join(f"#{cid}×{n}" for cid, n in summary))
    # 回读一句：摘要说的是"我们写了什么"，这一行说的是"库里现在是什么样"。
    # 这两者不一致时（曾经真的发生过：user_id 取错，数据写到别人账号上），只有回读看得出来。
    state = readback(db, args.device)
    if state is None:
        sys.stderr.write("⚠️ 回读：库里查不到设备 %s —— 这次造数没落上\n" % args.device)
        raise SystemExit(1)
    print(f"回读：设备 → 账号 {state[0]}（发放 {state[1]} 条 / 花园数据 {state[2]} 行）")
    if state[1] < min(args.days, len(summary)) and not args.reset_today:
        sys.stderr.write("⚠️ 回读的发放条数比预期少——别只看上面的摘要，先查库\n")
        raise SystemExit(1)
    # ⚠️ 张数 ≠ 盆数：花园只放习惯卡（GardenService.visibleInGarden），
    #    所以轮转里混进来的探索卡不算盆。以前这里把张数说成盆数，会让人以为工具坏了一半。
    habit_pots = sum(1 for cid, _ in summary if cid in habit_card_ids)
    print(
        f"→ 花园窗台上应有 {habit_pots} 盆（{len(summary)} 张里有 {len(summary) - habit_pots} 张不是习惯卡，"
        "不进花园）；≥7 次的那几盆带「可毕业」小标记；"
        + ("能看到放纵入口" if len(summary) >= 5 else "还看不到放纵入口（需要 ≥5 种）")
    )
    if args.reset_today and not args.fresh:
        print("→ 今天那张已**复活**：未留住、回到卡背、抽卡次数归零（反复测「抽→揭晓→留住」用）")
    elif args.unrevealed:
        print("→ 今天那张刻意留在**卡背**状态（revealed_at = NULL，draw_count = 0）")
    else:
        print(f"→ 今天那张已预先揭晓（draw_count = {args.draw_count}）")
    if args.today_card:
        print(f"→ 今天指定为 #{args.today_card}（--today-card，不按轮转）")
    if args.fresh:
        print("→ 这是**新设备**：打开页面就是「首次进入」（卡背 + 同步码提示那次路径）")
    print()
    print("在浏览器控制台粘这一行，然后刷新：")
    print(f"  localStorage.setItem('dailyseed.deviceId', '{args.device}'); location.reload()")
    print("（想变回真正的新用户：localStorage.clear(); location.reload()）")


if __name__ == "__main__":
    main()
