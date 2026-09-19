param([string]$PythonExecutable = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
foreach ($directory in @('RuntimeTemp', 'Cache', 'Build')) {
    New-Item -ItemType Directory -Path (Join-Path $projectRoot $directory) -Force | Out-Null
}
$env:TEMP = Join-Path $projectRoot 'RuntimeTemp'
$env:TMP = $env:TEMP
$env:PYINSTALLER_CONFIG_DIR = Join-Path $projectRoot 'Cache\pyinstaller'
if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $projectRoot 'Runtime\Python3147\python.exe'
}
& $pythonExecutable -B -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
$frontendData = (Join-Path $projectRoot 'frontend') + ';frontend'
& $pythonExecutable -m PyInstaller --noconfirm --onedir --windowed --name EmailAssistant --distpath Program --workpath Build\pyinstaller --specpath Build --paths $projectRoot --add-data $frontendData --hidden-import PIL._tkinter_finder launch_desktop.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
$programPath = Join-Path $projectRoot 'Program\EmailAssistant\EmailAssistant.exe'
$verificationProcess = Start-Process -FilePath $programPath -ArgumentList '--self-test' -WorkingDirectory $projectRoot -WindowStyle Hidden -Wait -PassThru
if ($verificationProcess.ExitCode -ne 0) { throw 'Bundled executable self-test failed.' }
Get-Content -LiteralPath (Join-Path $projectRoot 'Build\desktop-self-test.json')
