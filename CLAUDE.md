# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository contains Python utilities for post-production video workflows. There are three main tool categories:

1. **Extract Stills** - Extracts PNG frames from video files (every 24 frames + last frame)
2. **Rename Stills** - Batch renames image files using project naming conventions
3. **Technical QC** - Validates video file technical specifications based on filename conventions
4. **Split Video** - Splits videos into frame-accurate chunks

## Common Commands

### Development Setup

```bash
# Install dependencies
python3 -m pip install -r requirements.txt

# Install FFmpeg (required for Technical QC and Extract Stills)
# macOS
brew install ffmpeg

# Windows
winget install Gyan.FFmpeg
```

### Running the Tools

```bash
# Extract stills from a video
python Extract_stills/extract_stills.py "path/to/video.mp4"

# Rename stills (run from the folder containing images)
cd folder_with_images
python /path/to/Rename_stills/rename_stills.py

# Technical QC - GUI version
python Technical_QC/qc_gui.py

# Technical QC - Command line version
python Technical_QC/technical_qc.py "path/to/deliverables"

# Split video into chunks
python Split_video/split_video.py
```

### Building Standalone Apps

```bash
# Install PyInstaller
python -m pip install pyinstaller

# Build the Technical QC standalone app (from Technical_QC folder)
cd Technical_QC
python build_app.py              # one-file build with bundled FFmpeg
python build_app.py --onedir     # one-folder build (faster startup)
python build_app.py --no-ffmpeg  # rely on system FFmpeg

# (Optional) Regenerate app icon
python make_icon.py
```

Build outputs:
- **Windows**: `Technical_QC/dist/Technical QC.exe`
- **macOS**: `Technical_QC/dist/Technical QC.app`

Note: PyInstaller is NOT a cross-compiler. Build the Windows .exe on Windows and the macOS .app on macOS.

### Testing

```bash
# Test packaged app with headless diagnostic
# Windows
"dist/Technical QC.exe" --selftest "path/to/test/folder" "output.json"

# macOS
"dist/Technical QC.app/Contents/MacOS/Technical QC" --selftest "path/to/test/folder" "output.json"
```

## Architecture

### Technical QC System

The Technical QC tool is the most complex component in this repository. It has a layered architecture:

**Core Engine** (`technical_qc.py`):
- `run_qc()` - Main orchestration function, reusable by both CLI and GUI
- `parse_filename()` - Extracts expected specs from filename using naming convention
- `get_expected_specs()` - Derives technical requirements from parsed filename tags
- `analyze_file()` - Compares actual video metadata against expected specs
- `measure_loudness()` - Uses FFmpeg ebur128 filter for audio analysis
- FFmpeg/FFprobe detection handles bundled binaries (PyInstaller), local `ffmpeg/` folder, PATH, and common install locations

**GUI** (`qc_gui.py`):
- PySide6-based cross-platform desktop application
- `QcWorker` - Background thread for non-blocking QC execution
- Theme system with persistent light/dark mode (stored in QSettings)
- Drag-and-drop folder selection
- Collapsible file result cards (auto-expand failures)
- On-demand report export (does not auto-write files)
- `--selftest` mode for headless validation of packaged builds

**Build System** (`build_app.py`):
- PyInstaller wrapper for creating standalone executables
- Bundles FFmpeg/FFprobe from `Technical_QC/ffmpeg/` if present, otherwise falls back to system binaries
- On macOS, Homebrew's FFmpeg links external dylibs and won't work in a bundle - use static builds from evermeet.cx or osxexperts.net instead

### Filename Convention Parser

The QC tool expects deliverable filenames to follow this pattern:

```
[Client]_[Project]_[Type]_[Duration]_[Orientation]_[Res]_[Audio]_[Codec].[ext]
```

Example: `Carve_Feb2026_Signature_15_Horizontal_HD_SOCIAL_H264.mp4`

It also supports a shortened Filmkraft-style format (omitting Type and/or Orientation):

```
[Client]_[Project]_[Duration]_[Res]_[Audio]_[Codec].[ext]
```

Example: `Mixbook_StoryModeLaunch_15_4K_SOCIAL_H264.mp4`

The parser (`parse_filename()`) works in reverse from the end of the filename:
1. Codec tag (H264 / ProRes)
2. Audio type (SOCIAL / TV)
3. Resolution tag (HD / 4K)
4. Orientation (Horizontal / Vertical) - defaults to Horizontal if missing
5. Duration (numeric seconds or "Longform")

Files not matching this convention are skipped during QC runs.

### Duration Checking

Duration validation is frame-based, not time-based:
- Target duration of "30" at 23.976 fps means exactly 720 frames (30 × 24)
- `seconds_to_timecode()` converts using logical base FPS (e.g., 23.976 → 24)
- Comparison uses exact frame count (`expected_total_frames == actual_total_frames`)
- Longform files report duration informationally without pass/fail

### FFmpeg Binary Resolution

`find_executable()` searches in this order:
1. Bundled locations (PyInstaller `_MEIPASS`, executable dir, macOS .app Resources/Frameworks)
2. Local `Technical_QC/ffmpeg/` folder
3. System PATH
4. Common install fallback directories (`/opt/homebrew/bin`, `/usr/local/bin`, `C:\ffmpeg\bin`, etc.)

### Split Video Architecture

The Split Video tool (`split_video.py`) uses frame-accurate splitting:
- Probes video with `ffprobe` to get exact frame count and FPS (as a `Fraction`)
- Uses FFmpeg filter chains to extract specific frame ranges
- Maintains CFR (constant frame rate) with PTS manipulation
- Handles audio trimming synchronized to video frames
- Exports to H.264 MP4 with AAC audio

## Key Implementation Details

### Subprocess Management
- All FFmpeg/FFprobe calls use `stdin=subprocess.DEVNULL` to prevent hangs in windowed/packaged apps
- Windows builds use `CREATE_NO_WINDOW` flag to prevent console flashing
- Error handling distinguishes between missing tools and execution failures

### GUI-CLI Reusability
- `run_qc()` accepts `log` and `progress` callbacks so the same engine powers both interfaces
- `write_files` parameter controls whether reports are auto-written (CLI) or on-demand (GUI)
- Returns a dict with both processed data and generated report content

### Theme System
- QSS stylesheet generation in `build_stylesheet()`
- Two palettes: light and dark (defined in `THEMES`)
- Fusion style forced on all platforms for consistent rendering
- Uses transparent containers with gradient background on root widget

### Loudness Measurement
- Scans half the video duration for performance (configurable)
- Parses FFmpeg's ebur128 filter stderr output with regex
- Tolerance: ±2 LU from target (-14 LKFS for SOCIAL, -24 LKFS for TV)

### Extract Stills Implementation
- OpenCV-based frame extraction
- Saves frames at 24-frame intervals plus the last frame
- Creates `stills/` subfolder next to source video
- Progress display with frame counter
