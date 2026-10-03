param(
    [string]$Serial = "",
    [switch]$ProbeRemote,
    [switch]$ProbeRestore
)

$ErrorActionPreference = "Stop"

$PackageName = "io.github.michalduffs.bondiktv"
$ActivityName = "$PackageName/.MainActivity"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AndroidDir = Split-Path -Parent $ScriptDir
$ApkPath = Join-Path $AndroidDir "app\build\outputs\apk\debug\app-debug.apk"

function Invoke-Adb {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $base = @()

    if ($Serial) {
        $base += @("-s", $Serial)
    }

    & adb @base @Arguments

    if ($LASTEXITCODE -ne 0) {
        throw "adb command failed: adb $($Arguments -join ' ')"
    }
}

if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    throw "adb was not found in PATH. Install Android platform-tools first."
}

if (-not (Test-Path $ApkPath)) {
    throw "Debug APK not found at $ApkPath. Run .\gradlew.bat assembleDebug first."
}

$deviceLines = & adb devices |
    Select-Object -Skip 1 |
    Where-Object { $_ -match "\tdevice$" }

if (-not $Serial -and $deviceLines.Count -ne 1) {
    throw "Expected exactly one authorized Android device. Found $($deviceLines.Count). Use -Serial when multiple devices are connected."
}

Write-Host ""
Write-Host "Bondik TV Android TV smoke" -ForegroundColor Cyan
Write-Host "APK: $ApkPath"

Write-Host ""
Write-Host "[1/5] Installing debug APK..." -ForegroundColor Yellow
Invoke-Adb @("install", "-r", $ApkPath)

Write-Host ""
Write-Host "[2/5] Verifying package..." -ForegroundColor Yellow
$packages = Invoke-Adb @("shell", "pm", "list", "packages", $PackageName)

if ($packages -notmatch [regex]::Escape($PackageName)) {
    throw "Package $PackageName was not found after install."
}

Write-Host ""
Write-Host "[3/5] Verifying Android TV launcher entry..." -ForegroundColor Yellow
$leanback = Invoke-Adb @(
    "shell",
    "cmd",
    "package",
    "resolve-activity",
    "--brief",
    "-a",
    "android.intent.action.MAIN",
    "-c",
    "android.intent.category.LEANBACK_LAUNCHER",
    $PackageName
)

if ($leanback -notmatch [regex]::Escape($PackageName)) {
    throw "LEANBACK_LAUNCHER activity was not resolved."
}

Write-Host ""
Write-Host "[4/5] Launching Bondik TV..." -ForegroundColor Yellow
Invoke-Adb @(
    "shell",
    "am",
    "start",
    "-W",
    "-n",
    $ActivityName
)

Start-Sleep -Seconds 2

$appPid = Invoke-Adb @(
    "shell",
    "pidof",
    $PackageName
)

if ([string]::IsNullOrWhiteSpace(($appPid | Out-String))) {
    throw "Bondik TV is not running after launch."
}

if ($ProbeRemote) {
    Write-Host ""
    Write-Host "Remote probe: DOWN, DOWN, OK" -ForegroundColor Magenta
    Invoke-Adb @("shell", "input", "keyevent", "KEYCODE_DPAD_DOWN")
    Start-Sleep -Milliseconds 500
    Invoke-Adb @("shell", "input", "keyevent", "KEYCODE_DPAD_DOWN")
    Start-Sleep -Milliseconds 500
    Invoke-Adb @("shell", "input", "keyevent", "KEYCODE_DPAD_CENTER")
    Start-Sleep -Seconds 2
}

if ($ProbeRestore) {
    Write-Host ""
    Write-Host "Restore probe: force-stop and relaunch" -ForegroundColor Magenta
    Invoke-Adb @("shell", "am", "force-stop", $PackageName)
    Start-Sleep -Seconds 1
    Invoke-Adb @(
        "shell",
        "am",
        "start",
        "-W",
        "-n",
        $ActivityName
    )
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "[5/5] Automated smoke GREEN" -ForegroundColor Green
Write-Host "Confirmed:"
Write-Host "  - APK installs"
Write-Host "  - package is present"
Write-Host "  - LEANBACK_LAUNCHER resolves"
Write-Host "  - MainActivity launches"
Write-Host "  - process is running"

Write-Host ""
Write-Host "Human TV checks still required:" -ForegroundColor Cyan
Write-Host "  1. D-pad focus highlight is visible on exactly one channel row."
Write-Host "  2. Up/Down moves focus predictably."
Write-Host "  3. OK on another channel moves selection and starts playback."
Write-Host "  4. Relaunch restores the last selected channel into view."
Write-Host "  5. Relaunch does not force autoplay."
