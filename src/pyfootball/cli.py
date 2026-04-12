"""CLI entry points for PyFootballVideo tools."""

import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def splitter_main():
    """Interactive video splitter."""
    from pyfootball.splitter import VideoSplitter
    from pyfootball.ui.dialogs import select_file, select_folder, select_files

    print("Select operation:")
    print("1. Split video into clips")
    print("2. Create dartclip files for existing clips")
    print("3. Split video and create dartclip files")
    print("4. Advanced configuration")
    print("5. Split video series (multiple files)")

    choice = input("Enter choice (1-5): ")

    if choice == '1':
        splitter = VideoSplitter({'split_video': True, 'create_dartclip': False})
    elif choice == '2':
        splitter = VideoSplitter({'split_video': False, 'create_dartclip': True})
    elif choice == '3':
        splitter = VideoSplitter({'split_video': True, 'create_dartclip': True})
    elif choice == '4':
        print("\nAdvanced Configuration:")
        start_number = int(input("Enter starting number for clips (default: 1): ") or 1)
        skip = int(input("Number of initial events to skip (default: 0): ") or 0)
        reencode = input("Re-encode video? (y/n, default: n): ").lower() == 'y'
        time_offset = float(input("Time offset in seconds (default: 0): ") or 0)
        buffer = float(input("Buffer time in seconds (default: 0.5): ") or 0.5)
        create_dartclip = input("Create dartclip files? (y/n, default: y): ").lower() != 'n'

        splitter = VideoSplitter({
            'split_video': True,
            'create_dartclip': create_dartclip,
            'skip': skip,
            'reencode': reencode,
            'time_offset': time_offset,
            'buffer': buffer,
            'start_number': start_number,
        })
    elif choice == '5':
        print("\nVideo series input mode:")
        print("  a. From Dartfish dartclip files (select folder)")
        print("  b. From CSV with per-file timestamps")
        print("  c. From CSV with absolute timestamps")

        sub = input("Enter choice (a/b/c, default: a): ").lower() or 'a'
        mode_map = {'a': 'dartclip', 'b': 'csv_per_file', 'c': 'csv_absolute'}
        input_mode = mode_map.get(sub, 'dartclip')

        naming = input("Clip naming - (a)uto numbering or (m)etadata from events? [a/m]: ").lower() or 'a'
        clip_naming = 'metadata' if naming == 'm' else 'auto'

        splitter = VideoSplitter({
            'video_series': True,
            'series_input_mode': input_mode,
            'split_video': True,
            'create_dartclip': True,
            'clip_naming': clip_naming,
        })
    else:
        print("Invalid choice. Exiting.")
        return

    # Gather paths via dialogs based on config
    kwargs = {}
    if splitter.config['video_series']:
        mode = splitter.config['series_input_mode']
        if mode == 'dartclip':
            kwargs['series_folder'] = select_folder(title="Select folder with .dartclip files")
            if not kwargs['series_folder']:
                return
        elif mode in ('csv_per_file', 'csv_absolute'):
            csv_folder, csv_name = select_file(title="Choose the CSV file")
            if not csv_folder:
                return
            kwargs['csv_path'] = os.path.join(csv_folder, csv_name)
            kwargs['video_paths'] = select_files(title="Select video files in order")
            if not kwargs['video_paths']:
                return
            if mode == 'csv_absolute':
                kwargs['output_folder'] = select_folder(title="Select output folder")
                if not kwargs['output_folder']:
                    return
    else:
        if splitter.config['split_video'] or splitter.config['create_dartclip']:
            csv_folder, csv_name = select_file(title="Choose the CSV file with event data")
            if not csv_folder:
                return
            kwargs['csv_path'] = os.path.join(csv_folder, csv_name)

        if splitter.config['split_video']:
            video_folder, video_name = select_file(title="Choose the video file")
            if not video_folder:
                return
            kwargs['video_path'] = os.path.join(video_folder, video_name)
            kwargs['output_folder'] = select_folder(title="Select output folder for clips")
            if not kwargs['output_folder']:
                return
        elif splitter.config['create_dartclip']:
            kwargs['clips_folder'] = select_folder(title="Select folder containing existing clips")
            if not kwargs['clips_folder']:
                return

    result = splitter.process_video(**kwargs)
    if result:
        print(f"Done! Output: {result}")
    else:
        print("Processing was not completed successfully.")


def sync_angle_main():
    """Interactive sync angle tool."""
    from pyfootball.sync_angle import (
        build_absolute_timeline, parse_timestamp,
        calculate_sync_offset, export_synced_csv
    )
    from pyfootball.ui.dialogs import select_folder

    print("=== Sync Angle Tool ===\n")

    gopro_folder = select_folder(title="Select GoPro folder with MP4s and dartclips")
    if not gopro_folder:
        print("No folder selected.")
        return

    print("\nBuilding absolute timeline from GoPro segments...")
    absolute_events = build_absolute_timeline(gopro_folder)
    print(f"Found {len(absolute_events)} plays\n")

    print("First plays on absolute timeline:")
    for e in absolute_events[:5]:
        mins = e['Position_abs_ms'] / 60000
        secs = (e['Position_abs_ms'] % 60000) / 1000
        print(f"  {e['Name']:15s} -> {int(mins)}:{secs:05.2f} "
              f"({e['source_file']})")
    print("  ...")

    ref_play = input("\nReference play name (e.g. 'Play (2)'): ").strip()
    ref_time_str = input("Time of that play on camera 2 (e.g. '2:01.20'): ").strip()
    ref_time_ms = parse_timestamp(ref_time_str)

    offset = calculate_sync_offset(absolute_events, ref_play, ref_time_ms)
    print(f"Calculated offset: {offset/1000:+.2f}s")

    import os
    output_path = os.path.join(gopro_folder, "synced_angle_times.csv")
    custom_path = input(f"\nOutput CSV path [{output_path}]: ").strip()
    if custom_path:
        output_path = custom_path

    export_synced_csv(absolute_events, offset, output_path)
    print(f"\nDone! CSV written to: {output_path}")


