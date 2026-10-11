"""把评审截图（其实是 JPEG，扩展名却写成 .png）转成真正的 PNG，便于查看。"""
import os
from PIL import Image

base = os.path.dirname(os.path.abspath(__file__))
for name in ("today-mobile", "today-desktop"):
    src = os.path.join(base, name + ".jpg")
    im = Image.open(src)
    print(name, im.format, im.size, im.mode)
    im.convert("RGB").save(os.path.join(base, name + "-conv.png"))
print("done")
