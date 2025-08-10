@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ------------------------------------------------------------
REM  github.bat
REM  Script para versionar e publicar alterações no GitHub.
REM  Uso:
REM    github.bat [REPO_URL] [COMMIT_MSG]
REM  Exemplos:
REM    github.bat https://github.com/usuario/Agentes_Contabeis.git "chore: initial commit"
REM    github.bat
REM      (se o remoto já existir, apenas commita e faz push)
REM ------------------------------------------------------------

cd /d "%~dp0"

set "REPO_URL=%~1"
set "COMMIT_MSG=%~2"

REM Parametro fixo (DEFAULT) para o repositório remoto deste projeto
set "DEFAULT_REPO_URL=https://github.com/carloseducorinto/agentes_contabeis.git"
if not defined REPO_URL set "REPO_URL=%DEFAULT_REPO_URL%"

REM Mensagem de commit default com timestamp sanitizado
if not defined COMMIT_MSG (
  set "TS=%DATE%_%TIME%"
  set "TS=!TS:/=-!"
  set "TS=!TS::=-!"
  set "TS=!TS:.=-!"
  set "TS=!TS:,=-!"
  set "TS=!TS: =_!"
  set "COMMIT_MSG=chore: update (!TS!)"
)

echo.
echo [1/6] Verificando Git...
git --version >NUL 2>&1
if errorlevel 1 (
  echo ERRO: Git nao encontrado no PATH.
  echo Instale o Git em https://git-scm.com/download/win
  exit /b 1
)

echo [2/6] Inicializando repositório (se necessario)...
if not exist .git (
  git init -b main || exit /b 1
)

REM Config local opcional via variaveis de ambiente
for /f "usebackq delims=" %%A in (`git config --get user.name 2^>NUL`) do set "_GUN=%%A"
for /f "usebackq delims=" %%A in (`git config --get user.email 2^>NUL`) do set "_GUE=%%A"
if not defined _GUN if defined GIT_USER  git config user.name  "%GIT_USER%"
if not defined _GUE if defined GIT_EMAIL git config user.email "%GIT_EMAIL%"

echo [3/6] Preparando stage...
git add -A

echo [4/6] Criando commit...
git commit -m "%COMMIT_MSG%" >NUL 2>&1
if errorlevel 1 (
  echo Nenhuma alteracao para commitar. Seguindo adiante.
)

echo [5/6] Configurando remoto 'origin'...
git remote get-url origin >NUL 2>&1
if errorlevel 1 (
  echo 'origin' ausente. Configurando para: %REPO_URL%
  git remote add origin "%REPO_URL%" || exit /b 1
)

for /f "usebackq delims=" %%U in (`git remote get-url origin`) do set "ORIGIN_URL=%%U"

echo [6/6] Enviando para %ORIGIN_URL% (branch main)...
git push -u origin main
if errorlevel 1 (
  echo Push falhou. Tentando sincronizar via pull --rebase e reenviar...
  git pull --rebase origin main || exit /b 1
  git push -u origin main || exit /b 1
)

echo.
echo Sucesso! Alteracoes publicadas em: %ORIGIN_URL%
endlocal
exit /b 0


