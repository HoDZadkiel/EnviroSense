@echo off
rem EnviroSense HA 0.2.2-ha  flasher for Seeed XIAO ESP32C6 (Windows)
rem usage: flash.bat COM5 [full^|update]
setlocal
set "HERE=%~dp0"
set "ESPTOOL=%HERE%tools\windows\esptool.exe"
set "PREFIX=%HERE%bins\envirosense-ha-0.2.2-esp32c6"
set "PORT=%~1"
set "MODE=%~2"

if not exist "%ESPTOOL%" goto :noesptool
if not exist "%PREFIX%-merged.bin" goto :nobin

if not "%PORT%"=="" goto :haveport
echo.
echo Put the board in download mode first: hold BOOT, tap RESET, release BOOT.
echo.
set /p PORT=Your COM port, e.g. COM5: 
if "%PORT%"=="" goto :noport
:haveport

if not "%MODE%"=="" goto :havemode
echo.
echo [1] Full install  - erases the whole flash, WiFi/MQTT settings are lost
echo [2] Update only   - replaces the app, keeps settings, needs this firmware already installed
choice /c 12 /n /m "Choose 1 or 2: "
if errorlevel 2 (set "MODE=update") else (set "MODE=full")
:havemode

echo.
if /i "%MODE%"=="update" goto :update

echo [full] writing merged image to 0x0 on %PORT%
"%ESPTOOL%" --chip esp32c6 -p %PORT% -b 460800 write-flash 0x0 "%PREFIX%-merged.bin"
goto :check

:update
echo [update] writing app to 0x10000 on %PORT%
"%ESPTOOL%" --chip esp32c6 -p %PORT% -b 460800 write-flash 0x10000 "%PREFIX%-app.bin"

:check
if errorlevel 1 goto :failed
echo.
echo DONE. Press RESET once to start the new firmware.
echo First install: press RESET twice quickly after the LED lights to open the setup page.
exit /b 0

:failed
echo.
echo FAILED. Check: the COM port number, a data-capable USB cable, the board is in
echo download mode, and no other program is holding the serial port.
exit /b 1

:noesptool
echo tools\windows\esptool.exe not found. Keep the folder structure intact.
exit /b 1

:nobin
echo bins\ folder not found. Keep the folder structure intact.
exit /b 1

:noport
echo No COM port given.
exit /b 1