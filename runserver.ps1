$pythonExe = "C:\ProgramData\anaconda3\envs\DjangoEnv2\python.exe"
$ip = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet").IPAddress
$port = 8002

if (-not (Test-Path $pythonExe)) {
    throw "Expected Django env python was not found at $pythonExe"
}

& $pythonExe manage.py runserver "${ip}:${port}"
