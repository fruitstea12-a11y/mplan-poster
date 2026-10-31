"""post.yaml의 slides로 9:16 쇼츠 영상(1080x1920)을 만든다.

- 슬라이드 이미지(선택) + 자막 텍스트를 Pillow로 합성
- narration: true 이면 edge-tts(무료)로 한국어 음성 생성, 슬라이드 길이 = 음성 길이
- ffmpeg로 슬라이드별 클립 생성 후 이어붙임
"""
import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1920
BRAND_BG = (20, 36, 84)      # 기본 배경 (네이비)
BRAND_ACCENT = (255, 196, 0)  # 강조 박스 (옐로)
DEFAULT_VOICE = "ko-KR-SunHiNeural"

FONT_CANDIDATES = [
    os.environ.get("FONT_PATH", ""),
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    str(Path(__file__).parent / "fonts" / "NotoSansKR-Bold.ttf"),
]


def _font(size):
    for p in FONT_CANDIDATES:
        if p and Path(p).exists():
            return ImageFont.truetype(p, size)
    raise RuntimeError("한글 폰트를 찾을 수 없음. FONT_PATH 환경변수로 지정하세요.")


def _wrap(draw, text, font, max_w):
    lines = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            if draw.textlength(line + ch, font=font) <= max_w:
                line += ch
            else:
                # 공백 기준으로 끊을 수 있으면 단어 단위로 넘김
                cut = line.rfind(" ")
                if cut > 0:
                    lines.append(line[:cut])
                    line = line[cut + 1:] + ch
                else:
                    lines.append(line)
                    line = ch
        lines.append(line)
    return lines


def make_frame(text, image_path, out_path, size=78):
    if image_path:
        bg = Image.open(image_path).convert("RGB")
        bg = ImageOps.fit(bg, (W, H), Image.LANCZOS)
    else:
        bg = Image.new("RGB", (W, H), BRAND_BG)

    if text:
        draw = ImageDraw.Draw(bg, "RGBA")
        font = _font(size)
        lines = _wrap(draw, text, font, W - 160)
        line_h = int(size * 1.35)
        block_h = line_h * len(lines)
        # 이미지가 있으면 하단 1/3, 없으면 중앙
        top = (H - block_h) // 2 if not image_path else int(H * 0.62)
        draw.rounded_rectangle(
            (50, top - 40, W - 50, top + block_h + 40),
            radius=36, fill=(0, 0, 0, 150) if image_path else (255, 255, 255, 18),
        )
        for i, ln in enumerate(lines):
            tw = draw.textlength(ln, font=font)
            y = top + i * line_h
            fill = BRAND_ACCENT if i == 0 and not image_path else (255, 255, 255)
            draw.text(((W - tw) / 2, y), ln, font=font, fill=fill,
                      stroke_width=3, stroke_fill=(0, 0, 0))
    bg.save(out_path, "PNG")


async def _tts(text, out_mp3, voice):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate="+8%").save(out_mp3)


def _run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    return float(out.strip())


def render(post_dir: Path, meta: dict, out_path: Path) -> Path:
    slides = meta.get("slides") or []
    if not slides:
        raise ValueError(f"{post_dir.name}: video.mp4도 slides도 없음")
    narration = meta.get("narration", True)
    voice = meta.get("voice", DEFAULT_VOICE)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips = []
        for i, s in enumerate(slides):
            text = s.get("text", "")
            img = post_dir / s["image"] if s.get("image") else None
            frame = tmp / f"f{i}.png"
            make_frame(text, img, frame, s.get("font_size", 78))

            clip = tmp / f"c{i}.mp4"
            speech = s.get("say", text)
            if narration and speech:
                mp3 = tmp / f"a{i}.mp3"
                asyncio.run(_tts(speech, str(mp3), voice))
                dur = _duration(mp3) + 0.4
                audio_in = ["-i", str(mp3)]
            else:
                dur = float(s.get("duration", 3))
                audio_in = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            _run([
                "ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(frame),
                *audio_in, "-t", f"{dur:.2f}",
                "-vf", "scale=1080:1920,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                "-af", "apad", "-shortest", str(clip),
            ])
            clips.append(clip)

        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{c}'\n" for c in clips))
        bgm = post_dir / meta["bgm"] if meta.get("bgm") else None
        if bgm and bgm.exists():
            joined = tmp / "joined.mp4"
            _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
            _run([
                "ffmpeg", "-y", "-i", str(joined), "-stream_loop", "-1", "-i", str(bgm),
                "-filter_complex", "[1:a]volume=0.12[b];[0:a][b]amix=inputs=2:duration=first[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                "-movflags", "+faststart", str(out_path),
            ])
        else:
            _run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                "-c", "copy", "-movflags", "+faststart", str(out_path),
            ])
    return out_path
