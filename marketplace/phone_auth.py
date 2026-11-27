"""Вход и регистрация по номеру телефона с кодом подтверждения.

Прототип: SMS не отправляется. Код хранится в сессии пользователя,
а в демо-режиме (PHONE_AUTH_DEMO = True) показывается прямо на странице.
Чтобы подключить настоящие SMS, достаточно отправлять `code`
в функции start_verification через SMS-сервис и выключить демо-режим.
"""
import hashlib
import re
import secrets
import time

from django.conf import settings

SESSION_KEY = 'phone_verification'
CODE_TTL = 5 * 60          # код действует 5 минут
MAX_ATTEMPTS = 5           # после 5 неверных попыток нужно запросить новый код
RESEND_COOLDOWN = 30       # новый код можно запросить не чаще раза в 30 секунд


class VerificationError(Exception):
    """Код неверный, устарел или не запрашивался."""


def normalize_phone(raw):
    """Приводит номер к виду +7XXXXXXXXXX. Возвращает None, если номер некорректный.

    Принимает: +7 701 123 45 67, 8 (701) 123-45-67, 77011234567, 7011234567.
    """
    digits = re.sub(r'\D', '', raw or '')
    if len(digits) == 10:
        digits = '7' + digits
    elif len(digits) == 11 and digits[0] in '78':
        digits = '7' + digits[1:]
    else:
        return None
    return '+' + digits


def format_phone(phone):
    """+77011234567 -> +7 701 123 45 67 (для показа)."""
    if not phone or len(phone) != 12:
        return phone or ''
    d = phone[2:]
    return f'+7 {d[:3]} {d[3:6]} {d[6:8]} {d[8:]}'


def _hash(code):
    return hashlib.sha256(f'{settings.SECRET_KEY}:{code}'.encode()).hexdigest()


def start_verification(request, phone, purpose, payload=None):
    """Создаёт новый код и сохраняет его в сессии. Возвращает код (для демо-режима)."""
    code = f'{secrets.randbelow(10000):04d}'
    request.session[SESSION_KEY] = {
        'phone': phone,
        'purpose': purpose,          # 'login' или 'register'
        'payload': payload or {},    # данные регистрации до подтверждения
        'code_hash': _hash(code),
        'expires': time.time() + CODE_TTL,
        'sent_at': time.time(),
        'attempts': 0,
        'demo_code': code if getattr(settings, 'PHONE_AUTH_DEMO', True) else None,
    }
    return code


def pending(request):
    """Текущая ожидающая проверка или None."""
    return request.session.get(SESSION_KEY)


def can_resend(request):
    data = pending(request)
    return bool(data) and time.time() - data['sent_at'] >= RESEND_COOLDOWN


def resend(request):
    data = pending(request)
    if not data:
        raise VerificationError('Request a new code.')
    return start_verification(request, data['phone'], data['purpose'], data['payload'])


def check_code(request, code):
    """Проверяет код. При успехе удаляет проверку из сессии и возвращает её данные."""
    data = pending(request)
    if not data:
        raise VerificationError('Request a new code.')
    if time.time() > data['expires'] or data['attempts'] >= MAX_ATTEMPTS:
        request.session.pop(SESSION_KEY, None)
        raise VerificationError('The code has expired. Request a new one.')
    if not secrets.compare_digest(_hash((code or '').strip()), data['code_hash']):
        data['attempts'] += 1
        request.session[SESSION_KEY] = data
        raise VerificationError('Wrong code.')
    request.session.pop(SESSION_KEY, None)
    return data


def cancel(request):
    request.session.pop(SESSION_KEY, None)
