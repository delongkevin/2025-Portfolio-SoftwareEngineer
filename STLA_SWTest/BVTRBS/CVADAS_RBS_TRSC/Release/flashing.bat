rem To update this batch script, please use path for cmm script and what board type you have? Fs or leave blank to default to DK board
start /B /wait python Flashing_Lauterbach_boot_app.py "C:\JS\ws\develop\sw\Release\Tools\CMMscripts_HSDK" "fs"

rem Clean up
taskkill /IM t32marm.exe





