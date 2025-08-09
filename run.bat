@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

rem ---------- cores ANSI ----------
for /f "delims=" %%A in ('echo prompt $E^| cmd') do set "ESC=%%A"
if defined ESC (
  set "RESET=%ESC%[0m"
  set "BOLD=%ESC%[1m"
  set "RED=%ESC%[31m"
  set "GREEN=%ESC%[32m"
  set "YELLOW=%ESC%[33m"
  set "CYAN=%ESC%[36m"
) else (
  set "RESET=" & set "BOLD=" & set "RED=" & set "GREEN=" & set "YELLOW=" & set "CYAN="
)

rem ---------- parametros ----------
set "DIR_XML=%~1"
if "%DIR_XML%"=="" set "DIR_XML=data\exemplos"

set "REGIME=%~2"
set "LOG_LEVEL=%~3"
if "%LOG_LEVEL%"=="" set "LOG_LEVEL=INFO"

set "LOGDIR=logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
set "SUMMARY=%LOGDIR%\summary.csv"
> "%SUMMARY%" echo file,ok,needs_review,motivo

echo.
echo %BOLD%================== CONFIG ==================%RESET%
echo Pasta XML........: %CYAN%%DIR_XML%%RESET%
echo Regime...........: %CYAN%%REGIME%%RESET%
echo Log level........: %CYAN%%LOG_LEVEL%%RESET%
echo Logs em..........: %CYAN%%LOGDIR%%RESET%
echo Summary..........: %CYAN%%SUMMARY%%RESET%
echo %BOLD%=============================================%RESET%
echo.

rem ---------- resolver runner ----------
where uv >nul 2>&1 && goto USE_UV
where python >nul 2>&1 && goto USE_PY
echo %RED%[ERRO]%RESET% Nem "uv" nem "python" encontrados no PATH.
exit /b 2
:USE_UV
set "RUNNER=uv run -m"
goto RUNNER_OK
:USE_PY
set "RUNNER=python -m"
:RUNNER_OK

rem ---------- validar pasta ----------
if not exist "%DIR_XML%" (
  echo %RED%[ERRO]%RESET% Pasta nao existe: "%DIR_XML%"
  exit /b 3
)

rem ---------- contadores ----------
set /a TOTAL=0
set /a OK=0
set /a FAIL=0
set /a REVIEW=0
set "STARTTIME=%time%"

rem não passar --regime * para o CLI
set "REGIME_PARAM="
if not "%REGIME%"=="" if /I not "%REGIME%"=="*" set "REGIME_PARAM=--regime %REGIME%"

echo Procurando XMLs em "%CYAN%%DIR_XML%%RESET%" (recursivo)...
echo.

rem ---------- loop principal ----------
for /R "%DIR_XML%" %%F in (*.xml) do (
  set /a TOTAL+=1
  echo %BOLD%========= %%~nxF =========%RESET%

  rem 1a execucao
  cmd /c %RUNNER% src.app.run_graph --xml "%%~fF" --log-level %LOG_LEVEL% %REGIME_PARAM% > "%TEMP%\run_graph_output.txt"
  set "EC=!ERRORLEVEL!"
  type "%TEMP%\run_graph_output.txt" 2>nul
  copy /Y "%TEMP%\run_graph_output.txt" "%LOGDIR%\%%~nF.json" >nul 2>&1

  rem se a app pedir revisao (codigo 5), chama sub-rotina e atualiza EC
  if "!EC!"=="5" (
    set /a REVIEW+=1
    call :HANDLE_REVIEW "%%~fF" "%%~nF"
    set "EC=!ERRORLEVEL!"
  )

  rem tratamento de retorno
  if "!EC!"=="0" (
    set /a OK+=1
    echo %GREEN%[OK]%RESET% Resultado salvo em "%LOGDIR%\%%~nF.json"
  ) else (
    if "!EC!"=="5" (
      echo %YELLOW%[PENDENTE]%RESET% Aguardando revisao ^(arquivo mantido em "%LOGDIR%\%%~nF.json"^)
    ) else (
      set /a FAIL+=1
      echo %RED%[FALHA]%RESET% Veja "%LOGDIR%\%%~nF.json"
    )
  )

  rem registrar no summary
  powershell -NoProfile -Command ^
    "$p = '%LOGDIR%\%%~nF.json'; if (Test-Path -LiteralPath $p) { " ^
    " $j = Get-Content -Raw -LiteralPath $p | ConvertFrom-Json; " ^
    " $ok=[bool]$j.ok; $nr=[bool]$j.classificacao_needs_review; $mot=$j.classificacao_review_reason; " ^
    " if($mot){ $mot = ($mot -replace '\r?\n',' ' -replace ',',';') } else { $mot='' } ; " ^
    " '{0},{1},{2},{3}' -f '%%~nxF.json',$ok,$nr,$mot | Out-File -FilePath '%SUMMARY%' -Append -Encoding utf8 }"

  echo.
)

