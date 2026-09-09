param(
    [string]$InstallDirectory = "$env:LOCALAPPDATA\Programs\3SD",
    [string]$ProjectDirectory = "",
    [string[]]$Thumbprint = @(),
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($InstallDirectory).TrimEnd('\')
$stores = @('Cert:\CurrentUser\My', 'Cert:\CurrentUser\Root', 'Cert:\CurrentUser\TrustedPublisher',
            'Cert:\LocalMachine\Root', 'Cert:\LocalMachine\TrustedPublisher')
$files = @((Join-Path $root '3SD.exe'), (Join-Path $root '3SD-LocalDev.cer'))
if ($ProjectDirectory) {
    $project = [IO.Path]::GetFullPath($ProjectDirectory).TrimEnd('\')
    if (-not (Test-Path -LiteralPath (Join-Path $project 'pyproject.toml'))) { throw 'Proyecto no reconocido.' }
    $files += @((Join-Path $project 'dist\3SD.exe'), (Join-Path $project 'dist\3SD-LocalDev.cer'),
                (Join-Path $project 'dist\3SD-local-dev\3SD.exe'),
                (Join-Path $project 'dist\3SD-local-dev\3SD-LocalDev.cer'),
                (Join-Path $project 'dist\3SD-local-dev\LEEME-INSTALACION.txt'))
}
$evidence = @{}
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
    if ($file.EndsWith('.cer')) {
        $cert = [Security.Cryptography.X509Certificates.X509Certificate2]::new($file)
    } elseif ($file.EndsWith('.exe')) {
        $cert = (Get-AuthenticodeSignature -LiteralPath $file).SignerCertificate
    } else { continue }
    if ($null -ne $cert -and $cert.Subject -eq 'CN=3SD Local Dev' -and $cert.Issuer -eq $cert.Subject) {
        $evidence[$cert.Thumbprint] = $file
    }
}
foreach ($value in $Thumbprint) {
    if ($value -notmatch '^[0-9a-fA-F]{40}$') { throw 'Huella invalida.' }
    $evidence[$value.ToUpperInvariant()] = 'Huella seleccionada explicitamente tras inventario'
}
$inventory = @()
foreach ($store in $stores) {
    foreach ($cert in @(Get-ChildItem -LiteralPath $store)) {
        if ($cert.Subject -ne 'CN=3SD Local Dev') { continue }
        $codeSigning = @($cert.Extensions | Where-Object { $_ -is [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension] } |
            ForEach-Object { $_.EnhancedKeyUsages } | Where-Object Value -eq '1.3.6.1.5.5.7.3.3').Count -gt 0
        $matched = $cert.Issuer -eq $cert.Subject -and $codeSigning -and $evidence.ContainsKey($cert.Thumbprint)
        $inventory += [pscustomobject]@{
            Store = $store; Thumbprint = $cert.Thumbprint; Subject = $cert.Subject
            HasPrivateKey = $cert.HasPrivateKey; Identified = $matched
            Evidence = $evidence[$cert.Thumbprint]; Result = 'Inventariado'
        }
    }
}
$inventory = @($inventory | Sort-Object Store,Thumbprint -Unique)
$report = [pscustomobject]@{
    Time = (Get-Date).ToString('o'); Applied = [bool]$Apply
    Certificates = $inventory
    Files = @($files | ForEach-Object { [pscustomobject]@{ Path = $_; Exists = (Test-Path -LiteralPath $_); Result = 'Inventariado' } })
}
$report | ConvertTo-Json -Depth 5
if (-not $Apply) { return }
$manifest = Join-Path $root 'installation.json'
if (-not (Test-Path -LiteralPath $manifest)) { throw 'Primero prepara y verifica la instalacion Python.' }
$state = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
$runtime = [IO.Path]::GetFullPath($state.runtime)
if (-not $runtime.StartsWith($root + '\runtimes\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Entorno fuera de 3SD.' }
$python = Join-Path $runtime 'Scripts\python.exe'
& $python -I -m cartridge_launcher.app.diagnostics
if ($LASTEXITCODE -ne 0) { throw 'El diagnostico fallo. No se eliminara la instalacion anterior.' }
$reportPath = Join-Path $root 'legacy-cleanup-report.json'
if (Test-Path -LiteralPath $reportPath) {
    Copy-Item -LiteralPath $reportPath -Destination (Join-Path $root ('legacy-cleanup-' + [Guid]::NewGuid().ToString('N') + '.json'))
}
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class ThreeSdKeyCleanup {
    [DllImport("crypt32.dll", SetLastError=true)]
    static extern bool CryptAcquireCertificatePrivateKey(IntPtr cert, uint flags, IntPtr reserved,
        out IntPtr key, out uint spec, out bool release);
    [DllImport("ncrypt.dll")] static extern int NCryptDeleteKey(IntPtr key, uint flags);
    [DllImport("ncrypt.dll")] static extern int NCryptFreeObject(IntPtr key);
    public static string Remove(IntPtr cert) {
        IntPtr key; uint spec; bool release;
        // CNG only, compare the public key, and do not show provider dialogs.
        if (!CryptAcquireCertificatePrivateKey(cert, 0x40044, IntPtr.Zero, out key, out spec, out release)) {
            int error = Marshal.GetLastWin32Error();
            if (error == unchecked((int)0x80090016) || error == unchecked((int)0x8009000D)
                || error == unchecked((int)0x80092004)) return "Ausente";
            throw new Win32Exception(error);
        }
        int status = NCryptDeleteKey(key, 0x40);
        if (status != 0) {
            if (release) NCryptFreeObject(key);
            throw new Win32Exception(status);
        }
        return "Eliminada";
    }
}
'@
$removedKeys = @{}
foreach ($item in $inventory) {
    if (-not $item.Identified) { $item.Result = 'Pendiente: falta evidencia'; continue }
    try {
        $path = Join-Path $item.Store $item.Thumbprint
        if (-not (Test-Path -LiteralPath $path)) { $item.Result = 'Ausente'; continue }
        $live = Get-Item -LiteralPath $path
        if ($live.HasPrivateKey -and -not $removedKeys.ContainsKey($item.Thumbprint)) {
            $keyResult = [ThreeSdKeyCleanup]::Remove($live.Handle)
            $item | Add-Member -NotePropertyName KeyResult -NotePropertyValue $keyResult -Force
            $removedKeys[$item.Thumbprint] = $true
        }
        $storeName = Split-Path -Leaf $item.Store
        $certutilArguments = @('-f')
        if ($item.Store.StartsWith('Cert:\CurrentUser\')) { $certutilArguments += '-user' }
        $certutilArguments += @('-delstore', $storeName, $item.Thumbprint)
        & certutil.exe @certutilArguments
        if ($LASTEXITCODE -ne 0) { throw "certutil fallo con codigo $LASTEXITCODE" }
        $item.Result = 'Eliminado'
    } catch { $item.Result = 'Pendiente: ' + $_.Exception.Message }
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
}
# Exact files only. Never remove the install root, runtimes, user data or SSD content.
foreach ($item in $report.Files) {
    if (-not $item.Exists) { $item.Result = 'Ausente'; continue }
    if ($item.Path.EndsWith('.cer') -and @($inventory | Where-Object Result -like 'Pendiente*').Count -gt 0) {
        $item.Result = 'Pendiente: conservado como evidencia para repetir la limpieza'; continue
    }
    try {
        Remove-Item -LiteralPath $item.Path -Force
        $item.Result = 'Eliminado'
    } catch { $item.Result = 'Pendiente: ' + $_.Exception.Message }
}
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
Write-Host "Informe: $reportPath"
$pending = @($inventory | Where-Object Result -like 'Pendiente*').Count + @($report.Files | Where-Object Result -like 'Pendiente*').Count
if ($pending -gt 0) { Write-Warning "Quedan $pending elementos pendientes. Revisa el informe; los almacenes LocalMachine requieren administrador."; exit 2 }
