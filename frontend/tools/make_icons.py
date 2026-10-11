"""生成 PWA 图标（可复现）：近黑底 + 「窗台上的一盆小苗」。

和产品里的植株是同一套语言：一个盆、一根茎、两片叶子。
用法（沙箱里要用带 Pillow 的 Python）：
    python tools/make_icons.py
"""
from pathlib import Path

import math

from PIL import Image, ImageDraw, ImageFilter

SS = 4  # 超采样倍数，最后缩回去，边缘才干净
BG = (10, 12, 15, 255)

OUT = Path(__file__).resolve().parent.parent / "public" / "icons"


def leaf(img: Image.Image, cx: float, cy: float, length: float, width: float,
         angle_deg: float, color: tuple[int, int, int, int]) -> None:
    """一片叶子：尖头 + 圆底的叶形（不是椭圆），长轴与竖直方向成 angle_deg 度。

    为什么要自己描轮廓：椭圆在 30°~45° 的旋转下看起来就是个圆球，
    40 多像素的小图标里"球"和"叶"是分不出来的。
    坐标和尺寸**全部是画布像素**——缩放（含超采样）由调用方负责。
    """
    a = math.radians(angle_deg)
    hw, hl = width / 2, length / 2

    def T(x: float, y: float) -> tuple[float, float]:
        return (cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a))

    # 钟形叶：一个叶尖 + 两侧各两个点，顶点顺序按顺时针排（顺序错了会变成棱角块）
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(
        [
            T(0, -hl),                # 叶尖
            T(hw * 0.62, -hl * 0.55),
            T(hw, -hl * 0.05),        # 右侧最宽处
            T(hw * 0.80, hl * 0.55),
            T(hw * 0.32, hl),         # 右下
            T(-hw * 0.32, hl),        # 左下
            T(-hw * 0.80, hl * 0.55),
            T(-hw, -hl * 0.05),
            T(-hw * 0.62, -hl * 0.55),
        ],
        fill=color,
    )
    img.alpha_composite(layer)


def draw_icon(size: int, maskable: bool) -> Image.Image:
    s = size * SS
    img = Image.new("RGBA", (s, s), BG)
    draw = ImageDraw.Draw(img)

    # 背景一团极淡的绿光，让图标在深色系统里不显得死板
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    r = int(s * 0.55)
    gd.ellipse([s / 2 - r, s * 0.34 - r, s / 2 + r, s * 0.34 + r], fill=(95, 216, 164, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(s * 0.09))
    img.alpha_composite(glow)

    # maskable 要留安全区（系统可能裁成圆形）：整幅图形按 k 缩放，中心不动
    k = 0.66 if maskable else 0.82

    def P(x: float, y: float) -> tuple[float, float]:
        """把 0..1 的设计坐标映射到画布，并按 k 围绕中心缩放。"""
        return (s * 0.5 + (x - 0.5) * k * s, s * 0.5 + (y - 0.5) * k * s)

    def L(v: float) -> float:
        """长度同样按 k 缩放"""
        return v * k * s

    cx = s / 2

    green_hi = (140, 236, 196, 255)
    green = (95, 216, 164, 255)
    green_lo = (47, 157, 114, 255)

    # 盆沿在 y=0.30，所以茎和叶都必须落在它上方。
    # ⚠️ 这里一开始踩了两次坑：leaf() 收的是**像素坐标**，必须用 P()/L() 换算，
    #    直接把 0..1 的设计坐标传进去，叶子会被画到左上角外面去。
    # 主茎稍微偏右，再补一根左倾的短茎 —— 完全居中的对称构图看着像徽标，不像植物
    draw.line([P(0.53, 0.10), P(0.53, 0.40)], fill=green_lo, width=max(3, int(L(0.026))))
    draw.line([P(0.53, 0.30), P(0.385, 0.20)], fill=green_lo, width=max(3, int(L(0.022))))

    # 两片叶子先画，盆后画 —— 叶底要落到盆沿**内部**，才像从土里长出来
    low = P(0.385, 0.185)
    leaf(img, low[0], low[1], L(0.34), L(0.20), 30, green)
    high = P(0.645, 0.245)
    leaf(img, high[0], high[1], L(0.30), L(0.18), -28, green_hi)

    # 盆：上宽下窄的圆角梯形（盆沿做厚一点，把叶底压干净）
    top_w = L(0.50)
    bot_w = L(0.35)
    top_y = P(0.5, 0.40)[1]
    bot_y = P(0.5, 0.71)[1]
    pot = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pot)
    pd.polygon(
        [
            (cx - top_w / 2, top_y),
            (cx + top_w / 2, top_y),
            (cx + bot_w / 2, bot_y - L(0.04)),
            (cx + bot_w / 2 - L(0.02), bot_y),
            (cx - bot_w / 2 + L(0.02), bot_y),
            (cx - bot_w / 2, bot_y - L(0.04)),
        ],
        fill=(233, 240, 236, 255),
    )
    # 盆身左侧一条极淡的高光，平面才不会发死
    pd.polygon(
        [
            (cx - top_w / 2 + L(0.02), top_y + L(0.012)),
            (cx - top_w / 2 + L(0.075), top_y + L(0.012)),
            (cx - bot_w / 2 + L(0.075), bot_y - L(0.03)),
            (cx - bot_w / 2 + L(0.03), bot_y - L(0.05)),
        ],
        fill=(255, 255, 255, 150),
    )
    # 盆沿
    rim_h = L(0.10)
    pd.rounded_rectangle(
        [cx - top_w / 2 - L(0.012), top_y - rim_h / 2, cx + top_w / 2 + L(0.012), top_y + rim_h / 2],
        radius=rim_h / 2,
        fill=(255, 255, 255, 255),
    )
    img.alpha_composite(pot)

    # 盆底阴影，让它"坐"在窗台上
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([cx - top_w * 0.62, bot_y - L(0.02), cx + top_w * 0.62, bot_y + L(0.045)],
               fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(s * 0.02))
    img.alpha_composite(shadow)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    targets = [
        (192, False, "icon-192.png"),
        (512, False, "icon-512.png"),
        (512, True, "icon-maskable-512.png"),
        (180, False, "apple-touch-icon.png"),
    ]
    for size, maskable, name in targets:
        draw_icon(size, maskable).save(OUT / name)
        print("wrote", (OUT / name).relative_to(OUT.parents[1]))


if __name__ == "__main__":
    main()
