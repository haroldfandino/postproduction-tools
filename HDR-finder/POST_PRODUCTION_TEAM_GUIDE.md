# Rec. 709 Finder - Post-Production Team Guide

Rec. 709 Finder checks video files in a folder, Premiere project, or After Effects project and flags media that may not be standard Rec. 709.

Use this before final delivery or when checking a project for HDR, Log, phone footage, or other media with unexpected color metadata.

## How to Use It

1. Open `Rec 709 Finder.app`.
2. Drag in one of these:
   - A folder of media
   - A Premiere Pro project, `.prproj`
   - An After Effects project, `.aep` or `.aepx`
   - A single video file
3. Click `Run scan`.
4. Wait for the scan to finish.

The app can read project references from Premiere and After Effects projects. On macOS, it can also translate Windows-style LucidLink paths to the matching `/Volumes/...` path when the media is available on the Mac.

## How to Read the Results

The most important section is shown first.

- `Non-Rec. 709` means the file has color metadata outside standard Rec. 709. These files should be reviewed.
- `Unknown` means the file does not have enough color metadata for the app to prove whether it is Rec. 709. These files may need manual review.
- `Hidden video errors` contains missing files or files that could not be read by the scanner.
- `Hidden Rec. 709 videos` contains files that passed the Rec. 709 metadata check.

Click any result row to expand it and see the full path, source project, codec, resolution, and color metadata.

## What to Do With Findings

If the app finds `Non-Rec. 709` media, check whether the file is expected to be HDR, Log, phone HDR, or another non-standard source.

If it should be Rec. 709, conform or transcode the file before delivery, then run the scan again.

If a file appears under `Unknown`, treat it as a manual-check item. The file may still be Rec. 709, but the metadata does not clearly say so.

If files appear under `Hidden video errors`, expand that section and check whether the media is missing, offline, unsupported, or not mounted.

## Exporting a Report

After a scan, click `Export report` to save a Markdown report. This is useful for sharing findings with producers, editors, or finishing.

## Important Notes

- The tool checks video color metadata. It does not visually judge the image.
- A clean scan means the available metadata looks Rec. 709.
- A finding does not always mean the file is wrong. It means the file should be reviewed.
- Make sure LucidLink or any shared storage is mounted before scanning projects.
