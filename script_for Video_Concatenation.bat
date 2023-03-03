:: Concatenate all the videos in the root folder

:: make a temporary list of files
:: foreach ($i in Get-ChildItem .\*.mp4) {echo "file '$i'" >> files.txt}

@echo off
setlocal enabledelayedexpansion


:: check for the temp_files.txt
if exist temp_files.txt del temp_files.txt

:: build file list
for /r %%i in (*.mp4) do (
	@echo file '%%i' >> temp_files.txt
	)

:: concatenate files
:: picture black when different res but would work perfectly when same res
ffmpeg -f concat -safe 0 -i temp_files.txt -c copy concatenated_video.mp4

:: recodes everything and has still frames when different res
:: ffmpeg -f concat -safe 0 -i temp_files.txt output.mp4 