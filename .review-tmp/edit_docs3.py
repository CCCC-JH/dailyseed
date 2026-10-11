# -*- coding: utf-8 -*-
"""第五批文档更新：把"审美这一轮"的结论落回各文档（命中必须恰好一次）。"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEF = "DailySeed-交接简报.md"
LOG = "DailySeed-会话纪要.md"
FEREADME = os.path.join("frontend", "README.md")
RECORD = os.path.join("docs", "review-20261011", "优化记录.md")

EDITS = []


def edit(path, old, new):
    EDITS.append((path, old, new))


# ── 交接简报 ──
edit(BRIEF,
     "**11/11（+8 条自检）**：产物里没有任何「次数/进度」文案",
     "**11/11（+8 条自检）**、**加 `--style` 另 8 条样式断言（对比度 / 调色板 / 字号 / 圆角）+7 条自检**"
     "（判据与实测数见 `docs/review-20261011/视觉规范.md`）：产物里没有任何「次数/进度」文案")

edit(BRIEF,
     "python tools/verify_redlines.py          # 加 --selftest 会额外验证\"检测器本身会不会报\"",
     "python tools/verify_redlines.py          # 加 --selftest 会额外验证\"检测器本身会不会报\"\n"
     "# 样式契约（对比度/调色板/字号/圆角）：改了 src/styles/** 或 Icon.tsx 就跑它\n"
     "python tools/verify_redlines.py --style --selftest   # 34 条 = 11 红线 + 8 样式 + 15 自检")

edit(BRIEF,
     "· `verify_redlines.py` **11/11（+8 自检）** · `qa-verify-bootstrap.mjs`",
     "· `verify_redlines.py` **11/11（+8 自检）**、**`--style --selftest` 34/34**（11 红线 + 8 样式 + 15 自检） · `qa-verify-bootstrap.mjs`")

edit(BRIEF,
     "④ 那两张截图其实是 JPEG 却命名 `.png` → 已改名 `.jpg`；⑤ `verify_pwa.py` / `seed_dev_user.py` 在 cp936 控制台上会崩 → 已修（见 §5） |",
     "④ 那两张截图其实是 JPEG 却命名 `.png` → 已改名 `.jpg`；⑤ `verify_pwa.py` / `seed_dev_user.py` 在 cp936 控制台上会崩 → 已修（见 §5）；"
     "⑥ **界面里三处小字低于 WCAG AA、侧栏那句被 `<br/>` 挤断、桌面卡片\"只变宽没变构图\"、调色板漂到 40 个色 / 字号 20 档** → "
     "全部**先算数再改**（`--ink-3`、`--harvest` 换成刚好达标的取值；半像素字号整数化到 15 档；插画 230→300px、两面 400→440px），"
     "并把判据写成 `--style` 断言、立了 `docs/review-20261011/视觉规范.md` |")

edit(BRIEF,
     "| **`frontend/README.md`**  | **改前端时先读**（接口契约 / 红线落点 / 前端沙箱坑） |",
     "| **`frontend/README.md`**  | **改前端时先读**（接口契约 / 红线落点 / 前端沙箱坑） |\n"
     "| **`docs/review-20261011/视觉规范.md`** | **改样式前先读**（颜色语义与达标对比度 / 15 档字号阶梯 / 断点 / 触控尺寸 / 图标与插画约定；配套 `verify_redlines.py --style`） |")

# ── frontend/README ──
edit(FEREADME,
     "> ⚠️ 这两张截图是 **360px** 宽，而验收清单要的是 **375px** —— 375px 那一轮仍然只能人点。",
     "> ⚠️ 这两张截图是 **360px** 宽，而验收清单要的是 **375px** —— 375px 那一轮仍然只能人点。\n\n"
     "### 样式契约：改 `src/styles/**` 或 `components/Icon.tsx` 之前先读这个\n\n"
     "```powershell\npython tools/verify_redlines.py --style --selftest   # 34 条 = 11 红线 + 8 样式 + 15 自检\n```\n\n"
     "它量四件事：**对比度**（正文/次级/三级/按钮/难度 chip 都要 ≥4.5:1，且三级信息要压在**最暗的那块底**上也达标）、\n"
     "**调色板**（不许出现「和某个令牌只差 ≤2/255」的一次性色；令牌外的不透明色必须白名单里且写了理由）、\n"
     "**字号**（只许用 `FONT_SCALE` 里的 15 档，半像素会被拦下）、**圆角**（要么 `var(--r-*)`，要么白名单里的有机形状）。\n\n"
     "语义、取值理由与「机器不管什么」的边界都写在 **`../docs/review-20261011/视觉规范.md`**（2026-10-11 定稿）。\n"
     "这一轮据它改掉的东西：`--ink-3` `#73776b`→`#6a6e62`（4.27→4.87，最暗的侧栏底 4.53）、`--harvest` `#956638`→`#8e5f31`（4.10→4.53）、\n"
     "半像素字号整数化（20→15 档）、侧栏那句的 padding 12→8px（原来只余 4px 余量，会被挤断）、\n"
     "桌面端插画 230→300px 且两面 `min-height` 同步 400→440px（**必须成对改**，否则翻面会跳高）。")

# ── 会话纪要 ──
edit(LOG,
     "| `tools/verify_redlines.py` | **红线巡检 11 条（+8 条自检）**（2026-10-10 新增）：",
     "| `tools/verify_redlines.py` | **红线巡检 11 条（+8 条自检）**；**加 `--style` 再 8 条样式断言（对比度/调色板/字号/圆角）+7 条自检**（2026-10-11 新增，判据见 `docs/review-20261011/视觉规范.md`）（2026-10-10 新增）：")

edit(LOG,
     "| `frontend/qa-verify-bootstrap.mjs` | **身份回归**（纯 Node，不需要浏览器与后端）",
     "| `docs/review-20261011/视觉规范.md` | **视觉判据**（2026-10-11 定稿）：颜色语义与达标对比度 · 15 档字号阶梯 · 圆角/间距/动效令牌 · 断点（420/700/960）· 触控 44px · 图标与插画约定 · 「机器不管什么」的边界。**改样式前先读，配套 `verify_redlines.py --style`** |\n"
     "| `frontend/qa-verify-bootstrap.mjs` | **身份回归**（纯 Node，不需要浏览器与后端）")

# ── 优化记录：把审美这一轮补成一节 ──
edit(RECORD,
     "| `today-desktop.jpg` | 「今天」页（桌面，含左侧栏） | 1264 × 803 |",
     """| `today-desktop.jpg` | 「今天」页（桌面，含左侧栏） | 1264 × 803 |

