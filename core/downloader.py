"""Manbani tayyorlash: YouTube havolani yuklab olish yoki mahalliy faylni qabul qilish."""
import re
import shutil
import sys
from pathlib import Path

import config
from core.ffmpeg_utils import ffmpeg_path


def is_url(text: str) -> bool:
    return text.lower().startswith(("http://", "https://", "www.", "youtu"))


def safe_name(text: str, limit: int = 60) -> str:
    name = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE).strip("_")
    return (name[:limit].rstrip("_")) or "video"


def _deno_path():
    """yt-dlp YouTube uchun JavaScript muhitini (deno) talab qiladi; u env ichiga o'rnatiladi."""
    exe = "deno.exe" if sys.platform == "win32" else "deno"
    candidate = Path(sys.executable).parent / exe
    if candidate.exists():
        return str(candidate)
    return shutil.which("deno")


def _ydl_opts(extra=None):
    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": str(Path(ffmpeg_path()).parent),
    }
    deno = _deno_path()
    if deno:
        opts["js_runtimes"] = {"deno": {"path": deno}}
    if extra:
        opts.update(extra)
    return opts


def prepare_source(inp: str):
    """Qaytaradi: (video_fayl, sarlavha, ish_papkasi)."""
    inp = inp.strip().strip('"').strip("'")
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not is_url(inp):
        path = Path(inp).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Fayl topilmadi: {path}")
        title = path.stem
        workdir = config.OUTPUT_DIR / safe_name(title)
        workdir.mkdir(parents=True, exist_ok=True)
        return path.resolve(), title, workdir

    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp kutubxonasi topilmadi. Dasturni run.bat orqali ishga tushiring yoki "
            "setup.bat ni qayta ishga tushirib, kutubxonalarni o'rnating.") from exc

    if inp.lower().startswith(("www.", "youtu")):
        inp = "https://" + inp

    with YoutubeDL(_ydl_opts()) as ydl:
        info = ydl.extract_info(inp, download=False)
    title = info.get("title") or info.get("id") or "video"
    workdir = config.OUTPUT_DIR / f"{safe_name(title)}_{info.get('id', '')}".rstrip("_")
    workdir.mkdir(parents=True, exist_ok=True)

    existing = workdir / "source.mp4"
    if existing.exists() and existing.stat().st_size > 0:
        print("  Video avval yuklangan, qayta yuklanmaydi.")
        return existing, title, workdir

    h = config.MAX_VIDEO_HEIGHT
    fmt = (f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/"
           f"b[height<={h}][ext=mp4]/bv*[height<={h}]+ba/b[height<={h}]/b")
    print(f"  Yuklab olinmoqda: {title}")
    with YoutubeDL(_ydl_opts({
        "format": fmt,
        "merge_output_format": "mp4",
        "outtmpl": str(workdir / "source.%(ext)s"),
        "quiet": False,
        "noprogress": False,
    })) as ydl:
        ydl.download([inp])

    if not existing.exists():
        found = sorted(workdir.glob("source.*"), key=lambda p: p.stat().st_size, reverse=True)
        if not found:
            raise RuntimeError("Video yuklanmadi.")
        return found[0], title, workdir
    return existing, title, workdir
