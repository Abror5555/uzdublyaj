"""SRT subtitr fayllarini yaratish."""
import math
from pathlib import Path

import config

PUNCT = (",", ".", "?", "!", ";", ":")


def fmt_ts(t: float) -> str:
    t = max(0.0, t)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap(text: str, width: int):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def _balanced_two_lines(text: str, width: int):
    """Ikki qatorni taxminan teng uzunlikda bo'ladi."""
    lines = wrap(text, width)
    if len(lines) != 2:
        return lines
    words = text.split()
    best, best_diff = lines, abs(len(lines[0]) - len(lines[1]))
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        if len(a) <= width and len(b) <= width and abs(len(a) - len(b)) < best_diff:
            best, best_diff = [a, b], abs(len(a) - len(b))
    return best


def split_text(text: str, max_chars: int):
    """Uzun matnni ekranga sig'adigan, taxminan teng bo'laklarga bo'ladi
    (iloji bo'lsa tinish belgisidan keyin)."""
    if len(text) <= max_chars:
        return [text]
    k = math.ceil(len(text) / max_chars)
    target = len(text) / k
    chunks, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and len(cand) > max_chars:
            chunks.append(cur)
            cur = word
            continue
        cur = cand
        if len(chunks) < k - 1 and (
            len(cur) >= target or (len(cur) >= target * 0.75 and word.endswith(PUNCT))
        ):
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def build_cues(segments, key: str):
    width = config.SUB_MAX_LINE_CHARS
    cues = []
    for i, seg in enumerate(segments):
        text = (seg.get(key) or "").strip()
        if not text:
            continue
        start, end = seg["start"], seg["end"]
        nxt = segments[i + 1]["start"] if i + 1 < len(segments) else None
        # O'qishga ulgurish uchun subtitrni biroz uzoqroq ushlab turamiz
        end = max(end, start + 1.0) + 0.4
        if nxt is not None:
            end = min(end, nxt - 0.05)
        end = max(end, start + 0.5)
        parts = split_text(text, width * 2 - 6)
        total_chars = sum(len(p) for p in parts) or 1
        t = start
        for p in parts:
            d = (end - start) * len(p) / total_chars
            cues.append((t, t + d, "\n".join(_balanced_two_lines(p, width))))
            t += d
    return cues


def write_srt(cues, path: Path):
    out = []
    for n, (s, e, text) in enumerate(cues, 1):
        out.append(f"{n}\n{fmt_ts(s)} --> {fmt_ts(e)}\n{text}\n")
    Path(path).write_text("\n".join(out), encoding="utf-8")
    return path
