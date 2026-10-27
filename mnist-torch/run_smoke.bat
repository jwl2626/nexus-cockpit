@echo off
rem 无数据自检：验证训练/评估/保存/导出/推理全链路
setlocal

if not defined PY (
  if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
  ) else (
    set "PY=python"
  )
)

set "PYTHONPATH=%~dp0src"
"%PY%" -m mnist_torch.cli smoke %*
exit /b %ERRORLEVEL%
