"""YouTube Shorts 업로드 (YouTube Data API v3, 무료 쿼터 10,000/일 → 업로드 약 6건/일).

필요 환경변수:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN   유튜브 채널 계정으로 발급한 토큰
"""
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CATEGORY_EDUCATION = "27"


def _client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def post_youtube(video: Path, title: str, caption: str, hashtags: list) -> dict:
    description = caption if "#shorts" in caption.lower() else f"{caption}\n\n#Shorts"
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": hashtags[:30],
            "categoryId": CATEGORY_EDUCATION,
            "defaultLanguage": "ko",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video), mimetype="video/*", chunksize=8 * 1024 * 1024, resumable=True)
    req = _client().videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}"}
