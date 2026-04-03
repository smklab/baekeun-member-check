# 백은공종중 종원 확인 + 주소 제출/수정 + 관리자 조회 (Apps Script 저장형)

이 버전은 **서비스 계정 JSON 키 없이** Google Apps Script 웹앱을 통해 Google Sheets에 주소를 저장합니다.

## 포함 기능
- 종원 여부 확인
- 종원 확인 성공 시 주소 제출/수정
- 주소 제출 전 개인정보 수집·이용 동의 체크박스
- Google Sheets 저장 (Apps Script 웹앱 경유)
- 관리자 전용 조회 페이지 (`/admin`)
- 관리자 비밀번호 로그인
- 관리자 주소 수정 기능
- `35세세` 중복 표시 방지
- 제목 `백은공종중 종원 확인`

## 1. GitHub 업로드
압축을 푼 뒤 아래 파일/폴더를 기존 저장소에 덮어쓰기 업로드합니다.

- `app.py`
- `requirements.txt`
- `Procfile`
- `runtime.txt`
- `render.yaml`
- `templates/`
- `data/`
- `apps_script/Code.gs`

## 2. Render 환경변수
아래 값을 Render > Environment에 추가합니다.

### 필수
- `ADMIN_CONTACT`
- `APPS_SCRIPT_WEB_APP_URL`
- `APPS_SCRIPT_SHARED_SECRET`
- `ADMIN_PASSWORD`
- `FLASK_SECRET_KEY`

### 예시
- `ADMIN_CONTACT=010-2923-2912 신무광`
- `APPS_SCRIPT_WEB_APP_URL=https://script.google.com/macros/s/.../exec`
- `APPS_SCRIPT_SHARED_SECRET=여기에_직접_정한_랜덤문자열`
- `ADMIN_PASSWORD=여기에_직접_정한_비밀번호`
- `FLASK_SECRET_KEY=여기에_직접_정한_긴_랜덤문자열`

## 3. Google Apps Script 설정
1. Google Sheets를 하나 새로 만듭니다.
2. 메뉴에서 **확장 프로그램 > Apps Script**를 엽니다.
3. `apps_script/Code.gs` 파일 내용을 그대로 붙여넣습니다.
4. 코드 상단의 `SECRET_TOKEN` 값을 Render의 `APPS_SCRIPT_SHARED_SECRET`와 **같은 값**으로 바꿉니다.
5. 저장합니다.
6. 오른쪽 위 **배포 > 새 배포**를 클릭합니다.
7. 유형에서 **웹 앱**을 선택합니다.
8. 실행 사용자: **나**
9. 액세스 권한: **모든 사용자**
10. 배포 후 발급된 URL을 `APPS_SCRIPT_WEB_APP_URL` 환경변수에 넣습니다.

## 4. Google Sheets 시트 이름
Apps Script 코드 기본값은 `주소제출`입니다. 같은 이름의 탭이 없으면 자동으로 생성합니다.

## 5. 관리자 페이지
- 종원 확인 페이지: `/`
- 관리자 로그인: `/admin/login`
- 관리자 화면: `/admin`

예시:
- `https://배포주소.onrender.com/admin`

## 6. 주소 수정 방식
같은 종원이 다시 주소를 제출하면 Google Sheets에 새 행을 계속 쌓지 않고 기존 행을 찾아 최신 정보로 갱신합니다.

## 7. 배포 후 기본 테스트
1. `/healthz` 접속
2. 종원 조회 테스트
3. 주소 제출 테스트
4. Google Sheets에 행이 저장되는지 확인
5. `/admin/login` 접속
6. 관리자 수정 테스트
