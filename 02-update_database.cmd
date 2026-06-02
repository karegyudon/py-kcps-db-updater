@echo off
chcp 936 >nul
echo === Step 2: 更新数据库 ===
python update_db_from_json.py
if errorlevel 1 (
    echo [ERROR] 数据库更新失败
    pause
    exit /b 1
)
echo === 完成 ===
pause
