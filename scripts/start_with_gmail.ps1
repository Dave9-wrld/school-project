# Run from a terminal you control. Credentials stay in this process and its Django child.
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) {
    throw 'Django is already on port 8000. Stop that server with Ctrl+C before running this launcher.'
}
$senderAddress = Read-Host 'Gmail address to send reset emails from'
if ($senderAddress -notmatch '^[^\s@]+@[^\s@]+\.[^\s@]+$') { throw 'Enter a valid email address.' }
$appSecret = Read-Host 'Google App Password (not your normal Gmail password)' -AsSecureString
$mailVariables = @('EMAIL_BACKEND','EMAIL_HOST','EMAIL_PORT','EMAIL_USE_TLS','EMAIL_HOST_USER','EMAIL_HOST_PASSWORD','DEFAULT_FROM_EMAIL')
$previousMailEnvironment = @{}
foreach ($variableName in $mailVariables) { $previousMailEnvironment[$variableName] = [Environment]::GetEnvironmentVariable($variableName, 'Process') }
try {
    $env:EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    $env:EMAIL_HOST = 'smtp.gmail.com'
    $env:EMAIL_PORT = '587'
    $env:EMAIL_USE_TLS = 'true'
    $env:EMAIL_HOST_USER = $senderAddress.Trim()
    $env:EMAIL_HOST_PASSWORD = ([System.Net.NetworkCredential]::new('', $appSecret)).Password.Replace(' ', '')
    $env:DEFAULT_FROM_EMAIL = "Dave University <$($env:EMAIL_HOST_USER)>"
    Write-Host 'Checking Gmail connection and credentials (no email is sent)...'
    & (Join-Path $projectDirectory 'env\Scripts\python.exe') (Join-Path $projectDirectory 'manage.py') check_mail
    if ($LASTEXITCODE -ne 0) { throw 'Gmail setup failed. Check the details above and try again.' }
    Write-Host 'Starting Django with Gmail delivery. Keep this terminal open.'
    & (Join-Path $projectDirectory 'env\Scripts\python.exe') (Join-Path $projectDirectory 'manage.py') runserver 127.0.0.1:8000
} finally {
    foreach ($variableName in $mailVariables) { [Environment]::SetEnvironmentVariable($variableName, $previousMailEnvironment[$variableName], 'Process') }
    $appSecret.Dispose()
}
