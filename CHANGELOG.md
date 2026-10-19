# Changelog

All notable changes to **VidShrink** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-18

### Added
- **Multi-Vendor GPU Acceleration**: Auto-detection for NVIDIA NVENC, Intel QuickSync (QSV), AMD AMF, and Apple VideoToolbox with automatic CPU fallback.
- **Target File Size Mode**: Instant presets for Discord (25 MB), Telegram (50 MB), and Web / Email (10 MB) with automatic bitrate calculation.
- **Orientation-Aware Downscaling**: Intelligently handles portrait (vertical smartphone) and landscape videos without aspect distortion.
- **Click-to-Open**: Click or double-click completed queue items to directly open the compressed video in your default media player.
- **Keyboard Shortcuts**: Added `Ctrl+O` (Open files), `Space`/`Enter` (Start/Stop), and `Esc` (Cancel/Close).
- **Smart Queue Clear**: Automatically clears completed/failed items first before clearing pending items.
- **Persian Typography Support**: Enhanced fallback font stack with Vazirmatn and Tahoma.
- **Cross-Platform CI & Security**: Multi-OS automated pytest testing on GitHub Actions, SHA-256 release checksum generation, and PEP 621 packaging (`pyproject.toml`).

### Fixed
- **Output Preservation Bug**: Fixed bug where valid conversions (downscaling or audio removal) were erroneously deleted if the output size was within 2% of the input.
- **Queue Hit-Testing**: Fixed coordinate translation mismatch in QueueItem remove button and badge hover triggers.
- **Progress & ETA Parsing**: Overhauled FFmpeg progress parsing with multi-format time parser (`out_time` and `out_time_us`), eliminating 100% progress jumps on unknown durations.
- **Process Cleanup**: Added resilient cleanup and process termination to prevent zombie FFmpeg background instances and file permission locks on Windows.
- **Cover Art Rejection**: Audio files with embedded album artwork (`[attached pic]`) are now properly ignored instead of falsely treated as video streams.

---

## [1.0.0] - 2026-10-17

- Initial release of VidShrink with PySide6 neon glowing GUI, CRF presets, and bundled FFmpeg.
