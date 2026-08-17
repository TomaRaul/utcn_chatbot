@echo off
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set RESUME_INGEST=1
echo === smart_ingest (RESUME) ===
python smart_ingest.py
echo === patch_missing_year ===
python patch_missing_year.py
echo === build_manifest ===
python build_manifest.py
echo === build_reverse_index ===
python build_reverse_index.py
endlocal
echo.
echo === DONE ===
pause
