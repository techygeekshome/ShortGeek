$ErrorActionPreference = 'Stop'

# ShortGeek ships an Inno Setup installer. The package downloads it from the GitHub release for the
# matching tag and verifies it against a SHA-256 checksum rather than embedding the binary. Because
# nothing is embedded, this package must NOT contain a tools\VERIFICATION.txt - that file is only
# for packages that ship a binary inside the nupkg, and including one is what the USP 8.0.0
# submission was rejected for.
$packageArgs = @{
  packageName    = 'shortgeek'
  fileType       = 'exe'
  url            = 'https://github.com/techygeekshome/ShortGeek/releases/download/v2.0.1/ShortGeekSetup.exe'
  checksum       = '4c257ef378fb5b12327574d477ee01a6d37e6aaf16b07a04ead0fd0ba6f5f7b6'
  checksumType   = 'sha256'
  silentArgs     = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-'
  validExitCodes = @(0, 3010, 1641)
}

Install-ChocolateyPackage @packageArgs
