@echo off
chcp 65001 >nul
title 智单 (SmartOrder) - 包装单据智能提取系统启动器
echo ========================================================
echo   正在启动 SmartOrder (智单) - 包装制造单据智能提取中台
echo ========================================================
echo.
cd /d "%~dp0"

echo [1/2] 正在启动 Streamlit 交互演示前端...
start "" python -m streamlit run web_ui.py --server.port 8501

echo.
echo ========================================================
echo 启动完成！
echo 正在打开浏览器: http://localhost:8501
echo ========================================================
start http://localhost:8501
pause
