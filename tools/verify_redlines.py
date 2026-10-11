# -*- coding: utf-8 -*-
"""红线巡检：把《交接简报》§2 那 9 条里**能机器判定**的部分变成断言。

为什么值得单独一个脚本：这 9 条是"违反了要停下来重做"的规则，但此前**只写在文档里**。
而红线最典型的破法不是把代码写错，是**加功能时顺手加了一句文案**（"已连续 3 天"、"还差 2 张"、
"进度 60%"）——那种改动 typecheck 全过、57 条接口断言全绿、页面还挺好看。

⚠️ **为什么不做"违禁词表"**（这是本脚本最容易写错的地方，三条都是实测踩出来的）：
  1. 这个产品**故意**把"打卡/连续"写在界面上，而且是在**否定它们**——
     "留着不是打卡"、"它不打卡、不算连续天数、不发通知"。一刀切的词表会把好文案判成违规。
     所以判据是「**这些词只允许出现在否定句里**」（词前 4 个字内要有 不/没/别/非/无/否）。
  2. `必须` **不在**词表里：它在设置页有一处正当用法——"这是'零注册'必须付出的代价"，
     那是在**陈述取舍**，不是在命令用户。判据要能从文案意图上站得住，不能凭手感拉清单。
  3. "没有第三方源"也不能写成"产物里不许出现 http"：React 自带
     `https://reactjs.org/docs/error-decoder.html`，SVG/MathML 还带一堆
     `http://www.w3.org/...` **命名空间标识符**——它们不是会被加载的资源。
     所以只查**可加载**的形态（`src=` / `href=` / `import(` / `url(` / `fetch(` 后面紧跟 http）。

用法（产物那部分要先构建；卡片库那部分随时可跑）：
    cd frontend; npm run build
    python tools/verify_redlines.py

⚠️ 读产物**必须显式按 UTF-8 读**。实测：用 `Get-Content -Raw` 读同一份文件，
   所有中文词都数出 0 —— 一个"干净"的假结果，比报错危险得多。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "frontend", "dist")
SRC = os.path.join(ROOT, "frontend", "src")
CARDS = os.path.join(ROOT, "DailySeed-卡片库v2.md")

results = []


def check(label, ok, detail=""):
    results.append((ok, label, detail))
    print("%s %s%s" % ("PASS" if ok else "FAIL", label, ("  ← " + detail) if detail else ""))


def read(path):
    with open(path, encoding="utf-8") as fh:   # ← 显式 UTF-8，见文件头那条实测教训
        return fh.read()


# ==================== 三个纯函数：检测器本体（--selftest 直接拿它们做正反例） ====================

# 监工 / 催促词：**只允许出现在否定它们的句子里**
MONITOR_WORDS = ["连续", "打卡", "坚持", "红点", "进度", "你还没做", "你应该", "还差", "别忘了", "加油", "该毕业"]
NEGATIONS = "不没别非无否"
# 计数 / 进度类文案：一处都不该有
HARD_ZERO_WORDS = ["还剩", "已抽", "剩余", "可再抽", "百分比", "进度条"]
# 只认"数字 + 单位"或"货币符号 + 数字"：宽匹配会把"时间块"判成金额（实测假阳性）
MONEY = re.compile(r"\d+\s*(元|块钱|块|万)|[¥$]\s*\d|人民币|美元|RMB")
# 只查**会被加载**的外链形态：命名空间与错误提示里的 URL 不算（实测 13 处都是这类）
LOADABLE = [r'src="http', r'href="http', r'import\("http', r"url\(http", r'fetch\("http']


def monitor_violations(text):
    """返回违规命中 [(词, 上下文)]；词前 4 个字内有否定词就算"否定用法"，放行。"""
    bad = []
    for w in MONITOR_WORDS:
        for m in re.finditer(re.escape(w), text):
            before = text[max(0, m.start() - 4):m.start()]
            if not any(c in NEGATIONS for c in before):
                bad.append((w, text[max(0, m.start() - 20):m.start() + len(w) + 14]))
    return bad


def monitor_mentions(text):
    """返回**所有**命中（含否定用法），只用来在报告里说明"这些词出现在哪" """
    return [(w, text[max(0, m.start() - 20):m.start() + len(w) + 14])
            for w in MONITOR_WORDS for m in re.finditer(re.escape(w), text)]


def money_violations(text):
    # 用 finditer 取 group(0)：MONEY 里带一个分组，findall 只会回分组内容（¥200 会显示成空串）
    return [m.group(0) for m in MONEY.finditer(text)]


def loadable_external(text):
    return [p for p in LOADABLE if re.search(p, text)]


# ==================== A. 产物层：用户真能看到的那一份 ====================

bundle_text = ""
if os.path.isdir(DIST):
    files = [os.path.join(DIST, f) for f in os.listdir(DIST) if f.endswith(".js")]
    assets = os.path.join(DIST, "assets")
    if os.path.isdir(assets):
        files += [os.path.join(assets, f) for f in os.listdir(assets) if f.endswith(".js")]
    idx = os.path.join(DIST, "index.html")
    if os.path.exists(idx):
        files.append(idx)
    bundle_text = "\n".join(read(f) for f in sorted(set(files)))
    print("扫的产物：%s（共 %d 字符）" % (", ".join(os.path.basename(f) for f in sorted(set(files))),
                                        len(bundle_text)))
else:
    print("!! 没有 frontend/dist —— 产物那部分跳过（先 cd frontend; npm run build）")

if bundle_text:
    found = {w: len(re.findall(re.escape(w), bundle_text)) for w in HARD_ZERO_WORDS}
    check("红1 产物里没有任何「次数 / 进度」文案（无 ← 这是最容易顺手加的东西）",
          all(v == 0 for v in found.values()), " ".join("%s=%d" % kv for kv in found.items()))

    mentions, violations = monitor_mentions(bundle_text), monitor_violations(bundle_text)
    check("红1/红2 监工与催促的词只出现在「否定句」里（%d 处命中，逐处看前 4 字是否有否定词）"
          % len(mentions),
          not violations,
          "；".join("[%s] …%s…" % v for v in violations) if violations
          else "全部是否定用法：%s" % "；".join("…%s…" % c for _, c in mentions))

    ext = loadable_external(bundle_text)
    check("红「不引第三方」产物里没有可加载的外链（CSP 敢收那么紧的前提）",
          not ext, "命中：%s" % (" ".join(ext) if ext else "无"))
else:
    # ⚠️ 这一条是补的，起因是一次实测：`frontend/dist` 目录**还在、里面却是空的**
    #    （构建清空了输出目录又没把它写回去），旧写法只打一行「共 0 字符」就安静地
    #    少跑了上面 3 条断言 —— 总数从 11 变成 8，但看起来仍然是"全绿"。
    #    **产物层断言没跑过，不许算通过**：宁可红一条，也不要一个假的绿。
    check("红1/红2/红「不引第三方」产物层断言真的跑到了产物（dist 里没有 index.html / 没有 js）",
          False,
          "frontend/dist %s —— 先 cd frontend; npm run build"
          % ("是空目录" if os.path.isdir(DIST) else "不存在"))

# ==================== B. 源码结构守卫（入口该不该画） ====================


def src(name):
    path = os.path.join(SRC, name)
    return read(path) if os.path.exists(path) else ""


today_src = src(os.path.join("pages", "Today.tsx"))
evidence_src = src(os.path.join("components", "EvidenceSheet.tsx"))

check("红3 「?」入口只在 `today.evidence` 存在时才渲染（没依据就不给入口）",
      "{today.evidence && (" in today_src,
      "守卫在 Today.tsx：`{today.evidence && (`")

check("红5 放纵卡没有「留住它」：走 INDULGE 分支，文案是「这张不用留住」",
      "today.type === 'INDULGE'" in today_src and "这张不用留住" in today_src)

check("红6 放纵入口只按服务端的 `today?.canIndulge` 画，前端不预告门槛（不公示）",
      "today?.canIndulge &&" in today_src)

check("红2 B 级卡固定挂一句「这是机制，不是研究结论。」（诚实写在界面上，不靠话术补）",
      "这是机制，不是研究结论。" in evidence_src)

check("红3/§5 判定依据用 `if (evidence)` 而不是 `=== null`（后端 non_null 下那个键可能压根不存在）",
      "=== null" not in evidence_src and "!== undefined" not in evidence_src)

# ==================== C. 卡片库内容层（md 是唯一源，红线 4 / 7） ====================

INDULGE_ROWS = [ln for ln in read(CARDS).splitlines()
                if re.match(r"^\|\s*\d+\s*\|", ln) and "INDULGE" in ln]


def column(row, idx):
    parts = row.split("|")
    return parts[idx].strip() if len(parts) > idx else ""


# C1 红7：花钱的卡不写金额，写"按你自己的预算"
# ⚠️ 别用 `元|块` 这种宽匹配：实测它把 98 号卡的"时间**块**"判成金额（假阳性）。
#    只认"数字 + 单位"或"货币符号 + 数字"。
MONEY = re.compile(r"\d+\s*(元|块钱|块|万)|[¥$]\s*\d|人民币|美元|RMB")
money_hits = [column(r, 2) for r in INDULGE_ROWS if money_violations(column(r, 2))]
check("红7 放纵卡原文里不出现任何金额（%d 张逐张查）" % len(INDULGE_ROWS),
      not money_hits, "命中：%s" % money_hits or "无")

# C2 放纵卡是"零消耗"，难度必须恒为 0（难度列在第九章表的第 5 列）
diffs = sorted({column(r, 5) for r in INDULGE_ROWS})
check("红5 放纵卡难度恒为 0（零消耗；出现难度 ≥1 的放纵卡就是把它变成了任务）",
      diffs == ["0"], "难度取值=%s" % diffs)

# C3 红4：被排除的研究不许被捡回来——先守住"那张清单还在"
excluded = read(CARDS).split("### 10.1")[-1].split("###")[0] if "### 10.1" in read(CARDS) else ""
excluded_items = [ln for ln in excluded.splitlines() if ln.startswith("|") and "---" not in ln]
check("红4 §10.1「已排除的研究」清单还在（%d 行）——补依据前要查的就是它" % len(excluded_items),
      len(excluded_items) >= 4,
      "§10.1 条目数 %d（少于 4 行就说明有人删过）" % len(excluded_items))

# ==================== D. 样式契约（`--style`）：配色 / 对比度 / 字号 / 圆角 ====================
#
# 为什么单独一个开关：这几条守的是**视觉里可判定的那部分**，和红线不是一回事
# （红线是"不做监工"，这里是"小字看不看得清、调色板有没有漂"），所以默认不跑。
# 起因：2026-10-11 换了浅色主题之后量出来三处小字低于 WCAG AA（4.5:1）——
# 这种事肉眼看不出来，但一量就现形。判据与实测数见 `docs/review-20261011/视觉规范.md`。

STYLE_FILES = [os.path.join(SRC, "styles", n) for n in ("base.css", "components.css")]
# 字号阶梯（2026-10-11 定）：半像素档位已全部并掉。新增字号要**先在这里加一行**，
# 这样"再顺手写一个 13.5px"就必须过一次手，而不是悄悄多出一档。
FONT_SCALE = [9, 10, 11, 12, 13, 14, 15, 16, 19, 21, 22, 23, 25, 27, 30]
# 允许硬写的圆角：百分比（圆点）与有机形状（盆/叶/碟）——语义上本来就该一次性
RADIUS_ALLOWED = {"50%", "52% 48% 46% 54% / 72% 70% 30% 28%", "80% 20% 75% 25%",
                  "8px 8px 13px 13px / 6px 6px 17px 17px"}
# 允许硬写的不透明色（令牌之外）：逐条写清理由，**加一条要有理由**
OPAQUE_ALLOWED = {
    "#2c4438": "toast 底（比 --seed-deep 更深，压在白字下面才够）",
    "#d69b79": "CSS 画的那盆：陶土亮面",
    "#b57758": "CSS 画的那盆：陶土暗面",
    "#d5cbb9": "CSS 画的那盆：碟子",
    # 上面三个和 Icon.tsx 里 SVG 插画的陶土色（#bc775a / #ce8c6b / #dbd4c1）是有意分开的：
    # 一个是 CSS 画的盆、一个是手绘插画，各自内部要一致，不必跨渲染方式对齐。
}


def strip_css_comments(text):
    """去掉 /* … */。

    ⚠️ 这条是实测踩出来的：注释里写「原来的 #73776b 只有 3.98」，
    扫描器会把它当成"这个颜色还在用"——于是**修完仍然报不达标**（假失败）。
    凡是要在注释里提到旧值的脚本，都得先剥注释再扫。
    """
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def css_texts():
    return [(os.path.basename(p), strip_css_comments(read(p))) for p in STYLE_FILES if os.path.exists(p)]


def rgb_of(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _linear(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(h):
    r, g, b = (_linear(c) for c in rgb_of(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def hex_distance(a, b):
    """逐分量最大差。1–2/255 就是"吸管点了两次"的指纹。"""
    return max(abs(x - y) for x, y in zip(rgb_of(a), rgb_of(b)))


if "--style" in sys.argv:
    token_colors = {}
    for _name, _text in css_texts():
        for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", _text):
            token_colors[m.group(1)] = m.group(2).lower()
    tok = lambda var, fallback=None: token_colors.get(var, fallback or var)

    AA = 4.5
    groups = [
        ("正文 / 次级 / 三级，在页面底上",
         [("--ink", "--bg"), ("--ink-2", "--bg"), ("--ink-3", "--bg")]),
        ("三级信息压在**最暗的几块底**上（最紧的一处决定取值）",
         [("--ink-3", "--bg-deep"), ("--ink-3", "--surface-1"), ("--ink-3", "#fafaf5")]),
        ("交互色：主按钮文字 / 卡上的强调色 / 危险动作",
         [("--seed-ink", "--seed"), ("--seed", "--surface-1"), ("--danger", "--bg")]),
        ("难度 chip（棕底棕字，最容易不达标的一处",
         [("--harvest", "--harvest-glow")]),
    ]
    for label, pairs in groups:
        detail = []
        worst = 99.0
        for fg_var, bg_var in pairs:
            fg, bg = tok(fg_var), tok(bg_var, bg_var)
            r = contrast_ratio(fg, bg)
            worst = min(worst, r)
            detail.append("%s on %s = %.2f" % (fg, bg, r))
        check("样式·对比度：%s（最低 %.2f ≥ %.1f，WCAG AA）" % (label, worst, AA),
              worst >= AA, "；".join(detail))

    # 调色板纪律：一次性色不许和某个令牌"差 1–2/255"（那就是同一件事写了两遍）
    all_literals = []
    for _name, _text in css_texts():
        all_literals += ["#" + m.group(1).lower() for m in re.finditer(r"#([0-9a-fA-F]{6})\b", _text)]
    token_values = set(token_colors.values())
    drift = []
    for lit in sorted(set(all_literals)):
        if lit in token_values:
            continue
        for tv in sorted(token_values):
            if hex_distance(lit, tv) <= 2:
                drift.append("%s ≈ %s（差 %d/255）" % (lit, tv, hex_distance(lit, tv)))
    check("样式·调色板：没有「和某个令牌只差 ≤2/255」的一次性色（吸管点两次的指纹）",
          not drift, "；".join(drift) if drift else "一次性色 %d 个，无一与令牌近似" % len(set(all_literals)))

    strangers = sorted({lit for lit in all_literals if lit not in token_values and lit not in OPAQUE_ALLOWED})
    check("样式·调色板：令牌之外的不透明色都在白名单里（加一条要有理由）",
          not strangers,
          "不在令牌与白名单里：%s" % (strangers or "无"))

    sizes = sorted({float(m.group(1)) for _n, t in css_texts() for m in re.finditer(r"font-size:\s*([0-9.]+)px", t)})
    strays = [s for s in sizes if s not in FONT_SCALE]
    check("样式·字号：只用阶梯上的 %d 档（%s）" % (len(FONT_SCALE), "/".join(str(s) for s in FONT_SCALE)),
          not strays, "阶梯外：%s" % (strays or "无"))

    hard = []
    for _name, _text in css_texts():
        for m in re.finditer(r"border-radius:\s*([^;]+);", _text):
            value = m.group(1).strip()
            if "var(" not in value and value not in RADIUS_ALLOWED:
                hard.append(value)
    check("样式·圆角：要么走 var(--r-*)，要么在一次性白名单里",
          not hard, "硬写且不在白名单：%s" % (sorted(set(hard)) or "无"))

    # 产物同步：改了令牌却忘了 `npm run build`，用户看到的还是旧颜色。
    # 这一条是照"dist 空了却没人发现"那次事故补的——源码对、产物旧，是最难自己发现的一类错。
    dist_assets = os.path.join(DIST, "assets")
    dist_css = [os.path.join(dist_assets, f) for f in os.listdir(dist_assets) if f.endswith(".css")] \
        if os.path.isdir(dist_assets) else []
    bundled = read(dist_css[0]) if dist_css else ""
    stale = [v for v in (tok("--ink-3"), tok("--harvest"), tok("--shadow-ink")) if v not in bundled]
    check("样式·产物同步：dist 的 CSS 里能读到当前令牌值（改了样式忘 build 就会被抓到）",
          bool(dist_css) and not stale,
          "dist 里有 %d 个 CSS；读不到的令牌：%s" % (len(dist_css), stale or "无"))

# ==================== E. 自检：检测器本身能不能触发（--selftest） ====================

#
# **只能通过的守卫等于没有守卫。** 这里拿"人造违规"喂给三个纯函数确认它们**会**报，
# 再拿真实存在的好文案确认它们**不会**误报——"时间块"和 React 的错误链接都是实测踩过的假阳性。

if "--selftest" in sys.argv:
    for label, hits, want_hit in [
        ("监工词：断言句要被抓到", monitor_violations("你已经连续 3 天完成了"), True),
        ("监工词：否定句不该被抓到", monitor_violations("它不打卡、不算连续天数"), False),
        ("监工词：催促用法要被抓到", monitor_violations("坚持 21 天就能养成习惯"), True),
        ("金额：'25 元'要被抓到", money_violations("今天给自己买一杯 25 元的饮料"), True),
        ("金额：'时间块'不该被抓到（实测假阳性）", money_violations("给\"喜欢\"留出时间块，而不是缝隙"), False),
        ("金额：货币符号要被抓到", money_violations("预算 ¥200 以内"), True),
        ("外链：可加载的第三方要被抓到",
         loadable_external('<script src="https://cdn.example.com/x.js"></script>'), True),
        ("外链：命名空间/错误提示不该被抓到（实测 13 处都是这类）",
         loadable_external('https://reactjs.org/docs/error-decoder.html http://www.w3.org/2000/svg'), False),
        # —— 样式检测器自己的正反例（--style 那一段用的就是这几个函数）——
        #   ⚠️ 这个循环的判据是 `bool(hits) == want_hit`，而**非空列表恒为真**：
        #   所以每行必须写成「检测器报了 → 非空列表；没报 → 空列表」。
        #   写成 `[False]` 会永远为真，自检就变成了空转（第一版正是这么错的，四条自检当场红）。
        ("对比度：纯黑 on 纯白 = 21:1（公式没算反）",
         ["21:1"] if round(contrast_ratio("#000000", "#ffffff")) == 21 else [], True),
        ("对比度：同色只能是 1:1（不会凭空给出高分）",
         ["1:1"] if round(contrast_ratio("#45664b", "#45664b")) == 1 else [], True),
        ("近似色：差 1/255 要被抓到",
         ["#eeeee3≈#eeeee4"] if hex_distance("#eeeee3", "#eeeee4") <= 2 else [], True),
        ("近似色：差 40/255 不该被抓到",
         ["#293f34≈#45664b"] if hex_distance("#293f34", "#45664b") <= 2 else [], False),
        ("字号：13.5px 这种半像素档位在阶梯外（改回半像素会被拦下）",
         ["13.5px"] if 13.5 in FONT_SCALE else [], False),
        ("圆角：裸的 13px 不在白名单里",
         ["13px"] if "13px" in RADIUS_ALLOWED else [], False),
        ("注释剥离：注释里提到的旧色值不算「还在用」",
         ["#73776b"] if "#73776b" in strip_css_comments("/* 原来是 #73776b */ .a { color: #6a6e62; }") else [], False),
    ]:
        check("自检 " + label, bool(hits) == want_hit, "命中=%s" % (hits if hits else "无"))

print("\n" + "=" * 72)
failed = [r for r in results if not r[0]]
print("合计 %d 条断言：%d PASS / %d FAIL" % (len(results), len(results) - len(failed), len(failed)))
for _, label, detail in failed:
    print("  FAIL %s  ← %s" % (label, detail))
print("\n（这个脚本管的是**能机器判定的那部分**红线；卡片质量、语气、'巧思'仍然只能人看。）")
raise SystemExit(1 if failed else 0)
