"""Time motion detection on a small sample from each angle."""

import logging
import os
import shutil
import tempfile
import time

from pyfootball.autocrop import (
    _analyze_one,
    analyze_clips_folder,
    load_calibration,
    make_field_mask,
)

logging.basicConfig(level=logging.WARNING)

BASE = r"E:\Invaders\W06 Glarus"
SAMPLES = 5
ANGLES = ["EZN", "EZF"]


def time_angle(angle):
    clips_folder = os.path.join(BASE, angle)
    calibration  = os.path.join(BASE, angle, "field_calibration.json")

    polygon, cw, ch = load_calibration(calibration)
    mask = make_field_mask(polygon, cw, ch)

    clips = sorted(f for f in os.listdir(clips_folder)
                   if f.lower().endswith(".mp4"))[:SAMPLES]

    print(f"\n=== {angle} ({cw}x{ch}, {len(clips)} clips) ===")
    total = 0.0
    for name in clips:
        path = os.path.join(clips_folder, name)
        size_mb = os.path.getsize(path) / 1024 / 1024
        t0 = time.perf_counter()
        result = _analyze_one(path, mask, polygon, cw, ch,
                              sample_interval=15, padding=0.15)
        dt = time.perf_counter() - t0
        total += dt
        status = "ok" if result else "no motion"
        print(f"  {name:32s}  {size_mb:6.1f} MB   {dt:6.2f}s   {status}")
    print(f"  -- total: {total:.2f}s, avg: {total/len(clips):.2f}s/clip")
    return total, len(clips)


def time_parallel(workers):
    angle = "EZN"
    clips_folder = os.path.join(BASE, angle)
    calibration  = os.path.join(BASE, angle, "field_calibration.json")
    clips = sorted(f for f in os.listdir(clips_folder)
                   if f.lower().endswith(".mp4"))[:SAMPLES * 2]

    with tempfile.TemporaryDirectory(dir=BASE) as tmp:
        sample_folder = os.path.join(tmp, "sample")
        os.makedirs(sample_folder)
        for c in clips:
            os.link(os.path.join(clips_folder, c), os.path.join(sample_folder, c))

        out = os.path.join(tmp, "analysis")
        t0 = time.perf_counter()
        analyze_clips_folder(
            clips_folder=sample_folder,
            calibration_path=calibration,
            output_folder=out,
            save_heatmaps=False,
            workers=workers,
        )
        dt = time.perf_counter() - t0

    print(f"  workers={workers}: {dt:.2f}s for {len(clips)} clips "
          f"({dt/len(clips):.2f}s/clip wall)")
    return dt, len(clips)


def main():
    grand_total = 0.0
    grand_count = 0
    for a in ANGLES:
        t, n = time_angle(a)
        grand_total += t
        grand_count += n

    avg = grand_total / grand_count
    full_count = 132 * 2  # both angles
    print(f"\nOverall avg (sequential, _analyze_one): {avg:.2f}s/clip")
    print(f"Projected sequential full run ({full_count} clips): "
          f"{avg * full_count:.1f}s = {avg * full_count / 60:.1f} min")

    print(f"\n=== process-pool sweep on {SAMPLES*2} EZN clips ===")
    seq_t, n = time_parallel(1)
    best = (seq_t, 1)
    for w in (2, 4, 8, 16, os.cpu_count() or 4):
        t, _ = time_parallel(w)
        if t < best[0]:
            best = (t, w)
    par_t, par_w = best
    print(f"\n  best: workers={par_w}  ({seq_t/par_t:.2f}x vs sequential)")
    par_avg = par_t / n
    print(f"  Projected parallel full run ({full_count} clips): "
          f"{par_avg * full_count:.1f}s = {par_avg * full_count / 60:.1f} min")


if __name__ == "__main__":
    main()
