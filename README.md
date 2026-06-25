# Postproduction Tools

Small Python utilities for common post-production workflows:

- Extract still frames from video files.
- Rename still images using a consistent project naming convention.
- Run technical QC checks on delivered video files and export Markdown reports.
- Find video references whose color metadata is not standard Rec. 709.

## Tools

### Extract Stills

`Extract_stills/extract_stills.py` extracts PNG stills from a video every 24 frames and also saves the last frame. Stills are written to a `stills` folder next to the source video.

```powershell
python Extract_stills\extract_stills.py "C:\path\to\video.mp4"
```

### Rename Stills

`Rename_stills/rename_stills.py` renames `.png`, `.jpg`, and `.jpeg` files in the current directory using this pattern:

```text
ProjectName_ProjectType_Still_01.png
```

Run it from the folder containing the images:

```powershell
python C:\path\to\Rename_stills\rename_stills.py
```

### Technical QC

`Technical_QC/technical_qc.py` scans a folder for `.mp4` and `.mov` files, derives expected specs from the filename, checks metadata and loudness, and writes:

- `specifications.md`
- `QC_Report.md`

`Technical_QC/qc_gui.py` is a desktop GUI (Windows + macOS) over the same engine: pick or drag-and-drop a folder of videos, run the QC pass, and review pass/fail results per file and per parameter without using a terminal. The GUI shows everything on screen and does **not** write report files automatically — use the **Export report** button to save `specifications.md` and `QC_Report.md` into the source folder when you want them. The command-line tool always writes both files.

The QC tool expects filenames like:

```text
Client_ProjectDescription_ProjectType_Duration_Orientation_HD_SOCIAL_H264.mp4
Client_ProjectDescription_Duration_4K_TV_ProRes.mov
```

`Duration` can be a numeric target such as `6`, `15`, or `30`. It can also be
`Longform`; longform files report the measured video duration without checking
it against a target duration.

#### Desktop GUI

```powershell
# Windows
python Technical_QC\qc_gui.py
```

```bash
# macOS / Linux
python3 Technical_QC/qc_gui.py
```

Then choose (or drag in) the folder of deliverables and click **Run QC**. Use the ☾ / ☀ toggle for dark / light mode (your choice is remembered between launches), the **Progress log** bar to show/hide the live log, and **Export report** to save `specifications.md` and `QC_Report.md` into the source folder.

#### Command line

Run it from the folder containing the videos, or pass a target folder:

```powershell
# Windows
python Technical_QC\technical_qc.py "C:\path\to\deliverables"
```

```bash
# macOS / Linux
python3 Technical_QC/technical_qc.py "/path/to/deliverables"
```

### Rec. 709 Finder

`HDR-finder/rec709_finder.py` scans folders, individual videos, After Effects
projects (`.aep` / `.aepx`), and Premiere Pro projects (`.prproj`) for video
references whose color metadata is not standard Rec. 709.

```powershell
python HDR-finder\rec709_finder.py "C:\path\to\project.aep"
python HDR-finder\rec709_finder.py "C:\path\to\folder" --json scan.json --markdown scan.md
python HDR-finder\rec709_finder.py "C:\path\to\project.aep" --quiet --compact-report
```

The tool uses `ffprobe` to check `color_primaries`, `color_transfer`, and
`color_space` / matrix. Known values other than `bt709` are reported as
`non_rec709`; files with missing color metadata are listed as `unknown`.

## Requirements

- Python 3.10 or newer
- FFmpeg and FFprobe (required by Technical QC)
- Python packages listed in `requirements.txt` (`PySide6` is only needed for the QC GUI)

Install Python dependencies:

```powershell
# Windows
python -m pip install -r requirements.txt
```

```bash
# macOS / Linux
python3 -m pip install -r requirements.txt
```

### Installing FFmpeg

**Windows**

```powershell
winget install Gyan.FFmpeg
# or download from https://www.gyan.dev/ffmpeg/builds/ and add the bin folder to PATH
```

**macOS** (via [Homebrew](https://brew.sh)):

```bash
brew install ffmpeg
```

The QC tool searches your `PATH` first and then common install locations
(Homebrew on Intel and Apple Silicon, MacPorts, typical Windows folders), so it
usually works even if FFmpeg isn't exported on `PATH`. If it still can't be
found, the tool prints an OS-specific install hint.

Check FFmpeg availability:

```bash
ffmpeg -version
ffprobe -version
```

## Building a standalone app (Windows .exe / macOS .app)

`Technical_QC/build_app.py` wraps [PyInstaller](https://pyinstaller.org/) to
produce a **fully self-contained, double-clickable app** — it bundles Python,
Qt, and (by default) FFmpeg, so the end user installs **nothing** and never
touches a terminal.

> **PyInstaller is not a cross-compiler.** Build the Windows `.exe` **on
> Windows** and the macOS `.app` **on macOS** — each OS builds only its own
> bundle.

### 1. (Optional) prepare the icon and FFmpeg

```bash
python make_icon.py            # regenerate icon.ico / icon.icns (already committed)
```

On macOS this builds the `.icns` with Apple's `iconutil` for best fidelity
(it falls back to Pillow elsewhere), so it's worth re-running on the Mac before
building the `.app`.

To bundle FFmpeg (recommended for a no-install experience), drop a **static**
build of `ffmpeg` and `ffprobe` into `Technical_QC/ffmpeg/`:

- **Windows:** the "essentials"/"full" builds from <https://www.gyan.dev/ffmpeg/builds/>
  are static — copy `ffmpeg.exe` and `ffprobe.exe` in.
- **macOS:** use a self-contained static build (e.g. <https://evermeet.cx/ffmpeg/>
  or <https://osxexperts.net>). **Do not** use Homebrew's `ffmpeg` — it links
  external dylibs and won't run inside the bundle.

If `Technical_QC/ffmpeg/` is empty, the script falls back to a system copy (with
a warning), or you can skip bundling with `--no-ffmpeg`.

### 2. Build

```bash
python -m pip install pyinstaller

# from the Technical_QC folder, on the target OS:
python build_app.py             # default per-OS (see below), FFmpeg bundled
python build_app.py --onefile   # force a single file
python build_app.py --onedir    # force a one-folder build
python build_app.py --no-ffmpeg # rely on system FFmpeg instead of bundling
```

The default packaging mode is chosen per-OS (override with the flags above):

- **macOS → one-folder `.app`.** Starts fast — nothing is extracted at launch.
- **Windows → one-file `.exe`.** A single shareable file (no `_internal` folder);
  it unpacks the bundled FFmpeg to a temp dir on each launch, so first paint is
  a little slower. Use `--onedir` if you prefer faster Windows startup over a
  single file.

Output lands in `Technical_QC/dist/`:

- **Windows:** `dist/Technical QC.exe` (one file)
- **macOS:** `dist/Technical QC.app` (drag to `/Applications`)

> macOS note: an unsigned `.app` will be Gatekeeper-blocked on first launch.
> Right-click → **Open** (or run `xattr -dr com.apple.quarantine "Technical QC.app"`)
> to allow it. Code-signing/notarization requires an Apple Developer account.

## Repository Setup

This folder is prepared for:

```text
https://github.com/haroldfandino/postproduction-tools.git
```

Common first push flow:

```powershell
git add .
git commit -m "Initial postproduction tools"
git branch -M main
git push -u origin main
```
