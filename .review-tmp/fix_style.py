# -*- coding: utf-8 -*-
"""第三批：把"是错"的那几条落到代码里。

原则：**每一处都先算过数再改，改不中/数量不对就整体报错**（不静默半改）。
  ① 对比度：--ink-3 / --harvest 换成"刚好达标"的值（四种底上都不低于 4.5:1）
  ② 侧栏断行：note 的左右 padding 12 → 8px（可用 164 → 172px，那句话要 160px）
  ③ 桌面构图：≥960px 时插画 230 → 300px，两面 min-height 同步 400 → 440px（防翻面跳高）
  ④ 调色板：把"只差 1–2/255"的一次性色折进令牌（肉眼不可辨，纯收敛）
  ⑤ 字号：半像素（11.5/12.5/13.5/14.5/15.5）整体进位成整数 —— 逐个核过受影响的元素，
     没有一个是"固定宽度 + 不换行"的容器，最紧的那处仍有 ≥25% 余量
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "frontend", "src", "styles", "base.css")
COMP = os.path.join(ROOT, "frontend", "src", "styles", "components.css")

EDITS = []          # (文件, 旧, 新, 期望次数)
SUBSTITUTIONS = []  # (文件, 正则, 新, 期望次数)


def edit(path, old, new, times=1):
    EDITS.append((path, old, new, times))


def sub(path, pattern, new, times):
    SUBSTITUTIONS.append((path, pattern, new, times))


# ── ① 令牌：三级文字与难度棕换成算好的值；顺手补三个语义令牌 ──
edit(BASE,
     "  --ink: #293f34; --ink-2: #5c695e; --ink-3: #73776b;",
     """  /* ⚠️ 三级文字的取值是**算出来的**，不是挑出来的：它要同时压在四种底上都 ≥4.5:1
     （WCAG AA 正文）—— --bg 4.87 · --bg-deep 4.53（侧栏）· 底部导航底 4.99 · --surface-1 5.18。
     原来的 #73776b 在 --bg-deep 上只有 3.98。**改它之前先跑 `python tools/verify_redlines.py --style`。** */
  --ink: #293f34; --ink-2: #5c695e; --ink-3: #6a6e62;
  --seed-tint: #e8edde;        /* 品牌绿最浅一档：品牌图标底 / chip--seed / 激活页签底 */
  --seed-tint-strong: #dfe6d4; /* 桌面侧栏的激活页签底（再深半档） */
  --leaf-ink: #879777;         /* 叶子图标的柔绿：装饰性图标，按 WCAG 1.4.11 豁免对比度 */""")

edit(BASE,
     "  --harvest: #956638; --harvest-glow: #f3e8d8; --danger: #ac4c3d;",
     "  /* 难度 chip 的文字要在 --harvest-glow 上 ≥4.5：原来 #956638 只有 4.10，现在 4.53 */\n"
     "  --harvest: #8e5f31; --harvest-glow: #f3e8d8; --danger: #ac4c3d;")

# ── ④ 调色板收敛：只折"肉眼看不出差别"的那些 ──
edit(BASE, ".chip--seed { background: #e8edde;", ".chip--seed { background: var(--seed-tint);")
edit(BASE, "background: #e8ecdf; border-radius: 14px;", "background: var(--seed-tint); border-radius: var(--r-sm);")
edit(BASE, ".tab[aria-current='page'] { background: #e9eddf;", ".tab[aria-current='page'] { background: var(--seed-tint);")
edit(BASE, "linear-gradient(100deg, #eeeee5 30%, #e6e8dc 48%, #eeeee5 66%)",
     "linear-gradient(100deg, var(--surface-2) 30%, var(--surface-3) 48%, var(--surface-2) 66%)")
