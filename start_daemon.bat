@echo off
cd /d C:\Users\nicod\aurum-trading
set PYTHONPATH=C:\Users\nicod\aurum-trading
echo Starting AURUM at %date% %time% >> logs\daemon_scheduler.log
C:\Users\nicod\AppData\Local\Microsoft\WindowsApps\pythonw.exe daemon.py >> logs\daemon_scheduler.log 2>&1
echo Daemon exited at %date% %time% with code %errorlevel% >> logs\daemon_scheduler.log
