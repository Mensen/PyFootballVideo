"""
Shared FFmpeg encoding presets.

Each preset is a list of FFmpeg args trading off file size, encode speed,
and seek precision differently. Callers pick a preset by name through
`get_encoding_args(preset)`; passing None falls back to DEFAULT_PRESET.

Add a new preset here instead of mutating an existing one — every preset
has callers that may rely on its current behavior.
"""

ENCODING_PRESETS = {
    # Every frame a keyframe. Frame-by-frame scrubbing in any analysis tool
    # without decoding through a GOP. ~3-5x larger than short_gop and slower
    # to encode. Use when single-frame stepping is mandatory.
    "all_intra": [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-g", "1",
        "-keyint_min", "1",
        "-sc_threshold", "0",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
    ],
    # Keyframe every 15 frames (~0.5s at 30fps). Near-instant seek in any
    # player without all-intra's bloat. Good balance for typical analysis
    # workflows that scrub but don't single-step.
    "short_gop": [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-g", "15",
        "-keyint_min", "15",
        "-sc_threshold", "0",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
    ],
    # Codec default GOP (~250 frames) with a slightly looser CRF. Smallest
    # files, fastest encode. Seeks jump to the nearest keyframe (a few
    # seconds away). Fine for playback-only / share-only outputs.
    "standard": [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
    ],
}

DEFAULT_PRESET = "short_gop"


def get_encoding_args(preset=None):
    """Return a fresh FFmpeg arg list for a named preset.

    Args:
        preset: Preset name from ENCODING_PRESETS, or None for DEFAULT_PRESET.

    Returns:
        New list copy of the preset's args (safe to mutate).
    """
    name = preset or DEFAULT_PRESET
    if name not in ENCODING_PRESETS:
        raise ValueError(
            f"Unknown encoding preset {name!r}. "
            f"Available: {sorted(ENCODING_PRESETS)}"
        )
    return list(ENCODING_PRESETS[name])


# Back-compat alias for code that imported the constant directly. Kept at
# the original all_intra behavior so external imports don't silently switch.
# New code should call get_encoding_args() with an explicit preset.
SCRUB_FRIENDLY_VIDEO_ARGS = ENCODING_PRESETS["all_intra"]
