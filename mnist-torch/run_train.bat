@echo off
rem 训练入口。用法：run_train.bat --config configs/cnn.json --epochs 5
setlocal

rem 优先用装了 PyTorch 的那个解释器，可用环境变量 PY 覆盖
if not defined PY (
  if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
  ) else (
    set "PY=python"
  )
)

set "PYTHONPATH=%~dp0src"
"%PY%" -m mnist_torch.cli train %*
exit /b %ERRORLEVEL%
