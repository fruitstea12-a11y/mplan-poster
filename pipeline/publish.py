"""구글드라이브 '쇼츠업로드' 폴더의 영상을 인스타·페북·유튜브에 게시한다.

    python pipeline/publish.py            # 실제 게시
    python pipeline/publish.py --dry-run  # 무엇이 올라갈지만 출력

- 영상(video/*)과 같은 이름의 캡션(.txt 또는 구글문서)을 한 쌍으로 본다.
- 플랫폼별 성공 기록은 드라이브 파일 속성(appProperties)에 남겨, 실패한 플랫폼만 다음 실행 때 재시도한다.
- 모든 플랫폼 게시가 끝나면 영상과 캡션을 '완료' 폴더로 옮긴다.
"""
import argparse
import os
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from caption import KST, parse  # noqa: E402

MAX_FAIL = 3
IG_CAPTION_LIMIT = 2200
NAMES = {"instagram": "인스타", "facebook": "페북", "youtube": "유튜브"}


REQUIRED_ENV = {
    "instagram": ["META_PAGE_TOKEN", "IG_USER_ID"],
    "facebook": ["META_PAGE_TOKEN", "FB_PAGE_ID"],
    "youtube": ["YOUTUBE_REFRESH_TOKEN", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
}


def enabled_platforms():
    """ENABLED_PLATFORMS 중 키가 실제로 등록된 플랫폼만. 키 없는 플랫폼은 실패 대신 건너뜀."""
    raw = os.environ.get("ENABLED_PLATFORMS") or "instagram,facebook,youtube"
    wanted = [p.strip() for p in raw.split(",") if p.strip()]
    return [p for p in wanted if all(os.environ.get(k) for k in REQUIRED_ENV.get(p, []))]


def post(platform, video, post_meta):
    if platform == "instagram":
        from platforms.meta import post_instagram
        return post_instagram(video, post_meta["caption"][:IG_CAPTION_LIMIT])
    if platform == "facebook":
        from platforms.meta import post_facebook
        return post_facebook(video, post_meta["caption"], post_meta["title"])
    if platform == "youtube":
        from platforms.youtube import post_youtube
        return post_youtube(video, post_meta["title"], post_meta["caption"], post_meta["hashtags"])
    raise ValueError(f"알 수 없는 플랫폼: {platform}")


def stem(name):
    return Path(name).stem if "." in name else name


def run(drive, dry_run=False):
    now = datetime.now(KST)
    enabled = enabled_platforms()
    files = drive.list_inbox()
    videos = [f for f in files if f["mimeType"].startswith("video/")]
    captions = {stem(f["name"]): f for f in files if not f["mimeType"].startswith("video/")}

    report, had_error = [], False
    for v in sorted(videos, key=lambda f: f["name"]):
        key = stem(v["name"])
        cap_file = captions.get(key)
        if not cap_file:
            report.append(f"⏸ {v['name']}: 캡션 파일({key}.txt) 없음 → 대기")
            continue

        meta = parse(drive.read_text(cap_file), fallback_title=key)
        if meta["publish_at"] and meta["publish_at"] > now:
            report.append(f"🕒 {v['name']}: {meta['publish_at']:%m/%d %H:%M} 예약 대기")
            continue

        props = dict(v.get("appProperties") or {})
        targets = [p for p in meta["platforms"] if p in enabled]
        pending = [p for p in targets
                   if not props.get(f"{p}_id") and int(props.get(f"{p}_fail", 0)) < MAX_FAIL]

        if dry_run:
            report.append(f"🧪 {v['name']}: 게시 예정 {[NAMES[p] for p in pending]} / 제목: {meta['title']}")
            continue

        if pending:
            with tempfile.TemporaryDirectory() as tmp:
                local = drive.download(v, Path(tmp) / v["name"])
                for p in pending:
                    had_error_before = had_error
                    try:
                        res = post(p, local, meta)
                        drive.set_props(v, {f"{p}_id": str(res["id"]), f"{p}_url": (res.get("url") or "")[:100]})
                        report.append(f"✅ {v['name']} → {NAMES[p]}: {res.get('url')}")
                    except Exception as e:  # noqa: BLE001
                        had_error = True
                        msg = str(e)
                        traceback.print_exc()
                        if "quotaExceeded" in msg:
                            had_error = had_error_before
                            report.append(f"⏳ {v['name']} → {NAMES[p]}: 일일 쿼터 초과, 내일 재시도")
                            continue
                        fails = int(v.get("appProperties", {}).get(f"{p}_fail", 0)) + 1
                        drive.set_props(v, {f"{p}_fail": str(fails)})
                        tail = " (재시도 중단, 수동 확인 필요)" if fails >= MAX_FAIL else ""
                        report.append(f"❌ {v['name']} → {NAMES[p]} 실패 {fails}/{MAX_FAIL}{tail}: {msg[:300]}")

        props = v.get("appProperties") or {}
        stuck = [p for p in targets if not props.get(f"{p}_id") and int(props.get(f"{p}_fail", 0)) >= MAX_FAIL]
        if stuck and not pending:
            report.append(f"⛔ {v['name']}: {[NAMES[p] for p in stuck]} 3회 실패로 멈춤 — 드라이브 파일 속성 확인 필요")

        if targets and all(props.get(f"{p}_id") for p in targets):
            drive.move_done(v)
            drive.move_done(cap_file)
            report.append(f"📦 {v['name']}: 전체 게시 완료 → 완료 폴더로 이동")

    if not videos:
        report.append("새 영상 없음")
    return report, had_error


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    account = os.environ.get("ACCOUNT_NAME", "")

    missing = [k for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "DRIVE_REFRESH_TOKEN",
                           "DRIVE_INBOX_ID", "DRIVE_DONE_ID") if not os.environ.get(k)]
    if missing:
        report, had_error = [f"⚙️ 세팅 전이라 건너뜀 (없는 값: {', '.join(missing)})"], False
    elif not enabled_platforms():
        report, had_error = ["⚙️ 게시할 플랫폼 키가 아직 없음 → 건너뜀"], False
    else:
        from drive import Drive
        report, had_error = run(Drive(), dry_run=args.dry_run)
        report.insert(0, f"게시 대상: {[NAMES[p] for p in enabled_platforms()]}")

    text = "\n".join(f"- {r}" for r in report)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## 쇼츠 자동 게시 결과 {account} ({datetime.now(KST):%Y-%m-%d %H:%M} KST)\n\n{text}\n")
    sys.exit(1 if had_error else 0)


if __name__ == "__main__":
    main()
