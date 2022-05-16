:: $Path = "c:\temp\Winti D Scout"
:: $files = Get-ChildItem $Path -filter "*.mp4"
:: Foreach ($file in $files) {
::    Write-Host "$file"
::    ffprobe -v quiet -show_entries format=duration >> $Path\$file
::    Write-Host " "
:: }

:: -sexagesimal gives hh:mm:ss:mm

@echo off
setlocal enabledelayedexpansion


:: check for the durations.txt
if exist durations.txt del durations.txt
	

for /r %%i in (*.mp4) do (
	echo %%i
	REM ffprobe -show_entries format=duration -v quiet -of default=noprint_wrappers=1:nokey=1 %%i >> temp.txt
	ffprobe -show_entries format=duration -v quiet -of default=noprint_wrappers=1:nokey=1^
	"%%i"^
	>> durations.txt
	)