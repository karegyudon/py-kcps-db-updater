@echo off
setlocal enabledelayedexpansion
chcp 936 >nul

echo ========================================
echo    KC 舰队数据库自动更新工具
echo ========================================
echo.

set DIFF_FOUND=0

if exist api_start2.json (
    if exist api_start2.json.old (
        del /f /q api_start2.json.old
    )
    echo [Step 1] 将现有 api_start2.json 改名为 api_start2.json.old
    ren api_start2.json api_start2.json.old
) else (
    echo [Step 1] 未找到 api_start2.json，将直接下载最新数据
)

echo.
echo [Step 2] 下载最新的 api_start2.json 和映射文件...
python update_mappings.py
if errorlevel 1 (
    echo [ERROR] 下载数据失败
    pause
    exit /b 1
)

echo.
if not exist api_start2.json (
    echo [WARN] api_start2.json 下载失败，保持原状
    pause
    exit /b 1
)

echo [Step 3] 对比文件差异...
if not exist api_start2.json.old (
    echo [INFO] 首次运行，无历史版本，直接进入更新
    set DIFF_FOUND=1
) else (
    fc /b api_start2.json.old api_start2.json >nul 2>nul
    if errorlevel 1 (
        echo [INFO] 检测到文件变化，将更新数据库
        set DIFF_FOUND=1
    ) else (
        echo [INFO] 文件无变化，无需更新数据库
    )
)

if "!DIFF_FOUND!"=="1" (
    echo.
    echo [Step 4] 更新数据库...
    python update_db_from_json.py
    if errorlevel 1 (
        echo [ERROR] 数据库更新失败
        pause
        exit /b 1
    )
    echo.
    echo ========================================
    echo    数据库已更新完成！
    echo ========================================
) else (
    echo.
    echo ========================================
    echo    无需更新，数据库已是最新
    echo ========================================
)

pause
endlocal
