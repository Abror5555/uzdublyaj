"""Segmentlarni inglizchadan o'zbekchaga tarjima qilish (gemini flash, JSON chiqish)."""
import json
from pathlib import Path

import config
from core.gemini_client import call_with_retry, get_client, tracker

SYSTEM_PROMPT = """You are a professional translator who localizes English video tutorials \
(mostly programming and IT) into Uzbek for Uzbek viewers.

Rules:
1. Translate the meaning naturally, the way an experienced Uzbek teacher would SAY it out loud. \
Spoken, clear, friendly; never word-for-word.
2. Use the Uzbek Latin alphabet. Write o' and g' with a plain apostrophe, and use ' for the \
tutuq belgisi. Write numbers as digits.
3. Keep code, commands, file and folder names, function and variable names, URLs, keyboard \
shortcuts, product and brand names exactly as in the original. Also keep these terms in their \
original form: {terms}.
4. Each segment has "max_chars": the translation will be voiced over the original timing, so \
keep it at or under that length by phrasing concisely. Never drop important information.
5. Remove filler words (um, uh, you know, like, so yeah) and false starts.
6. Return exactly one item for every input id. Never merge, split or reorder segments. If a \
segment contains only filler, return an empty string for it.
7. "context" contains earlier segments that are already translated; use them only for \
consistency of terms and tone. Do not return them."""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "uz": {"type": "string"}},
                "required": ["id", "uz"],
            },
        }
    },
    "required": ["items"],
}

SHORTEN_SCHEMA = {
    "type": "object",
    "properties": {"uz": {"type": "string"}},
    "required": ["uz"],
}


def _max_chars(seg, next_start=None):
    slot = (next_start if next_start is not None else seg["end"] + 0.5) - seg["start"]
    slot = max(slot, seg["end"] - seg["start"], 0.8)
    # Haqiqiy o'lchov: Gemini TTS o'zbekcha ~12.5 belgi/s gapiradi; zaxira bilan qisqaroq so'raymiz
    factor = getattr(config, "TRANSLATION_LENGTH_FACTOR", 0.85)
    return max(12, int(slot * config.UZ_CHARS_PER_SECOND * factor))


def _ask(prompt: str, schema: dict, system: str):
    client = get_client()
    interaction = call_with_retry(
        client.interactions.create,
        model=config.TRANSLATE_MODEL,
        system_instruction=system,
        input=prompt,
        response_format={"type": "text", "mime_type": "application/json", "schema": schema},
        generation_config={"thinking_level": config.THINKING_LEVEL},
        timeout=getattr(config, "TEXT_TIMEOUT", 300),
    )
    tracker.add_text(interaction)
    text = (interaction.output_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    return json.loads(text)


def _translate_batch(batch, context, title):
    payload = {
        "video_title": title,
        "context": context,
        "segments": batch,
    }
    prompt = ("Translate the following segments into Uzbek. Input JSON:\n"
              + json.dumps(payload, ensure_ascii=False))
    system = SYSTEM_PROMPT.format(terms=", ".join(config.KEEP_TERMS))
    data = _ask(prompt, SCHEMA, system)
    return {int(it["id"]): (it.get("uz") or "").strip() for it in data.get("items", []) if "id" in it}


def translate_segments(segments, workdir: Path, title: str):
    """Har bir segmentga 'uz' maydonini qo'shadi. Natija har bir paketdan keyin saqlanadi."""
    cache = workdir / "translation.json"
    en_by_id = {s["id"]: s["en"] for s in segments}
    pos = {s["id"]: i for i, s in enumerate(segments)}
    done = {}
    if cache.exists():
        saved = json.loads(cache.read_text(encoding="utf-8"))
        done = {s["id"]: s["uz"] for s in saved
                if "uz" in s and en_by_id.get(s["id"]) == s.get("en")}

    todo = [s for s in segments if s["id"] not in done]
    if not todo:
        print("  Tarjima keshdan olindi.")
    size = config.TRANSLATE_BATCH_SIZE

    for b in range(0, len(todo), size):
        batch_segs = todo[b:b + size]
        print(f"  Tarjima qilinmoqda: {b + 1}-{min(b + size, len(todo))} / {len(todo)} gap...")
        batch = []
        for s in batch_segs:
            idx = pos[s["id"]]
            nxt = segments[idx + 1]["start"] if idx + 1 < len(segments) else None
            batch.append({"id": s["id"], "en": s["en"], "max_chars": _max_chars(s, nxt)})
        first_idx = pos[batch_segs[0]["id"]]
        context = [{"en": segments[j]["en"], "uz": done[segments[j]["id"]]}
                   for j in range(max(0, first_idx - 4), first_idx) if segments[j]["id"] in done]

        result = _translate_batch(batch, context, title)
        missing = [x for x in batch if x["id"] not in result]
        if missing:  # tushib qolganlarini bir marta qayta so'raymiz
            result.update(_translate_batch(missing, context, title))
        for x in batch:
            if x["id"] not in result:
                print(f"    ! {x['id']}-gap tarjima qilinmadi, bo'sh qoldirildi.")
            done[x["id"]] = result.get(x["id"], "")

        _save(segments, done, cache)

    for s in segments:
        s["uz"] = done.get(s["id"], "")
    _save(segments, done, cache)
    return segments


def _save(segments, done, cache):
    out = [dict(s, uz=done[s["id"]]) for s in segments if s["id"] in done]
    cache.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def shorten(uz_text: str, en_text: str, max_chars: int) -> str:
    """Ovoz vaqtga sig'masa, tarjimani ma'nosini saqlagan holda qisqartiradi."""
    prompt = (
        f"This Uzbek sentence is too long for the dubbing slot. Rewrite it in natural spoken Uzbek "
        f"(Latin script) in at most {max_chars} characters, keeping the key meaning and all code, "
        f"names and terms unchanged.\nEnglish original: {en_text}\nCurrent Uzbek: {uz_text}"
    )
    system = "You shorten Uzbek dubbing lines without losing their meaning."
    try:
        data = _ask(prompt, SHORTEN_SCHEMA, system)
        new = (data.get("uz") or "").strip()
        return new if new and len(new) < len(uz_text) else uz_text
    except Exception as exc:  # noqa: BLE001
        print(f"    ! Qisqartirib bo'lmadi: {exc}")
        return uz_text
