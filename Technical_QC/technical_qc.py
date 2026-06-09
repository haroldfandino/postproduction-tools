import os
import shutil
import subprocess
import json
import re
import sys

# --- Configuration & Tolerances ---
LOUDNESS_TOLERANCE = 2.0  # LU
BITRATE_TOLERANCE = 2.0   # Mbps (for MP4)
DURATION_TOLERANCE_SEC = 1.0 # Seconds
EXPECTED_FRAME_RATE = "23.976"
LONGFORM_DURATION_TAG = "longform"

# Common install locations to fall back on when a binary is not on PATH.
# Covers Homebrew (Intel + Apple Silicon), MacPorts, and typical Windows installs.
_FFMPEG_FALLBACK_DIRS = [
    "/opt/homebrew/bin",      # macOS Apple Silicon (Homebrew)
    "/usr/local/bin",         # macOS Intel (Homebrew) / Linux
    "/opt/local/bin",         # macOS MacPorts
    "/usr/bin",               # Linux
    r"C:\ffmpeg\bin",         # common manual Windows install
    r"C:\Program Files\ffmpeg\bin",
]


class ToolNotFoundError(RuntimeError):
    """Raised when ffmpeg/ffprobe cannot be located on the system."""


def _bundle_dirs():
    """
    Directories to check before PATH for a bundled ffmpeg/ffprobe.

    Covers a frozen PyInstaller build (binaries added next to the app land in
    sys._MEIPASS / the executable dir, or the macOS .app Resources/Frameworks),
    plus a local `ffmpeg/` folder next to this module for development.
    """
    dirs = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(meipass)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        dirs.append(exe_dir)
        dirs.append(os.path.join(exe_dir, "..", "Resources"))   # macOS .app
        dirs.append(os.path.join(exe_dir, "..", "Frameworks"))  # macOS .app
    dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg"))
    return [os.path.normpath(d) for d in dirs if d]


def find_executable(name):
    """
    Locate an executable (e.g. "ffmpeg" / "ffprobe") cross-platform.

    Order: a bundled copy (inside the packaged app or a local ffmpeg/ folder),
    then PATH, then common install directories. Bundled-first means a packaged
    app uses its own ffmpeg even on machines that have a different one on PATH.
    Returns the resolved path, or None if it cannot be found.
    """
    exe_names = [name]
    if os.name == "nt":
        exe_names.append(name + ".exe")

    for directory in _bundle_dirs():
        for exe in exe_names:
            candidate = os.path.join(directory, exe)
            if os.path.isfile(candidate):
                return candidate

    found = shutil.which(name)
    if found:
        return found

    for directory in _FFMPEG_FALLBACK_DIRS:
        for exe in exe_names:
            candidate = os.path.join(directory, exe)
            if os.path.isfile(candidate):
                return candidate
    return None


def check_tools():
    """
    Verify ffmpeg and ffprobe are available.

    Returns a dict {"ffmpeg": path_or_None, "ffprobe": path_or_None}. Used by
    both the CLI and the GUI to give a clear, OS-appropriate error message
    instead of an opaque crash deep inside subprocess.
    """
    return {
        "ffmpeg": find_executable("ffmpeg"),
        "ffprobe": find_executable("ffprobe"),
    }


def require_tools():
    """Resolve ffmpeg/ffprobe paths or raise a helpful, OS-specific error."""
    tools = check_tools()
    missing = [name for name, path in tools.items() if not path]
    if missing:
        if sys.platform == "darwin":
            hint = "Install with Homebrew:  brew install ffmpeg"
        elif os.name == "nt":
            hint = ("Install from https://www.gyan.dev/ffmpeg/builds/ (or "
                    "`winget install Gyan.FFmpeg`) and ensure it is on your PATH.")
        else:
            hint = "Install with your package manager, e.g.  sudo apt install ffmpeg"
        raise ToolNotFoundError(
            f"Required tool(s) not found: {', '.join(missing)}.\n{hint}"
        )
    return tools


# --- Helper Functions ---

