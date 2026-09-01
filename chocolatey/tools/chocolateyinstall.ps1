$ErrorActionPreference = 'Stop'

# ShortGeek ships an Inno Setup installer. The package downloads it from the GitHub release for the
# matching tag and verifies it against a SHA-256 checksum rather than embedding the binary. Because
# nothing is embedded, this package must NOT contain a tools\VERIFICATION.txt - that file is only
# for packages that ship a binary inside the nupkg, and including one is what the USP 8.0.0
# submission was rejected for.
$packageArgs = @{
  packageName    = 'shortgeek'
  fileType       = 'exe'
  url            = 'https://github.com/techygeekshome/ShortGeek/releases/download/v1.0.2/ShortGeekSetup.exe'
  checksum       = '100af9f43d88e32a2d9d4127df60f4f4037ee6bfb1e8cb65a88f98740936a91d'
  checksumType   = 'sha256'
  silentArgs     = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-'
  validExitCodes = @(0, 3010, 1641)
}

Install-ChocolateyPackage @packageArgs
