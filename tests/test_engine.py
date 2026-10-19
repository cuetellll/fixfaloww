import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vidshrink.engine import (  # noqa: E402
    Job, Options, VideoInfo, build_cmd, calc_target_bitrate,
    fmt_time, human_size, parse_time_str, probe
)
from vidshrink import i18n  # noqa: E402
from vidshrink.theme import clamp, mix, rgba  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402


def _job(h=1080, w=1920, dur=60.0):
    return Job(0, "in.mkv", "out.mp4", VideoInfo(size=50_000_000, duration=dur, width=w, height=h))


# --------------------------------------------------------------------------- formatting & helpers
def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(512) == "512 B"
    assert human_size(1024) == "1.0 KB"
    assert human_size(1536) == "1.5 KB"
    assert human_size(10 * 1024 * 1024) == "10.0 MB"
    assert human_size(5 * 1024 ** 3) == "5.0 GB"
    assert human_size(2 * 1024 ** 4) == "2.0 TB"


def test_fmt_time():
    assert fmt_time(0) == "00:00"
    assert fmt_time(59) == "00:59"
    assert fmt_time(75) == "01:15"
    assert fmt_time(3600) == "1:00:00"
    assert fmt_time(3661) == "1:01:01"


def test_parse_time_str():
    assert parse_time_str("00:01:23.456") == 83.456
    assert parse_time_str("01:00:00.00") == 3600.0
    assert parse_time_str("02:30") == 150.0
    assert parse_time_str("45.5") == 45.5
    assert parse_time_str("N/A") == 0.0
    assert parse_time_str("") == 0.0
    assert parse_time_str("invalid") == 0.0


def test_calc_target_bitrate():
    # 25 MB Discord limit for 60-second video with 64kbps audio
    # 25 * 8 * 1024 * 1024 * 0.95 = 199,229,440 bits
    # 199,229,440 / 60 / 1000 = ~3320 kbps total - 64 audio = ~3256 kbps video
    v_br = calc_target_bitrate(duration=60.0, target_mb=25.0, audio_kbps=64)
    assert 3000 <= v_br <= 3500

    # Zero or invalid duration fallback
    assert calc_target_bitrate(duration=0.0, target_mb=25.0) == 1000


# --------------------------------------------------------------------------- command builder
def test_h265_cpu_defaults():
    cmd = build_cmd("ffmpeg", _job(), Options(preset=1, codec=0), use_gpu=False)
    assert "libx265" in cmd
    assert "hvc1" in cmd
    assert "27" in cmd
    assert cmd[-1] == "out.mp4"


def test_h264_cpu_defaults():
    cmd = build_cmd("ffmpeg", _job(), Options(preset=1, codec=1), use_gpu=False)
    assert "libx264" in cmd
    assert "23" in cmd
    assert "-tag:v" not in cmd


def test_target_size_command():
    cmd = build_cmd("ffmpeg", _job(dur=60.0), Options(target_mb=25.0, codec=0), use_gpu=False)
    assert "libx265" in cmd
    assert "-b:v" in cmd
    assert "-maxrate" in cmd
    assert "-bufsize" in cmd


def test_downscale_landscape():
    big = build_cmd("ffmpeg", _job(h=1080, w=1920), Options(res=2), False)    # target 720p
    small = build_cmd("ffmpeg", _job(h=480, w=854), Options(res=2), False)
    assert any("scale=-2:720" in c for c in big)
    assert not any("scale=" in c for c in small)


def test_downscale_portrait():
    # Vertical video (e.g. 1080x1920 from phone), target 720p: width should be scaled to 720
    portrait = build_cmd("ffmpeg", _job(h=1920, w=1080), Options(res=2), False)
    assert any("scale=720:-2" in c for c in portrait)


def test_mute_and_gpu_nvenc():
    cmd = build_cmd("ffmpeg", _job(), Options(codec=1, gpu=True, mute=True, hw_vendor="nvenc"), use_gpu=True)
    assert "h264_nvenc" in cmd
    assert "-an" in cmd
    assert "aac" not in cmd


def test_gpu_qsv_and_amf():
    qsv_cmd = build_cmd("ffmpeg", _job(), Options(codec=0, gpu=True, hw_vendor="qsv"), use_gpu=True)
    assert "hevc_qsv" in qsv_cmd
    assert "-global_quality" in qsv_cmd

    amf_cmd = build_cmd("ffmpeg", _job(), Options(codec=0, gpu=True, hw_vendor="amf"), use_gpu=True)
    assert "hevc_amf" in amf_cmd
    assert "-rc" in amf_cmd


# --------------------------------------------------------------------------- i18n completeness
def test_i18n_key_parity():
    en_keys = set(i18n.STR["en"].keys())
    fa_keys = set(i18n.STR["fa"].keys())
    missing_in_fa = en_keys - fa_keys
    missing_in_en = fa_keys - en_keys
    assert not missing_in_fa, f"Missing Persian keys: {missing_in_fa}"
    assert not missing_in_en, f"Missing English keys: {missing_in_en}"


def test_i18n_formatting():
    i18n.set_lang("en")
    assert "100 MB freed" in i18n.tr("saved_sub", size="100 MB")
    i18n.set_lang("fa")
    assert "100 MB آزاد شد" in i18n.tr("saved_sub", size="100 MB")


# --------------------------------------------------------------------------- theme helpers
def test_theme_mix_and_clamp():
    assert clamp(-0.5) == 0.0
    assert clamp(1.5) == 1.0
    assert clamp(0.5) == 0.5

    c1 = QColor(0, 0, 0)
    c2 = QColor(100, 100, 100)
    mixed = mix(c1, c2, 0.5)
    assert mixed.red() == 50

    q = rgba(c2, 0.5)
    assert abs(q.alphaF() - 0.5) < 1e-4
