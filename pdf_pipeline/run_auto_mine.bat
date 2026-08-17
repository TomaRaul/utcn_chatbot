@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8
echo === Auto-mine === >> logs\auto_mine.log
python auto_mine.py >> logs\auto_mine.log 2>&1
echo === Reverse-index refresh === >> logs\auto_mine.log
python build_reverse_index.py >> logs\auto_mine.log 2>&1
endlocal
