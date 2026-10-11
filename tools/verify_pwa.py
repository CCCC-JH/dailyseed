# -*- coding: utf-8 -*-
"""把「PWA 与静态资源契约」从**眼睛看**变成**跑一遍**。

为什么单独一个脚本：验收清单里 PWA 那一整节（manifest 无报错 / 图标都加载出来 /
SW activated / 离线还能打开 / 可安装）原来只能靠 DevTools 手工看，而其中**能机器判定**的部分
其实不少——尤其两条容易出事、又看不出来的：

  1. **SW 与产物是否配套**：`sw.js` 的预缓存清单一旦写错（或哪天有人往里面塞了带哈希的
     文件名），离线就会在**下一次发布**之后才坏——那时你早就忘了这回事了
  2. **产物名必须带内容哈希**：nginx 给 `/assets/` 的是 `immutable` 长缓存，
     这个"敢长缓存"的前提就是文件名带哈希。名字一变就不带哈希，缓存就成了隐患

用法（默认对着**预览服务器** 4173，那是会注册 Service Worker 的那条路）：
    npm run preview                                  # 另开一个窗口
    python tools/verify_pwa.py                       # 或：python tools/verify_pwa.py http://127.0.0.1:18088
    python tools/verify_pwa.py http://localhost:5173 # 开发服务器也能跑（但要记住它不注册 SW）

⚠️ 这个脚本验的是**静态契约**，不是"手机上好用"。真机手感（安装、离线、iOS 的 share）
仍然要人点。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4173").rstrip("/")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SW_SOURCE = os.path.join(ROOT, "frontend", "public", "sw.js")

# 兜底：任何"这台控制台编不出来"的字符都降级成 '?'，绝不让整个脚本崩在半路。
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001 —— 老 Python 没有 reconfigure，就当没这回事
    pass

results = []


def fetch(path):
    """返回 (状态码, 正文文本, 响应头)。连不上时状态码给 0，好在断言里说清楚。"""
    req = urllib.request.Request(BASE + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.headers
    except Exception as e:  # noqa: BLE001 —— 连不上就是连不上，正文里写清楚原因
        return 0, "%s: %s" % (type(e).__name__, e), {}


def head(headers, name):
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return ""


# ⚠️ 中文 Windows 的控制台是 cp936，而 **GB2312 只有 ①–⑩**：⑪(U+246A) 起就编不出来。
# 实测：这个脚本跑到第 ⑪ 条时抛 `UnicodeEncodeError: 'gbk' codec can't encode '\u246a'`
# 直接死掉 —— 前面 10 条的结论全白跑，而且看起来像"脚本坏了"。
# 处理办法不是改标签（标签是断言编号，文档里引用着它们），而是**按这台控制台的实际编码
# 决定用圈码还是用数字**：能编出来就用 ⑪，编不出来就退回 11。
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱"


def safe_label(label):
    if label and label[0] in CIRCLED:
        try:
            label[0].encode(sys.stdout.encoding or "utf-8")
        except UnicodeEncodeError:
            return "%d.%s" % (CIRCLED.index(label[0]) + 1, label[1:])
    return label


def check(label, ok, detail=""):
    label = safe_label(label)
    results.append((ok, label, detail))
    print("%s %s%s" % ("PASS" if ok else "FAIL", label, ("  ← " + detail) if detail else ""))


print("base = %s" % BASE)
print("=" * 72)

# ── 1. index.html：移动端与中文界面的前提 ──
html_s, html, html_head = fetch("/")
if html_s == 0:
    print("连不上 %s —— 先把预览服务器起起来：cd frontend; npm run preview" % BASE)
    print("（或者对着容器跑：python tools/verify_pwa.py http://127.0.0.1:18088）")
    raise SystemExit(2)

# ⚠️ 先确认"这个地址上真的有一个前端"。对着后端（8080）跑会拿到一堆 404，
#    于是 14 条全 FAIL —— 那看起来像"前端坏了"，其实只是**跑错了地址**。
if html_s != 200 or "text/html" not in head(html_head, "Content-Type"):
    print("这个地址上没有前端页面：GET / → %s（Content-Type=%s）"
          % (html_s, head(html_head, "Content-Type") or "（无）"))
    print("看着像后端或别的服务。请对着**前端**跑：4173 预览页 / 5173 开发页 / 18088 容器里的 nginx。")
    raise SystemExit(2)

check("① index.html → 200 + text/html", html_s == 200 and "text/html" in head(html_head, "Content-Type"),
      "status=%s Content-Type=%s" % (html_s, head(html_head, "Content-Type")))
check("② lang=zh-CN（中文断行与字体回退都靠它）", 'lang="zh-CN"' in html)
check("③ viewport 含 width=device-width（375px 那份清单的前提）",
      re.search(r'name="viewport"[^>]*width=device-width', html) is not None
      or re.search(r'width=device-width', html) is not None)
check("④ 指向 manifest", re.search(r'<link[^>]+rel="manifest"[^>]+href="([^"]+)"', html) is not None,
      (re.search(r'<link[^>]+rel="manifest"[^>]+href="([^"]+)"', html) or [None, "（缺）"])[1])

assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
check("⑤ index.html 引用的产物存在（js/css）", len(assets) >= 2, "引用了 %s" % assets)
bad_assets = []
for a in assets:
    s, _, hd = fetch(a)
    if s != 200:
        bad_assets.append("%s→%s" % (a, s))
check("⑥ 每个产物都取得到（200）", not bad_assets, " ".join(bad_assets) or "全部 200")

hashed = [a for a in assets if re.search(r"-[A-Za-z0-9_]{8,}\.(js|css)$", a)]
check("⑦ ★ 产物名带内容哈希（形如 index-DL0ZbyQQ.js）——nginx 敢给 /assets/ 长缓存的**前提**",
      len(hashed) == len(assets) and bool(assets),
      "带哈希 %d / 共 %d：%s" % (len(hashed), len(assets), assets))

external = re.findall(r'https?://[^"\'\s>]+', html)
check("⑧ ★ 页面里没有第三方源（不引 CDN / 统计 / 字体；CSP 敢收那么紧就靠这条）",
      not external, "发现：%s" % external or "无")

# ── 2. manifest ──
mf_s, mf_text, mf_head = fetch("/manifest.webmanifest")
mf = {}
try:
    mf = json.loads(mf_text)
except Exception:  # noqa: BLE001
    pass
check("⑨ /manifest.webmanifest → 200 且是合法 JSON", mf_s == 200 and bool(mf),
      "status=%s Content-Type=%s" % (mf_s, head(mf_head, "Content-Type")))
missing = [k for k in ("name", "short_name", "start_url", "display") if not mf.get(k)]
check("⑩ manifest 必填项齐全（name / short_name / start_url / display）", not missing,
      "缺 %s；实际 keys=%s" % (missing or "无", sorted(mf.keys())))

icons = mf.get("icons", [])
sizes = {i.get("sizes", "") for i in icons}
purposes = " ".join(i.get("purpose", "") for i in icons)
check("⑪ ★ 图标覆盖 192 / 512 / maskable（缺哪个，哪个平台就不给装）",
      any("192" in s for s in sizes) and any("512" in s for s in sizes) and "maskable" in purposes,
      "sizes=%s purpose=%s" % (sorted(sizes), purposes or "（无）"))

bad_icons = []
for i in icons:
    src = i.get("src", "")
    s, _, hd = fetch(src)
    if s != 200 or "image" not in head(hd, "Content-Type"):
        bad_icons.append("%s→%s/%s" % (src, s, head(hd, "Content-Type")))
check("⑫ 每个图标都取得到、且真是图片", not bad_icons, " ".join(bad_icons) or "%d 个图标全 200" % len(icons))

# ── 3. Service Worker：与产物配套，且不许碰接口 ──
sw_s, sw, sw_head = fetch("/sw.js")
check("⑬ /sw.js → 200 + JS 类型", sw_s == 200 and "javascript" in head(sw_head, "Content-Type"),
      "status=%s Content-Type=%s" % (sw_s, head(sw_head, "Content-Type")))

if os.path.exists(SW_SOURCE):
    # 保留 CRLF；默认文本读取会自动转成 LF，Windows 上会把相同文件误报成不同。
    with open(SW_SOURCE, encoding="utf-8", newline="") as fh:
        src = fh.read()
    check("⑭ 线上 sw.js 与源码逐字节一致（构建漏拷/被旧文件顶掉，都会在这里现形）",
          sw == src, "线上 %d 字节 / 源码 %d 字节" % (len(sw.encode('utf-8')), len(src.encode('utf-8'))))
else:
    print("SKIP ⑭ 找不到 %s（不在仓库里就在别的机器上跑的？）" % SW_SOURCE)

precache = re.findall(r"PRECACHE\s*=\s*\[([^\]]*)\]", sw)
precache_urls = re.findall(r"['\"]([^'\"]+)['\"]", precache[0]) if precache else []
bad_pre = []
for u in precache_urls:
    s, _, _ = fetch(u)
    if s != 200:
        bad_pre.append("%s→%s" % (u, s))
check("⑮ ★ SW 预缓存的每一项都存在（写错一个，离线就在**下一次发布之后**才坏）",
      bool(precache_urls) and not bad_pre,
      "预缓存 %s%s" % (precache_urls, ("；坏的：" + " ".join(bad_pre)) if bad_pre else ""))

check("⑯ ★ SW 明确不碰 /api/**（缓存接口 = 让用户看到昨天的卡）",
      "startsWith('/api/')" in sw or 'startsWith("/api/")' in sw)
check("⑰ ★ 策略没被改反：导航 network-first（先拿最新）+ 静态 cache-first",
      "request.mode === 'navigate'" in sw and "caches.match(request)" in sw)

# ── 4. index.html 里的图标链接：浏览器/系统直接按 href 去取，写错一个就是"图标不显示" ──
# （这条是实测补上的：`rel="apple-touch-icon"` 一度指向 icon-192.png，
#   而专门为 iOS 准备的那张 180×180 躺在 public/icons 里没人引用——真机上加到主屏幕就会糊一点）
icon_links = re.findall(r'<link[^>]+rel="(?:icon|apple-touch-icon)"[^>]*href="([^"]+)"', html)
bad_icons = []
for href in icon_links:
    s, _, hd = fetch(href)
    if s != 200 or "image" not in head(hd, "Content-Type"):
        bad_icons.append("%s→%s/%s" % (href, s, head(hd, "Content-Type")))
check("⑱ index.html 里 rel=icon / apple-touch-icon 的每个链接都取得到、且真是图片",
      bool(icon_links) and not bad_icons,
      "链接=%s%s" % (icon_links, ("；坏的：" + " ".join(bad_icons)) if bad_icons else ""))

print("\n" + "=" * 72)
failed = [r for r in results if not r[0]]
print("合计 %d 条断言：%d PASS / %d FAIL" % (len(results), len(results) - len(failed), len(failed)))
for _, label, detail in failed:
    print("  FAIL %s  ← %s" % (label, detail))
print()
print("提醒：这几条**仍然要人点**——安装到桌面、断网刷新、iOS 上从分享面板存 .ics、")
print("      以及 5173 开发页上 SW **应当**是未注册的（那是故意的，不是 bug）。")
raise SystemExit(1 if failed else 0)
