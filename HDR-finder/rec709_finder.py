import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


VIDEO_EXTENSIONS = {
    ".3gp",
    ".ari",
    ".avi",
    ".braw",
    ".crm",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mxf",
    ".r3d",
    ".webm",
}

PROJECT_EXTENSIONS = {".aep", ".aepx", ".prproj"}
REC709_VALUE = "bt709"
UNKNOWN_VALUES = {"", "unknown", "unspecified", "reserved"}


@dataclass(frozen=True)
class MediaReference:
    path: Path
    source: str
    source_type: str


def find_ffprobe() -> str | None:
    exe_names = ["ffprobe.exe", "ffprobe"] if os.name == "nt" else ["ffprobe"]
    local_ffmpeg = Path(__file__).resolve().parent / "ffmpeg"

    for name in exe_names:
        candidate = local_ffmpeg / name
        if candidate.is_file():
            return str(candidate)

    found = shutil.which("ffprobe")
    if found:
        return found

    fallback_dirs = [
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/opt/local/bin"),
        Path("/usr/bin"),
        Path(r"C:\ffmpeg\bin"),
        Path(r"C:\Program Files\ffmpeg\bin"),
    ]
    for directory in fallback_dirs:
        for name in exe_names:
            candidate = directory / name
            if candidate.is_file():
                return str(candidate)
    return None


def run_ffprobe(ffprobe: str, media_path: Path) -> dict:
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,pix_fmt,color_range,color_space,color_transfer,color_primaries",
        "-of",
        "json",
        str(media_path),
    ]
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        **kwargs,
    )
    if result.returncode != 0:
        return {"error": result.stderr.strip() or "ffprobe failed"}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {"error": f"Could not parse ffprobe JSON: {exc}"}

    streams = data.get("streams") or []
    if not streams:
        return {"error": "No video stream found"}
    return streams[0]


def color_status(stream: dict, include_unknown: bool = False) -> tuple[str, dict, list[str]]:
    fields = {
        "color_primaries": stream.get("color_primaries", ""),
        "color_transfer": stream.get("color_transfer", ""),
        "color_space": stream.get("color_space", ""),
    }

    non_rec709 = {
        key: value
        for key, value in fields.items()
        if value and value.lower() not in UNKNOWN_VALUES and value.lower() != REC709_VALUE
    }
    unknown = [
        key
        for key, value in fields.items()
        if not value or value.lower() in UNKNOWN_VALUES
    ]

    if non_rec709:
        return "non_rec709", non_rec709, unknown
    if include_unknown and unknown:
        return "unknown", {}, unknown
    if len(unknown) == len(fields):
        return "unknown", {}, unknown
    return "rec709", {}, unknown


def normalize_embedded_path(raw: str) -> str:
    text = raw.replace("\x00", "").strip().strip("'\"")
    text = text.replace("\\\\", "\\")
    text = text.replace("/", "\\") if re.match(r"^[A-Za-z]:/", text) else text

    drive_match = re.search(r"[A-Za-z]:[\\/].+", text)
    if drive_match:
        text = drive_match.group(0)

    unc_match = re.search(r"\\\\[^\\/:*?\"<>|\r\n]+\\[^:*?\"<>|\r\n]+\\.+", text)
    if unc_match:
        text = unc_match.group(0)

    return text.strip().strip("'\"")


def read_project_text(project_path: Path) -> str:
    data = project_path.read_bytes()
    if project_path.suffix.lower() == ".prproj" and data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)

    chunks = []
    for encoding in ("utf-8", "utf-16le", "utf-16be"):
        chunks.append(data.decode(encoding, errors="ignore"))
    return "\n".join(chunks)


def extract_media_paths_from_project(project_path: Path) -> list[Path]:
    text = read_project_text(project_path)
    ext_pattern = "|".join(re.escape(ext[1:]) for ext in sorted(VIDEO_EXTENSIONS))
    full_path_pattern = re.compile(
        rf"(?:[A-Za-z]:[\\/]|\\\\)[^\r\n<>\"|?*]{{1,500}}?\.(?:{ext_pattern})",
        re.IGNORECASE,
    )
    relative_pattern = re.compile(
        rf"[^\r\n<>\"|?*]{{1,260}}?\.(?:{ext_pattern})",
        re.IGNORECASE,
    )

    found: set[Path] = set()
    for match in full_path_pattern.finditer(text):
        candidate = Path(normalize_embedded_path(match.group(0)))
        found.add(candidate)

    if project_path.suffix.lower() in {".aepx", ".prproj"}:
        for match in relative_pattern.finditer(text):
            raw = normalize_embedded_path(match.group(0))
            if re.match(r"^[A-Za-z]:[\\/]", raw) or raw.startswith("\\\\"):
                continue
            if any(char in raw for char in "<>"):
                continue
            candidate = (project_path.parent / raw).resolve()
            if candidate.suffix.lower() in VIDEO_EXTENSIONS:
                found.add(candidate)

    return sorted(found, key=lambda path: str(path).lower())


