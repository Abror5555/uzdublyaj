"""Nutqni matnga aylantirish (gemini-3.5-transcribe, so'z darajasidagi vaqtlar bilan)."""
import json
import re
import time
from pathlib import Path

import config
from core import ffmpeg_utils as ff
from core.gemini_client import call_with_retry, get_client, tracker
from core.languages import current as current_language

PUNCT = ".,!?;:…"


def parse_offset(value):
    """'1.5s', '00:00:01.500', 'PT1.5S', 1.5 kabi vaqtlarni soniyaga aylantiradi."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    m = re.fullmatch(r"PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?", s, re.I)
    if m and any(m.groups()):
        h, mi, se = (float(x) if x else 0.0 for x in m.groups())
        return h * 3600 + mi * 60 + se
    if ":" in s:
        total = 0.0
        for part in s.rstrip("sS").split(":"):
            total = total * 60 + float(part)
        return total
    if s.endswith("ms"):
        return float(s[:-2]) / 1000
    return float(s.rstrip("sS"))


def extract_words(interaction):
    """Javobdagi word_info izohlaridan so'zlar ro'yxatini oladi: [{'w','s','e'}]."""
    words = []
    for step in getattr(interaction, "steps", None) or []:
        if getattr(step, "type", None) != "model_output":
            continue
        for content in getattr(step, "content", None) or []:
            text = getattr(content, "text", None) or ""
            raw = text.encode("utf-8")
            anns = [a for a in (getattr(content, "annotations", None) or [])
                    if getattr(a, "type", None) == "word_info"]
            for i, a in enumerate(anns):
                start = parse_offset(getattr(a, "start_offset", None))
                end = parse_offset(getattr(a, "end_offset", None))
                word = (getattr(a, "text", None) or "").strip()
                si, ei = getattr(a, "start_index", None), getattr(a, "end_index", None)
                if raw and isinstance(si, int) and isinstance(ei, int):
                    # Tinish belgilarini to'liq matndan olamiz (gaplarga bo'lish uchun kerak)
                    if not word:
                        word = raw[si:ei].decode("utf-8", "ignore").strip()
                    nxt = anns[i + 1].start_index if i + 1 < len(anns) else None
                    nxt = nxt if isinstance(nxt, int) else len(raw)
                    tail = raw[ei:nxt].decode("utf-8", "ignore")
                    punct = "".join(ch for ch in tail if ch in PUNCT)
                    if punct and not word.endswith(tuple(PUNCT)):
                        word += punct
                if not word:
                    continue
                words.append({"w": word, "s": start, "e": end})
    # Vaqti yo'q so'zlarga qo'shnisining vaqtini beramiz
    last = 0.0
    for w in words:
        if w["s"] is None:
            w["s"] = last
        if w["e"] is None or w["e"] < w["s"]:
            w["e"] = w["s"]
        last = w["e"]
    return words


def plan_chunks(audio_path, total):
    """Uzun audioni ~CHUNK_MINUTES li bo'laklarga, iloji boricha jimlik joyidan bo'ladi."""
    size = config.CHUNK_MINUTES * 60
    if total <= size + 60:
        return [(0.0, total)]
    silences = ff.find_silences(audio_path)
    mids = [(s + e) / 2 for s, e in silences]
    chunks, start = [], 0.0
    while total - start > size + 60:
        target = start + size
        near = [m for m in mids if target - 90 <= m <= target]
        cut = max(near) if near else target
        chunks.append((start, cut))
        start = cut
    chunks.append((start, total))
    return chunks


def _wait_active(client, f, timeout=300):
    t0 = time.time()
    while True:
        state = str(getattr(f, "state", "") or "")
        if "PROCESSING" not in state.upper():
            if "FAILED" in state.upper():
                raise RuntimeError(f"Fayl serverda ishlanmadi: {f.name}")
            return f
        if time.time() - t0 > timeout:
            raise TimeoutError("Fayl serverda uzoq ishlanmoqda.")
        time.sleep(2)
        f = client.files.get(name=f.name)


def transcribe_chunk(piece: Path):
    client = get_client()
    uploaded = call_with_retry(client.files.upload, file=str(piece), config={"mime_type": "audio/mpeg"})
    uploaded = _wait_active(client, uploaded)
    try:
        interaction = call_with_retry(
            client.interactions.create,
            model=config.TRANSCRIBE_MODEL,
            input=[{"type": "audio", "uri": uploaded.uri, "mime_type": uploaded.mime_type or "audio/mpeg"}],
            generation_config={
                "transcription_config": {
                    "language_codes": [current_language()["code"]],
                    "mode": {"type": "verbatim", "timestamp_granularities": ["word"]},
                }
            },
            timeout=15 * 60,
        )
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:  # noqa: BLE001
            pass
    return interaction


def transcribe(video_path, workdir: Path, total_duration: float):
    """Butun video uchun so'zlar ro'yxati (natija keshlanadi)."""
    cache = workdir / "words.json"
    if cache.exists():
        print("  Transkripsiya keshdan olindi.")
        return json.loads(cache.read_text(encoding="utf-8"))

    tdir = workdir / "transcribe"
    tdir.mkdir(exist_ok=True)
    audio = tdir / "audio_16k.mp3"
    if not audio.exists():
        print("  Audio ajratilmoqda...")
        ff.extract_audio(video_path, audio)

    chunks = plan_chunks(audio, total_duration)
    all_words = []
    for i, (s, e) in enumerate(chunks):
        part_cache = tdir / f"chunk_{i:02d}.json"
        if part_cache.exists():
            words = json.loads(part_cache.read_text(encoding="utf-8"))
        else:
            print(f"  Nutq aniqlanmoqda: bo'lak {i + 1}/{len(chunks)} "
                  f"({s / 60:.1f}-{e / 60:.1f} daqiqa)...")
            piece = tdir / f"chunk_{i:02d}.mp3"
            ff.extract_audio(audio, piece, start=s, duration=e - s)
            interaction = transcribe_chunk(piece)
            tracker.add_transcribe((e - s) / 60)
            words = extract_words(interaction)
            if not words:
                debug = tdir / f"chunk_{i:02d}_raw.json"
                debug.write_text(interaction.model_dump_json(indent=2), encoding="utf-8")
                raise RuntimeError(
                    "Transkripsiyada so'z vaqtlari topilmadi. Javob saqlandi: " + str(debug))
            part_cache.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
            piece.unlink(missing_ok=True)
        for w in words:
            all_words.append({"w": w["w"], "s": round(w["s"] + s, 3), "e": round(w["e"] + s, 3)})

    cache.write_text(json.dumps(all_words, ensure_ascii=False), encoding="utf-8")
    return all_words
