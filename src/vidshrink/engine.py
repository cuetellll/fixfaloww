"""FFmpeg engine: locating ffmpeg, hardware encoders, probing videos and compressing them."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

VIDEO_EXTS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv", ".flv",
    ".ts", ".mts", ".m2ts", ".3gp", ".mpg", ".mpeg", ".ogv", ".vob",
}

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_BELOW_NORMAL = 0x00004000 if os.name == "nt" else 0   # keep the UI & the PC responsive while encoding

# Hardware encoder cache: (ffmpeg_path) -> (vendor_key, label)
_HW_ENCODER_CACHE: dict[str, tuple[str, str]] = {}


# --------------------------------------------------------------------------- helpers
def human_size(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_time(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_time_str(time_str: str) -> float:
    """Parse FFmpeg time string (HH:MM:SS.micro or S+.micro) into seconds."""
    time_str = time_str.strip()
    if not time_str or time_str.upper() == "N/A":
        return 0.0
    try:
        if ":" in time_str:
            parts = time_str.split(":")
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        return float(time_str)
    except (ValueError, IndexError):
        return 0.0


def find_ffmpeg() -> Optional[str]:
    """Priority: next to the exe -> bundled (PyInstaller) -> imageio-ffmpeg -> PATH."""
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    candidates = [
        Path(getattr(sys, "_MEIPASS", "")) / name if hasattr(sys, "_MEIPASS") else None,
        Path(sys.executable).resolve().parent / name,
        Path(__file__).resolve().parent / name,
        Path.cwd() / name,
    ]
    for c in candidates:
        if c and c.exists():
            return str(c)
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    return shutil.which("ffmpeg")


def detect_hardware_encoder(ffmpeg: str) -> tuple[str, str]:
    """Detect available hardware encoders from FFmpeg.

    Returns: (vendor_id, display_label)
        vendor_id is one of: 'nvenc', 'qsv', 'amf', 'videotoolbox', or '' (CPU only)
    """
    if not ffmpeg:
        return "", "CPU"
    if ffmpeg in _HW_ENCODER_CACHE:
        return _HW_ENCODER_CACHE[ffmpeg]

    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=_NO_WINDOW, timeout=10,
        )
        out = proc.stdout or ""
    except Exception:
        return "", "CPU"

    # Priority order: NVIDIA NVENC -> Intel QuickSync -> AMD AMF -> Apple VideoToolbox
    if "hevc_nvenc" in out or "h264_nvenc" in out:
        res = ("nvenc", "NVIDIA NVENC")
    elif "hevc_qsv" in out or "h264_qsv" in out:
        res = ("qsv", "Intel QuickSync")
    elif "hevc_amf" in out or "h264_amf" in out:
        res = ("amf", "AMD AMF")
    elif "hevc_videotoolbox" in out or "h264_videotoolbox" in out:
        res = ("videotoolbox", "Apple VideoToolbox")
    else:
        res = ("", "CPU")

    _HW_ENCODER_CACHE[ffmpeg] = res
    return res


# --------------------------------------------------------------------------- probing
@dataclass
class VideoInfo:
    size: int = 0
    duration: float = 0.0
    width: int = 0
    height: int = 0
    codec: str = ""
    rotation: int = 0


_RE_DUR = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_RE_VID = re.compile(r"Video:\s*([\w]+).*?,\s*(\d{2,5})x(\d{2,5})")
_RE_ROT = re.compile(r"(?:rotate\s*:\s*|rotation of\s*)(-?\d+(?:\.\d+)?)")


def probe(ffmpeg: str, path: str) -> Optional[VideoInfo]:
    """Returns VideoInfo or None if the file has no decodable video stream."""
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=_NO_WINDOW, timeout=25,
        )
    except Exception:
        return None
    err = proc.stderr or ""

    # Filter out audio files that only have an embedded album cover [attached pic]
    lines = err.splitlines()
    vid_line = None
    for line in lines:
        if "Video:" in line:
            if "[attached pic]" in line or "mjpeg" in line and "attached pic" in line:
                continue
            vid_line = line
            break
    if not vid_line:
        # Fall back to first Video: match if no separate line found
        v = _RE_VID.search(err)
    else:
        v = _RE_VID.search(vid_line)

    if not v:
        return None

    info = VideoInfo(size=os.path.getsize(path))
    info.codec, info.width, info.height = v.group(1), int(v.group(2)), int(v.group(3))

    d = _RE_DUR.search(err)
    if d:
        info.duration = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))

    rot = _RE_ROT.search(err)
    if rot:
        try:
            r = int(float(rot.group(1))) % 360
            info.rotation = r
            # If rotated 90 or 270 degrees, display width & height are transposed
            if r in (90, 270):
                info.width, info.height = info.height, info.width
        except ValueError:
            pass

    return info


# --------------------------------------------------------------------------- options
RES_TARGETS = [None, 1080, 720, 480]

# (cpu crf h265, cpu crf h264, nvenc cq h265, nvenc cq h264, audio kbps, cpu preset h265, preset h264)
PRESETS = [
    dict(crf265=30, crf264=26, cq265=34, cq264=30, qsv265=32, qsv264=28, amf265=32, amf264=28,
         abr=64, p265="medium", p264="slow"),     # Tiny
    dict(crf265=27, crf264=23, cq265=30, cq264=26, qsv265=28, qsv264=24, amf265=28, amf264=24,
         abr=96, p265="fast", p264="medium"),      # Balanced
    dict(crf265=23, crf264=19, cq265=26, cq264=22, qsv265=24, qsv264=20, amf265=24, amf264=20,
         abr=128, p265="fast", p264="medium"),     # Quality
]


@dataclass
class Options:
    preset: int = 1          # index in PRESETS
    codec: int = 0           # 0 = H.265, 1 = H.264
    res: int = 0             # index in RES_TARGETS
    gpu: bool = False
    mute: bool = False
    hw_vendor: str = ""      # "nvenc", "qsv", "amf", "videotoolbox", or ""
    target_mb: float = 0.0   # 0.0 = CRF mode, >0 = target file size mode in MB


@dataclass
class Job:
    jid: int
    src: str
    dst: str
    info: VideoInfo


def calc_target_bitrate(duration: float, target_mb: float, audio_kbps: int = 96) -> int:
    """Calculate video bitrate in kbps to achieve target_mb with 5% safety margin."""
    if duration <= 0.1 or target_mb <= 0:
        return 1000
    total_bits = target_mb * 8 * 1024 * 1024 * 0.95  # 5% mux overhead
    total_kbps = int((total_bits / duration) / 1000)
    video_kbps = max(64, total_kbps - audio_kbps)
    return video_kbps


def build_cmd(ffmpeg: str, job: Job, o: Options, use_gpu: bool) -> list[str]:
    P = PRESETS[o.preset]
    h265 = o.codec == 0
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
           "-i", job.src, "-map", "0:v:0", "-map", "0:a?", "-sn", "-dn"]

    # Resolution downscaling (respecting orientation)
    vf = []
    target = RES_TARGETS[o.res]
    if target:
        if job.info.width >= job.info.height:
            # Landscape or square: scale height
            if job.info.height > target:
                vf.append(f"scale=-2:{target},setsar=1")
        else:
            # Portrait: scale width
            if job.info.width > target:
                vf.append(f"scale={target}:-2,setsar=1")
    vf.append("format=yuv420p")
    cmd += ["-vf", ",".join(vf)]

    vendor = o.hw_vendor or "nvenc"
    abr = 0 if o.mute else P["abr"]
    target_mode = o.target_mb > 0.0 and job.info.duration > 0.5
    v_kbps = calc_target_bitrate(job.info.duration, o.target_mb, abr) if target_mode else 0

    if use_gpu:
        if vendor == "qsv":
            enc = "hevc_qsv" if h265 else "h264_qsv"
            q = P["qsv265"] if h265 else P["qsv264"]
            if target_mode:
                cmd += ["-c:v", enc, "-b:v", f"{v_kbps}k", "-maxrate", f"{int(v_kbps * 1.5)}k"]
            else:
                cmd += ["-c:v", enc, "-global_quality", str(q), "-preset", "medium"]
        elif vendor == "amf":
            enc = "hevc_amf" if h265 else "h264_amf"
            qp = P["amf265"] if h265 else P["amf264"]
            if target_mode:
                cmd += ["-c:v", enc, "-rc", "cbr", "-b:v", f"{v_kbps}k"]
            else:
                cmd += ["-c:v", enc, "-rc", "cqp", "-qp_i", str(qp), "-qp_p", str(qp)]
        elif vendor == "videotoolbox":
            enc = "hevc_videotoolbox" if h265 else "h264_videotoolbox"
            if target_mode:
                cmd += ["-c:v", enc, "-b:v", f"{v_kbps}k"]
            else:
                cmd += ["-c:v", enc, "-q:v", str(65 if o.preset == 0 else 75 if o.preset == 1 else 85)]
        else:
            # Default to NVENC
            enc = "hevc_nvenc" if h265 else "h264_nvenc"
            cq = P["cq265"] if h265 else P["cq264"]
            if target_mode:
                cmd += ["-c:v", enc, "-preset", "p5", "-rc", "vbr", "-b:v", f"{v_kbps}k",
                        "-maxrate", f"{int(v_kbps * 1.5)}k", "-bufsize", f"{v_kbps * 2}k"]
            else:
                cmd += ["-c:v", enc, "-preset", "p5", "-rc", "vbr", "-cq", str(cq), "-b:v", "0",
                        "-spatial-aq", "1"]
    else:
        # Software encoding (CPU)
        if target_mode:
            enc = "libx265" if h265 else "libx264"
            preset = P["p265"] if h265 else P["p264"]
            cmd += ["-c:v", enc, "-preset", preset, "-b:v", f"{v_kbps}k",
                    "-maxrate", f"{int(v_kbps * 1.5)}k", "-bufsize", f"{v_kbps * 2}k"]
            if h265:
                cmd += ["-x265-params", "log-level=error"]
        else:
            if h265:
                cmd += ["-c:v", "libx265", "-preset", P["p265"], "-crf", str(P["crf265"]),
                        "-x265-params", "log-level=error"]
            else:
                cmd += ["-c:v", "libx264", "-preset", P["p264"], "-crf", str(P["crf264"])]

    if h265:
        cmd += ["-tag:v", "hvc1"]  # makes Apple devices and modern players happy

    if o.mute:
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "aac", "-b:a", f"{P['abr']}k"]
        if o.preset == 0:
            cmd += ["-ac", "2"]

    cmd += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", job.dst]
    return cmd


# --------------------------------------------------------------------------- worker
class Worker(QThread):
    started_file = Signal(int)
    progress = Signal(int, float, float, float)   # jid, fraction, speed, eta seconds
    finished_file = Signal(int, str, int, int)    # jid, out_path ("" = kept original), in, out
    failed_file = Signal(int, str)
    gpu_fallback = Signal(int)
    all_done = Signal(bool)                       # cancelled?

    def __init__(self, ffmpeg: str, jobs: list[Job], opts: Options, parent=None):
        super().__init__(parent)
        self.ffmpeg, self.jobs, self.opts = ffmpeg, jobs, opts
        self._cancel = False
        self._proc: Optional[subprocess.Popen] = None

    def cancel(self):
        self._cancel = True
        p = self._proc
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=1.0)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    # ---- main loop
    def run(self):
        for job in self.jobs:
            if self._cancel:
                break
            self.started_file.emit(job.jid)
            ok, msg = self._encode(job, self.opts.gpu)
            if not ok and self.opts.gpu and not self._cancel:
                self.gpu_fallback.emit(job.jid)
                ok, msg = self._encode(job, False)
            if self._cancel:
                self._cleanup(job.dst)
                break
            if not ok:
                self._cleanup(job.dst)
                self.failed_file.emit(job.jid, msg)
                continue
            in_size = job.info.size
            out_size = os.path.getsize(job.dst) if os.path.exists(job.dst) else 0
            if out_size <= 0:
                self.failed_file.emit(job.jid, "empty output")
            # Only discard output if user did NOT explicitly request downscaling, mute, or target size
            elif (out_size >= in_size * 0.98 and
                  self.opts.res == 0 and
                  not self.opts.mute and
                  self.opts.target_mb <= 0):
                # No intentional transformation and no real size reduction -> keep original
                self._cleanup(job.dst)
                self.finished_file.emit(job.jid, "", in_size, in_size)
            else:
                self.finished_file.emit(job.jid, job.dst, in_size, out_size)
        self.all_done.emit(self._cancel)

    def _encode(self, job: Job, use_gpu: bool) -> tuple[bool, str]:
        cmd = build_cmd(self.ffmpeg, job, self.opts, use_gpu)
        tail: deque[str] = deque(maxlen=8)
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=_NO_WINDOW | _BELOW_NORMAL,
            )
        except Exception as e:
            return False, str(e)

        dur = job.info.duration
        has_dur = dur > 0.05
        dur = max(dur, 0.001)
        t0 = time.monotonic()
        speed = 0.0
        cur = 0.0
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.strip()
            if "=" not in line:
                if line:
                    tail.append(line)
                continue
            key, _, val = line.partition("=")
            val = val.strip()

            if key in ("out_time_us", "out_time_ms"):
                try:
                    cur = int(val) / 1_000_000
                except ValueError:
                    continue
            elif key == "out_time":
                # Fallback to standard HH:MM:SS.micro format
                t_val = parse_time_str(val)
                if t_val > 0:
                    cur = t_val
            elif key == "speed":
                # Real-time speed from ffmpeg (e.g. " 1.85x")
                s_str = val.rstrip("x").strip()
                try:
                    speed = float(s_str)
                except ValueError:
                    pass
                continue
            elif key in ("progress", "bitrate", "total_size", "frame", "fps", "stream_0_0_q",
                         "drop_frames", "dup_frames", "elapsed"):
                continue
            else:
                tail.append(line)
                continue

            if cur < 0:
                continue

            elapsed = max(time.monotonic() - t0, 1e-3)
            if speed <= 0.01:
                speed = cur / elapsed

            if has_dur:
                frac = min(max(cur / dur, 0.0), 1.0)
                eta = (dur - cur) / speed if speed > 0.01 else 0.0
            else:
                # Duration was unknown: report elapsed time and zero fraction
                frac = 0.0
                eta = 0.0

            self.progress.emit(job.jid, frac, speed, eta)

        rc = self._proc.wait()
        self._proc = None
        if rc != 0:
            return False, (tail[-1] if tail else f"ffmpeg exited with code {rc}")
        return True, ""

    @staticmethod
    def _cleanup(path: str):
        """Remove file with retry logic to ensure Windows handles are freed."""
        if not path:
            return
        for _ in range(5):
            try:
                if os.path.exists(path):
                    os.remove(path)
                return
            except OSError:
                time.sleep(0.1)
