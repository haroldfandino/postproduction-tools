"""
Build a standalone Technical QC app with PyInstaller.

Run this on the platform you want to target — PyInstaller is NOT a
cross-compiler, so build the Windows .exe on Windows and the macOS .app on
macOS. PyInstaller bundles Python itself, so end-users need nothing installed.

    python build_app.py             # one-file, FFmpeg bundled (default)
    python build_app.py --onedir    # one-folder build (faster startup)
    python build_app.py --no-ffmpeg # don't bundle FFmpeg (use system FFmpeg)

Output:
    Windows : dist/Technical QC.exe          (one-file)
              dist/Technical QC/...           (one-folder)
    macOS   : dist/Technical QC.app           (drag to /Applications)

FFmpeg: by default the script bundles ffmpeg + ffprobe so the app is fully
self-contained (no terminal, no installs for the end user). It looks for them
in `Technical_QC/ffmpeg/` first (drop a STATIC build there — recommended), then
falls back to a system copy. On macOS, Homebrew's ffmpeg is NOT self-contained
(it links external dylibs), so prefer a static build from e.g. evermeet.cx or
osxexperts.net placed in `Technical_QC/ffmpeg/`.
"""

import os
import subprocess
import sys

APP_NAME = "Technical QC"
HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "qc_gui.py")


def _icon_path():
    """Per-OS icon file, if present."""
    name = "icon.icns" if sys.platform == "darwin" else "icon.ico"
    path = os.path.join(HERE, name)
    return path if os.path.isfile(path) else None


def _ffmpeg_binaries():
    """
    Resolve ffmpeg + ffprobe to bundle.

    Returns (found, from_system) where `found` is {name: abs_path} and
    `from_system` is True if any came from PATH rather than Technical_QC/ffmpeg/.
    """
    names = ["ffmpeg", "ffprobe"]
    ext = ".exe" if os.name == "nt" else ""
    local_dir = os.path.join(HERE, "ffmpeg")
    found, from_system = {}, False

    for n in names:
        p = os.path.join(local_dir, n + ext)
        if os.path.isfile(p):
            found[n] = p

    missing = [n for n in names if n not in found]
    if missing:
        sys.path.insert(0, HERE)
        try:
            import technical_qc as qc
            for n in missing:
                p = qc.find_executable(n)
                if p:
                    found[n] = os.path.realpath(p)
                    from_system = True
        except Exception:
            pass
    return found, from_system


def main():
    onedir = "--onedir" in sys.argv
    bundle_ffmpeg = "--no-ffmpeg" not in sys.argv

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

    icon = _icon_path()
    if icon:
        args += ["--icon", icon]
        print("Using icon:", icon)
    else:
        print("No icon found (run `python make_icon.py` to generate one).")

    if bundle_ffmpeg:
        found, from_system = _ffmpeg_binaries()
        if found:
            for n, p in found.items():
                args += ["--add-binary", p + os.pathsep + "."]
            print("Bundling FFmpeg:")
            for n, p in found.items():
                print(f"  {n}: {p}")
            if from_system:
                print("  NOTE: using a system copy. On macOS, Homebrew's ffmpeg "
                      "links external dylibs and may NOT run inside the bundle — "
                      "place a static build in Technical_QC/ffmpeg/ instead.")
            missing = [n for n in ("ffmpeg", "ffprobe") if n not in found]
            if missing:
                print(f"  WARNING: could not find {', '.join(missing)} — the app "
                      "will fall back to system FFmpeg for those.")
        else:
            print("WARNING: ffmpeg/ffprobe not found — building without them. "
                  "The app will require FFmpeg to be installed on the target "
                  "machine. Put static builds in Technical_QC/ffmpeg/ to bundle.")

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
