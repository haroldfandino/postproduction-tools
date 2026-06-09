# Postproduction Tools

Small Python utilities for common post-production workflows:

- Extract still frames from video files.
- Rename still images using a consistent project naming convention.
- Run technical QC checks on delivered video files and export Markdown reports.

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

`Technical_QC/qc_gui.py` is a desktop GUI (Windows + macOS) over the same engine: pick or drag-and-drop a folder of videos, run the QC pass, and review pass/fail results per file and per parameter without using a terminal. It also writes the same `specifications.md` and `QC_Report.md` next to the videos.

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

Then choose (or drag in) the folder of deliverables and click **Run QC**. Use the ☾ / ☀ toggle for dark / light mode, and **Open report** to view the generated `QC_Report.md`.

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

## Packaging the QC GUI as a standalone app (optional)

The GUI is structured to bundle with [PyInstaller](https://pyinstaller.org/)
into a double-clickable app. Build on the target OS (build on Windows for a
`.exe`, on macOS for a `.app`):

```bash
python -m pip install pyinstaller
# from the Technical_QC folder:
pyinstaller --noconfirm --windowed --name "Technical QC" qc_gui.py
```

The bundle still relies on FFmpeg/FFprobe being installed on the machine (or
placed next to the executable). Output lands in `dist/`.

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
