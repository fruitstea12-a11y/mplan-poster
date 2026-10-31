"""캡션 메모(.txt 또는 구글문서) 파싱.

형식 (윗부분 설정줄은 모두 선택):

    제목: 중3 겨울방학, 이것 모르면 고1 수학 무너집니다
    예약: 2026-11-03 18:00
    채널: 인스타, 유튜브, 페북
    ---
    캡션 본문...
    #엠플랜 #수학학원

`---` 가 없으면 전체를 캡션으로 보고, 첫 줄을 제목으로 쓴다.
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
ALL_PLATFORMS = ["instagram", "facebook", "youtube"]
ALIASES = {
    "인스타": "instagram", "인스타그램": "instagram", "instagram": "instagram", "ig": "instagram", "릴스": "instagram",
    "페북": "facebook", "페이스북": "facebook", "facebook": "facebook", "fb": "facebook",
    "유튜브": "youtube", "youtube": "youtube", "yt": "youtube", "쇼츠": "youtube",
}
KEYS = {"제목": "title", "title": "title", "예약": "publish_at", "publish_at": "publish_at",
        "채널": "platforms", "platforms": "platforms"}


def parse(text: str, fallback_title: str = "") -> dict:
    text = text.replace("\r\n", "\n").strip()
    head, body = "", text
    parts = re.split(r"^\s*-{3,}\s*$", text, maxsplit=1, flags=re.M)
    if len(parts) == 2:
        head, body = parts[0], parts[1].strip()

    meta = {}
    for line in head.splitlines():
        m = re.match(r"\s*([^:：]+)\s*[:：]\s*(.*)$", line)
        if m and m.group(1).strip().lower() in KEYS:
            meta[KEYS[m.group(1).strip().lower()]] = m.group(2).strip()

    title = meta.get("title") or next((ln.strip() for ln in body.splitlines() if ln.strip()), fallback_title)

    platforms = ALL_PLATFORMS
    if meta.get("platforms"):
        platforms = []
        for p in re.split(r"[,\s/]+", meta["platforms"]):
            p = ALIASES.get(p.strip().lower())
            if p and p not in platforms:
                platforms.append(p)

    publish_at = None
    if meta.get("publish_at"):
        publish_at = datetime.strptime(meta["publish_at"], "%Y-%m-%d %H:%M").replace(tzinfo=KST)

    return {
        "title": _strip_tags(title)[:100] or fallback_title[:100],
        "caption": body,
        "hashtags": re.findall(r"#([^\s#]+)", body),
        "platforms": platforms,
        "publish_at": publish_at,
    }


def _strip_tags(s: str) -> str:
    return re.sub(r"\s*#[^\s#]+", "", s).strip()
