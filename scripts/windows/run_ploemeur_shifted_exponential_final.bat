@echo off
setlocal
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"

if not exist "results\final_article_simulations\ploemeur_shifted_exponential_final" mkdir "results\final_article_simulations\ploemeur_shifted_exponential_final"

echo [%date% %time%] Starting the four-case Ploemeur shifted-exponential campaign.
echo Existing pilot and chain files will be reused after an interruption.
echo No Holten or other Ploemeur simulation is launched.

python -m scripts.article.run_ploemeur_shifted_exponential_final all --workers 5 1> "results\final_article_simulations\ploemeur_shifted_exponential_final\batch.stdout.log" 2> "results\final_article_simulations\ploemeur_shifted_exponential_final\batch.stderr.log"
set "PLOEMEUR_EXIT=%ERRORLEVEL%"

if not "%PLOEMEUR_EXIT%"=="0" (
  echo Campaign stopped with exit code %PLOEMEUR_EXIT%.
  echo Inspect results\final_article_simulations\ploemeur_shifted_exponential_final\batch.stderr.log
  exit /b %PLOEMEUR_EXIT%
)

echo [%date% %time%] Campaign complete.
echo Report: results\final_article_simulations\ploemeur_shifted_exponential_final\PLOEMEUR_SHIFTED_EXPONENTIAL_FINAL.md
echo Figure: results\final_article_simulations\ploemeur_shifted_exponential_final\figure4_ploemeur_final.png
exit /b 0
