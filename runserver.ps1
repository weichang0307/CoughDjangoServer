#variables
$ip = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet").IPAddress
$port = 8002

#commands
conda activate env_itcough
python manage.py runserver "${ip}:${port}"