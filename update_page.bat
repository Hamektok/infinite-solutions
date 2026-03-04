@echo off
chcp 65001 > nul
cd /d "E:\Python Project"

echo ============================================================================
echo  Deploy to Live
echo ============================================================================
echo.

REM Remember which branch we're on so we can switch back
for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD') do set ORIG_BRANCH=%%b
echo Current branch: %ORIG_BRANCH%

REM Switch to main (where GitHub Pages serves from)
if /i not "%ORIG_BRANCH%"=="main" (
    echo Switching to main...
    git checkout main
    if %errorlevel% neq 0 (
        echo ERROR: Could not switch to main branch.
        pause
        exit /b 1
    )
)

REM Pull any remote changes first to avoid conflicts
echo Pulling latest from origin/main...
git pull origin main --quiet

REM Regenerate buyback data from database
echo.
echo Regenerating buyback data...
"C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe" generate_buyback_data.py
echo.

REM Stage and commit
git add index.html buyback_data.js
git diff --cached --quiet
if %errorlevel% equ 0 (
    echo No changes detected - site is already up to date.
    goto :switchback
)

git commit -m "Update site data - %date% %time%"
echo.
echo Pushing to GitHub...
git push origin main

if %errorlevel% equ 0 (
    echo.
    echo ============================================================================
    echo  SUCCESS! Your page is updating now.
    echo  Live URL: https://hamektok.github.io/infinite-solutions/
    echo  Wait 1-2 minutes then refresh.
    echo ============================================================================
) else (
    echo.
    echo ============================================================================
    echo  ERROR: Push failed. Check your internet connection or run:
    echo    git push origin main
    echo ============================================================================
)

:switchback
REM Switch back to the original branch
if /i not "%ORIG_BRANCH%"=="main" (
    echo.
    echo Switching back to %ORIG_BRANCH%...
    git checkout %ORIG_BRANCH%
)

echo.
pause
