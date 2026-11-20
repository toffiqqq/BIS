#!/usr/bin/env bash
# Запуск проекта на macOS/Linux без Docker:  bash run.sh
set -e
cd "$(dirname "$0")"
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Создан .env — впишите POSTGRES_PASSWORD (или раскомментируйте DJANGO_DB=sqlite) и запустите снова."
  exit 1
fi
python manage.py migrate
python manage.py seed_demo
echo "Сервер: http://127.0.0.1:8000  (остановить: Ctrl+C)"
python manage.py runserver
