@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title GomokuFloat 安装

echo ============================================
echo   GomokuFloat 安装
echo ============================================
echo.

set "PYEXE="
where python >nul 2>nul
if not errorlevel 1 (set "PYEXE=python" & goto :havepy)
where py >nul 2>nul
if not errorlevel 1 (set "PYEXE=py -3" & goto :havepy)
echo [x] 未找到 Python。请先安装 Python 3.10+，并勾选 "Add to PATH"。
pause
exit /b 1

:havepy
echo [1/4] Python: %PYEXE%

if exist ".venv\Scripts\python.exe" goto :havevenv
echo       创建虚拟环境 .venv ...
%PYEXE% -m venv .venv
if errorlevel 1 (
    echo [x] 虚拟环境创建失败。
    pause
    exit /b 1
)
:havevenv

set "PIP_CACHE_DIR=%~dp0.cache\pip"
set "TMP=%~dp0.cache\tmp"
set "TEMP=%~dp0.cache\tmp"
if not exist ".cache\tmp" mkdir ".cache\tmp" >nul 2>nul

echo [2/4] 安装依赖 PyQt6 / pygomo-lib ...
".venv\Scripts\python.exe" -m pip install --upgrade pip --no-cache-dir -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt --no-cache-dir -q
if errorlevel 1 (
    echo [x] 依赖安装失败，请检查网络。
    pause
    exit /b 1
)

echo [3/4] 检查引擎 ...
if exist "engine\pbrain-rapfi-windows-avxvnni.exe" goto :haveexe
if exist "engine\pbrain-rapfi-windows-avx2.exe" goto :haveexe
if exist "engine\pbrain-rapfi-windows-sse.exe" goto :haveexe
echo.
echo [!] 未找到 engine\pbrain-rapfi-*.exe
echo     请下载 Rapfi 后解压，把 pbrain-rapfi-windows-avx2.exe 改名为 rapfi.exe
echo     或直接保留原名放到 engine\ 目录，并保留同目录的 config.toml 与权重文件。
echo     下载页: https://github.com/dhbloo/rapfi/releases
echo.
pause
exit /b 1

:haveexe
if exist "engine\config.toml" goto :havecfg
echo.
echo [!] 未找到 engine\config.toml
echo     Rapfi 需要配置文件与 NNUE 权重才能启动，请把整个解压目录的内容放进 engine\。
echo.
pause
exit /b 1

:havecfg
echo       引擎与配置就绪

echo [4/4] 运行验证 ...
".venv\Scripts\python.exe" tools\validate_m0.py
if errorlevel 1 (
    echo [!] 引擎验证未通过。
    pause
    exit /b 1
)

echo.
echo ============================================
echo   安装完成，双击 run.bat 启动
echo ============================================
pause
