import os
import csv
import pickle

import scenedetect

# for the user selection of the path / file
from tkinter import Tk
from tkinter import filedialog


def select_file():
    # Create an instance of Tkinter's Tk class
    root = Tk()

    # Hide the main window of Tkinter
    root.withdraw()

    # Open a dialog for file selection
    selected_file = filedialog.askopenfilename()

    # Check if the user clicked "Cancel"
    if not selected_file:
        print("No file selected.")
        return None, None

    # Split the file path and name
    file_path, file_name = os.path.split(selected_file)

    # Return the selected file path and name
    return file_path, file_name


def scene_detection(full_video_path):
    # use pyscenedetect to find the most probably splits to the video

    # separate the path, and video name
    file_path, file_name = os.path.split(full_video_path)
    video_name = os.path.splitext(file_name)[0]

    # specify later save locations and names
    stats_file = os.path.join(file_path, video_name+"_stats.csv")
    scene_file = os.path.join(file_path, video_name + "_scene.csv")

    # setup the scenedetect parameters
    video_stream = scenedetect.open_video(full_video_path)
    stats_manager = scenedetect.StatsManager()
    scene_manager = scenedetect.SceneManager(stats_manager)

    scene_manager.add_detector(
        scenedetect.AdaptiveDetector(
        adaptive_threshold=5,                               # experimental value of 5 seems optimal
        window_width=5,                                     # average [int] frames before/after for running average 
        min_scene_len=20,                                   # at least 30 frames (0.5 seconds at 60fps)
        min_content_val=15))

    # detect the scenes using the defined settings
    scene_manager.detect_scenes(video=video_stream, show_progress=True)
    scene_list = scene_manager.get_scene_list()

    # Store the frame metrics we calculated for the next time the program runs.
    stats_manager.save_to_csv(csv_file=stats_file)

    return scene_list, scene_file


def print_scene_info(scene_list):
    # print each scene in the terminal line-by-line 
    for i, scene in enumerate(scene_list):
        print(
            'Scene %2d: Start %s / Frame %.5d  ->  End %s / Frame %.5d -> Duration %s' % (
            i+1,
            scene[0].get_timecode(), scene[0].get_frames(),
            scene[1].get_timecode(), scene[1].get_frames(),
            [scene[1].get_frames()-scene[0].get_frames()]))


def save_scene_list_to_csv(scene_list, csv_file):

    # specify the number of scenes each play has 
    # e.g. 3 if play clock, all22, then endzone
    angle_count = 3

    # Define the angle values
    if angle_count == 2:
        angle_values = ["All 22", "Endzone"]
    else:
        angle_values = ["Score Board", "All 22", "Endzone"]

    angle_index = 0

    # Open the CSV file in write mode
    with open(csv_file, 'w', newline='') as file:
        writer = csv.writer(file)

        # Write the header row
        writer.writerow(['Name', 'Start Time', 'End Time', 'Duration', 'Angle'])  # Modify the column names as needed

        # Write each scene's start frame, end frame, and duration as a new row in the CSV file
        count = 1
        for i, scene in enumerate(scene_list, start=1):
            start_time = scene[0].get_frames() / scene[0].get_framerate()
            end_time = scene[1].get_frames() / scene[0].get_framerate()
            duration_seconds = end_time - start_time

           # Get the current angle value and update the index
            angle_value = angle_values[angle_index]
            angle_index = (angle_index + 1) % len(angle_values)

            writer.writerow([f"Play {count}", start_time, end_time, duration_seconds, angle_value])

            # Increment the count every "n" rounds of the loop
            if i % angle_count == 0:
                count += 1

    # Print a success message
    print(f"Scene list has been saved to {csv_file}.")


def scene_splitter(video_file, scene_manager):

  scene_list = scene_manager.get_scene_list()

  # NOTE: scene_list is a "two-column" list of start and end times (and frames) for each detected scene
  # get the starting/ending frames for each scene (in FrameTimeCode format native to PySceneDetect)
  # could also use .get_seconds() for the time 
  start_frames = np.array([row[0].get_frames() for row in scene_list])
  end_frames = np.array([row[1].get_frames() for row in scene_list])
  frame_rate = scene_list[0][0].get_framerate()
  scene_durations = np.divide(np.subtract(end_frames, start_frames), frame_rate)
  # print scene_durations
  for x in enumerate(scene_durations):
    print(x)

  # delete short scenes (not football plays)
  short_scenes = [idx for idx, val in enumerate(scene_durations) if val < 3]
  scene_list_cut = [element for i, element in enumerate(scene_list) if i not in short_scenes]

  # cut out every second scene for endzone only
  all22_scenes = scene_list_cut[0:-1:2]
  endzone_scenes = scene_list_cut[1:-1:2]             # first int should be either 0 or 1 / 3rd int is the space (e.g. 3 if scorebord present)
  for x in enumerate(endzone_scenes): 
    print(x)

  # split all video scenes with PySceneDetect
  scenedetect.video_splitter.split_video_ffmpeg(video_file, all22_scenes, output_file_template='$VIDEO_NAME-$SCENE_NUMBER-All22.mp4', show_progress=True)
  scenedetect.video_splitter.split_video_ffmpeg(video_file, endzone_scenes, output_file_template='$VIDEO_NAME-$SCENE_NUMBER-Endzone.mp4', show_progress=True)
  
  #TODO: specify output folder (currently does not work)
  output_dir = r'F:\Gamepass_Clips'
  output_template = os.path.join(os.path.join(output_dir,"Endzone-$SCENE_NUMBER.mp4"))
  print(output_template)
  scenedetect.video_splitter.split_video_ffmpeg(video_file, scene_list_cut,
    output_file_template=output_template)

  scenedetect.video_splitter.split_video_ffmpeg(video_file, scene_list[26:28], 
    output_file_template='Clip-$SCENE_NUMBER.mp4')


