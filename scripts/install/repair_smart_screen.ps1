param(
    [string]$InstallDirectory = "$([Environment]::GetFolderPath('LocalApplicationData'))\Programs\3SD",
    [string]$CertificatePath = "",
    [switch]$Elevate
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-ElevatedSelf {
    if (-not $Elevate -or (Test-IsAdministrator)) {
        return
    }

    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-InstallDirectory", "`"$InstallDirectory`""
    )
    if ($CertificatePath -ne "") {
        $arguments += @("-CertificatePath", "`"$CertificatePath`"")
    }

    Start-Process powershell.exe -Verb RunAs -Wait -ArgumentList $arguments
    exit $LASTEXITCODE
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
        if ($existing.Count -eq 0) {
            $store.Add($Certificate)
        }
    }
    finally {
        $store.Close()
    }
}

function Unblock-PathTree {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
    if ((Get-Item -LiteralPath $Path).PSIsContainer) {
        Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
    }
}

Invoke-ElevatedSelf

$exePath = Join-Path $InstallDirectory "3SD.exe"
if ($CertificatePath -eq "") {
    $CertificatePath = Join-Path $InstallDirectory "3SD-LocalDev.cer"
}

if (-not (Test-Path -LiteralPath $exePath)) {
    throw "No se encontro 3SD.exe en: $InstallDirectory"
}
if (-not (Test-Path -LiteralPath $CertificatePath)) {
    throw "No se encontro el certificado local en: $CertificatePath"
}

Unblock-PathTree -Path $InstallDirectory
$certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2((Resolve-Path -LiteralPath $CertificatePath).Path)

Add-CertificateToStore -Certificate $certificate -StoreLocation ([System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser) -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::Root)
Add-CertificateToStore -Certificate $certificate -StoreLocation ([System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser) -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::TrustedPublisher)

if (Test-IsAdministrator) {
    Add-CertificateToStore -Certificate $certificate -StoreLocation ([System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine) -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::Root)
    Add-CertificateToStore -Certificate $certificate -StoreLocation ([System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine) -StoreName ([System.Security.Cryptography.X509Certificates.StoreName]::TrustedPublisher)
}

$signature = Get-AuthenticodeSignature -FilePath $exePath
if ($signature.Status -ne "Valid") {
    throw "La firma sigue sin ser confiable: $($signature.Status) $($signature.StatusMessage)"
}

Write-Host "Bloqueo local reparado."
Write-Host "Ruta: $exePath"
Write-Host "Firma: valida"
Write-Host "Certificado: $($certificate.Thumbprint)"
if (Test-IsAdministrator) {
    Write-Host "Confianza instalada en CurrentUser y LocalMachine."
}
else {
    Write-Host "Confianza instalada en CurrentUser. Ejecuta con -Elevate para LocalMachine."
}