def run_command(command):
    """
    Runs a command and returns (stdout, stderr).

    The first element of `command` is resolved against PATH and common install
    locations so the tool works even when ffmpeg/ffprobe are installed but not
    exported on PATH (common on macOS). CREATE_NO_WINDOW keeps a console window
    from flashing when launched from a GUI on Windows.
    """
    if command:
        resolved = find_executable(command[0])
        if resolved:
            command = [resolved, *command[1:]]

    kwargs = {}
    if os.name == "nt":
        # Avoid a flashing console window when called from the GUI.
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            **kwargs,
        )
        return result.stdout, result.stderr
    except Exception as e:
        return None, str(e)

def parse_filename(filename):
    """
    Parses the filename based on the convention:
    [Client]_[Project]_[Type]_[Duration]_[Orientation]_[Res]_[Audio]_[Codec].[ext]
    Example: Carve_Feb2026_Signature_15_Horizontal_HD_SOCIAL_H264.mp4

    Also supports Filmkraft-style names without project type or orientation:
    [Client]_[Project]_[Duration]_[Res]_[Audio]_[Codec].[ext]
    Example: Mixbook_StoryModeLaunch_15_4K_SOCIAL_H264.mp4
    """
    name_without_ext = os.path.splitext(filename)[0]
    parts = name_without_ext.split('_')
    
    # We expect at least 6 parts for the shortest supported format.
    # [Client] [Project] (Type?) [Duration] (Orientation?) [Res] [Audio] [Codec]
    
    if len(parts) < 6:
        return None # Invalid filename structure

    # reverse parsing for safety
    try:
        codec_tag = parts[-1]
        audio_tag = parts[-2]
        res_tag = parts[-3]

        if codec_tag.lower() not in ["h264", "prores"]:
            return None

        if audio_tag.lower() not in ["social", "tv"]:
            return None

        if res_tag.lower() not in ["hd", "4k"]:
            return None
        
        # Check if parts[-4] is an orientation
        potential_orientation = parts[-4]
        
        if potential_orientation.lower() in ["horizontal", "vertical"]:
            orientation_tag = potential_orientation
            duration_tag = parts[-5]
            format_type = "standard"
        else:
            # Assume Orientation is missing -> Default to Horizontal
            # And parts[-4] is actually the Duration
            orientation_tag = "Horizontal"
            duration_tag = parts[-4]

            # Filmkraft files can omit both ProjectType and Orientation:
            # Mixbook_StoryModeLaunch_15_4K_SOCIAL_H264.mp4
            format_type = "filmkraft_short" if len(parts) == 6 else "standard_missing_orientation"

        is_longform = duration_tag.lower() == LONGFORM_DURATION_TAG
        if not duration_tag.isdigit() and not is_longform:
            return None
        
        return {
            "codec_tag": codec_tag,         # H264 / Prores
            "audio_type": audio_tag,        # SOCIAL / TV
            "resolution_tag": res_tag,      # HD / 4K
            "orientation": orientation_tag, # Horizontal / Vertical
            "duration_tag": duration_tag,   # 6 / 15 / 30 / Longform etc
            "is_longform": is_longform,
            "filename": filename,
            "format_type": format_type
        }
    except IndexError:
        return None