def explore_stats(video_file, scene_manager, video_stream):
    
    # you can get the metrics for any frame / metric 
    # 'adaptive_ratio (w=5)', 'content_val', 'delta_edges', 'delta_lum', 'delta_hue', 'delta_sat'
    x = scene_manager.stats_manager.get_metrics(922, ['adaptive ratio (w=5)'])[0]

    delta_edges = []
    for n in range(video_stream.frame_number):
        delta_edges.append(
        scene_manager.stats_manager.get_metrics(n, ['delta_edges'])[0])
    delta_edges = np.array(delta_edges, dtype=np.float64)
    edges_diff = np.diff(delta_edges, 1)
    edges_median = np.nanmedian(edges_diff)

    # plot the edge data and its differential 
    plt.plot(delta_edges)
    plt.plot(edges_diff, color='green')
    plt.show()

    # find where edges are 2x the median
    cut_indices = [idx for idx, val in enumerate(edges_diff) if val < 2*edges_median]


    # print stats for cut frames
    with open(stats_file, 'r') as f:
        stats_data = list(csv.reader(f, delimiter=";"))

    # print the stat lines for the "detected" scene cuts  
    for i in list(start_frames):
        print(stats_data[i])


def save_scene_list_to_pickle(video_file, scene_manager):
    # pickle/save the original scene list
    pickle_name = os.path.join(base_path, game_path, video_name+"_SceneManager.pkl")
    pickle_file = open(pickle_name, 'wb')
    pickle.dump(scene_manager, pickle_file)
    pickle_file.close()

    # load scene_list from pickled file
    tmp = open(pickle_name, 'rb')
    loaded_scene_list = pickle.load(tmp)
    tmp.close()


def filter_expected_scenes(scene_list):
    expected_scenes = []

    # Loop through the detected scenes to match the expected pattern.
    for i in range(len(scene_list) - 2):
        scene_a = scene_list[i]
        scene_b = scene_list[i + 1]
        scene_c = scene_list[i + 2]

        # Check if the scenes match the expected pattern.
        if is_expected_scene_pattern(scene_a, scene_b, scene_c):
            expected_scenes.append(scene_a)
            expected_scenes.append(scene_b)
            expected_scenes.append(scene_c)

    return expected_scenes


def is_expected_scene_pattern(scene_a, scene_b, scene_c):
    # Check if the durations match the expected pattern.
    max_short_scene_duration = 2.5  # Adjust as per your requirements.
    max_duration_difference = 0.3  # Maximum difference in duration between scenes B and C.

    duration_a = scene_a[1].get_seconds() - scene_a[0].get_seconds()
    duration_b = scene_b[1].get_seconds() - scene_b[0].get_seconds()
    duration_c = scene_c[1].get_seconds() - scene_c[0].get_seconds()

    if (
        duration_a < max_short_scene_duration and
        abs(duration_b - duration_c) <= max_duration_difference * min(duration_b, duration_c)
    ):
        return True

    return False


def main_pipeline():
  
    # choose the file to be split (somehow)
    video_path, video_file = select_file()

    # combine to (re)create full path
    full_video_path = video_file = os.path.join(video_path, video_file)

    # get the scene list
    scene_list, scene_file = scene_detection(full_video_path)

    # print all the detected scenes start and stops
    print_scene_info(scene_list)

    # save to a csv file for DF
    save_scene_list_to_csv(scene_list, scene_file)

    # filter the scene_list to look for the pattern "short scene followed by two longer ones"
    filtered_scenes = filter_expected_scenes(scene_list)

    # save filtered
    video_name = os.path.splitext(video_file)[0]
    filtered_scene_file = os.path.join(video_path, video_name + "_filtered_scene.csv")
    save_scene_list_to_csv(filtered_scenes, filtered_scene_file)



    # scene_list[0][1].get_seconds() - scene_list[0][0].get_seconds()
    scene_list[0][1].get_framerate()