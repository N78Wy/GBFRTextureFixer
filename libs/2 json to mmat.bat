@echo off
setlocal

set "scriptDir=%~dp0"

set "inputFile=%~1"
set "inputDir=%~dp1"
set "inputName=%~n1"

set "flatcExe=%scriptDir%flatc.exe"
set "schemaFile=%scriptDir%MMat_ModelMaterial.fbs"


Call "%flatcExe%" -b "%schemaFile%" "%inputFile%"


set "binFile=%inputDir%%inputName%.bin"
set "mmatFile=%inputDir%%inputName%.mmat"

if exist "%binFile%" (
ren "%binFile%" "%inputName%.mmat"
echo Successfully created: %inputName%.mmat
) else (
echo Error: .bin file was not generated.
)

echo.
echo Done.
echo.

endlocal
