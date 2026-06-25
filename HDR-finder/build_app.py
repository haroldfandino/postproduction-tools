"""
Build a standalone Rec. 709 Finder app with PyInstaller.

Run this on the platform you want to target. On Windows, the default output is
a single .exe in HDR-finder/dist/.

    python build_app.py
    python build_app.py --onefile
    python build_app.py --onedir
    python build_app.py --no-ffprobe
"""

import os
import re
import subprocess
import sys


APP_NAME = "Rec 709 Finder"
HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "rec709_gui.py")


def _ffprobe_binary():
    ext = ".exe" if os.name == "nt" else ""
    local = os.path.join(HERE, "ffmpeg", "ffprobe" + ext)
    if os.path.isfile(local):
        return local, False

    sys.path.insert(0, HERE)
    try:
        import rec709_finder as finder

        found = finder.find_ffprobe()
        if found:
            return _resolve_windows_shim(os.path.realpath(found)), True
    except Exception:
        pass
    return None, False


def _resolve_windows_shim(path):
    if os.name != "nt":
        return path

    shim_path = os.path.splitext(path)[0] + ".shim"
    if not os.path.isfile(shim_path):
        return path

    try:
        text = open(shim_path, "r", encoding="utf-8").read()
    except OSError:
        return path

    match = re.search(r'path\s*=\s*"([^"]+)"', text)
    if match and os.path.isfile(match.group(1)):
        return os.path.realpath(match.group(1))
    return path


def main():
    if "--onedir" in sys.argv:
        onedir = True
    elif "--onefile" in sys.argv:
        onedir = False
    else:
        onedir = sys.platform == "darwin"
    bundle_ffprobe = "--no-ffprobe" not in sys.argv

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Install it with:")
        print("    python -m pip install pyinstaller")
        return 1

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--onedir" if onedir else "--onefile",
    ]

    if bundle_ffprobe:
        ffprobe, from_system = _ffprobe_binary()
        if ffprobe:
            args += ["--add-binary", ffprobe + os.pathsep + "."]
            print("Bundling ffprobe:", ffprobe)
            if from_system:
                print("  NOTE: using the system ffprobe found on this machine.")
        else:
            print("WARNING: ffprobe not found. The app will require FFmpeg on PATH.")

    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "io.indie.rec709finder"]

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
    raise SystemExit(main())