def iter_folder_media(folder: Path, max_depth: int | None = None) -> Iterable[Path]:
    root_parts = len(folder.resolve().parts)
    for current_root, dirnames, filenames in os.walk(folder):
        current = Path(current_root)
        if max_depth is not None:
            depth = len(current.resolve().parts) - root_parts
            if depth >= max_depth:
                dirnames[:] = []
        for filename in filenames:
            path = current / filename
            if path.suffix.lower() in VIDEO_EXTENSIONS:
                yield path


def collect_references(targets: list[Path], max_depth: int | None) -> list[MediaReference]:
    references: dict[Path, MediaReference] = {}

    for target in targets:
        if target.is_dir():
            for media_path in iter_folder_media(target, max_depth=max_depth):
                resolved = media_path.resolve()
                references[resolved] = MediaReference(resolved, str(target), "folder")
            continue

        suffix = target.suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            resolved = target.resolve()
            references[resolved] = MediaReference(resolved, str(target), "file")
        elif suffix in PROJECT_EXTENSIONS:
            for media_path in extract_media_paths_from_project(target):
                references[media_path] = MediaReference(media_path, str(target), suffix[1:])
        else:
            print(f"Skipping unsupported target: {target}", file=sys.stderr)

    return sorted(references.values(), key=lambda ref: str(ref.path).lower())


def scan_references(
    references: list[MediaReference],
    ffprobe: str,
    include_unknown: bool = False,
    verbose: bool = True,
) -> list[dict]:
    results = []
    for index, ref in enumerate(references, start=1):
        if verbose:
            print(f"[{index}/{len(references)}] {ref.path}")
        item = {
            "path": str(ref.path),
            "source": ref.source,
            "source_type": ref.source_type,
            "exists": ref.path.is_file(),
        }
        if not item["exists"]:
            item["status"] = "missing"
            results.append(item)
            continue

        stream = run_ffprobe(ffprobe, ref.path)
        if "error" in stream:
            item["status"] = "probe_error"
            item["error"] = stream["error"]
            results.append(item)
            continue

        status, non_rec709, unknown = color_status(stream, include_unknown=include_unknown)
        item.update(
            {
                "status": status,
                "codec_name": stream.get("codec_name", ""),
                "width": stream.get("width", ""),
                "height": stream.get("height", ""),
                "pix_fmt": stream.get("pix_fmt", ""),
                "color_range": stream.get("color_range", ""),
                "color_space": stream.get("color_space", ""),
                "color_transfer": stream.get("color_transfer", ""),
                "color_primaries": stream.get("color_primaries", ""),
                "non_rec709_fields": non_rec709,
                "unknown_fields": unknown,
            }
        )
        results.append(item)
    return results


def write_json_report(results: list[dict], output_path: Path) -> None:
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")


def format_finding_summary(result: dict) -> str:
    if result["status"] == "non_rec709":
        fields = ", ".join(
            f"{key}={value}" for key, value in result["non_rec709_fields"].items()
        )
        return fields
    if result["status"] == "unknown":
        return f"unknown fields: {', '.join(result.get('unknown_fields', []))}"
    if result["status"] == "missing":
        return "missing media"
    if result["status"] == "probe_error":
        return f"probe error: {result.get('error', '')}"
    return result["status"]


