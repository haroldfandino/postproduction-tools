from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class VideoInfo:
    fps: Fraction
    total_frames: int
    has_audio: bool


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} was not found on PATH. Install FFmpeg and try again.")


def parse_fraction(value: str) -> Fraction:
    try:
        parsed = Fraction(value)
    except ZeroDivisionError as exc:
        raise RuntimeError(f"Invalid frame-rate value from ffprobe: {value}") from exc

    if parsed <= 0:
        raise RuntimeError(f"Invalid frame-rate value from ffprobe: {value}")

    return parsed


def probe_video(video_path: Path) -> VideoInfo:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-count_frames",
        "-show_entries",
        "stream=index,codec_type,avg_frame_rate,r_frame_rate,nb_read_frames,nb_frames",
        "-of",
        "json",
        str(video_path),
    ]

    data = json.loads(run_command(command).stdout)
    streams = data.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)

    if video_stream is None:
        raise RuntimeError("No video stream was found in the selected file.")

    fps_text = video_stream.get("avg_frame_rate")
    if not fps_text or fps_text == "0/0":
        fps_text = video_stream.get("r_frame_rate")

    if not fps_text or fps_text == "0/0":
        raise RuntimeError("Could not determine the source frame rate.")

    fps = parse_fraction(fps_text)
    frame_count_text = video_stream.get("nb_read_frames") or video_stream.get("nb_frames")

    if not frame_count_text or frame_count_text == "N/A":
        raise RuntimeError("Could not determine the exact frame count.")

    total_frames = int(frame_count_text)
    if total_frames <= 0:
        raise RuntimeError("The selected video has no readable frames.")

    return VideoInfo(
        fps=fps,
        total_frames=total_frames,
        has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
    )


def prompt_video_path() -> Path:
    while True:
        raw_path = input("Video file path: ").strip().strip('"')
        video_path = Path(raw_path).expanduser()

        if video_path.is_file():
            return video_path.resolve()

        print("That file was not found. Please enter a valid video file path.")


def prompt_duration_seconds() -> float:
    while True:
        raw_duration = input("Chunk duration in seconds: ").strip()

        try:
            duration_seconds = float(raw_duration)
        except ValueError:
            print("Please enter a number, such as 4 or 2.5.")
            continue

        if duration_seconds > 0:
            return duration_seconds

        print("Duration must be greater than 0 seconds.")


def frame_to_seconds(frame_number: int, fps: Fraction) -> str:
    seconds = Fraction(frame_number, 1) / fps
    return f"{float(seconds):.9f}"


def fps_expression(fps: Fraction) -> str:
    return f"{fps.numerator}/{fps.denominator}"


def output_name(video_path: Path, part_number: int, total_parts: int) -> str:
    width = max(2, len(str(total_parts)))
    return f"{video_path.stem}_part{part_number:0{width}d}.mp4"


def ask_before_overwrite(outputs: list[Path]) -> None:
    existing = [path for path in outputs if path.exists()]
    if not existing:
        return

    print("\nThese output files already exist:")
    for path in existing:
        print(f"  {path}")

    answer = input("Overwrite them? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        raise RuntimeError("Canceled before overwriting existing files.")


def export_chunk(
    video_path: Path,
    output_path: Path,
    info: VideoInfo,
    start_frame: int,
    end_frame_exclusive: int,
) -> None:
    end_frame_inclusive = end_frame_exclusive - 1
    fps_expr = fps_expression(info.fps)

    video_filter = (
        f"[0:v:0]select=between(n\\,{start_frame}\\,{end_frame_inclusive}),"
        f"setpts=N/({fps_expr}*TB)[v]"
    )

    command = ["ffmpeg", "-hide_banner", "-y", "-i", str(video_path)]

    if info.has_audio:
        start_seconds = frame_to_seconds(start_frame, info.fps)
        end_seconds = frame_to_seconds(end_frame_exclusive, info.fps)
        audio_filter = f"[0:a:0]atrim=start={start_seconds}:end={end_seconds},asetpts=PTS-STARTPTS[a]"
        command.extend(
            [
                "-filter_complex",
                f"{video_filter};{audio_filter}",
                "-map",
                "[v]",
                "-map",
                "[a]",
            ]
        )
    else:
        command.extend(["-filter_complex", video_filter, "-map", "[v]"])

    command.extend(
        [
            "-r",
            fps_expr,
            "-fps_mode",
            "cfr",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]
    )

    if info.has_audio:
        command.extend(["-c:a", "aac"])

    command.append(str(output_path))

    run_command(command)


def main() -> int:
    try:
        require_tool("ffmpeg")
        require_tool("ffprobe")

        video_path = prompt_video_path()
        duration_seconds = prompt_duration_seconds()
        info = probe_video(video_path)

        chunk_frames = round(duration_seconds * float(info.fps))
        if chunk_frames <= 0:
            raise RuntimeError("The requested duration is shorter than one source frame.")

        total_parts = math.ceil(info.total_frames / chunk_frames)
        output_paths = [
            SCRIPT_DIR / output_name(video_path, part_number, total_parts)
            for part_number in range(1, total_parts + 1)
        ]
        ask_before_overwrite(output_paths)

        print(f"\nSource FPS: {info.fps} ({float(info.fps):.6f})")
        print(f"Total frames: {info.total_frames}")
        print(f"Frames per full chunk: {chunk_frames}")
        print(f"Output folder: {SCRIPT_DIR}\n")

        for part_number, output_path in enumerate(output_paths, start=1):
            start_frame = (part_number - 1) * chunk_frames
            end_frame_exclusive = min(start_frame + chunk_frames, info.total_frames)
            frame_count = end_frame_exclusive - start_frame

            print(
                f"Exporting {output_path.name}: "
                f"frames {start_frame}-{end_frame_exclusive - 1} ({frame_count} frames)"
            )
            export_chunk(video_path, output_path, info, start_frame, end_frame_exclusive)

        print("\nDone.")
        return 0
    except subprocess.CalledProcessError as exc:
        print("\nFFmpeg failed.", file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
