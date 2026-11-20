#!/bin/sh
# Запуск на сервере: миграции, статика, стартовые данные, веб-сервер.
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py seed_demo
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-80} --workers ${WEB_CONCURRENCY:-2} --access-logfile -