edit(BASE, ".daily-note svg { margin-top: 3px; color: #879777; }", ".daily-note svg { margin-top: 3px; color: var(--leaf-ink); }")
edit(BASE, "width: 240px; padding: 44px 26px; background: #f0f1e9;", "width: 240px; padding: 44px 26px; background: var(--bg-deep);")
edit(BASE, "  .tab[aria-current='page'] { background: #dfe6d4; }", "  .tab[aria-current='page'] { background: var(--seed-tint-strong); }")
edit(COMP, "border: 1px solid #dedfce; border-radius: var(--r-lg); background: #f0f1e6;",
     "border: 1px solid var(--edge); border-radius: var(--r-lg); background: var(--bg-deep);")
edit(COMP, ".empty-trail > svg { color: #869875; margin-bottom: 20px; }",
     ".empty-trail > svg { color: var(--leaf-ink); margin-bottom: 20px; }")
edit(COMP, "  background: #eeeee3;", "  background: var(--surface-2);")

# ── ② 侧栏那句为什么会被挤断（算过的），顺便把它的颜色并进令牌 ──
edit(BASE,
     "  .navigation__note { display: block; margin-top: auto; padding: 44px 12px 0; color: #75826b; }",
     """  /* 下面那句话是手写 <br/> 断的两行，第二行「生活会长出自己的样子。」= 10 个汉字 × 16px = 160px。
     可用宽度 = 240 − 26×2（.navigation）− 12×2（这里）= 164px —— 只余 4px，字体一回退就断成
     「…的样／子。」（截图里就是这个结果）。把左右 padding 收到 8px → 可用 172px，留出 12px 余量。
     颜色也并进令牌：原来的 #75826b 在这块底上只有 3.53:1。 */
  .navigation__note { display: block; margin-top: auto; padding: 44px 8px 0; color: var(--ink-3); }""")

# ── ③ 桌面构图：插画要宽过最宽的那行字，两面同高以免翻面跳 ──
edit(BASE,
     """  .page-heading { margin-bottom: 16px; }
  .toast { left: calc(50% + 120px); bottom: 28px; }""",
     """  .page-heading { margin-bottom: 16px; }
  .toast { left: calc(50% + 120px); bottom: 28px; }
  /* 桌面端卡片内宽 ≈670px，而插画固定 230px（占 34%），看着"手机版被拉宽"。
     卡背上最宽的一行（「一件事，也会慢慢发芽。」23px × 12 字 ≈ 276px）本来就比插画宽，
     所以把插画提到 300px：**图比最宽的文字略宽**，层级才对。
     ⚠️ 两面 min-height 必须一起抬（.cardback / .today__card 同值），否则翻面时卡片会跳高。 */
  .cardback .seed-art { width: 300px; }
  .cardback, .today__card { min-height: 440px; }""")

# ── ⑤ 半像素字号 → 整数（每个受影响元素都核过容器余量） ──
for path in (BASE, COMP):
    sub(path, r"font-size: 11\.5px", "font-size: 12px", 2)
    sub(path, r"font-size: 12\.5px", "font-size: 13px", 7)
    sub(path, r"font-size: 13\.5px", "font-size: 14px", 4)
    sub(path, r"font-size: 14\.5px", "font-size: 15px", 2)
    sub(path, r"font-size: 15\.5px", "font-size: 16px", 1)

# ─────────────────────────── 执行 ───────────────────────────
problems = []
done = 0
for path, old, new, times in EDITS:
    text = io.open(path, encoding="utf-8").read()
    n = text.count(old)
    if n != times:
        problems.append("× 命中 %d 次（期望 %d）：%s" % (n, times, old[:60].replace("\n", " ")))
        continue
    io.open(path, "w", encoding="utf-8", newline="").write(text.replace(old, new))
    done += 1

for path, pattern, new, times in SUBSTITUTIONS:
    text = io.open(path, encoding="utf-8").read()
    n = len(re.findall(pattern, text))
    if n != times:
        problems.append("× 正则命中 %d 次（期望 %d）：%s" % (n, times, pattern))
        continue
    io.open(path, "w", encoding="utf-8", newline="").write(re.sub(pattern, new, text))
    done += 1

print("完成 %d 处；文件：base.css / components.css" % done)
for p in problems:
    print(p)
sys.exit(1 if problems else 0)
