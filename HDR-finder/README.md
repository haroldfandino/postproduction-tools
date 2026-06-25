# Rec. 709 Finder

`rec709_finder.py` scans video files and project references for media whose
video color metadata is not standard Rec. 709.

Supported targets:

- Folders, recursively
- Individual video files
- After Effects projects: `.aep`, `.aepx`
- Premiere Pro projects: `.prproj`

The scanner uses `ffprobe` as the source of truth for video metadata. Project
files are used only to discover referenced media paths.

## Usage

```powershell
python HDR-finder\rec709_finder.py "C:\path\to\folder"
```

```powershell
python HDR-finder\rec709_finder.py "C:\path\to\project.aep" --json scan.json --markdown scan.md
```

```powershell
python HDR-finder\rec709_finder.py "C:\path\to\project.prproj" --include-unknown
```

## What Counts As Non-Rec. 709

A video is reported as `non_rec709` when any known video color field is not
`bt709`:

- `color_primaries`
- `color_transfer`
- `color_space` / matrix

Files with no color metadata are listed as `unknown`, because the tool cannot
prove that they are Rec. 709 or non-Rec. 709 from metadata alone.

## Requirements

- Python 3.10 or newer
- FFmpeg / FFprobe available on `PATH`

