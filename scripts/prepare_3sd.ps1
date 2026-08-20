param(
    [string]$Name = "3SD",
    [string]$PythonExe = "",
    [string]$InstallDirectory = "$([Environment]::GetFolderPath('LocalApplicationData'))\Programs\3SD",
    [string]$LocalCertificateSubject = "CN=3SD Local Dev",
    [string]$IconPath = ".\assets\3SD.ico",
    [switch]$SkipDependencyInstall,
    [switch]$NoStopRunningApp,
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$AppName = "3SD"
$ExeName = "$Name.exe"
$CertificateName = "3SD-LocalDev.cer"
$ExecutablePath = Join-Path $ProjectRoot "dist\$ExeName"
$CertificateOutputPath = Join-Path $ProjectRoot "dist\$CertificateName"
$PackageDirectory = Join-Path $ProjectRoot "dist\3SD-local-dev"
$ExeInstallPath = Join-Path $InstallDirectory "3SD.exe"

function Resolve-Python {
    param([string]$ExplicitPython)

    if ($ExplicitPython -ne "") {
        if (-not (Test-Path -LiteralPath $ExplicitPython) -and $null -eq (Get-Command $ExplicitPython -ErrorAction SilentlyContinue)) {
            throw "Python was not found at: $ExplicitPython"
        }
        return $ExplicitPython
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) { return "py" }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) { return "python" }

    throw "Python was not found. Install Python for Windows or pass -PythonExe with the full path to python.exe."
}

function Resolve-PythonWindowHost {
    param([string]$BuildPython)

    if ($BuildPython -ne "" -and (Test-Path -LiteralPath $BuildPython)) {
        $pythonDirectory = Split-Path -Parent (Resolve-Path -LiteralPath $BuildPython)
        foreach ($candidateName in @("pythonw.exe", "python.exe")) {
            $candidate = Join-Path $pythonDirectory $candidateName
            if (Test-Path -LiteralPath $candidate) { return $candidate }
        }
    }

    foreach ($commandName in @("pyw", "pythonw", "py", "python")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
    }

    return ""
}

