@echo off
rem AzerothGPS StreetView tools with the AzerothGPS venv (works from any folder).
"%USERPROFILE%\.venvs\azerothgps\Scripts\python.exe" "%~dp0tools\sv.py" %*
