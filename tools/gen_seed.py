# -*- coding: utf-8 -*-
"""从《DailySeed-卡片库v2.md》生成数据库种子。

**md 是唯一维护源**：改了卡片库就重跑这个脚本，SQL 永远不该手改。
输出：
  backend/src/main/resources/db/migration/V2__seed_cards.sql
  backend/src/main/resources/science-notes.json
"""
import io, json, os, re, sys

SRC = "DailySeed-卡片库v2.md"
RES = "backend/src/main/resources"
MIG = RES + "/db/migration"
os.makedirs(MIG, exist_ok=True)

md = io.open(SRC, encoding="utf-8").read().replace("\r\n", "\n")
lines = md.split("\n")

TYPE_RE = re.compile(r"^(HABIT|EXPLORE|INDULGE)$")
DIFF_RE = re.compile(r"^[0-3]$")
LEVEL_RE = re.compile(r"^\*{0,2}([AB]) · (研究|机制)\*{0,2}$")
KIND = {"停止型": "STOP", "给予型": "GIVE"}
CHAPTER_RE = re.compile(r"^## ([一二三四五六七八九十]+)、([^（]+)（")

def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]

def plain(s):
    """去掉行内 markdown 标记（**粗体**、*斜体*、`代码`）—— 进 API 的应是纯文本。"""
    return re.sub(r"[*`]", "", s) if s else s

cards, evidence, notes, refs = {}, {}, [], {}
section = None

for ln in lines:
    m = CHAPTER_RE.match(ln)
    if m:
        section = m.group(2).strip()
        continue
    if ln.startswith("### 10.3"):
        section = "SCIENCE"
        continue

    if not ln.startswith("|") or set(ln) <= set("|-: "):
        continue

    c = cells(ln)
    if len(c) < 4:
        continue

    # 10.3 科普库：| `key` | 标题 | 文案 | 依据/来源 | 被哪些卡引用 |
    if section == "SCIENCE" and c[0].startswith("`"):
        key = c[0].strip("`")
        notes.append({"key": key, "title": plain(c[1]), "body": plain(c[2]), "source": plain(c[3])})
        for no in re.findall(r"#(\d+)", c[4]):
            refs.setdefault(int(no), []).append(key)
        continue

    # 十、依据库：| 卡片 | 层级 | ① 好处 | ② 依据/机制 | ③ 出处 |
    lvl = next((x for x in c if LEVEL_RE.match(x)), None)
    if lvl and re.fullmatch(r"\d{1,3}", c[0]):
        evidence[int(c[0])] = (LEVEL_RE.match(lvl).group(1), plain(c[2]), plain(c[3]), plain(c[4]))
        continue

    # 一～九章卡片表
    if not re.fullmatch(r"\d{1,3}", c[0]):
        continue
    ti = next((k for k, x in enumerate(c) if TYPE_RE.match(x)), None)
    if ti is None:
        continue
    di = next((k for k in range(ti + 1, len(c)) if DIFF_RE.match(c[k])), None)
    if di is None:
        continue

    no = int(c[0])
    ctype = c[ti]
    kind = KIND.get(c[di + 1]) if di + 1 < len(c) else None
    category = c[ti + 1] if kind else section
    photo = "📷" in ln
    diff = int(c[di])
    cards[no] = {
        "no": no, "text": c[1], "type": ctype, "category": category,
        "difficulty": diff, "photo": photo,
        "shareable": True if ctype == "INDULGE" else (photo and diff <= 2),
        "kind": kind, "why": c[-1],
    }

# ---------- 校验 ----------
errs = []
if len(cards) != 100:
    errs.append("卡片数不是 100：%d" % len(cards))
if sorted(cards) != list(range(1, 101)):
    errs.append("编号不连续")
for no in evidence:
    if no not in cards:
        errs.append("依据库引用了不存在的卡 #%d" % no)
for no in refs:
    if no not in cards:
        errs.append("科普库引用了不存在的卡 #%d" % no)
if len(notes) != 8:
    errs.append("科普条数不是 8：%d" % len(notes))
if errs:
    sys.stdout.write("ABORT\n  " + "\n  ".join(errs) + "\n")
    sys.exit(1)

types = {}
diffs = {}
for c in cards.values():
    types[c["type"]] = types.get(c["type"], 0) + 1
    diffs[c["difficulty"]] = diffs.get(c["difficulty"], 0) + 1

# ---------- SQL ----------
def q(s):
    """MySQL 单引号字符串：\\n 本身就是换行，所以不需要 E'' 前缀。"""
    if s is None:
        return "NULL"
    return "'" + s.replace("\\", "\\\\").replace("'", "''").replace("\n", "\\n") + "'"

def qs(s):
    return "NULL" if s is None else "'" + s.replace("'", "''") + "'"

rows = []
for no in sorted(cards):
    c = cards[no]
    ev, lvl, sci = None, None, (refs.get(no) or [None])[0]
    if no in evidence:
        level, benefit, basis, source = evidence[no]
        lvl = level
        ev = benefit + "\n" + basis + (("\n" + source) if level == "A" else "")
    rows.append("(%d, %s, %s, %s, %d, %s, %s, %s, %s, %s, %s, %s)" % (
        no, qs(c["type"]), qs(c["category"]), qs(c["text"]), c["difficulty"],
        "TRUE" if c["photo"] else "FALSE", "TRUE" if c["shareable"] else "FALSE",
        qs(c["kind"]), qs(c["why"]), q(ev), qs(lvl), qs(sci)))

sql = """-- ============================================================
-- DailySeed 卡片种子（%d 张）—— **自动生成，请勿手改**
-- 来源：DailySeed-卡片库v2.md   ·   目标库：MySQL 8
-- 重新生成：python tools/gen_seed.py
-- 类型：%s
-- 难度：%s
-- 依据：A 级 %d 张 / B 级 %d 张；科普 key 引用 %d 张卡
-- ============================================================

INSERT INTO cards
    (id, type, category, `text`, difficulty, photo_hint, shareable,
     indulgence_kind, why, evidence, evidence_level, science_key)
VALUES
%s;
"""  % (len(cards),
       " · ".join("%s %d" % (k, v) for k, v in sorted(types.items())),
       " · ".join("难度 %d：%d 张" % (k, v) for k, v in sorted(diffs.items())),
       sum(1 for v in evidence.values() if v[0] == "A"),
       sum(1 for v in evidence.values() if v[0] == "B"),
       len(refs),
       ",\n".join(rows))

io.open(MIG + "/V2__seed_cards.sql", "w", encoding="utf-8", newline="\n").write(sql)
io.open(RES + "/science-notes.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(notes, ensure_ascii=False, indent=2) + "\n")

sys.stdout.write("cards=%d types=%s diffs=%s\n" % (len(cards), types, diffs))
sys.stdout.write("evidence A=%d B=%d | science notes=%d | cards with science_key=%d\n"
                 % (sum(1 for v in evidence.values() if v[0] == "A"),
                    sum(1 for v in evidence.values() if v[0] == "B"), len(notes), len(refs)))
sys.stdout.write("written: %s/V2__seed_cards.sql , %s/science-notes.json\n" % (MIG, RES))
