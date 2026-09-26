"""So'zlarni tarjima va ovoz berish uchun qulay gaplarga (segmentlarga) bo'lish."""
import config

SENTENCE_END = (".", "?", "!", "…")
SOFT_END = (",", ";", ":")


def build_segments(words):
    max_len = config.MAX_SEGMENT_SECONDS
    min_len = config.MIN_SEGMENT_SECONDS
    pause = config.PAUSE_SPLIT_SECONDS

    segments, cur = [], []

    def flush():
        if cur:
            segments.append({
                "id": len(segments) + 1,
                "start": round(cur[0]["s"], 3),
                "end": round(cur[-1]["e"], 3),
                "en": " ".join(w["w"] for w in cur).strip(),
            })
            cur.clear()

    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None:
            flush()
            break
        dur = w["e"] - cur[0]["s"]
        gap = nxt["s"] - w["e"]
        word = w["w"]
        if gap >= pause * 2:
            flush()
        elif gap >= pause and dur >= min_len:
            flush()
        elif word.endswith(SENTENCE_END) and dur >= min_len:
            flush()
        elif dur >= max_len and (word.endswith(SOFT_END) or gap >= 0.25):
            flush()
        elif dur >= max_len * 1.5:
            flush()
    return segments
