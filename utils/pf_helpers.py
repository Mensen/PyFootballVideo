# pf_helpers.py

from tkinter import Tk, filedialog
import os

def select_file(title="Select a File"):
  """
    Opens a file dialog for selecting a file.

    Args:
        title (str): Custom title for the file dialog (optional).

    Returns:
        tuple: A tuple containing the selected file path and file name.
               If no file is selected (user clicks "Cancel"), returns (None, None).
    """
  
  # Create an instance of Tkinter's Tk class
  root = Tk()

  # Hide the main window of Tkinter
  root.withdraw()
  root.wm_attributes('-topmost', 1)

  # Open a dialog for file selection
  selected_file = filedialog.askopenfilename(title=title)

  # Check if the user clicked "Cancel"
  if not selected_file:
    print("No file selected.")
    return None, None

  # Split the file path and name
  file_path, file_name = os.path.split(selected_file)

  # Return the selected file path and name
  return file_path, file_name


def select_folder(title="Select a Folder"):
    # Create an instance of Tkinter's Tk class
    root = Tk()

    # Hide the main window of Tkinter
    root.withdraw()  
    root.wm_attributes('-topmost', 1)

    # Open a dialog for folder selection
    selected_folder = filedialog.askdirectory(title=title)

    # Check if the user clicked "Cancel"
    if not selected_folder:
        print("No folder selected.")
        return None
    
    # Normalize the selected folder path
    selected_folder = os.path.normpath(selected_folder)

    # Return the selected folder path
    return selected_folder

def define_paths_breakdown():
  base_path = r"C:\Users\mensen\Bern Grizzlies\Coaches - Documents"
  game_path = r"NCAA Film\YoutubeBreakdowns"

  base_path = r"F:\Gamepass_Clips"
  base_path = r"F:\NCAA"
  game_path = r""
  
  video_name = "TestClip_BillsChiefs_DR_2021"
  video_name = "CoachesTape - 22 01 Florida O vs Utah"

  full_video_path = os.path.join(base_path, game_path, video_name + ".mp4")

  # Check existence
  if os.path.exists(full_video_path) == False:
    print("Error - File: " + full_video_path + " doesn't exist")
  else:
     print("Found it! " + full_video_path)