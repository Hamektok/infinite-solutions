# run_gank_fetch.ps1
# Runs the daily gank candidate fetch (last 24 hours).
# Schedule this via Windows Task Scheduler to run nightly.

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python).Source
$Script = Join-Path $ProjectDir "scripts\fetch_gank_candidates.py"
$LogFile = Join-Path $ProjectDir "logs\gank_fetch.log"

# Ensure logs directory exists
$LogDir = Join-Path $ProjectDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "`n=== $Timestamp ==="

& $Python $Script --hours 48 2>&1 | Tee-Object -Append -FilePath $LogFile

# Rebuild the public watchlist page and push to GitHub Pages
$BuildScript = Join-Path $ProjectDir "_build_gank_watchlist.py"
Add-Content -Path $LogFile -Value "Rebuilding gank_watchlist.html..."
& $Python $BuildScript 2>&1 | Tee-Object -Append -FilePath $LogFile

# Commit and push the updated page
$GitPath = (Get-Command git -ErrorAction SilentlyContinue).Source
if ($GitPath) {
    Set-Location $ProjectDir
    & git add gank_watchlist.html 2>&1 | Out-Null
    $CommitMsg = "Auto-update gank watchlist - $Timestamp"
    & git commit -m $CommitMsg 2>&1 | Tee-Object -Append -FilePath $LogFile
    & git push 2>&1 | Tee-Object -Append -FilePath $LogFile
    Add-Content -Path $LogFile -Value "Pushed gank_watchlist.html to GitHub Pages."
} else {
    Add-Content -Path $LogFile -Value "WARNING: git not found, skipping push."
}
