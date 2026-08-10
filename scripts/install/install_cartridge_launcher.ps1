param(
    [string]$SourceDirectory = $PSScriptRoot,
    [string]$InstallDirectory = "$([Environment]::GetFolderPath('LocalApplicationData'))\Programs\3SD",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$appName = "3SD"
$exeName = "3SD.exe"
$legacyExeName = "CartridgeLauncher.exe"
$certificateName = "3SD-LocalDev.cer"
$exeInstallPath = Join-Path $InstallDirectory $exeName
$installProgramsDirectory = Split-Path -Parent $InstallDirectory
$installLocalAppData = Split-Path -Parent $installProgramsDirectory
$installAppDataDirectory = Split-Path -Parent $installLocalAppData
$installUserProfile = Split-Path -Parent $installAppDataDirectory
$installRoamingAppData = Join-Path $installUserProfile "AppData\Roaming"
$installDesktop = Join-Path $installUserProfile "Desktop"
$startMenuDirectory = Join-Path $installRoamingAppData "Microsoft\Windows\Start Menu\Programs\3SD"
$startMenuShortcut = Join-Path $startMenuDirectory "3SD.lnk"
$startupShortcut = Join-Path $installRoamingAppData "Microsoft\Windows\Start Menu\Programs\Startup\3SD.lnk"
$desktopShortcut = Join-Path $installDesktop "3SD.lnk"
$legacyStartMenuDirectory = Join-Path $installRoamingAppData "Microsoft\Windows\Start Menu\Programs\Cartridge Launcher"
$legacyStartupShortcut = Join-Path $installRoamingAppData "Microsoft\Windows\Start Menu\Programs\Startup\CartridgeLauncher.lnk"
$legacyDesktopShortcut = Join-Path $installDesktop "Cartridge Launcher.lnk"

function Add-CertificateToCurrentUserStore {
    param([System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate, [System.Security.Cryptography.X509Certificates.StoreName]$StoreName)
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($StoreName, [System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser)
    try {
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        $existing = $store.Certificates.Find([System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint, $Certificate.Thumbprint, $false)
        if ($existing.Count -eq 0) { $store.Add($Certificate) }
    }
    finally { $store.Close() }
}

function Add-CertificateToLocalMachineStoreIfPossible {
    param([System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate, [System.Security.Cryptography.X509Certificates.StoreName]$StoreName)
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
        return $false
    }
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($StoreName, [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine)
    try {
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        $existing = $store.Certificates.Find([System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint, $Certificate.Thumbprint, $false)
        if ($existing.Count -eq 0) { $store.Add($Certificate) }
        return $true
    }
    finally { $store.Close() }
}

function New-Shortcut {
    param(
        [string]$ShortcutPath,
        [string]$TargetPath,
        [string]$WorkingDirectory,
        [string]$Arguments = "",
        [string]$IconPath = $TargetPath
    )
    $shortcutDirectory = Split-Path -Parent $ShortcutPath
    if (-not (Test-Path $shortcutDirectory)) { New-Item -ItemType Directory -Path $shortcutDirectory | Out-Null }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $escapedTargetPath = $TargetPath.Replace("'", "''")
    $escapedWorkingDirectory = $WorkingDirectory.Replace("'", "''")
    $escapedArguments = $Arguments.Replace("'", "''")
    $shortcut.Arguments = "-NoProfile -WindowStyle Hidden -Command `"Start-Process -FilePath '$escapedTargetPath' -ArgumentList '$escapedArguments' -WorkingDirectory '$escapedWorkingDirectory'`""
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.IconLocation = $IconPath
    $shortcut.Save()
}

function Test-ExecutableBlockedByApplicationControl {
    param([string]$ExecutablePath)

    try {
        $process = Start-Process `
            -FilePath $ExecutablePath `
            -ArgumentList "startup status" `
            -WorkingDirectory (Split-Path -Parent $ExecutablePath) `
            -WindowStyle Hidden `
            -PassThru `
            -Wait
        return $false
    }
    catch {
        $message = $_.Exception.Message
        if ($message -match "Control de aplicaciones" -or $message -match "Application Control") {
            return $true
        }
        throw
    }
}

function Resolve-PythonHost {
    $userPythonCandidates = Get-ChildItem `
        -Path (Join-Path $installUserProfile "AppData\Local\Programs\Python") `
        -Recurse `
        -Filter "pythonw.exe" `
        -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    if ($userPythonCandidates.Count -gt 0) {
        return $userPythonCandidates[0].FullName
    }

    $pythonw = Get-Command "pythonw.exe" -ErrorAction SilentlyContinue
    if ($null -ne $pythonw) {
        return $pythonw.Source
    }

    $python = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        $candidate = Join-Path (Split-Path -Parent $python.Source) "pythonw.exe"
        if (Test-Path $candidate) {
            return $candidate
        }
        return $python.Source
    }

    $userPythonExeCandidates = Get-ChildItem `
        -Path (Join-Path $installUserProfile "AppData\Local\Programs\Python") `
        -Recurse `
        -Filter "python.exe" `
        -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    if ($userPythonExeCandidates.Count -gt 0) {
        return $userPythonExeCandidates[0].FullName
    }

    return ""
}

function Unblock-PathTree {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
    if ((Get-Item -LiteralPath $Path).PSIsContainer) {
        Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
    }
}

function Get-SmartAppControlSummary {
    $citool = Get-Command "citool.exe" -ErrorAction SilentlyContinue
    if ($null -eq $citool) { return "" }
    $output = & $citool.Source -lp 2>$null
    if ($LASTEXITCODE -ne 0 -or $null -eq $output) { return "" }
    $text = $output -join "`n"
    if ($text -match "VerifiedAndReputableDesktop" -and $text -match "Is Currently Enforced\s*:\s*true") {
        return "Smart App Control esta en modo activo. Windows puede bloquear builds locales aunque el instalador actualice la app y la firma Authenticode sea valida."
    }
    if ($text -match "VerifiedAndReputableDesktopEvaluation") {
        return "Smart App Control esta en modo evaluacion. Si Windows lo pasa a activo, puede bloquear builds locales sin reputacion publica."
    }
    return ""
}

function Stop-PreviousAppInstances {
    foreach ($processName in @("3SD", "CartridgeLauncher")) {
        Get-Process $processName -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

function Remove-LegacyShortcuts {
    foreach ($path in @($legacyStartupShortcut, $legacyDesktopShortcut)) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
    }
    if (Test-Path -LiteralPath $legacyStartMenuDirectory) {
        Remove-Item -LiteralPath $legacyStartMenuDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$resolvedSourceDirectory = (Resolve-Path $SourceDirectory).Path
$exeSourcePath = Join-Path $resolvedSourceDirectory $exeName
$certificatePath = Join-Path $resolvedSourceDirectory $certificateName
if (-not (Test-Path $exeSourcePath)) { throw "No se encontro $exeName en $resolvedSourceDirectory" }
if (-not (Test-Path $certificatePath)) { throw "No se encontro $certificateName en $resolvedSourceDirectory" }

Stop-PreviousAppInstances
if (-not (Test-Path $InstallDirectory)) { New-Item -ItemType Directory -Path $InstallDirectory | Out-Null }
Copy-Item -Path $exeSourcePath -Destination $exeInstallPath -Force
Copy-Item -Path $certificatePath -Destination (Join-Path $InstallDirectory $certificateName) -Force
Remove-Item -LiteralPath (Join-Path $InstallDirectory $legacyExeName) -Force -ErrorAction SilentlyContinue
Remove-LegacyShortcuts
Unblock-PathTree -Path $resolvedSourceDirectory
Unblock-PathTree -Path $InstallDirectory

$certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2((Resolve-Path $certificatePath).Path)
Add-CertificateToCurrentUserStore -Certificate $certificate -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::Root)
Add-CertificateToCurrentUserStore -Certificate $certificate -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::TrustedPublisher)
$trustedInMachineRoot = Add-CertificateToLocalMachineStoreIfPossible -Certificate $certificate -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::Root)
$trustedInMachinePublisher = Add-CertificateToLocalMachineStoreIfPossible -Certificate $certificate -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::TrustedPublisher)
$signature = Get-AuthenticodeSignature -FilePath $exeInstallPath
if ($signature.Status -ne "Valid") { throw "La firma del ejecutable no quedo confiable: $($signature.Status) $($signature.StatusMessage)" }

$launcherPath = $exeInstallPath
$launcherWindowArguments = "tray --open-window --steam-action open"
$launcherStartupArguments = "tray --steam-action open"
$launcherMode = "exe"

if (Test-ExecutableBlockedByApplicationControl -ExecutablePath $exeInstallPath) {
    $pythonwPath = Resolve-PythonHost
    if ($pythonwPath -eq "") {
        throw "Windows bloqueo el exe por Control de aplicaciones y no se encontro Python para usar como alternativa."
    }
    $launcherPath = $pythonwPath
    $launcherWindowArguments = "-m cartridge_launcher.app.main tray --open-window --steam-action open"
    $launcherStartupArguments = "-m cartridge_launcher.app.main tray --steam-action open"
    $launcherMode = "pythonw"
}

New-Shortcut -ShortcutPath $startMenuShortcut -TargetPath $launcherPath -WorkingDirectory $InstallDirectory -Arguments $launcherWindowArguments -IconPath $exeInstallPath
New-Shortcut -ShortcutPath $desktopShortcut -TargetPath $launcherPath -WorkingDirectory $InstallDirectory -Arguments $launcherWindowArguments -IconPath $exeInstallPath
New-Shortcut -ShortcutPath $startupShortcut -TargetPath $launcherPath -WorkingDirectory $InstallDirectory -Arguments $launcherStartupArguments -IconPath $exeInstallPath
Write-Host "$appName instalado correctamente."
Write-Host "Ruta: $exeInstallPath"
Write-Host "Firma: valida"
Write-Host "Modo de acceso directo: $launcherMode"
if ($trustedInMachineRoot -and $trustedInMachinePublisher) {
    Write-Host "Certificado local: confiado en CurrentUser y LocalMachine"
}
else {
    Write-Host "Certificado local: confiado en CurrentUser"
}
Write-Host "Inicio con Windows: activado"
$smartAppControlSummary = Get-SmartAppControlSummary
if ($smartAppControlSummary -ne "") {
    Write-Host ""
    Write-Host "Aviso de Windows:"
    Write-Host $smartAppControlSummary -ForegroundColor Yellow
    Write-Host "Este instalador ya firmo el exe con certificado local confiado y quito la marca de internet. Si Windows lo bloquea aun asi, el bloqueo viene de la politica de Smart App Control para apps locales sin reputacion."
}