def get_expected_specs(tags):
    """
    Derives the expected technical specifications from the parsed tags.
    """
    specs = {
        "File Type": "",
        "Video Codec": "",
        "Resolution": "",
        "Frame rate": "23.976",
        "Duration": "", # To be calculated
        "Total bitrate": None, # Only for MP4
        "Color Space": "Rec. 709",
        "Audio Codec": "",
        "Channels": "2 Stereo",
        "Sample Rate": "48 kHz",
        "Loudness": ""
    }

    # 1. File Type & Codec
    if tags["codec_tag"].lower() == "h264":
        specs["File Type"] = "MP4"
        specs["Video Codec"] = "H.264"
        specs["Audio Codec"] = "Compressed" # AAC
    elif "prores" in tags["codec_tag"].lower():
        specs["File Type"] = "MOV"
        specs["Video Codec"] = "ProRes 422"
        specs["Audio Codec"] = "Uncompressed PCM"
    
    # 2. Resolution
    # Vertical is strictly 1080x1920
    if tags["orientation"].lower() == "vertical":
        specs["Resolution"] = "1080 X 1920"
    else:
        # Horizontal
        if tags["resolution_tag"].lower() == "4k":
            specs["Resolution"] = "3840 X 2160"
        else:
            specs["Resolution"] = "1920 X 1080" # Default HD

    # 3. Bitrate (Only checked for MP4)
    if specs["File Type"] == "MP4":
        if tags["resolution_tag"].lower() == "4k":
            specs["Total bitrate"] = "⁓75 mbps"
        else:
            specs["Total bitrate"] = "⁓25 mbps"
    
    # 4. Loudness
    if tags["audio_type"].lower() == "social":
        specs["Loudness"] = "⁓14 LKFS"
    elif tags["audio_type"].lower() == "tv":
        specs["Loudness"] = "⁓24 LKFS"
        
    # 5. Duration (Set as integer seconds, conversion happens later with known FPS)
    if tags.get("is_longform"):
        specs["Duration_Tag"] = None
        specs["Duration_Check"] = False
        specs["Duration"] = "Informational only"
    else:
        try:
            seconds = int(tags["duration_tag"])
            specs["Duration_Tag"] = seconds
            specs["Duration_Check"] = True
            specs["Duration"] = f"{seconds} seconds" # Will update with TC later
        except:
            specs["Duration_Tag"] = None
            specs["Duration_Check"] = False
            specs["Duration"] = "Unknown"

    return specs

def seconds_to_timecode(seconds, fps):
    """
    Converts seconds to HH:MM:SS:FF based on FPS.
    """
    if fps == 0: return "00:00:00:00"
    
    total_frames = int(round(seconds * fps))
    
    # Calculate logical base FPS for modulo math (e.g. 23.976 -> 24)
    if 23.0 < fps < 24.5: base_fps = 24
    elif 29.0 < fps < 30.5: base_fps = 30
    elif 59.0 < fps < 60.5: base_fps = 60
    elif 49.0 < fps < 50.5: base_fps = 50
    elif 24.5 < fps < 25.5: base_fps = 25
    else: base_fps = int(round(fps))
    
    ff = total_frames % base_fps
    rem_seconds = total_frames // base_fps
    ss = rem_seconds % 60
    rem_minutes = rem_seconds // 60
    mm = rem_minutes % 60
    hh = rem_minutes // 60
    
    return f"{hh:02}:{mm:02}:{ss:02}:{ff:02}"

def get_video_metadata(filepath):
    """
    Uses ffprobe to get technical metadata.
    """
    cmd = [
        "ffprobe", 
        "-v", "quiet", 
        "-print_format", "json", 
        "-show_format", 
        "-show_streams", 
        filepath
    ]
    stdout, stderr = run_command(cmd)
    if not stdout:
        return None
    
    try:
        data = json.loads(stdout)
        return data
    except json.JSONDecodeError:
        return None

def measure_loudness(filepath, duration=None):
    """
    Uses ffmpeg ebur128 filter to measure Integrated Loudness.
    Returns float (LUFS/LKFS) or None.
    If duration is provided, only scans that many seconds (approx half video).
    """
    # fmpeg -i input -t [duration] -map 0:a:0 -af ebur128=peak=true -f null -
    cmd = [
        "ffmpeg",
        "-i", filepath
    ]
    
    if duration:
        # Ensure dot decimal separator and 2 decimal places
        cmd.extend(["-t", f"{duration:.2f}"])
        
    cmd.extend([
        "-map", "0:a:0", # Explicitly map first audio stream
        "-af", "ebur128=peak=true",
        "-f", "null",
        "-"
    ])
    
    # Output is in stderr
    stdout, stderr = run_command(cmd)
    
    # Regex to find: I:         -14.5 LUFS
    # Note: ebur128 prints many lines. We want the FINAL summary or the last update.
    # The summary looks like: "  I:         -13.4 LUFS"
    matches = re.findall(r"I:\s+([-\d\.]+)\s+LUFS", stderr)
    if matches:
        return float(matches[-1])
    return None

