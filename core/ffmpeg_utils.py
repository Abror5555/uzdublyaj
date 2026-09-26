"""ffmpeg bilan ishlash: audio ajratish, kesish, tezlashtirish, video yig'ish."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import config

_FFMPEG = None


def ffmpeg_path() -> str:
    """ffmpeg'ni topadi. Birinchi marta imageio-ffmpeg ichidagi nusxani bin/ ga ko'chiradi."""
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    local = config.BIN_DIR / exe
    if local.exists():
        _FFMPEG = str(local)
        return _FFMPEG
    try:
        import imageio_ffmpeg

        src = imageio_ffmpeg.get_ffmpeg_exe()
        config.BIN_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, local)  # yt-dlp "ffmpeg" nomli faylni kutadi
        _FFMPEG = str(local)
        return _FFMPEG
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("ffmpeg topilmadi. 'pip install imageio-ffmpeg' ni bajaring.")
    _FFMPEG = found
    return _FFMPEG


def _popen_kwargs():
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return kw


def run(args, cwd=None, loglevel="error"):
    cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", loglevel, "-y", *map(str, args)]
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", **_popen_kwargs(),
    )
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg xatosi:\n" + (proc.stderr or "")[-2500:])
    return proc


def probe(path) -> dict:
    """Davomiylik va audio bor-yo'qligini aniqlaydi (ffprobe'siz)."""
    proc = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        **_popen_kwargs(),
    )
    err = proc.stderr or ""
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if not m:
        raise RuntimeError(f"Fayl o'qilmadi: {path}\n{err[-800:]}")
    h, mi, s = m.groups()
    return {
        "duration": int(h) * 3600 + int(mi) * 60 + float(s),
        "has_audio": bool(re.search(r"Stream #.*Audio:", err)),
        "has_video": bool(re.search(r"Stream #.*Video:(?!.*attached pic)", err)),
    }


def extract_audio(src, dst, start=None, duration=None):
    """Nutqni aniqlash uchun 16 kHz mono mp3."""
    args = []
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    if duration is not None:
        args += ["-t", f"{duration:.3f}"]
    args += ["-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", dst]
    run(args)


def find_silences(path, noise_db=-35, min_dur=0.4):
    """Jimlik oraliqlari ro'yxati: [(boshlanish, tugash), ...]."""
    proc = run(["-i", path, "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
               loglevel="info")
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", proc.stderr)]
    return list(zip(starts, ends))


def change_tempo(src, dst, factor, sample_rate=24000):
    """Ovozni balandligini o'zgartirmasdan tezlashtiradi."""
    factor = max(0.5, min(2.0, factor))
    run(["-i", src, "-af", f"atempo={factor:.4f}", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", dst])


def burn_subtitles(video, srt, out):
    """Subtitrni videoga chizadi. Windows yo'l muammolarini chetlab o'tish uchun
    ffmpeg srt joylashgan papkadan ishga tushiriladi."""
    srt = Path(srt)
    tmp = srt.parent / "_burn.srt"  # nomdagi maxsus belgilar filtrni buzmasligi uchun
    shutil.copyfile(srt, tmp)
    style = (f"FontName={config.SUB_FONT},FontSize={config.SUB_FONT_SIZE},"
             "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,"
             "Outline=2,Shadow=0,MarginV=22")
    try:
        run([
            "-i", Path(video).resolve(),
            "-vf", f"subtitles={tmp.name}:charenc=UTF-8:force_style='{style}'",
            "-c:v", "libx264", "-preset", config.VIDEO_PRESET, "-crf", str(config.VIDEO_CRF),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            Path(out).resolve(),
        ], cwd=str(srt.parent))
    finally:
        tmp.unlink(missing_ok=True)


def add_soft_subtitles(video, srt, out):
    run([
        "-i", video, "-i", srt,
        "-map", "0:v", "-map", "0:a?", "-map", "1:0",
        "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
        "-metadata:s:s:0", "language=uzb", "-disposition:s:0", "default",
        "-movflags", "+faststart", out,
    ])


def mux_dub(video, dub_wav, out, original_volume=0.0, has_original_audio=True, srt=None, duration=None):
    """Video + o'zbekcha ovoz (+ fonda asl ovoz) (+ subtitr yo'lagi)."""
    args = ["-i", video, "-i", dub_wav]
    if srt:
        args += ["-i", srt]
    fg = "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000"
    if original_volume > 0 and has_original_audio:
        fc = (f"[0:a]volume={original_volume:.3f},aresample=48000[bg];{fg}[fg];"
              "[bg][fg]amix=inputs=2:duration=longest:normalize=0[aout]")
    else:
        fc = f"{fg}[aout]"
    args += ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]"]
    if srt:
        args += ["-map", "2:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=uzb",
                 "-disposition:s:0", "default"]
    args += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-metadata:s:a:0", "language=uzb"]
    if duration:
        args += ["-t", f"{duration:.3f}"]
    args += ["-movflags", "+faststart", out]
    run(args)