def autocrop_main():
    """Interactive autocrop tool."""
    from pyfootball.autocrop import calibrate_field, process_clips_folder
    from pyfootball.ui.dialogs import select_file, select_folder

    print("\n=== Football Video Auto-Crop ===\n")
    print("1. Calibrate field boundary (one-time per camera setup)")
    print("2. Auto-crop clips in a folder")
    print("3. Calibrate + auto-crop\n")

    choice = input("Select option (1/2/3): ").strip()

    calibration_path = None

    if choice in ('1', '3'):
        print("\nSelect a video from this camera setup for calibration.")
        video_dir, video_name = select_file(title="Select a video for field calibration")
        if video_dir is None:
            return
        import os
        video_path = os.path.join(video_dir, video_name)
        polygon = calibrate_field(video_path)
        if polygon is None:
            print("Calibration cancelled.")
            return
        calibration_path = os.path.join(video_dir, "field_calibration.json")
        print(f"Calibration saved: {calibration_path}")

    if choice in ('2', '3'):
        if calibration_path is None:
            cal_dir, cal_name = select_file(title="Select field_calibration.json")
            if cal_dir is None:
                return
            import os
            calibration_path = os.path.join(cal_dir, cal_name)

        clips_folder = select_folder(title="Select folder with video clips to auto-crop")
        if clips_folder is None:
            return

        process_clips_folder(clips_folder, calibration_path)


def concatenate_main():
    """Interactive concatenation tool."""
    from pyfootball.concatenate import (
        make_filelist, get_video_duration,
        calculate_video_starttime, write_clip_times_to_csv, concatenate_video
    )
    from pyfootball.ui.dialogs import select_folder

    video_path = select_folder(title="Select folder with current clips")
    output_path = select_folder(title="Select output folder for output video")
    if not video_path or not output_path:
        return

    import os
    output_name = os.path.join(output_path, "Concatenated_Video.mp4")

    file_list = make_filelist(video_path, output_filename="mp4_list.txt")
    video_duration, video_name = get_video_duration(file_list)
    video_starttime = calculate_video_starttime(video_duration)
    write_clip_times_to_csv(video_path, video_name, video_starttime, video_duration)
    concatenate_video(video_path, output_name)


def recode_main():
    """Interactive recode tool."""
    from pyfootball.recode import recode_video
    from pyfootball.ui.dialogs import select_file

    video_path, video_name = select_file(title="Select video to re-encode")
    if not video_path:
        return

    recode_video(video_path, video_name)


def extract_frames_main():
    """Interactive frame extraction tool."""
    import random
    from pyfootball.extract_frames import (
        get_video_files_from_folder, extract_random_frames
    )
    from pyfootball.ui.dialogs import select_file, select_folder

    video_mode = input("Mode - (f)ile or f(o)lder? [f/o]: ").strip().lower() or 'f'
    output_directory = select_folder(title="Choose the folder to save the images")
    if not output_directory:
        return

    if video_mode == 'f':
        video_dir, video_name = select_file(title="Choose the video file")
        if not video_dir:
            return
        import os
        video_path = os.path.join(video_dir, video_name)
        extract_random_frames(video_path, output_directory)
    else:
        folder_path = select_folder("Choose the folder where the video clips are located")
        if not folder_path:
            return
        filter_text = input("Filter text (or Enter to skip): ").strip() or None
        video_files = get_video_files_from_folder(folder_path, filter_text=filter_text)

        use_subset = input("Use random subset? (y/n, default: n): ").lower() == 'y'
        if use_subset:
            subset_size = int(input("Subset size (default: 30): ") or 30)
            subset_size = min(subset_size, len(video_files))
            video_files = random.sample(video_files, subset_size)

        for video_path in video_files:
            extract_random_frames(video_path, output_directory,
                                  num_frames=3, presnap_flag=True)


def scenedetect_main():
    """Interactive scene detection tool."""
    from pyfootball.scenedetect import (
        scene_detection, print_scene_info,
        save_scene_list_to_csv, filter_expected_scenes
    )
    from pyfootball.ui.dialogs import select_file

    video_dir, video_name = select_file(title="Select video for scene detection")
    if not video_dir:
        return

    import os
    full_video_path = os.path.join(video_dir, video_name)

    scene_list, scene_file = scene_detection(full_video_path)
    print_scene_info(scene_list)
    save_scene_list_to_csv(scene_list, scene_file)

    filtered_scenes = filter_expected_scenes(scene_list)
    base_name = os.path.splitext(video_name)[0]
    filtered_scene_file = os.path.join(video_dir, base_name + "_filtered_scene.csv")
    save_scene_list_to_csv(filtered_scenes, filtered_scene_file)


def main():
    """Main CLI entry point with tool selection."""
    print("\n=== PyFootballVideo ===\n")
    print("1. Split video into clips")
    print("2. Sync camera angle")
    print("3. Auto-crop clips")
    print("4. Concatenate clips")
    print("5. Re-encode with keyframes")
    print("6. Extract random frames")
    print("7. Scene detection")

    choice = input("\nSelect tool (1-7): ").strip()

    tools = {
        '1': splitter_main,
        '2': sync_angle_main,
        '3': autocrop_main,
        '4': concatenate_main,
        '5': recode_main,
        '6': extract_frames_main,
        '7': scenedetect_main,
    }

    func = tools.get(choice)
    if func:
        func()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()
