@echo off
setlocal
set "PYTHONNOUSERSITE=1"
cd /d "%~dp0\..\.."
if "%~1"=="" (
  echo Usage: scripts\windows\reproduce_article.bat OUTPUT_DIRECTORY [extra arguments]
  exit /b 2
)
set "ARTICLE_OUTPUT=%~f1"
shift
rem SHIFT updates %%1..%%9 but, by cmd.exe design, does not update %%*.
rem The launcher accepts at most eight optional tokens, which covers every
rem reproduce_article option after the mandatory output directory.
python -u -m scripts.article.reproduce_article resume --output "%ARTICLE_OUTPUT%" %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%
