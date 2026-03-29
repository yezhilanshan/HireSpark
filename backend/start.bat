@echo off
chcp 65001 >nul
echo ============================================================
echo 面试防作弊监控系统 - 后端服务启动脚本
echo ============================================================
echo.

echo [1/3] 检查虚拟环境...
call conda activate interview-anti-cheat
if errorlevel 1 (
    echo ✗ 虚拟环境激活失败
    echo 请确保已创建 interview-anti-cheat 虚拟环境
    pause
    exit /b 1
)
echo ✓ 虚拟环境已激活

echo.
echo [2/3] 检查依赖...
python -c "import flask, flask_socketio, cv2, mediapipe, psutil, yaml" 2>nul
if errorlevel 1 (
    echo ✗ 依赖检查失败，正在安装...
    pip install -r ..\requirements.txt
    if errorlevel 1 (
        echo ✗ 依赖安装失败
        pause
        exit /b 1
    )
)
echo ✓ 所有依赖已安装

echo.
echo [3/3] 启动服务...
echo ============================================================
echo 服务地址: http://localhost:5000
echo 健康检查: http://localhost:5000/health
echo 性能监控: http://localhost:5000/api/performance
echo.
echo 按 Ctrl+C 停止服务
echo ============================================================
echo.

python app.py

if errorlevel 1 (
    echo.
    echo ✗ 服务启动失败
    pause
)
