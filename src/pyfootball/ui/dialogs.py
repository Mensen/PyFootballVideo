"""Tkinter file/folder selection dialogs."""

from tkinter import Tk, filedialog
import os


def select_file(title="Select a File"):
    """
    Opens a file dialog for selecting a file.

    Args:
        title: Custom title for the file dialog.

    Returns:
        tuple: (file_path, file_name), or (None, None) if cancelled.
    """
    root = Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)

    selected_file = filedialog.askopenfilename(title=title)

    if not selected_file:
        print("No file selected.")
        return None, None

    file_path, file_name = os.path.split(selected_file)
    return file_path, file_name


def select_folder(title="Select a Folder"):
    """
    Opens a folder dialog for selecting a folder.

    Args:
        title: Custom title for the folder dialog.

    Returns:
        str: Selected folder path, or None if cancelled.
    """
    root = Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)

    selected_folder = filedialog.askdirectory(title=title)

    if not selected_folder:
        print("No folder selected.")
        return None

    return os.path.normpath(selected_folder)


def select_files(title="Select Files"):
    """
    Opens a file dialog for selecting multiple files.

    Args:
        title: Custom title for the file dialog.

    Returns:
        list: Sorted list of selected file paths, or None if cancelled.
    """
    root = Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)

    selected_files = filedialog.askopenfilenames(title=title)

    if not selected_files:
        print("No files selected.")
        return None

    return sorted(selected_files)
