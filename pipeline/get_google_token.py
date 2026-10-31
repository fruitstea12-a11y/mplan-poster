"""구글 리프레시 토큰 1회 발급 (내 PC에서 실행).

    pip install google-auth-oauthlib
    python get_google_token.py client_secret.json youtube   # 유튜브 채널 계정으로 로그인
    python get_google_token.py client_secret.json drive     # 드라이브 계정으로 로그인

출력된 refresh_token 을 GitHub Secrets 에 저장한다.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = {
    "youtube": ["https://www.googleapis.com/auth/youtube.upload"],
    "drive": ["https://www.googleapis.com/auth/drive"],
}

if len(sys.argv) != 3 or sys.argv[2] not in SCOPES:
    sys.exit(__doc__)

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES[sys.argv[2]])
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
secret = "YOUTUBE_REFRESH_TOKEN" if sys.argv[2] == "youtube" else "DRIVE_REFRESH_TOKEN"
print(f"\n{secret} =\n{creds.refresh_token}\n")
