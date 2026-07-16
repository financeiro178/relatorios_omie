@echo off
chcp 65001 >nul
title Analise Financeira OMIE
cd /d "%~dp0"

echo ============================================================
echo   Analise Financeira OMIE
echo ============================================================
echo.

REM Procura o Python (py launcher ou python no PATH)
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYEXE=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYEXE=python"
    ) else (
        echo [ERRO] Python nao encontrado. Instale em https://www.python.org/downloads/
        echo Marque a opcao "Add Python to PATH" durante a instalacao.
        pause
        exit /b 1
    )
)

echo Iniciando servidor... o navegador abrira sozinho.
echo Para encerrar, feche esta janela.
echo.
%PYEXE% "%~dp0server.py"
pause