def analyze_file(filepath, expected_specs, log=print):
    """
    Orchestrates the analysis of a single file.
    Returns valid specs + passed/failed status.

    `log` is a callable used for progress messages; defaults to print so the
    CLI behaves as before, while the GUI can pass its own sink to surface
    progress in the window.
    """
    meta = get_video_metadata(filepath)
    if not meta:
        return {"error": "Could not read metadata"}

    actual = {}
    
    # --- Extracting Actual Data ---
    
    # Stream Info
    video_stream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "audio"), None)
    
    # Get FPS first as it's needed for Duration check
    fps_val = 0.0
    if video_stream:
        fps_str = video_stream.get("r_frame_rate", "0/0")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            if float(den) > 0:
                fps_val = float(num) / float(den)
    
    # Format Info
    fmt = meta.get("format", {})
    actual["File Type"] = os.path.splitext(filepath)[1].replace(".", "").upper() # MP4 or MOV
    
    duration_sec = float(fmt.get("duration", 0))
    timecode = seconds_to_timecode(duration_sec, fps_val)
    actual["Duration_Sec"] = duration_sec
    actual["Duration"] = f"{duration_sec:.2f}s ({timecode})"
    
    bitrate_bps = float(fmt.get("bit_rate", 0))
    actual["Total bitrate"] = f"{bitrate_bps / 1_000_000:.2f} mbps"
    actual["Bitrate_Mbps"] = bitrate_bps / 1_000_000

    if video_stream:
        # Codec
        v_codec = video_stream.get("codec_name", "")
        v_codec_long = video_stream.get("codec_long_name", "")
        
        if "h264" in v_codec:
            actual["Video Codec"] = "H.264"
        elif "prores" in v_codec:
            # Use long name if available for better matching (e.g. Apple ProRes 422)
            if "iCodec Pro" in v_codec_long:
                 actual["Video Codec"] = "ProRes 422"
            elif "422" in v_codec_long:
                 actual["Video Codec"] = "ProRes 422"
            elif "HQ" in v_codec_long: 
                 actual["Video Codec"] = "ProRes 422 HQ"
            elif "Proxy" in v_codec_long:
                 actual["Video Codec"] = "ProRes 422 Proxy"
            elif "LT" in v_codec_long:
                 actual["Video Codec"] = "ProRes 422 LT"
            elif "4444" in v_codec_long:
                 actual["Video Codec"] = "ProRes 4444"
            else:
                 actual["Video Codec"] = v_codec_long if v_codec_long else f"ProRes {video_stream.get('profile', '')}"
        else:
            actual["Video Codec"] = v_codec_long if v_codec_long else v_codec

        # Resolution
        width = video_stream.get("width")
        height = video_stream.get("height")
        actual["Resolution"] = f"{width} X {height}"

        # Frame Rate formatting
        actual["Frame rate"] = f"{fps_val:.3f}" if fps_val > 0 else "0"
            
        # Color Space (Simple check)
        color_primaries = video_stream.get("color_primaries", "unknown")
        if "bt709" in color_primaries:
            actual["Color Space"] = "Rec. 709"
        else:
             actual["Color Space"] = color_primaries

    if audio_stream:
        # Audio Codec
        a_codec = audio_stream.get("codec_name", "")
        if "pcm" in a_codec:
            actual["Audio Codec"] = "Uncompressed PCM"
        elif "aac" in a_codec:
            actual["Audio Codec"] = "Compressed"
        else:
            actual["Audio Codec"] = a_codec

        # Sample Rate
        sample_rate = audio_stream.get("sample_rate", "")
        if sample_rate:
             actual["Sample Rate"] = f"{int(sample_rate)/1000:.0f} kHz"
        
        # Channels (Simple check)
        channels = audio_stream.get("channels", 0)
        if channels == 2:
            actual["Channels"] = "2 Stereo"
        else:
            actual["Channels"] = str(channels)

    # Loudness Measurement
    log(f"Measuring loudness for {os.path.basename(filepath)} (Half Duration)...")
    half_duration = duration_sec / 2 if duration_sec > 0 else None
    loudness = measure_loudness(filepath, duration=half_duration)
    
    if loudness is not None:
        actual["Loudness"] = f"{loudness:.2f} LKFS"
        actual["Loudness_Val"] = loudness
    else:
        actual["Loudness"] = "Error"
        actual["Loudness_Val"] = None

    # --- Comparison Logic ---
    report_items = []
    
    # 1. File Type
    if expected_specs["File Type"] == actual["File Type"]:
        report_items.append({"param": "File Type", "status": "PASS", "expected": expected_specs["File Type"], "actual": actual["File Type"]})
    else:
        report_items.append({"param": "File Type", "status": "FAIL", "expected": expected_specs["File Type"], "actual": actual["File Type"]})

    # 2. Codec (partial match)
    if expected_specs["Video Codec"].lower() in actual["Video Codec"].lower():
         report_items.append({"param": "Video Codec", "status": "PASS", "expected": expected_specs["Video Codec"], "actual": actual["Video Codec"]})
    else:
         report_items.append({"param": "Video Codec", "status": "FAIL", "expected": expected_specs["Video Codec"], "actual": actual["Video Codec"]})

    # 3. Resolution
    if expected_specs["Resolution"] == actual["Resolution"]:
        report_items.append({"param": "Resolution", "status": "PASS", "expected": expected_specs["Resolution"], "actual": actual["Resolution"]})
    else:
        report_items.append({"param": "Resolution", "status": "FAIL", "expected": expected_specs["Resolution"], "actual": actual["Resolution"]})

    # 4. Frame Rate (approx check)
    exp_fps = float(expected_specs["Frame rate"])
    act_fps = fps_val
    if abs(exp_fps - act_fps) < 0.01:
        report_items.append({"param": "Frame rate", "status": "PASS", "expected": expected_specs["Frame rate"], "actual": actual["Frame rate"]})
    else:
        report_items.append({"param": "Frame rate", "status": "FAIL", "expected": expected_specs["Frame rate"], "actual": actual["Frame rate"]})

    # 5. Duration (Strict Frame-Based Check)
    if expected_specs.get("Duration_Check") is False:
        report_items.append({"param": "Duration", "status": "INFO", "expected": "No target duration", "actual": actual["Duration"]})
    elif expected_specs["Duration_Tag"] is not None and fps_val > 0:
        target_sec_tag = expected_specs["Duration_Tag"]
        
        # Determine Base FPS for calculation
        if 23.0 < fps_val < 24.5: base_fps = 24
        elif 29.0 < fps_val < 30.5: base_fps = 30
        elif 59.0 < fps_val < 60.5: base_fps = 60
        elif 24.5 < fps_val < 25.5: base_fps = 25
        elif 49.0 < fps_val < 50.5: base_fps = 50
        else: base_fps = int(round(fps_val))

        # Expected Frames (e.g. 30s * 24fps = 720 frames)
        expected_total_frames = target_sec_tag * base_fps
        expected_timecode = seconds_to_timecode(target_sec_tag * (base_fps / fps_val) if base_fps != fps_val else target_sec_tag, fps_val)
        
        # For non-integer FPS (23.976), 30 "units" implies 00:00:30:00, which is calculated as expected_total_frames = 30 * 24
        # Just use strict frame count comparison
        actual_total_frames = int(round(duration_sec * fps_val))
        
        expected_display = f"{target_sec_tag}s ({expected_timecode})"
        # Update expected in actual dictionary for display if needed, but we pass it directly to report
        
        if abs(expected_total_frames - actual_total_frames) <= 1: # Allow max 1 frame slack? User said strict.
             # User said "29.99 is not 30". 29.99s @ 23.98 = 719fr. 30s = 720fr.
             # Diff is 1 frame. If user failed 29.99, then tolerance must be 0?
             # Let's try Tolerance 0 (Exact match) for "00:00:30:00"
             pass_duration = abs(expected_total_frames - actual_total_frames) == 0
        else:
             pass_duration = False
             
        # Re-eval tolerance. 
        # If I have 15.02s in the actual output from previous step.
        # 15s * 24 = 360 frames.
        # 15.02s * 23.976 = 360.11 frames -> 360 frames.
        # So 15.02s IS exactly 360 frames (15s spot).
        # So rounding handles the float drift.
        
        if expected_total_frames == actual_total_frames:
            report_items.append({"param": "Duration", "status": "PASS", "expected": expected_display, "actual": actual["Duration"]})
        else:
             report_items.append({"param": "Duration", "status": "FAIL", "expected": expected_display, "actual": actual["Duration"]})
    else:
        # Fallback if FPS is 0 or Duration unknown
        report_items.append({"param": "Duration", "status": "FAIL", "expected": expected_specs["Duration"], "actual": actual["Duration"]})

    # 6. Bitrate (MP4 only)
    if expected_specs["File Type"] == "MP4":
        target_br = 75.0 if "75" in expected_specs["Total bitrate"] else 25.0
        if abs(target_br - actual["Bitrate_Mbps"]) <= BITRATE_TOLERANCE:
            report_items.append({"param": "Total bitrate", "status": "PASS", "expected": expected_specs["Total bitrate"], "actual": actual["Total bitrate"]})
        else:
            report_items.append({"param": "Total bitrate", "status": "FAIL", "expected": expected_specs["Total bitrate"], "actual": actual["Total bitrate"]})

    # 7. Color Space
    if expected_specs["Color Space"] == actual["Color Space"]:
        report_items.append({"param": "Color Space", "status": "PASS", "expected": expected_specs["Color Space"], "actual": actual["Color Space"]})
    else:
        report_items.append({"param": "Color Space", "status": "FAIL", "expected": expected_specs["Color Space"], "actual": actual["Color Space"]})
    
    # 8. Audio Codec
    if expected_specs["Audio Codec"].lower() in actual["Audio Codec"].lower():
        report_items.append({"param": "Audio Codec", "status": "PASS", "expected": expected_specs["Audio Codec"], "actual": actual["Audio Codec"]})
    else:
        report_items.append({"param": "Audio Codec", "status": "FAIL", "expected": expected_specs["Audio Codec"], "actual": actual["Audio Codec"]})

    # 9. Channels
    if expected_specs["Channels"] == actual["Channels"]:
        report_items.append({"param": "Channels", "status": "PASS", "expected": expected_specs["Channels"], "actual": actual["Channels"]})
    else:
         report_items.append({"param": "Channels", "status": "FAIL", "expected": expected_specs["Channels"], "actual": actual["Channels"]})

    # 10. Sample Rate
    if expected_specs["Sample Rate"] == actual["Sample Rate"]:
        report_items.append({"param": "Sample Rate", "status": "PASS", "expected": expected_specs["Sample Rate"], "actual": actual["Sample Rate"]})
    else:
        report_items.append({"param": "Sample Rate", "status": "FAIL", "expected": expected_specs["Sample Rate"], "actual": actual["Sample Rate"]})

    # 11. Loudness
    if actual["Loudness_Val"] is not None:
        target_loudness = -14.0 if "14" in expected_specs["Loudness"] else -24.0
        if abs(target_loudness - actual["Loudness_Val"]) <= LOUDNESS_TOLERANCE:
             report_items.append({"param": "Loudness", "status": "PASS", "expected": expected_specs["Loudness"], "actual": actual["Loudness"]})
        else:
             report_items.append({"param": "Loudness", "status": "FAIL", "expected": expected_specs["Loudness"], "actual": actual["Loudness"]})
    else:
        report_items.append({"param": "Loudness", "status": "FAIL", "expected": expected_specs["Loudness"], "actual": "Error"})

    return report_items


