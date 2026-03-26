@echo off
chcp 65001 >nul
REM 面试防作弊监控系统 - 一键启动（双击运行）

echo ============================================================
echo 面试防作弊监控系统 - 一键启动
echo ============================================================
echo.
echo 正在检查环境并启动服务...
echo.

REM 使用 PowerShell 执行启动脚本
powershell -ExecutionPolicy Bypass -NoLogo -File "%~dp0start_all.ps1"

if errorlevel 1 (
    echo.
    echo ============================================================
    echo 启动失败，请检查上方的错误信息
    echo ============================================================
    echo.
    echo 常见问题:
    echo 1. 虚拟环境不存在: conda create -n interview-anti-cheat python=3.9
    echo 2. 依赖未安装: cd backend ^& pip install -r requirements.txt
    echo 3. Node.js 未安装: 从 https://nodejs.org/ 下载安装
    echo.
    echo 详细文档请查看: README_STARTUP.md
    echo.
    pause
) else (
    echo.
    echo 启动脚本执行完成
)
