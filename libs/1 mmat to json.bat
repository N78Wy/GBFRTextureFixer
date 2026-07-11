@echo off
setlocal

set "scriptDir=%~dp0"

set "inputFile=%~1"
set "inputDir=%~dp1"
set "inputName=%~n1"
set "outputFile=%inputDir%%inputName%.json"

set "flatcExe=%scriptDir%flatc.exe"
set "schemaFile=%scriptDir%MMat_ModelMaterial.fbs"

echo Converting: %inputFile%
echo Output will be saved to: %outputFile%
echo Using flatc: %flatcExe%
echo Using schema: %schemaFile%

Call "%flatcExe%" --json "%schemaFile%" -- "%inputFile%" --raw-binary"

echo.
echo Done! Hakunamatata!
echo.

endlocal
