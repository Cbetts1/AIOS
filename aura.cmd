@echo off
REM aura.cmd — AURA OS entry point for Windows
REM Sets AURA_HOME (defaulting to %USERPROFILE%\.aura) and delegates to Python.

if "%AURA_HOME%"=="" set "AURA_HOME=%USERPROFILE%\.aura"

REM Locate python
where python3 >nul 2>&1 && (
    set "PYTHON=python3"
    goto :found
)
where python >nul 2>&1 && (
    set "PYTHON=python"
    goto :found
)

echo [aura] Error: python3 not found in PATH. >&2
exit /b 1

:found
REM Prefer the installed library copy if it exists
if exist "%AURA_HOME%\lib" set "PYTHONPATH=%AURA_HOME%\lib;%PYTHONPATH%"

%PYTHON% -m aura_os.main %*
