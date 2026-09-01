$ErrorActionPreference = 'Stop'

# Inno Setup registers its own uninstaller. Find it through the uninstall registry key rather
# than guessing a path, so this keeps working if the install location ever changes.
$key = Get-UninstallRegistryKey -SoftwareName 'ShortGeek*'

if ($key.Count -eq 1) {
  $packageArgs = @{
    packageName    = 'shortgeek'
    fileType       = 'exe'
    file           = $key.UninstallString -replace '"', ''
    silentArgs     = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-'
    validExitCodes = @(0, 3010, 1641)
  }
  Uninstall-ChocolateyPackage @packageArgs
}
elseif ($key.Count -eq 0) {
  Write-Warning 'ShortGeek is not installed, or was installed outside of Chocolatey. Nothing to do.'
}
else {
  Write-Warning "$($key.Count) matches found for ShortGeek. Remove it manually rather than guessing:"
  $key | ForEach-Object { Write-Warning "  $($_.DisplayName) - $($_.UninstallString)" }
}