---

## 6. 审美：先量一遍再改（2026-10-11 补做）

审美本身不能量，但**它下面的机制能**。这一轮把界面里的可判定部分量了、改了、并固化成了断言
（全部判据与取值理由见 `视觉规范.md`）。

### 6.1 量出来的三处"错"

| 项 | 量到的数 | 改法 |
| --- | --- | --- |
| 三级小字低于 WCAG AA | `--ink-3 #73776b` 在页面底 4.27、**在侧栏底只有 3.98**、在底部导航 4.38；`--harvest #956638` 在 chip 底 4.10（都需 4.5） | 换成**算出来的**刚好达标值：`--ink-3 #6a6e62`（4.87 / **4.53** / 4.99 / 5.18）、`--harvest #8e5f31`（4.53）。取值由**最暗的那块底**决定 |
| 调色板漂移 | 改动前 base+components 只有 13 个色，改完变成 **40 个**；其中 `#eeeee3/#eeeee4/#eeeee5` **只差 1/255**、`#869875/#879777` 差 2/255（吸管点两次的指纹） | 把"差 ≤2/255"的一次性色折进令牌（`--seed-tint` / `--seed-tint-strong` / `--leaf-ink` / `--shadow-ink` / `--warn`），**肉眼零变化**；40 → 33 个色 |
| 字号 20 档、含 5 个半像素 | 11.5/12.5/13.5/14.5/15.5 共 16 处声明 | 逐条核过受影响的元素（**没有一个是"固定宽度且不换行"的容器**，最紧的那处仍有 ≥25% 余量）后整数化：**20 → 15 档** |

### 6.2 截图上看出来的两处

- **侧栏那句被 `<br/>` 挤断**成「生活会长出自己的样／子。」：可用宽度 = 240 − 26×2 − 12×2 = **164px**，
  而那句话第二行 10 个汉字 × 16px = **160px**，只余 **4px** —— 字体一回退就断。→ note 的左右 padding 12 → 8px（可用 172px）。
- **桌面端"只变宽、没变构图"**：卡片内宽 ≈670px，插画固定 230px（占 34%）；
  而卡背上最宽的一行字（23px × 12 字 ≈ 276px）本来就比插画宽。→ ≥960px 时插画 300px（**图比最宽的文字略宽**），
  两面 `min-height` **同步** 400 → 440px（不同步就会在翻面末段跳高）。

### 6.3 这一轮新增的"仪器"

- `tools/verify_redlines.py --style`：8 条样式断言 + 7 条自检（含正反例：黑/白必须 21:1、同色必须 1:1、差 1/255 要报、差 40/255 要放过）。
- 两个**实测过的假结论**（都写进脚本注释了，这类"仪器自己错"比被测对象错更危险）：
  ① 扫颜色前**必须剥掉 CSS 注释**——否则注释里那句"原来是 #73776b"会被当成"这个色还在用"，修完仍然报红；
  ② 自检行的判据是 `bool(hits) == want_hit`，而**非空列表恒为真**——第一版写成 `[False]` 让四条自检空转（当场被抓）。
- `docs/review-20261011/视觉规范.md`：把上面这些从"我的分析"变成"下一轮改样式时的判据"。

### 6.4 没做的（需要眼睛）

桌面端横向构图、插画统一令牌、装饰图标对比度（2.81:1，按 WCAG 1.4.11 对装饰性图形豁免）、
以及 `--serif` 在中文 Windows 上落到宋体的观感——**这些没有断言，只能人看**。""")

report = []
for path, old, new in EDITS:
    full = os.path.join(ROOT, path)
    text = io.open(full, encoding="utf-8").read()
    n = text.count(old)
    if n != 1:
        report.append("× 命中 %d 次：%s :: %s" % (n, path, old[:52].replace("\n", " ")))
        continue
    io.open(full, "w", encoding="utf-8", newline="").write(text.replace(old, new))
    report.append("√ %s :: %s" % (path, old[:46].replace("\n", " ")))

print("\n".join(report))
ok = sum(1 for r in report if r.startswith("√"))
print("\n%d/%d 处替换成功" % (ok, len(EDITS)))
sys.exit(0 if ok == len(EDITS) else 1)
