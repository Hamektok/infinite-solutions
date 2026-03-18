@echo off
REM Auto-update LX-ZOJ Inventory
cd /d "E:\Python Project"
set GIT_LFS_SKIP_SMUDGE=1
set GCM_INTERACTIVE=never
C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe update_lx_zoj_inventory.py >> "E:\Python Project\logs\inventory_updates.log" 2>&1