if %TOTAL%==0 (
  echo %YELLOW%Nenhum arquivo *.xml encontrado em "%DIR_XML%".%RESET%
  exit /b 4
)

set "ENDTIME=%time%"

echo %BOLD%================== SUMARIO ==================%RESET%
echo Total de arquivos.....: %CYAN%%TOTAL%%RESET%
echo Sucessos (OK).........: %GREEN%%OK%%RESET%
echo Falhas (FAIL).........: %RED%%FAIL%%RESET%
echo Pedem revisao.........: %YELLOW%%REVIEW%%RESET%
echo Summary...............: %CYAN%%SUMMARY%%RESET%
echo Inicio................: %CYAN%%STARTTIME%%RESET%
echo Fim...................: %CYAN%%ENDTIME%%RESET%
echo %BOLD%================================================%RESET%
echo.
echo Concluido.
exit /b 0

rem =========================================================
rem ============= SUB-ROTINA: HANDLE_REVIEW ================
rem args: %1 = caminho XML completo, %2 = base name (sem ext)
:HANDLE_REVIEW
setlocal EnableExtensions EnableDelayedExpansion
set "XMLFULL=%~1"
set "BASENAME=%~2"
echo %YELLOW%[REVIEW]%RESET% Revisao humana necessaria para "!BASENAME!.xml"
echo.

rem Perguntas (sem CFOP)
set /p REGIME=Regime (*^|simples^|presumido^|real): 
set /p CDEB=Conta Debito (numero): 
set /p CCRD=Conta Credito (numero): 
set /p JUST=Justificativa base: 
set /p CONF=Confianca (0.0 a 1.0): 

rem JSON temporario
set "RJSON=%TEMP%\review_!BASENAME!.json"
> "!RJSON!" echo {
>> "!RJSON!" echo   "human_review_input": {
>> "!RJSON!" echo     "regime": "!REGIME!",
>> "!RJSON!" echo     "conta_debito": "!CDEB!",
>> "!RJSON!" echo     "conta_credito": "!CCRD!",
>> "!RJSON!" echo     "justificativa_base": "!JUST!",
>> "!RJSON!" echo     "confianca": !CONF!
>> "!RJSON!" echo   }
>> "!RJSON!" echo }

rem não passar --regime * para o CLI
set "REGIME_ARG="
if not "!REGIME!"=="" if /I not "!REGIME!"=="*" set "REGIME_ARG=--regime !REGIME!"

echo Reexecutando com revisao: "!RJSON!"
cmd /c %RUNNER% src.app.run_graph --xml "!XMLFULL!" --log-level %LOG_LEVEL% !REGIME_ARG! --review-json "!RJSON!" > "%TEMP%\run_graph_output.txt"
set "EC=!ERRORLEVEL!"
type "%TEMP%\run_graph_output.txt" 2>nul
copy /Y "%TEMP%\run_graph_output.txt" "%LOGDIR%\!BASENAME!.json" >nul 2>&1

endlocal & exit /b %EC%
