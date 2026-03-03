@echo off
chcp 65001 > nul
echo ============================================================================
echo Local Preview Server
echo ============================================================================
echo.
echo Starting local server... your browser will open automatically.
echo.
echo When you're done testing, close this window to stop the server.
echo ============================================================================
echo.

cd /d "E:\Python Project"

start "" "http://localhost:8080/index_final.html"

"C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m http.server 8080

pause
