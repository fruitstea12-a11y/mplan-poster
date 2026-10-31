"""Instagram Reels + Facebook Page Reels 업로드 (Meta Graph API, 무료).

영상 호스팅 없이 rupload.facebook.com 으로 파일을 직접 올린다.
필요 환경변수:
  META_PAGE_TOKEN  페이지 액세스 토큰(장기, 만료 없음)
  IG_USER_ID       인스타그램 비즈니스/크리에이터 계정 ID
  FB_PAGE_ID       페이스북 페이지 ID
"""
import os
import time
from pathlib import Path

import requests

API_VER = os.environ.get("META_API_VERSION", "v21.0")
GRAPH = f"https://graph.facebook.com/{API_VER}"


def _token():
    return os.environ["META_PAGE_TOKEN"]


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"Meta API {r.status_code}: {r.text}")
    return r.json()


def _upload_binary(url, video: Path):
    size = video.stat().st_size
    with open(video, "rb") as f:
        r = requests.post(url, data=f, timeout=600, headers={
            "Authorization": f"OAuth {_token()}",
            "offset": "0",
            "file_size": str(size),
        })
    return _check(r)


def post_instagram(video: Path, caption: str) -> dict:
    ig = os.environ["IG_USER_ID"]
    c = _check(requests.post(f"{GRAPH}/{ig}/media", timeout=60, data={
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "share_to_feed": "true",
        "access_token": _token(),
    }))
    container = c["id"]
    _upload_binary(f"https://rupload.facebook.com/ig-api-upload/{API_VER}/{container}", video)

    # 인코딩 완료 대기 (최대 10분)
    for _ in range(60):
        s = _check(requests.get(f"{GRAPH}/{container}", timeout=30, params={
            "fields": "status_code,status", "access_token": _token()}))
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"IG 처리 실패: {s}")
        time.sleep(10)
    else:
        raise RuntimeError("IG 처리 시간 초과")

    pub = _check(requests.post(f"{GRAPH}/{ig}/media_publish", timeout=60, data={
        "creation_id": container, "access_token": _token()}))
    link = _check(requests.get(f"{GRAPH}/{pub['id']}", timeout=30, params={
        "fields": "permalink", "access_token": _token()}))
    return {"id": pub["id"], "url": link.get("permalink")}


def post_facebook(video: Path, caption: str, title: str = "") -> dict:
    page = os.environ["FB_PAGE_ID"]
    start = _check(requests.post(f"{GRAPH}/{page}/video_reels", timeout=60, data={
        "upload_phase": "start", "access_token": _token()}))
    vid = start["video_id"]
    _upload_binary(start.get("upload_url") or
                   f"https://rupload.facebook.com/video-upload/{API_VER}/{vid}", video)
    _check(requests.post(f"{GRAPH}/{page}/video_reels", timeout=60, data={
        "upload_phase": "finish",
        "video_id": vid,
        "video_state": "PUBLISHED",
        "description": caption,
        "title": title,
        "access_token": _token(),
    }))
    return {"id": vid, "url": f"https://www.facebook.com/reel/{vid}"}