function Test-IsAdministrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Stop-PreviousAppInstances {
    foreach ($processName in @($Name, "3SD")) {
        Get-Process $processName -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

function Get-LocalSigningCertificate {
    param([string]$Subject)

    $certificates = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
        Where-Object { $_.Subject -eq $Subject -and $_.NotAfter -gt (Get-Date) } |
        Sort-Object NotAfter -Descending
    if ($certificates.Count -gt 0) { return $certificates[0] }

    return New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $Subject `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyAlgorithm RSA `
        -KeyLength 3072 `
        -KeyUsage DigitalSignature `
        -NotAfter (Get-Date).AddYears(3)
}

function Add-CertificateToStore {
    param(
        [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,
        [System.Security.Cryptography.X509Certificates.StoreLocation]$StoreLocation,
        [System.Security.Cryptography.X509Certificates.StoreName]$StoreName
    )

    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($StoreName, $StoreLocation)
    try {
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        $existing = $store.Certificates.Find(
            [System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,
            $Certificate.Thumbprint,
            $false
        )
        if ($existing.Count -eq 0) { $store.Add($Certificate) }
    }
    finally {
        $store.Close()
    }
}

function Trust-LocalSigningCertificate {
    param([System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)

    Add-CertificateToStore `
        -Certificate $Certificate `
        -StoreLocation ([System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser) `
        -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::Root)
    Add-CertificateToStore `
        -Certificate $Certificate `
        -StoreLocation ([System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser) `
        -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::TrustedPublisher)

    if (Test-IsAdministrator) {
        Add-CertificateToStore `
            -Certificate $Certificate `
            -StoreLocation ([System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine) `
            -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::Root)
        Add-CertificateToStore `
            -Certificate $Certificate `
            -StoreLocation ([System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine) `
            -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::TrustedPublisher)
    }
}

function Unblock-PathTree {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { return }

    Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
    if ((Get-Item -LiteralPath $Path).PSIsContainer) {
        Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
            Unblock-File -ErrorAction SilentlyContinue
    }
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
    if (-not (Test-Path -LiteralPath $shortcutDirectory)) {
        New-Item -ItemType Directory -Path $shortcutDirectory | Out-Null
    }

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
    param([string]$Path)

    try {
        $process = Start-Process `
            -FilePath $Path `
            -ArgumentList "startup status" `
            -WorkingDirectory (Split-Path -Parent $Path) `
            -WindowStyle Hidden `
            -PassThru `
            -Wait
        return $false
    }
    catch {
        $message = $_.Exception.Message
        if ($message -match "Control de aplicaciones" -or $message -match "Application Control" -or $message -match "Smart App Control") {
            return $true
        }
        throw
    }
}

function Get-SmartAppControlSummary {
    $citool = Get-Command "citool.exe" -ErrorAction SilentlyContinue
    if ($null -eq $citool) { return "" }

    $output = & $citool.Source -lp 2>$null
    if ($LASTEXITCODE -ne 0 -or $null -eq $output) { return "" }

    $text = $output -join "`n"
    if ($text -match "VerifiedAndReputableDesktop" -and $text -match "Is Currently Enforced\s*:\s*true") {
        return "Smart App Control esta en modo activo. Windows puede bloquear builds locales aunque la firma Authenticode sea valida."
    }
    if ($text -match "VerifiedAndReputableDesktopEvaluation") {
        return "Smart App Control esta en modo evaluacion. Si Windows lo pasa a activo, puede bloquear builds locales sin reputacion publica."
    }
    return ""
}

function Build-Executable {
    $pythonCommand = Resolve-Python $PythonExe

    if (-not $NoClean) {
        foreach ($path in @(".\build", ".\dist")) {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Recurse -Force
            }
        }
    }

    if (-not $SkipDependencyInstall) {
        & $pythonCommand -m pip install --no-build-isolation -e ".[build]"
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    }

    $pyInstallerArguments = @(
        "--clean",
        "--noconfirm",
        "--name", $Name,
        "--noconsole",
        "--onefile",
        "--collect-submodules", "pystray",
        "--collect-submodules", "PIL",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--paths", ".\src",
        "--specpath", ".\build"
    )

    if ($IconPath -ne "" -and (Test-Path -LiteralPath $IconPath)) {
        $resolvedIconPath = (Resolve-Path -LiteralPath $IconPath).Path
        $pyInstallerArguments += @("--icon", $resolvedIconPath, "--add-data", "$resolvedIconPath;assets")
    }

    $pyInstallerArguments += ".\src\cartridge_launcher\app\main.py"
    & $pythonCommand -m PyInstaller @pyInstallerArguments
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

    if (-not (Test-Path -LiteralPath $ExecutablePath)) {
        throw "Build did not create executable: $ExecutablePath"
    }
}

function Sign-And-ExportCertificate {
    $certificate = Get-LocalSigningCertificate -Subject $LocalCertificateSubject
    Trust-LocalSigningCertificate -Certificate $certificate
    Unblock-File -Path $ExecutablePath -ErrorAction SilentlyContinue

    $signature = Set-AuthenticodeSignature -FilePath $ExecutablePath -Certificate $certificate -HashAlgorithm SHA256
    if ($signature.Status -ne "Valid") {
        throw "Executable signing failed: $($signature.Status) $($signature.StatusMessage)"
    }

    Export-Certificate -Cert $certificate -FilePath $CertificateOutputPath -Force | Out-Null
    return $certificate
}

function New-LocalPackage {
    if (Test-Path -LiteralPath $PackageDirectory) {
        Remove-Item -LiteralPath $PackageDirectory -Recurse -Force
    }
    New-Item -ItemType Directory -Path $PackageDirectory | Out-Null
    Copy-Item -Path $ExecutablePath -Destination (Join-Path $PackageDirectory "3SD.exe") -Force
    Copy-Item -Path $CertificateOutputPath -Destination (Join-Path $PackageDirectory $CertificateName) -Force

    @"
3SD - instalacion local

Este paquete contiene 3SD.exe y el certificado publico de desarrollo local.
Para instalar desde el repositorio, usa:

  .\Preparar-3SD.bat

Para reparar la confianza local despues de instalar, vuelve a ejecutar:

  .\Preparar-3SD.bat
"@ | Set-Content -Path (Join-Path $PackageDirectory "LEEME-INSTALACION.txt") -Encoding UTF8
}

function Install-Application {
    param(
        [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,
        [string]$BuildPythonCommand
    )

    $installRoamingAppData = [Environment]::GetFolderPath("ApplicationData")
    $installDesktop = [Environment]::GetFolderPath("DesktopDirectory")
    $startMenuDirectory = Join-Path $installRoamingAppData "Microsoft\Windows\Start Menu\Programs\3SD"
    $startMenuShortcut = Join-Path $startMenuDirectory "3SD.lnk"
    $startupShortcut = Join-Path $installRoamingAppData "Microsoft\Windows\Start Menu\Programs\Startup\3SD.lnk"
    $desktopShortcut = Join-Path $installDesktop "3SD.lnk"

    if (-not (Test-Path -LiteralPath $InstallDirectory)) {
        New-Item -ItemType Directory -Path $InstallDirectory | Out-Null
    }

    Copy-Item -Path $ExecutablePath -Destination $ExeInstallPath -Force
    Copy-Item -Path $CertificateOutputPath -Destination (Join-Path $InstallDirectory $CertificateName) -Force
    Unblock-PathTree -Path $PackageDirectory
    Unblock-PathTree -Path $InstallDirectory
    Trust-LocalSigningCertificate -Certificate $Certificate

    $signature = Get-AuthenticodeSignature -FilePath $ExeInstallPath
    if ($signature.Status -ne "Valid") {
        throw "La firma del ejecutable no quedo confiable: $($signature.Status) $($signature.StatusMessage)"
    }

    $launcherPath = $ExeInstallPath
    $launcherWindowArguments = "tray --open-window --steam-action open"
    $launcherStartupArguments = "tray --steam-action open"
    $launcherMode = "exe"

    if (Test-ExecutableBlockedByApplicationControl -Path $ExeInstallPath) {
        $pythonHost = Resolve-PythonWindowHost -BuildPython $BuildPythonCommand
        if ($pythonHost -eq "") {
            throw "Windows bloqueo 3SD.exe por Smart App Control y no se encontro Python para usar como alternativa."
        }
        $launcherPath = $pythonHost
        $launcherWindowArguments = "-m cartridge_launcher.app.main tray --open-window --steam-action open"
        $launcherStartupArguments = "-m cartridge_launcher.app.main tray --steam-action open"
        $launcherMode = "python"
    }

    New-Shortcut `
        -ShortcutPath $startMenuShortcut `
        -TargetPath $launcherPath `
        -WorkingDirectory $InstallDirectory `
        -Arguments $launcherWindowArguments `
        -IconPath $ExeInstallPath
    New-Shortcut `
        -ShortcutPath $desktopShortcut `
        -TargetPath $launcherPath `
        -WorkingDirectory $InstallDirectory `
        -Arguments $launcherWindowArguments `
        -IconPath $ExeInstallPath
    New-Shortcut `
        -ShortcutPath $startupShortcut `
        -TargetPath $launcherPath `
        -WorkingDirectory $InstallDirectory `
        -Arguments $launcherStartupArguments `
        -IconPath $ExeInstallPath

    return $launcherMode
}

if (-not $NoStopRunningApp) {
    Stop-PreviousAppInstances
}

Write-Host ""
Write-Host "3SD"
Write-Host "==="
Write-Host ""
Write-Host "Construyendo ejecutable..."
$pythonCommand = Resolve-Python $PythonExe
Build-Executable

Write-Host "Firmando ejecutable y exportando certificado..."
$localCertificate = Sign-And-ExportCertificate

Write-Host "Preparando paquete local..."
New-LocalPackage

Write-Host "Instalando en esta PC..."
$launcherMode = Install-Application -Certificate $localCertificate -BuildPythonCommand $pythonCommand

$file = Get-Item $ExecutablePath
$hash = Get-FileHash $ExecutablePath -Algorithm SHA256
Write-Host ""
Write-Host "$AppName quedo listo para usar."
Write-Host "Build: $ExecutablePath"
Write-Host "Instalacion: $ExeInstallPath"
Write-Host "Actualizado: $($file.LastWriteTime)"
Write-Host "SHA256: $($hash.Hash)"
Write-Host "Firma: valida"
Write-Host "Modo de acceso directo: $launcherMode"
if (Test-IsAdministrator) {
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
}
