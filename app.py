from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / 'data' / 'members.json'

ADMIN_CONTACT = os.getenv('ADMIN_CONTACT', '010-2923-2912 신무광')
REQUEST_WINDOW_SECONDS = int(os.getenv('REQUEST_WINDOW_SECONDS', '300'))
MAX_REQUESTS_PER_WINDOW = int(os.getenv('MAX_REQUESTS_PER_WINDOW', '20'))

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

_request_log: dict[str, deque[float]] = defaultdict(deque)


def load_members() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f'종원 데이터 파일을 찾을 수 없습니다: {DATA_PATH}')
    return json.loads(DATA_PATH.read_text(encoding='utf-8'))


MEMBERS = load_members()
MEMBER_INDEX: dict[tuple[str, str], dict[str, Any]] = {}
for member in MEMBERS:
    phone = re.sub(r'\D', '', member.get('phone', ''))
    for alias in member.get('aliases', []):
        normalized_alias = re.sub(r'\s+', '', alias or '')
        if normalized_alias and phone:
            MEMBER_INDEX[(normalized_alias, phone)] = member


def normalize_name(name: str) -> str:
    return re.sub(r'\s+', '', (name or '').strip())



def normalize_phone(phone: str) -> str:
    return re.sub(r'\D', '', phone or '')



def client_ip() -> str:
    return request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()



def is_rate_limited(ip: str) -> bool:
    now = time.time()
    history = _request_log[ip]
    while history and now - history[0] > REQUEST_WINDOW_SECONDS:
        history.popleft()
    if len(history) >= MAX_REQUESTS_PER_WINDOW:
        return True
    history.append(now)
    return False


@app.get('/')
def index() -> str:
    return render_template('index.html')


@app.get('/healthz')
def healthz():
    return jsonify({'ok': True, 'member_count': len(MEMBERS)})


@app.post('/api/check-member')
def check_member():
    ip = client_ip()
    if is_rate_limited(ip):
        return jsonify({
            'ok': False,
            'message': '조회 요청이 너무 많습니다. 잠시 후 다시 시도해 주십시오.'
        }), 429

    payload = request.get_json(silent=True) or {}
    input_name = (payload.get('name') or '').strip()
    input_phone = payload.get('phone') or ''

    normalized_name = normalize_name(input_name)
    normalized_phone = normalize_phone(input_phone)

    if not normalized_name or not normalized_phone:
        return jsonify({
            'ok': False,
            'message': '성명과 연락처를 모두 입력해 주십시오.'
        }), 400

    if len(normalized_phone) < 9:
        return jsonify({
            'ok': False,
            'message': '연락처를 올바르게 입력해 주십시오.'
        }), 400

    member = MEMBER_INDEX.get((normalized_name, normalized_phone))
    if member:
        generation = str(member.get('generation') or '').strip()
        if generation:
            text = f"'{input_name}'님은 평산신씨 '{generation}'세로서 문희공파백은공종중의 종원입니다."
        else:
            text = f"'{input_name}'님은 문희공파백은공종중의 종원입니다."
        return jsonify({
            'ok': True,
            'matched': True,
            'message': text,
            'official_name': member.get('name', ''),
            'generation': generation,
        })

    return jsonify({
        'ok': True,
        'matched': False,
        'message': f"'{input_name}'님은 종원등록이 되어 있지 않습니다. {ADMIN_CONTACT}에게 연락주십시오."
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
