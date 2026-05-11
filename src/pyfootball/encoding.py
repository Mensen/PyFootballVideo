"""
Shared FFmpeg encoding settings.

All re-encode paths (clip extraction, full-file recode, autocrop output)
share these args so they stay aligned: any tweak here propagates to every
caller instead of drifting across three copies.
"""

# All-intra H.264: every frame is a keyframe (-g 1) so downstream analysis
# tools can scrub frame-by-frame without decoding backward through a GOP.
# Trade-off: file size is ~3-5x larger than a typical keyint=15 encode.
SCRUB_FRIENDLY_VIDEO_ARGS = [
    "-c:v", "libx264",
    "-preset", "veryfast",
    "-g", "1",
    "-keyint_min", "1",
    "-sc_threshold", "0",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
]
