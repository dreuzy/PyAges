@echo off
setlocal
cd /d "%~dp0\..\.."
if "%~1"=="" (
  echo Usage: scripts\windows\reproduce_article.bat OUTPUT_DIRECTORY [extra arguments]
  exit /b 2
)
set "ARTICLE_OUTPUT=%~f1"
shift
python -u -m scripts.reproduce_article resume --output "%ARTICLE_OUTPUT%" %*
exit /b %ERRORLEVEL%