def generate_specifications_md(all_expected):
    """
    Generates specifications.md with profiles.
    """
    content = "# Video QC Specifications Profiles\n\n"
    content += "This file contains the expected specifications for the files found in the directory.\n\n"
    
    for filename, specs in all_expected.items():
        content += f"## Profile for: `{filename}`\n\n"
        for key, value in specs.items():
            if key in ["Duration_Sec", "Duration_Tag", "Duration_Check"]: continue # Skip internal values
            if key == "Total bitrate" and value is None: continue
            content += f"- [ ] {key}: {value}\n"
        content += "\n"
        
    return content

def generate_qc_report_md(all_results):
    """
    Generates the final QC Combined Report.
    """
    content = "# Technical QC Report\n\n"
    
    total_files = len(all_results)
    passed_files = 0
    
    # Pre-calculate overall stats
    for filename, items in all_results.items():
        if isinstance(items, list):
            if all(i['status'] != 'FAIL' for i in items):
                passed_files += 1
        # Else it's an error dict, counts as fail
            
    content += f"**Processed:** {total_files} Files | **Passed:** {passed_files} | **Failed:** {total_files - passed_files}\n\n"
    content += "---\n\n"
    
    for filename, items in all_results.items():
        if isinstance(items, dict) and "error" in items:
             # Handle error case
             content += f"### 🔴 FAIL : `{filename}`\n\n"
             content += f"**Error: {items['error']}**\n\n"
             continue

        # Check overall status
        failed_items = [i for i in items if i['status'] == 'FAIL']
        is_pass = len(failed_items) == 0
        status_icon = "🟢 PASS" if is_pass else "🔴 FAIL"
        
        
        content += f"### {status_icon} : `{filename}`\n\n"
        
        if is_pass:
            content += "**All checks passed.**\n\n"
            
        content += "| Parameter | Expected | Actual | Status |\n"
        content += "| :--- | :--- | :--- | :--- |\n"
        for item in items:
            if item['status'] == "PASS":
                icon = "✅"
            elif item['status'] == "FAIL":
                icon = "❌"
            else:
                icon = "INFO"
            content += f"| {item['param']} | {item['expected']} | {item['actual']} | {icon} |\n"
        
        content += "\n"
        
    return content

