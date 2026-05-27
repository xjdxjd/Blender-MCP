@echo off
REM === Blender MCP 插件打包脚本 ===
REM 用法: 双击运行，或命令行执行此脚本
REM 生成可被 Blender 直接安装的 blender_mcp.zip

setlocal
set SCRIPT_DIR=%~dp0
set TEMP_DIR=%SCRIPT_DIR%_temp_pack
set OUTPUT=%SCRIPT_DIR%blender_mcp.zip

echo [1/3] 创建临时目录...
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%\blender_mcp"

echo [2/3] 复制插件文件...
copy "%SCRIPT_DIR%__init__.py" "%TEMP_DIR%\blender_mcp\__init__.py" >nul
copy "%SCRIPT_DIR%connection.py" "%TEMP_DIR%\blender_mcp\connection.py" >nul

echo [3/3] 打包为 ZIP...
if exist "%OUTPUT%" del "%OUTPUT%"
powershell -Command "Compress-Archive -Path '%TEMP_DIR%\blender_mcp' -DestinationPath '%OUTPUT%' -Force"

rmdir /s /q "%TEMP_DIR%"
echo.
echo ==============================
echo   打包完成！
echo   文件: %OUTPUT%
echo   在 Blender 中安装此 ZIP 即可
echo ==============================
pause