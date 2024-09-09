# pf_random_functions.py

# use OpenCV for multimedia edits
import cv2

def playing_video(video_file, start_frame, end_frame):
  # TODO: do something useful with this code
  
  start_frame = 4738
  end_frame = 6283
  
  # load video file
  cap = cv2.VideoCapture(video_file)
  
  cap.get(cv2.CAP_PROP_FPS)

  # check if camera opened successfully
  if (cap.isOpened()== False):
      print("Error opening video file")

  # set start frame
  cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
  
  # read until video is completed
  while(cap.isOpened()):
      
  # Capture frame-by-frame
      ret, frame = cap.read()

      # get current frame 
      c_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)

      if c_frame == end_frame:
        break

      if ret == True:
      # Display the resulting frame
          cv2.imshow('Frame', frame)
          
      # Press Q on keyboard to exit
          if cv2.waitKey(1) & 0xFF == ord('q'):
              break
  
  # Break the loop
      else:
          break
  
  # When everything done, release
  # the video capture object
  cap.release()
  
  # Closes all the frames
  cv2.destroyAllWindows()

  ret, frame = cap.read()

  # release video object
  cap.release()
  cv2.destroyAllWindows()


def get_creation_time():
  # function to extract video creation times to use for splitting continuous files
  # e.g. one video angle used stop/start recording but others were continuous, so the creation times could serve to cut the others.

  # TODO: finish this code
  # get list of files
  file_list = glob.glob(sony_path + "**/*.mp4", recursive=True)

  video_duration = []
  video_createtimes = []
  for file in file_list:
    # probe video for info
    video_info = ffmpeg.probe(file)
    video_duration.append(video_info['streams'][0]['duration']) # in seconds

    create_datetime = video_info['streams'][0]['tags']['creation_time']
    # get date a time separately
    create_date, create_time = create_datetime.split("T", 1)
    create_time = create_time[0:-1]
    time_object = datetime.datetime.strptime(create_time, "%H:%M:%S.%f")
