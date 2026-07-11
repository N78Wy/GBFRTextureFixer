@echo off
for /l %%i in (0,1,8) do (
    GBFRDataTools.exe extract -i "J:\SteamLibrary\steamapps\common\Granblue Fantasy Relink\data.i" -f "model/pl/pl1800/vars/%%i.mmat" -o "J:\game\gbfr\gbfr-fix-texture\libs"
)
pause