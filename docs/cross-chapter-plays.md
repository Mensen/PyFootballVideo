# Cross-chapter plays (GoPro series)

## The problem

When splitting a GoPro series with `series_input_mode='dartclip'`, each chapter is
processed independently — `ffmpeg -i <chapter> -ss ... -t ... -c:v copy`. If a
play starts near the end of a chapter and runs longer than the remaining footage,
ffmpeg hits EOF and the clip is silently truncated.

Example: chapter is 320.32s long, play marker is at 316.48s with a 10s duration.
The clip will be ~3.84s instead of ~10.5s. No error is raised.

## Detection

After a series split, scan for clips whose actual duration is much shorter than
the dartclip's `Duration`. A simple ffprobe loop over the output folder works.

You can also pre-flight by reading each `.dartclip` and comparing
`Position + Duration` against the chapter's duration via ffprobe.

## Fix: re-cut the play across both chapters

Use ffmpeg's concat demuxer over the two relevant chapters and seek to the
play's local position within the first chapter. With concat demuxer, `-ss`
must go **after** `-i` so seeking is accurate across the segment boundary.

```bash
# concat_list.txt
file 'H:/path/GX17xxxx.MP4'
file 'H:/path/GX18xxxx.MP4'
```

```bash
ffmpeg -y -f concat -safe 0 -i concat_list.txt \
       -ss <local_pos_in_first_chapter_s> -t <duration_s + buffer> \
       -c:v copy -an \
       <output>/Play_NNN_<naming>.mp4
```

Same session = identical codec params, so `-c:v copy` works without re-encoding.

### Finding the local position

The local position is just the `Position` field of the play's event in the
first chapter's dartclip (in milliseconds, divide by 1000 for ffmpeg's `-ss`).

```python
from pyfootball.splitter import VideoSplitter
vs = VideoSplitter()
parsed = vs.parse_dartclip('GX17xxxx.MP4.dartclip')
event = next(e for e in parsed['events'] if 'Play (75)' in e.get('Name', ''))
local_pos_s = float(event['Position']) / 1000
duration_s = float(event['Duration']) / 1000 + 0.5  # buffer
```

## Note on `csv_absolute` mode

In principle, `csv_absolute` series mode could avoid this problem entirely by
feeding all chapters through the concat demuxer as one continuous timeline.
**This path has not been validated for production use** — there were issues
when previously attempted (possibly performance, possibly something else; not
re-tested). Test it on a full game before relying on it; until then, prefer
`dartclip` mode + post-split fix for any boundary-spanning plays.
