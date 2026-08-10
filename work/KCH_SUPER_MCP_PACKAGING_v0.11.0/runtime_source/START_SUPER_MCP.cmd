@echo off
setlocal
set "KCH_ROOT=%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -X utf8 -u "%KCH_ROOT%launcher\run_super_mcp.py"
  exit /b %errorlevel%
)
where python >nul 2>nul
if %errorlevel%==0 (
  python -X utf8 -u "%KCH_ROOT%launcher\run_super_mcp.py"
  exit /b %errorlevel%
)
echo Python 3.11 or newer is required. 1>&2
exit /b 2
