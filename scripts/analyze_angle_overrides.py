"""TEMPLATE: post-mortem on the multi-angle autocrop selection for one game.

Use case
--------
After running the multi-angle autocrop pipeline (calibrate -> analyze ->
select -> review -> encode) for a game, point this script at the resulting
angle_manifest.csv. It compares the default rule's auto-picks against the
user's reviewed selection and reports:

  * Overall agreement rate and the direction of disagreement (wide vs zoom).
  * For non-kick clips, a threshold sweep showing which `motion_bottom_frac`
    cutoff would have maximised agreement.
  * For kick clips, how often the "always wide for kicks" rule was wrong
    and the metrics of the overridden kicks.

Run after each game and accumulate the findings before changing the default
rule in autocrop._default_angle_rule (see memory: project-angle-rule-tuning).

How to use
----------
Set the constants in the CONFIGURE block below to point at the game's
manifest and which folder name is wide vs zoom for this setup, then run.

First applied: W07 Pirates (2026-05-24, 66 clips, 77% auto agreement).
"""

import csv
import os
import re
from collections import Counter

# ----- CONFIGURE ------------------------------------------------------------
MANIFEST = r"E:\Invaders\W07 Pirates\angle_manifest.csv"
WIDE = "EZN"   # the folder name of the wider angle (rule's first preference)
ZOOM = "EZF"   # the folder name of the zoomed/tighter angle
KICK_RE = re.compile(r"_K_Kick", re.IGNORECASE)  # filename pattern for kicks
THRESHOLD = 0.25  # current default in autocrop._default_angle_rule
# ----- END CONFIGURE --------------------------------------------------------


def auto_choice(row):
    """Re-derive what the default rule would have picked, ignoring `chosen_angle`."""
    if KICK_RE.search(row["clip"]):
        return WIDE, "kick -> wide"
    try:
        mb = float(row[f"{WIDE}_motion_bottom_frac"] or 0.5)
    except ValueError:
        mb = 0.5
    if mb >= THRESHOLD:
        return WIDE, f"near (mb={mb:.2f})"
    return ZOOM, f"far (mb={mb:.2f})"


def main():
    with open(MANIFEST, newline="") as f:
        rows = list(csv.DictReader(f))

    overrides = []
    kept = 0
    direction = Counter()

    for row in rows:
        auto, _ = auto_choice(row)
        chosen = row["chosen_angle"]
        if chosen == auto:
            kept += 1
        else:
            direction[f"{auto}->{chosen}"] += 1
            overrides.append((row, auto, chosen))

    n = len(rows)
    print(f"Total clips: {n}")
    print(f"Kept auto choice: {kept} ({100*kept/n:.0f}%)")
    print(f"Overrides: {n - kept} ({100*(n-kept)/n:.0f}%)")
    for d, c in direction.most_common():
        print(f"  {d}: {c}")

    print("\n--- Per-override detail ---")
    print(f"{'clip':<28} {'auto':<6} {'chosen':<6} "
          f"{'wide_mb':>8} {'wide_centroid':>14} {'wide_area':>10}  kick?")
    for row, auto, chosen in overrides:
        is_kick = bool(KICK_RE.search(row["clip"]))
        mb = row[f"{WIDE}_motion_bottom_frac"]
        cy = row[f"{WIDE}_centroid_y_frac"]
        ar = row[f"{WIDE}_motion_area_frac"]
        print(f"{row['clip']:<28} {auto:<6} {chosen:<6} "
              f"{mb:>8} {cy:>14} {ar:>10}  {is_kick}")

    print("\n--- Threshold-sweep on the non-kick rule ---")
    # For each candidate threshold, count how many non-kick clips' auto-picks
    # would match the user's chosen angle.
    non_kick = [r for r in rows if not KICK_RE.search(r["clip"])]
    candidates = [round(0.05 * i, 2) for i in range(1, 11)]  # 0.05..0.50
    best = (None, -1)
    for th in candidates:
        agree = 0
        for r in non_kick:
            try:
                mb = float(r[f"{WIDE}_motion_bottom_frac"] or 0.5)
            except ValueError:
                mb = 0.5
            picked = WIDE if mb >= th else ZOOM
            if picked == r["chosen_angle"]:
                agree += 1
        pct = 100 * agree / len(non_kick)
        marker = ""
        if agree > best[1]:
            best = (th, agree)
            marker = "  <-- best so far"
        if abs(th - THRESHOLD) < 1e-6:
            marker += "  (current default)"
        print(f"  threshold={th:.2f}  agree {agree}/{len(non_kick)} ({pct:.0f}%){marker}")

    print(f"\nBest non-kick threshold: {best[0]} ({best[1]}/{len(non_kick)} agree)")

    kicks = [r for r in rows if KICK_RE.search(r["clip"])]
    kick_to_wide = sum(1 for r in kicks if r["chosen_angle"] == WIDE)
    print(f"\nKick plays: {len(kicks)}, user kept wide on {kick_to_wide}; "
          f"overrode {len(kicks)-kick_to_wide} to {ZOOM}")
    if len(kicks) - kick_to_wide:
        print("  Overridden kicks:")
        for r in kicks:
            if r["chosen_angle"] != WIDE:
                print(f"    {r['clip']}  "
                      f"wide_mb={r[f'{WIDE}_motion_bottom_frac']}  "
                      f"wide_area={r[f'{WIDE}_motion_area_frac']}")


if __name__ == "__main__":
    main()
