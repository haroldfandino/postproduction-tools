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

`Technical-QC/technical_qc.py` scans a folder for `.mp4` and `.mov` files, derives expected specs from the filename, checks metadata and loudness, and writes:

- `specifications.md`
- `QC_Report.md`

The QC tool expects filenames like:

```text
Client_ProjectDescription_ProjectType_Duration_Orientation_HD_SOCIAL_H264.mp4
Client_ProjectDescription_Duration_4K_TV_ProRes.mov
```

Run it from the folder containing the videos, or pass a target folder:

```powershell
python Technical-QC\technical_qc.py "C:\path\to\deliverables"
```

## Requirements

- Python 3.10 or newer
- FFmpeg and FFprobe available on your `PATH` for Technical QC
- Python packages listed in `requirements.txt`

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Check FFmpeg availability:

```powershell
ffmpeg -version
ffprobe -version
```

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
