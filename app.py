
import json
import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import wraps

import requests
from flask import Flask, jsonify, render_template, request, session, redirect
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMBER_FILE = os.path.join(BASE_DIR, "data", "members.json")

ADMIN_CONTACT = os.getenv("ADMIN_CONTACT", "010-2923-2912 신무광")
APP_TITLE = os.getenv("APP_TITLE", "백은공종중 종원 확인")
ADMIN_TITLE = os.getenv("ADMIN_TITLE", "백은공종중 주소 관리")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
APPS_SCRIPT_WEB_APP_URL = os.getenv("APPS_SCRIPT_WEB_APP_URL", "").strip()
APPS_SCRIPT_SHARED_SECRET = os.getenv("APPS_SCRIPT_SHARED_SECRET", "").strip()

RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
APPS_SCRIPT_TIMEOUT_SECONDS = int(os.getenv("APPS_SCRIPT_TIMEOUT_SECONDS", "20"))
_recent_requests = defaultdict(deque)


def load_members():
    with open(MEMBER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


MEMBERS = load_members()


def normalize_phone(value: str) -> str:
    raw = str(value or "").strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    digits = re.sub(r"\D+", "", raw)
    return digits


def repair_phone_candidates(digits: str) -> set[str]:
    candidates = {digits}
    if not digits:
        return set()

    # 일부 데이터에서 맨 앞의 0이 맨 뒤로 밀린 형태(예: 10292329120 -> 01029232912)를 보정
    if len(digits) == 11 and not digits.startswith("0") and digits.endswith("0"):
        candidates.add("0" + digits[:-1])

    # 앞자리 0 누락 보정
    if len(digits) == 10 and not digits.startswith("0"):
        candidates.add("0" + digits)

    return {c for c in candidates if c}


def phone_variants(value: str) -> set[str]:
    digits = normalize_phone(value)
    variants = set()
    for candidate in repair_phone_candidates(digits):
        variants.add(candidate)
        if candidate.startswith("0"):
            variants.add(candidate[1:])
        else:
            variants.add("0" + candidate)
    return {v for v in variants if v}


def canonicalize_name(value: str) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    s = re.sub(r"\s+", "", s)
    return s


def split_name_variants(name: str) -> set[str]:
    name = canonicalize_name(name)
    variants = {name}
    m = re.match(r"^([^()]+)\(([^()]+)\)$", name)
    if m:
        outside = m.group(1)
        inside = m.group(2)
        variants.add(outside)
        variants.add(inside)
        if outside.startswith("신") and len(outside) > 1:
            variants.add(outside[1:])
        if inside.startswith("신") and len(inside) > 1:
            variants.add(inside[1:])
    if name.startswith("신") and len(name) > 1:
        variants.add(name[1:])
    return {v for v in variants if v}


def format_generation(generation: str) -> str:
    g = re.sub(r"\s+", "", str(generation or "").strip())
    if not g:
        return ""
    return g if g.endswith("세") else f"{g}세"


def clean_postcode(value: str) -> str:
    s = str(value or "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def rate_limit_ok(ip: str) -> bool:
    now = time.time()
    q = _recent_requests[ip]
    while q and now - q[0] > RATE_LIMIT_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    q.append(now)
    return True


def now_str() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def request_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"


def find_member(input_name: str, input_phone: str):
    input_name = canonicalize_name(input_name)
    input_phone_variants = phone_variants(input_phone)
    if not input_name or not input_phone_variants:
        return None

    for member in MEMBERS:
        member_phone_variants = phone_variants(member.get("phone", ""))
        if not (member_phone_variants & input_phone_variants):
            continue
        variants = split_name_variants(member.get("name", ""))
        if input_name in variants:
            return member
    return None


def apps_script_enabled() -> bool:
    return bool(APPS_SCRIPT_WEB_APP_URL and APPS_SCRIPT_SHARED_SECRET)


def call_apps_script(action: str, payload: dict | None = None):
    if not apps_script_enabled():
        raise RuntimeError("Apps Script 연결 정보가 설정되지 않았습니다.")

    body = {
        "secret": APPS_SCRIPT_SHARED_SECRET,
        "action": action,
        "payload": payload or {},
    }

    try:
        response = requests.post(
            APPS_SCRIPT_WEB_APP_URL,
            json=body,
            timeout=APPS_SCRIPT_TIMEOUT_SECONDS,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Apps Script 요청에 실패했습니다: {e}") from e

    if response.status_code != 200:
        raise RuntimeError(f"Apps Script 응답 오류: HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as e:
        raise RuntimeError("Apps Script가 JSON 응답을 반환하지 않았습니다.") from e

    if not data.get("ok"):
        raise RuntimeError(data.get("error") or "Apps Script 처리 중 오류가 발생했습니다.")

    return data.get("data")


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect("/admin/login")
        return func(*args, **kwargs)

    return wrapper


@app.get("/")
def index():
    return render_template("index.html", title=APP_TITLE)


@app.post("/api/check-member")
def api_check_member():
    ip = request_ip()
    if not rate_limit_ok(ip):
        return jsonify({"ok": False, "message": "요청이 너무 많습니다. 잠시 후 다시 시도해 주십시오."}), 429

    data = request.get_json(silent=True) or {}
    input_name = str(data.get("name", "")).strip()
    input_phone = str(data.get("phone", "")).strip()

    if not input_name or not input_phone:
        return jsonify({"ok": False, "message": "성명과 연락처를 모두 입력해 주십시오."}), 400

    member = find_member(input_name, input_phone)
    if not member:
        return jsonify({
            "ok": False,
            "message": f"'{input_name}'님은 종원등록이 되어 있지 않습니다. {ADMIN_CONTACT}에게 연락주십시오.",
        })

    generation_display = format_generation(member.get("generation", ""))
    if generation_display:
        message = f"'{input_name}'님은 평산신씨 '{generation_display}'로서 백은공종중의 종원입니다."
    else:
        message = f"'{input_name}'님은 백은공종중의 종원입니다."

    existing_address = {}
    apps_script_error = None
    if apps_script_enabled():
        try:
            result = call_apps_script(
                "findEntry",
                {
                    "input_name": input_name,
                    "input_phone": normalize_phone(input_phone),
                },
            )
            existing_address = result or {}
        except Exception as e:
            apps_script_error = str(e)

    member_payload = {
        "input_name": input_name,
        "input_phone": normalize_phone(input_phone),
        "member_name": member.get("name", ""),
        "generation": generation_display,
        "zipcode": clean_postcode(existing_address.get("zipcode") or member.get("zipcode", "") or ""),
        "address": existing_address.get("address") or member.get("address", "") or "",
        "detail_address": existing_address.get("detail_address") or member.get("detail_address", "") or "",
    }

    response = {
        "ok": True,
        "message": message,
        "member": member_payload,
    }
    if apps_script_error:
        response["warning"] = apps_script_error
    return jsonify(response)


@app.post("/api/address/upsert")
def api_address_upsert():
    ip = request_ip()
    if not rate_limit_ok(ip):
        return jsonify({"ok": False, "message": "요청이 너무 많습니다. 잠시 후 다시 시도해 주십시오."}), 429

    data = request.get_json(silent=True) or {}
    input_name = str(data.get("input_name", "")).strip()
    input_phone = str(data.get("input_phone", "")).strip()
    zipcode = str(data.get("zipcode", "")).strip()
    address = str(data.get("address", "")).strip()
    detail_address = str(data.get("detail_address", "")).strip()
    consent = bool(data.get("consent"))

    member = find_member(input_name, input_phone)
    if not member:
        return jsonify({"ok": False, "message": "종원 확인이 되지 않아 주소를 저장할 수 없습니다."}), 400

    if not consent:
        return jsonify({"ok": False, "message": "개인정보 수집·이용 동의가 필요합니다."}), 400

    if not zipcode or not address:
        return jsonify({"ok": False, "message": "우편번호와 주소를 입력해 주십시오."}), 400

    if not apps_script_enabled():
        return jsonify({"ok": False, "message": "주소 저장 기능이 아직 설정되지 않았습니다. 관리자에게 문의해 주십시오."}), 500

    generation_display = format_generation(member.get("generation", ""))
    payload = {
        "submitted_at": now_str(),
        "updated_at": now_str(),
        "input_name": input_name,
        "input_phone": normalize_phone(input_phone),
        "member_name": member.get("name", ""),
        "generation": generation_display,
        "zipcode": zipcode,
        "address": address,
        "detail_address": detail_address,
        "consent": "동의",
        "ip": ip,
        "user_agent": request.headers.get("User-Agent", ""),
    }

    try:
        result = call_apps_script("upsertEntry", payload)
    except Exception as e:
        return jsonify({"ok": False, "message": f"주소 저장 중 오류가 발생했습니다. {e}"}), 500

    row_number = result.get("row_number")
    if row_number:
        msg = f"주소 정보가 저장되었습니다. (시트 행 {row_number})"
    else:
        msg = "주소 정보가 저장되었습니다."
    return jsonify({"ok": True, "message": msg})


@app.get("/admin/login")
def admin_login_form():
    return render_template("admin_login.html", title=ADMIN_TITLE, error=None)


@app.post("/admin/login")
def admin_login_submit():
    password = str(request.form.get("password", ""))
    if not ADMIN_PASSWORD:
        return render_template(
            "admin_login.html",
            title=ADMIN_TITLE,
            error="서버에 ADMIN_PASSWORD가 설정되지 않았습니다.",
        )

    if password != ADMIN_PASSWORD:
        return render_template(
            "admin_login.html",
            title=ADMIN_TITLE,
            error="비밀번호가 올바르지 않습니다.",
        )

    session["admin_logged_in"] = True
    return redirect("/admin")


@app.post("/admin/logout")
@login_required
def admin_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/admin")
@login_required
def admin_page():
    return render_template("admin.html", title=ADMIN_TITLE)


@app.get("/api/admin/entries")
@login_required
def api_admin_entries():
    query = str(request.args.get("q", "")).strip()
    if not apps_script_enabled():
        return jsonify({"ok": False, "message": "Apps Script 연결 정보가 설정되지 않았습니다."}), 500

    try:
        result = call_apps_script("listEntries", {"query": query})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

    return jsonify({"ok": True, "rows": result.get("rows", [])})


@app.post("/api/admin/update")
@login_required
def api_admin_update():
    data = request.get_json(silent=True) or {}
    row_number = data.get("row_number")
    zipcode = str(data.get("zipcode", "")).strip()
    address = str(data.get("address", "")).strip()
    detail_address = str(data.get("detail_address", "")).strip()

    if not row_number:
        return jsonify({"ok": False, "message": "행 번호가 필요합니다."}), 400
    if not zipcode or not address:
        return jsonify({"ok": False, "message": "우편번호와 주소를 입력해 주십시오."}), 400
    if not apps_script_enabled():
        return jsonify({"ok": False, "message": "Apps Script 연결 정보가 설정되지 않았습니다."}), 500

    payload = {
        "row_number": int(row_number),
        "zipcode": zipcode,
        "address": address,
        "detail_address": detail_address,
        "updated_at": now_str(),
    }

    try:
        call_apps_script("adminUpdateEntry", payload)
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

    return jsonify({"ok": True, "message": "주소가 수정되었습니다."})


@app.get("/healthz")
def healthz():
    status = {
        "ok": True,
        "apps_script_configured": apps_script_enabled(),
        "admin_password_configured": bool(ADMIN_PASSWORD),
    }
    return jsonify(status)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