def write_markdown_report(
    results: list[dict],
    output_path: Path,
    compact: bool = False,
) -> None:
    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1

    lines = [
        "# Rec. 709 Scan Report",
        "",
        "## Summary",
        "",
        f"- Total references: {len(results)}",
        f"- Non-Rec. 709: {counts.get('non_rec709', 0)}",
        f"- Rec. 709: {counts.get('rec709', 0)}",
        f"- Unknown color metadata: {counts.get('unknown', 0)}",
        f"- Missing media: {counts.get('missing', 0)}",
        f"- Probe errors: {counts.get('probe_error', 0)}",
        "",
    ]

    sections = [
        ("Non-Rec. 709", "non_rec709"),
        ("Unknown Color Metadata", "unknown"),
        ("Missing Media", "missing"),
        ("Probe Errors", "probe_error"),
    ]
    if not compact:
        sections.append(("Rec. 709", "rec709"))

    for title, status in sections:
        section = [result for result in results if result["status"] == status]
        if not section:
            continue
        lines.extend([f"## {title}", ""])
        for result in section:
            if compact:
                lines.append(f"- `{result['path']}` - {format_finding_summary(result)}")
                continue

            lines.append(f"### {result['path']}")
            lines.append("")
            lines.append(f"- Source: {result['source_type']} - {result['source']}")
            if status in {"non_rec709", "unknown", "rec709"}:
                lines.append(f"- Codec: {result.get('codec_name', '')}")
                lines.append(f"- Size: {result.get('width', '')}x{result.get('height', '')}")
                lines.append(f"- Pixel format: {result.get('pix_fmt', '')}")
                lines.append(f"- Color primaries: {result.get('color_primaries', '') or 'unknown'}")
                lines.append(f"- Color transfer: {result.get('color_transfer', '') or 'unknown'}")
                lines.append(f"- Color space/matrix: {result.get('color_space', '') or 'unknown'}")
                lines.append(f"- Color range: {result.get('color_range', '') or 'unknown'}")
            if status == "non_rec709":
                fields = ", ".join(
                    f"{key}={value}" for key, value in result["non_rec709_fields"].items()
                )
                lines.append(f"- Non-Rec. 709 fields: {fields}")
            if status == "unknown":
                lines.append(f"- Unknown fields: {', '.join(result.get('unknown_fields', []))}")
            if status == "probe_error":
                lines.append(f"- Error: {result.get('error', '')}")
            lines.append("")

        if compact:
            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def default_report_path(targets: list[Path]) -> Path:
    if len(targets) == 1:
        target = targets[0]
        folder = target if target.is_dir() else target.parent
        return folder / "Rec709_Scan_Report.md"
    return Path.cwd() / "Rec709_Scan_Report.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find video files that are encoded with color metadata outside "
            "standard Rec. 709. Targets can be folders, video files, .aep/.aepx "
            "After Effects projects, or .prproj Premiere projects."
        )
    )
    parser.add_argument("targets", nargs="+", type=Path)
    parser.add_argument(
        "--include-unknown",
        action="store_true",
        help="Treat missing/unknown color metadata as a reportable finding.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Limit recursive folder scans to this many levels below the target folder.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="Markdown report path. Defaults to Rec709_Scan_Report.md next to a single target.",
    )
    parser.add_argument(
        "--compact-report",
        action="store_true",
        help="Write a shorter Markdown report with findings only.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file progress and print only the summary/findings.",
    )
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON report path.")
    return parser.parse_args()


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


def main() -> int:
    configure_console_encoding()
    args = parse_args()
    ffprobe = find_ffprobe()
    if not ffprobe:
        print("ffprobe was not found. Install FFmpeg and make sure ffprobe is on PATH.", file=sys.stderr)
        return 2

    targets = [target.expanduser() for target in args.targets]
    missing_targets = [str(target) for target in targets if not target.exists()]
    if missing_targets:
        print("These targets do not exist:", file=sys.stderr)
        for target in missing_targets:
            print(f"  {target}", file=sys.stderr)
        return 2

    references = collect_references(targets, max_depth=args.max_depth)
    if not references:
        print("No video references found.")
        return 0

    results = scan_references(
        references,
        ffprobe,
        include_unknown=args.include_unknown,
        verbose=not args.quiet,
    )
    markdown_path = args.markdown or default_report_path(targets)
    write_markdown_report(results, markdown_path, compact=args.compact_report)
    if args.json:
        write_json_report(results, args.json)

    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1

    print("")
    print(f"Scanned {len(results)} video reference(s).")
    print(f"Non-Rec. 709: {counts.get('non_rec709', 0)}")
    print(f"Unknown color metadata: {counts.get('unknown', 0)}")
    print(f"Missing media: {counts.get('missing', 0)}")
    print(f"Probe errors: {counts.get('probe_error', 0)}")
    print(f"Report: {markdown_path}")
    if args.quiet:
        findings = [
            result
            for result in results
            if result["status"] in {"non_rec709", "unknown", "missing", "probe_error"}
        ]
        if findings:
            print("")
            print("Findings:")
            for result in findings:
                print(f"- {result['path']} ({format_finding_summary(result)})")

    return 1 if counts.get("non_rec709", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
