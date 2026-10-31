# 쇼츠 자동 게시 파이프라인

구글드라이브 폴더에 **영상 + 캡션**을 넣으면, 매시간 GitHub Actions가 확인해서
**인스타 릴스 · 페이스북 릴스 · 유튜브 쇼츠**에 자동 게시합니다. 비용 0원.

> 네이버 클립은 공식 업로드 API가 없어 자동화 불가 → 네이버 앱에서 수동 업로드.

```
[구글드라이브/쇼츠업로드]  →  GitHub Actions (매시 17분)  →  인스타 / 페북 / 유튜브
        영상.mp4 + 영상.txt                                  ↓
                                              [구글드라이브/쇼츠완료] 로 자동 이동
```

---

## 매일 쓰는 법

1. 드라이브 `쇼츠업로드` 폴더에 영상 올리기 (예: `1103_겨울방학.mp4`)
2. **같은 이름**으로 캡션 파일 만들기 (`1103_겨울방학.txt` 또는 구글문서 `1103_겨울방학`)
3. 끝. 최대 1시간 안에 게시되고, 완료되면 `쇼츠완료` 폴더로 옮겨집니다.

### 캡션 파일 형식

```
제목: 중3 겨울방학, 이것 모르면 고1 수학 무너집니다
예약: 2026-11-03 18:00
채널: 인스타, 유튜브, 페북
---
고1 첫 시험에서 무너지는 학생들의 공통점은...

#엠플랜 #수학학원 #중3수학 #고1수학
```

| 줄 | 필수 | 설명 |
|---|---|---|
| `제목:` | 선택 | 유튜브 제목(100자). 없으면 본문 첫 줄 사용 |
| `예약:` | 선택 | 한국시간. 없으면 즉시 게시. 매시 17분 실행이라 최대 1시간 오차 |
| `채널:` | 선택 | 없으면 3곳 모두 |
| `---` | 선택 | 위는 설정, 아래는 캡션 본문. 없으면 전체가 캡션 |

### 영상 규격

- 세로 9:16 (1080×1920), MP4(H.264 + AAC)
- 길이 3초~3분 (유튜브 쇼츠 최대 3분, 인스타 릴스는 90초 이하 권장)

### 실패하면?

- 실패한 플랫폼만 다음 실행 때 자동 재시도 (최대 3회). 성공한 곳은 중복 게시 안 됨.
- 실패 시 GitHub에서 실패 알림 메일이 옵니다. Actions 탭 → 실행 결과 요약에서 원인 확인.
- 유튜브 일일 한도(약 6개) 초과 시 실패로 세지 않고 다음 날 재시도.

---

## 최초 세팅 (1회, 약 1~2주)

### 1) 구글드라이브 폴더

1. 드라이브에 `쇼츠업로드`, `쇼츠완료` 폴더 생성
2. 각 폴더를 열어 주소창의 `folders/` 뒤 문자열 복사 → 폴더 ID

### 2) 구글 클라우드 (유튜브 + 드라이브 공용)

1. https://console.cloud.google.com → 새 프로젝트
2. **API 및 서비스 → 라이브러리**: `YouTube Data API v3`, `Google Drive API` 사용 설정
3. **OAuth 동의 화면**: 외부 → 테스트 사용자에 본인 계정 추가 → **"앱 게시(프로덕션)"로 전환**
   - 테스트 상태로 두면 토큰이 7일마다 만료됩니다. 프로덕션 전환 필수(미인증 경고는 무시하고 진행 가능).
4. **사용자 인증 정보 → OAuth 클라이언트 ID → 데스크톱 앱** → JSON 다운로드(`client_secret.json`)
5. 내 PC에서 토큰 발급:
   ```bash
   pip install google-auth-oauthlib
   python pipeline/get_google_token.py client_secret.json drive
   python pipeline/get_google_token.py client_secret.json youtube
   ```
   - `drive`: 드라이브 폴더가 있는 계정으로 로그인
   - `youtube`: 유튜브 채널 선택 화면에서 **엠플랜 채널** 선택
6. **유튜브 공개 게시 심사 신청** (무료): 심사 전에는 업로드 영상이 "비공개"로 잠깁니다.
   https://support.google.com/youtube/contact/yt_api_form → API 감사(Audit) 신청. 보통 1~2주.

### 3) Meta (인스타 + 페북)

1. 인스타 계정을 **비즈니스/크리에이터**로 전환 → 페이스북 **페이지**와 연결
2. https://developers.facebook.com → 앱 만들기 (유형: 비즈니스)
3. 제품 추가: **Instagram Graph API**(페이스북 로그인 방식)
4. **그래프 API 탐색기**에서 권한 선택 후 사용자 토큰 발급:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `business_management`
5. **액세스 토큰 디버거**에서 "장기 토큰으로 연장" → 그 토큰으로 `GET /me/accounts` 호출
   → 응답의 해당 페이지 `access_token` = **만료 없는 페이지 토큰** (`META_PAGE_TOKEN`), `id` = `FB_PAGE_ID`
6. `GET /{FB_PAGE_ID}?fields=instagram_business_account` → `id` = `IG_USER_ID`
7. 앱은 **개발 모드 그대로** 사용 가능 (본인 계정에만 게시하므로 앱 검수 불필요)

### 4) GitHub 저장소 설정

**Settings → Secrets and variables → Actions**

| 종류 | 이름 | 값 |
|---|---|---|
| Secret | `GOOGLE_CLIENT_ID` | client_secret.json 의 client_id |
| Secret | `GOOGLE_CLIENT_SECRET` | client_secret.json 의 client_secret |
| Secret | `DRIVE_REFRESH_TOKEN` | 2-5 drive 결과 |
| Secret | `YOUTUBE_REFRESH_TOKEN` | 2-5 youtube 결과 |
| Secret | `META_PAGE_TOKEN` | 3-5 페이지 토큰 |
| Variable | `DRIVE_INBOX_ID` | 쇼츠업로드 폴더 ID |
| Variable | `DRIVE_DONE_ID` | 쇼츠완료 폴더 ID |
| Variable | `IG_USER_ID` | 3-6 |
| Variable | `FB_PAGE_ID` | 3-5 |
| Variable | `ENABLED_PLATFORMS` | (선택) 예: `instagram,facebook` — 유튜브 심사 전엔 빼두기 |

### 5) 실행

- 이 브랜치를 **기본 브랜치(main)에 머지**해야 매시간 자동 실행됩니다 (GitHub 정책).
- 첫 테스트: Actions 탭 → "쇼츠 자동 게시" → Run workflow → **테스트 모드 체크** → 결과 요약에서 게시 예정 목록 확인
- 이상 없으면 테스트 모드 해제하고 한 번 실행 → 실제 게시 확인

---

## 비용

| 항목 | 비용 |
|---|---|
| GitHub Actions | 공개 저장소 무료 / 비공개 월 2,000분 무료 (매시간 1분 내외 → 월 약 720분) |
| YouTube Data API | 무료 (일 10,000 쿼터) |
| Meta Graph API | 무료 |
| Google Drive API | 무료 |

## 파일 구조

```
pipeline/
  publish.py           메인: 드라이브 확인 → 게시 → 완료 폴더 이동
  caption.py           캡션 파일 파싱
  drive.py             구글드라이브 연동
  platforms/meta.py    인스타 릴스 · 페북 릴스
  platforms/youtube.py 유튜브 쇼츠
  get_google_token.py  구글 토큰 1회 발급용 (내 PC에서 실행)
.github/workflows/publish-shorts.yml  매시 자동 실행
```
