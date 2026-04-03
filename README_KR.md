# 문희공파백은공종중 종원 확인 앱 - Render 배포 안정화 버전

이 버전은 공개 링크 운영을 염두에 두고 Render 배포 성공률을 높이기 위해 아래 항목을 추가한 패키지입니다.

- `Procfile` 추가
- `runtime.txt` 추가
- `render.yaml` 추가
- `PORT` 환경변수 대응
- `ADMIN_CONTACT` 환경변수 대응
- `ProxyFix` 적용
- `/healthz` 상태 확인 경로 추가

## 폴더 구조
- `app.py`: Flask 서버 본체
- `templates/index.html`: 조회 화면
- `data/members.json`: 서버 내부 종원 데이터
- `requirements.txt`: 의존성
- `Procfile`: Render/기타 PaaS 시작 명령
- `runtime.txt`: 파이썬 버전 고정
- `render.yaml`: Render 블루프린트 설정

## 로컬 실행
```bash
pip install -r requirements.txt
python app.py
```
브라우저에서 `http://127.0.0.1:5000` 접속

## GitHub 업로드 시 주의
저장소 첫 화면에 아래가 바로 보여야 정상입니다.

```text
app.py
requirements.txt
Procfile
runtime.txt
render.yaml
data/
templates/
```

폴더가 한 겹 더 들어가면 Render에서 실행 실패할 수 있습니다.

## Render 배포 방법 1: 일반 Web Service 방식
1. GitHub에 이 폴더 내용 전체 업로드
2. Render → `New +` → `Web Service`
3. 저장소 연결
4. 설정값 입력
   - Runtime: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. Environment Variables 추가
   - `ADMIN_CONTACT=010-2923-2912 신무광`
   - `REQUEST_WINDOW_SECONDS=300`
   - `MAX_REQUESTS_PER_WINDOW=20`
6. 배포 완료

## Render 배포 방법 2: render.yaml 사용
1. GitHub에 업로드
2. Render → `New +` → `Blueprint`
3. 저장소 선택
4. `render.yaml` 내용을 읽어 자동 설정
5. 배포

## 헬스체크
배포 후 아래 주소로 확인 가능합니다.

```text
https://생성된주소.onrender.com/healthz
```

정상 응답 예시:
```json
{"ok": true, "member_count": 739}
```

## 조회 규칙
- 성명 + 전화번호가 함께 일치해야 종원으로 판정합니다.
- 성명은 다음과 같이 입력해도 조회됩니다.
  - 전체 이름: `신갑례(현숙)`
  - 성 제외: `갑례`
  - 괄호 안 이름: `현숙`
- 연락처는 숫자만 입력하거나 하이픈 포함 입력 모두 허용합니다.

## 환경변수
- `ADMIN_CONTACT`: 미등록 안내 문구에 표시할 연락처
- `REQUEST_WINDOW_SECONDS`: 요청 횟수 제한 시간창(초)
- `MAX_REQUESTS_PER_WINDOW`: 시간창 내 최대 요청 수
- `PORT`: Render가 자동 주입하므로 직접 수정 불필요

## 추천 운영 보강
1. Cloudflare Turnstile 또는 Google reCAPTCHA 추가
2. 맞춤 도메인 연결
3. 관리자 연락처를 코드가 아닌 Render 환경변수에서만 관리
4. 서버 로그 최소화
5. 정기적으로 명부 갱신