def list_video_files(target_dir):
    """Return sorted .mp4/.mov filenames in target_dir."""
    return sorted(
        f for f in os.listdir(target_dir)
        if f.lower().endswith((".mp4", ".mov"))
    )


def write_reports(target_dir, spec_content, report_content, log=lambda *_: None):
    """
    Write specifications.md and QC_Report.md into target_dir.

    Centralises report file creation here so it has a single owner: the CLI
    writes via run_qc(write_files=True), and the GUI calls this only on an
    explicit "Export report" action (never automatically).

    Returns (spec_path, report_path).
    """
    spec_path = os.path.join(target_dir, "specifications.md")
    report_path = os.path.join(target_dir, "QC_Report.md")
    log(f"Generating {spec_path}...")
    with open(spec_path, "w", encoding="utf-8") as fh:
        fh.write(spec_content)
    log(f"Generating {report_path}...")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_content)
    return spec_path, report_path


def run_qc(target_dir, log=print, progress=None, write_files=True):
    """
    Run the full QC pass over a directory. Reusable by the CLI and the GUI.

    Args:
        target_dir: folder to scan for .mp4/.mov files.
        log: callable for human-readable progress lines.
        progress: optional callable(done, total, current_filename) for UIs
            that want to drive a progress bar.
        write_files: when True, also write specifications.md and QC_Report.md
            into target_dir (CLI behaviour). The GUI sets this too so reports
            are saved alongside the videos, but uses the returned data to render.

    Returns a dict with: all_expected, all_results, spec_content, report_content,
    spec_path, report_path, skipped (list of filenames that did not match the
    naming convention).

    Raises ToolNotFoundError if ffmpeg/ffprobe are missing, and
    FileNotFoundError if target_dir does not exist.
    """
    require_tools()

    if not os.path.isdir(target_dir):
        raise FileNotFoundError(f"Directory not found: {target_dir}")

    log(f"Scanning directory: {target_dir}")
    files = list_video_files(target_dir)
    if not files:
        log("No .mp4 or .mov files found.")

    all_expected = {}
    all_results = {}
    skipped = []
    total = len(files)

    for index, f in enumerate(files):
        filepath = os.path.join(target_dir, f)
        log(f"Processing: {f}")
        if progress:
            progress(index, total, f)

        tags = parse_filename(f)
        if not tags:
            log(f"Skipping {f} - Does not match naming convention.")
            skipped.append(f)
            continue

        expected = get_expected_specs(tags)
        all_expected[f] = expected

        results = analyze_file(filepath, expected, log=log)
        all_results[f] = results

    if progress:
        progress(total, total, None)

    spec_content = generate_specifications_md(all_expected)
    report_content = generate_qc_report_md(all_results)

    spec_path = os.path.join(target_dir, "specifications.md")
    report_path = os.path.join(target_dir, "QC_Report.md")

    if write_files:
        write_reports(target_dir, spec_content, report_content, log=log)

    return {
        "all_expected": all_expected,
        "all_results": all_results,
        "spec_content": spec_content,
        "report_content": report_content,
        "spec_path": spec_path,
        "report_path": report_path,
        "skipped": skipped,
    }


def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    try:
        run_qc(target_dir, log=print)
    except ToolNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    print("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
