"""
Generate the Technical QC app icon — a green rounded square with a white
checkmark — as icon.png, icon.ico (Windows) and icon.icns (macOS).

    python make_icon.py

The .ico / .icns files are consumed by build_app.py when packaging. The live
app draws its own window/taskbar icon in qc_gui.py (no file needed), so this
script only needs to run when you want to (re)generate the bundle icons.

The .icns is written with Apple's `iconutil` when run on macOS (best quality),
and falls back to Pillow's ICNS writer on other platforms or if `iconutil`
isn't available.
"""

import os
import shutil
import subprocess
import sys

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


# Apple .iconset members: (pixel size, filename).
_ICONSET = [
    (16, "icon_16x16.png"),    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
]


def write_icns(out_path):
    """
    Write the .icns. On macOS with `iconutil`, build it from a proper .iconset
    (Apple's native tool, best fidelity). Otherwise fall back to Pillow.
    Returns the method used ("iconutil" or "pillow").
    """
    if sys.platform == "darwin" and shutil.which("iconutil"):
        iconset = os.path.join(HERE, "icon.iconset")
        if os.path.isdir(iconset):
            shutil.rmtree(iconset)
        os.makedirs(iconset)
        try:
            for size, fname in _ICONSET:
                render(size).save(os.path.join(iconset, fname))
            subprocess.run(
                ["iconutil", "-c", "icns", iconset, "-o", out_path], check=True
            )
            return "iconutil"
        finally:
            shutil.rmtree(iconset, ignore_errors=True)

    # Cross-platform fallback (e.g. building the .icns from Windows).
    render(1024).save(out_path)
    return "pillow"


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
        method = write_icns(icns)
        print(f"wrote {icns} (via {method})")
    except Exception as e:
        print("could not write icns:", e)


if __name__ == "__main__":
    main()
