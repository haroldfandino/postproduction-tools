"""
Build a standalone Technical QC app with PyInstaller.

Run this on the platform you want to target — PyInstaller is NOT a
cross-compiler, so build the Windows .exe on Windows and the macOS .app on
macOS.

    python build_app.py            # one-file build (single distributable)
    python build_app.py --onedir   # one-folder build (faster startup)

Output:
    Windows : dist/Technical QC.exe          (one-file)
              dist/Technical QC/...           (one-folder)
    macOS   : dist/Technical QC.app           (drag to /Applications)

Note: the app still expects FFmpeg/FFprobe to be installed on the target
machine (it searches PATH + common install locations). Install with
`winget install Gyan.FFmpeg` on Windows or `brew install ffmpeg` on macOS.
"""

import os
import subprocess
import sys

APP_NAME = "Technical QC"
HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "qc_gui.py")
ICON = None  # drop an .ico (Windows) / .icns (macOS) path here to brand the app


def main():
    onedir = "--onedir" in sys.argv

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Install it with:\n"
              "    python -m pip install pyinstaller")
        return 1

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--windowed",                       # GUI app, no console window
        "--name", APP_NAME,
        "--onedir" if onedir else "--onefile",
    ]
    if ICON and os.path.isfile(ICON):
        args += ["--icon", ICON]
    if sys.platform == "darwin":
        # Stable bundle id so macOS treats rebuilds as the same app.
        args += ["--osx-bundle-identifier", "io.indie.technicalqc"]
    args.append(ENTRY)

    print("Running:", " ".join(args))
    result = subprocess.run(args, cwd=HERE)
    if result.returncode != 0:
        return result.returncode

    dist = os.path.join(HERE, "dist")
    print("\nBuild complete. Find your app in:", dist)
    if sys.platform == "darwin":
        print("  ->", os.path.join(dist, APP_NAME + ".app"))
    elif os.name == "nt":
        target = APP_NAME + (os.sep if onedir else ".exe")
        print("  ->", os.path.join(dist, target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
