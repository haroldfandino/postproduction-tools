"""
Generate the Technical QC app icon — a green rounded square with a white
checkmark — as icon.png, icon.ico (Windows) and icon.icns (macOS).

    python make_icon.py

The .ico / .icns files are consumed by build_app.py when packaging. The live
app draws its own window/taskbar icon in qc_gui.py (no file needed), so this
script only needs to run when you want to (re)generate the bundle icons.
"""

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
GREEN = (31, 157, 87, 255)   # #1f9d57 — matches the app's pass-rate ring
WHITE = (255, 255, 255, 255)
SIZE = 1024


def render(size=SIZE):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded-square background.
    pad = int(size * 0.06)
    radius = int(size * 0.225)
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=radius, fill=GREEN)

    # White checkmark (thick rounded polyline).
    w = int(size * 0.085)
    pts = [
        (int(size * 0.30), int(size * 0.53)),
        (int(size * 0.44), int(size * 0.68)),
        (int(size * 0.72), int(size * 0.35)),
    ]
    d.line(pts, fill=WHITE, width=w, joint="curve")
    # Rounded end-caps.
    r = w // 2
    for (x, y) in (pts[0], pts[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=WHITE)
    return img


def main():
    img = render()
    png = os.path.join(HERE, "icon.png")
    ico = os.path.join(HERE, "icon.ico")
    icns = os.path.join(HERE, "icon.icns")

    img.save(png)
    print("wrote", png)

    img.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", ico)

    try:
        # ICNS wants square power-of-two sizes; 1024 is fine.
        img.save(icns)
        print("wrote", icns)
    except Exception as e:
        print("could not write icns (build on macOS will fall back):", e)


if __name__ == "__main__":
    main()
