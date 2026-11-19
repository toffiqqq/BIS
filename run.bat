@echo off
chcp 65001 >nul
REM Запуск проекта на Windows без Docker: двойной клик по файлу или "run.bat" в терминале.
REM Нужны: Python 3.12+ и PostgreSQL (или DJANGO_DB=sqlite в .env).
cd /d "%~dp0"

if not exist venv (
    echo [1/5] Создаю виртуальное окружение...
    python -m venv venv || goto :error
)
call venv\Scripts\activate.bat

echo [2/5] Устанавливаю зависимости...
pip install -q -r requirements.txt || goto :error

if not exist .env (
    copy .env.example .env >nul
    echo.
    echo Создан файл .env. Впишите в него пароль от PostgreSQL ^(POSTGRES_PASSWORD^)
    echo или раскомментируйте DJANGO_DB=sqlite, сохраните и запустите run.bat ещё раз.
    notepad .env
    pause
    exit /b
)

echo [3/5] Применяю миграции...
python manage.py migrate || goto :error
echo [4/5] Загружаю демо-данные...
python manage.py seed_demo || goto :error
echo [5/5] Запускаю сервер: http://127.0.0.1:8000  (остановить: Ctrl+C)
start "" http://127.0.0.1:8000
python manage.py runserver
exit /b

:error
echo.
echo Ошибка. Прочитайте сообщение выше (частые причины — в README.md, раздел "Проблемы").
pause
