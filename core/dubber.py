"""O'zbekcha ovoz berish: gaplarni bloklarga yig'ib TTS qilish, vaqtga moslash va bitta audio yo'lakka yig'ish."""
import base64
import hashlib
import io
import json
import wave
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import numpy as np
from tqdm import tqdm

import config
from core import ffmpeg_utils as ff
from core.gemini_client import DailyQuotaError, call_with_retry, get_client, set_status_handler, tracker
from core.translator import shorten

SR = 24000          # Gemini TTS chiqishi: 24 kHz, mono, 16-bit
GAP = 0.08          # gaplar orasidagi minimal pauza (s)


# ── WAV yordamchilari ───────────────────────────────────────
def read_wav(path) -> np.ndarray:
    try:
        with wave.open(str(path), "rb") as w:
            rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
            frames = w.readframes(w.getnframes())
        if width != 2:
            raise wave.Error("16-bit emas")
    except (wave.Error, EOFError):
        # Nostandart WAV bo'lsa, ffmpeg bilan oddiy 16-bit PCM ga o'tkazamiz
        fixed = Path(path).with_suffix(".fixed.wav")
        ff.run(["-i", path, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", fixed])
        with wave.open(str(fixed), "rb") as w:
            rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
            frames = w.readframes(w.getnframes())
        fixed.unlink(missing_ok=True)
    data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if rate != SR:  # oddiy chiziqli qayta namunalash
        n = int(len(data) * SR / rate)
        data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data).astype(np.float32)
    return data


def write_wav(path, data: np.ndarray):
    pcm = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def trim_silence(data: np.ndarray, threshold=0.012, pad=0.04) -> np.ndarray:
    idx = np.flatnonzero(np.abs(data) > threshold)
    if idx.size == 0:
        return data[:0]
    p = int(pad * SR)
    return data[max(0, idx[0] - p): min(len(data), idx[-1] + p)]


def _to_wav_bytes(audio) -> bytes:
    data = audio.data
    if isinstance(data, str):
        data = base64.b64decode(data)
    data = bytes(data)
    if data[:4] == b"RIFF":
        return data
    # Sarlavhasiz PCM (audio/l16) kelsa, WAV sarlavha qo'shamiz
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(getattr(audio, "sample_rate", None) or SR)
        w.writeframes(data)
    return buf.getvalue()


# ── TTS ─────────────────────────────────────────────────────
def _tts_key(text: str) -> str:
    raw = f"{config.TTS_MODEL}|{config.TTS_VOICE}|{config.TTS_STYLE}|{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


TTS_TIMEOUT = getattr(config, "TTS_TIMEOUT", 180)        # bitta so'rovni maksimal kutish (s)
# Ketma-ket gaplar bitta "blok"ka yig'ilib, bitta so'rovda ovozlanadi. Bu so'rovlar sonini
# 3-4 barobar kamaytiradi (Google kunlik limitlari uchun muhim). 0 = har bir gap alohida.
DUB_BLOCK_SECONDS = getattr(config, "DUB_BLOCK_SECONDS", 20.0)
DUB_BLOCK_MAX_GAP = getattr(config, "DUB_BLOCK_MAX_GAP", 1.2)  # bundan uzun pauzada blok yopiladi


def _tts_request(text: str):
    content = {"type": "text", "text": text}
    if config.TTS_STYLE:
        content["annotations"] = [{"type": "speech_metadata", "style": config.TTS_STYLE}]
    voice = {"voice": config.TTS_VOICE}
    if config.TTS_LANGUAGE:
        voice["language"] = config.TTS_LANGUAGE
    interaction = call_with_retry(
        get_client().interactions.create,
        model=config.TTS_MODEL,
        input=[{"type": "user_input", "content": [content]}],
        response_format={"type": "audio", "mime_type": "audio/wav"},
        generation_config={"speech_config": [voice]},
        timeout=TTS_TIMEOUT,
    )
    if getattr(interaction, "output_audio", None) is None:
        raise RuntimeError(f"TTS audio qaytarmadi: {text[:60]}")
    return _to_wav_bytes(interaction.output_audio), interaction


def _done(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 100


def synthesize(text: str, out_path: Path) -> Path:
    if _done(out_path):
        return out_path
    wav_bytes, interaction = _tts_request(text)
    tmp = out_path.with_suffix(".part")
    tmp.write_bytes(wav_bytes)
    tmp.replace(out_path)
    try:
        with wave.open(str(out_path), "rb") as w:
            seconds = w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError):
        seconds = len(wav_bytes) / (SR * 2)
    tracker.add_tts(interaction, seconds)
    return out_path


def _synthesize_many(jobs, desc):
    """jobs: [(blok, matn, fayl)] — parallel ravishda ovoz yaratadi."""
    errors, daily = [], None
    pbar = tqdm(total=len(jobs), desc=desc, ncols=90)
    set_status_handler(lambda text: pbar.set_postfix_str(text, refresh=True))
    pool = ThreadPoolExecutor(max_workers=max(1, config.TTS_WORKERS))
    interrupted = False
    try:
        futures = {pool.submit(synthesize, text, path): blk for blk, text, path in jobs}
        pending = set(futures)
        while pending and daily is None:
            # Qisqa kutish: Windows'da Ctrl+C darhol ishlashi uchun
            done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
            for fut in done:
                blk = futures[fut]
                try:
                    fut.result()
                except DailyQuotaError as exc:
                    daily = exc
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{blk['id']}: {exc}")
                    tqdm.write(f"    ! {blk['id']}-gapdan boshlangan blok ovozlanmadi: {exc}")
                pbar.update(1)
    except KeyboardInterrupt:
        interrupted = True
        raise
    finally:
        set_status_handler(None)
        pool.shutdown(wait=not interrupted, cancel_futures=True)
        pbar.close()
    if daily is not None:
        raise RuntimeError(
            "Bugungi ovoz berish limiti tugadi (Google hisobingiz bo'yicha). Tayyor qism saqlandi — "
            "limit yangilangach qayta ishga tushiring, faqat qolganlari so'raladi.\n"
            f"Server javobi: {daily}")
    if jobs and len(errors) == len(jobs):
        raise RuntimeError("Birorta ham ovoz yaratilmadi. Birinchi xato: " + errors[0])
    return errors


def make_blocks(segments):
    """Ketma-ket gaplarni ~DUB_BLOCK_SECONDS uzunlikdagi bloklarga yig'adi.
    Uzun pauzada blok yopiladi, shunda ovoz video bilan qayta sinxronlashadi."""
    groups, cur = [], []
    for s in segments:
        if not (s.get("uz") or "").strip():
            continue
        if cur and (DUB_BLOCK_SECONDS <= 0
                    or s["end"] - cur[0]["start"] > DUB_BLOCK_SECONDS
                    or s["start"] - cur[-1]["end"] > DUB_BLOCK_MAX_GAP):
            groups.append(cur)
            cur = []
        cur.append(s)
    if cur:
        groups.append(cur)
    return [{
        "id": g[0]["id"],
        "ids": [x["id"] for x in g],
        "start": g[0]["start"],
        "end": g[-1]["end"],
        "uz": " ".join(x["uz"].strip() for x in g),
        "en": " ".join(x["en"] for x in g),
    } for g in groups]


def _slot(blocks, i, total):
    nxt = blocks[i + 1]["start"] if i + 1 < len(blocks) else total
    return max(0.3, nxt - blocks[i]["start"] - GAP)


# ── Asosiy jarayon ──────────────────────────────────────────
def build_dub_track(segments, workdir: Path, total: float) -> Path:
    tts_dir = workdir / "tts"
    tts_dir.mkdir(exist_ok=True)
    plan_file = workdir / "dub_plan.json"
    plan = json.loads(plan_file.read_text(encoding="utf-8")) if plan_file.exists() else {}
    blocks = make_blocks(segments)

    # 1) Har bir blok uchun matn (avval qisqartirilgan bo'lsa, o'shani olamiz)
    for b in blocks:
        key = f"b{b['id']}"
        saved = plan.get(key)
        if saved and saved.get("uz") == b["uz"]:
            b["uz_dub"] = saved["uz_dub"]
        else:
            b["uz_dub"] = b["uz"]
            plan.pop(key, None)

    def path_for(b):
        return tts_dir / f"blk_{b['id']:04d}_{_tts_key(b['uz_dub'])}.wav"

    print(f"  {len(segments)} ta gap {len(blocks)} ta blokka yig'ildi (har blok — bitta so'rov).")
    todo = [(b, b["uz_dub"], path_for(b)) for b in blocks if not _done(path_for(b))]
    if todo:
        _synthesize_many(todo, "  Ovoz berilmoqda")
    else:
        print("  Ovozlar keshdan olindi.")

    # 2) Vaqtga sig'maydigan bloklarni qisqartirib, qayta ovoz beramiz
    redo = []
    for i, b in enumerate(blocks):
        p = path_for(b)
        if not _done(p):
            continue
        dur = len(trim_silence(read_wav(p))) / SR
        slot = _slot(blocks, i, total)
        if dur / slot > config.MAX_SPEEDUP and not plan.get(f"b{b['id']}", {}).get("shortened"):
            target = int(len(b["uz_dub"]) * (slot * config.MAX_SPEEDUP / dur) * 0.95)
            new = shorten(b["uz_dub"], b["en"], max(10, target))
            if new != b["uz_dub"]:
                b["uz_dub"] = new
                redo.append((b, new, path_for(b)))
            plan[f"b{b['id']}"] = {"uz": b["uz"], "uz_dub": b["uz_dub"], "shortened": True}
    for b in blocks:
        plan.setdefault(f"b{b['id']}", {"uz": b["uz"], "uz_dub": b["uz_dub"], "shortened": False})
    plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    if redo:
        print(f"  {len(redo)} ta blok vaqtga sig'maslik uchun qisqartirildi.")
        _synthesize_many(redo, "  Qayta ovoz")

    # 3) Hammasini vaqt chizig'iga joylashtiramiz
    print("  Audio yo'lak yig'ilmoqda...")
    track = np.zeros(int((total + 5) * SR), dtype=np.float32)
    cursor, late, sped = 0.0, 0, 0
    tmp_dir = workdir / "tts_fit"
    tmp_dir.mkdir(exist_ok=True)
    for i, b in enumerate(blocks):
        p = path_for(b)
        if not _done(p):
            continue
        audio = trim_silence(read_wav(p))
        if audio.size == 0:
            continue
        start = max(b["start"], cursor)
        nxt = blocks[i + 1]["start"] if i + 1 < len(blocks) else total
        slot = max(0.3, nxt - start - GAP)
        dur = len(audio) / SR
        if dur > slot:
            factor = min(dur / slot, config.MAX_SPEEDUP)
            if factor > 1.01:
                src = tmp_dir / "in.wav"
                dst = tmp_dir / "out.wav"
                write_wav(src, audio)
                ff.change_tempo(src, dst, factor, SR)
                audio = read_wav(dst)
                sped += 1
        a = int(start * SR)
        e = a + len(audio)
        if e > len(track):
            track = np.concatenate([track, np.zeros(e - len(track) + SR, dtype=np.float32)])
        track[a:e] += audio
        if start > b["start"] + 0.3:
            late += 1
        cursor = start + len(audio) / SR + GAP

    track = track[: int(max(total, cursor) * SR)]
    peak = float(np.max(np.abs(track))) if track.size else 0.0
    if peak > 0.98:
        track *= 0.98 / peak
    out = workdir / "dub_track.wav"
    write_wav(out, track)
    if sped or late:
        print(f"  Tezlashtirilgan bloklar: {sped}, biroz kechikkan bloklar: {late}")
    return out
