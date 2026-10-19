"""Gemini mijozi, qayta urinish va xarajat hisoblagichi."""
import random
import re
import sys
import threading
import time
import warnings

import config

# SDK har so'rovda "Interactions usage is experimental" deb ogohlantiradi — keraksiz shovqin
warnings.filterwarnings("ignore", message=".*Interactions usage is experimental.*")

_client = None


def _key_from_env_file():
    """Loyiha papkasidagi .env faylidan GEMINI_API_KEY ni o'qiydi (bu fayl GitHub'ga yuklanmaydi)."""
    path = config.BASE_DIR / ".env"
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and name.strip() == "GEMINI_API_KEY":
            value = value.strip().strip('"').strip("'")
            return "" if value.startswith("bu_yerga") else value
    return ""


def _looks_like_key(value: str) -> bool:
    """"API Kalitingiz" kabi namuna matnni haqiqiy kalit deb qabul qilmaslik uchun."""
    return bool(value) and not any(ch.isspace() for ch in value) and len(value) >= 30


def get_client():
    global _client
    if _client is None:
        key = config.get_api_key()
        if not _looks_like_key(key):
            key = _key_from_env_file()
        if not _looks_like_key(key):
            raise SystemExit(
                "\nXATO: API kalit topilmadi.\n"
                "Loyiha papkasida .env fayl yarating va unga shu qatorni yozing:\n"
                "    GEMINI_API_KEY=kalitingiz\n"
                "(yoki config.py dagi GEMINI_API_KEY = \"...\" qatoriga yozing).\n"
            )
        from google import genai

        # Standart holatda so'rovlarda vaqt chegarasi yo'q — uzilgan ulanishda dastur
        # abadiy kutib qolmasligi uchun chegara qo'yamiz (millisekund).
        # SDK ning o'z tezkor qayta urinishlari o'rniga pastdagi call_with_retry ishlaydi.
        _client = genai.Client(api_key=key, http_options={
            "timeout": 15 * 60 * 1000,
            "retry_options": {"attempts": 1},
        })
        install_response_hook(_client)
    return _client


def _strip_retry_after(response):
    """Google limit tugaganda javobga "retry-after-ms" (soatlab bo'lishi mumkin) qo'shadi va SDK
    shuncha vaqt jimgina uxlab qoladi — dastur "qotib qolgandek" ko'rinadi. Sarlavhani boshqa
    nomga o'tkazamiz: kutish qarorini call_with_retry o'zi qiladi va foydalanuvchiga ko'rsatadi."""
    value = response.headers.get("retry-after-ms")
    if value is not None:
        del response.headers["retry-after-ms"]
        response.headers["x-server-retry-after-ms"] = value


def install_response_hook(client):
    http = getattr(getattr(client, "_api_client", None), "_httpx_client", None)
    if http is None:
        return
    hooks = dict(http.event_hooks)
    hooks["response"] = [h for h in hooks.get("response", []) if h is not _strip_retry_after]
    hooks["response"].append(_strip_retry_after)
    http.event_hooks = hooks


_RETRY_MARKERS = ("RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL", "DEADLINE", "timed out",
                  "Timeout", "ConnectError", "ReadError", "RemoteProtocolError", "overloaded")

# Asosiy model band yoki limiti tugasa, shu modelga o'tiladi (config.py da o'zgartirish mumkin)
FALLBACK_MODELS = getattr(config, "FALLBACK_MODELS", {
    "gemini-3.8-flash": "gemini-3.5-flash",
    "gemini-3.8-flash-tts": "gemini-3.8-flash-lite-tts",
})

_cooldown_lock = threading.Lock()
_cooldown_until = 0.0     # 429 kelganda barcha oqimlar birga kutadi
_shown = set()            # bir xil ogohlantirishni qayta-qayta chiqarmaslik uchun
_switched = set()         # zaxira modelga o'tkazilgan modellar


def _status(exc):
    for attr in ("status_code", "code", "status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    resp = getattr(exc, "response", None) or getattr(exc, "raw_response", None)
    return getattr(resp, "status_code", None)


def _short_message(exc) -> str:
    """Server javobidan faqat odam o'qiydigan xabarni ajratib oladi."""
    raw = str(getattr(exc, "message", "") or exc)
    m = re.search(r"""['"]message['"]\s*:\s*(['"])(.+?)\1\s*[,}]""", raw)
    text = m.group(2) if m else raw
    return " ".join(text.split())[:240]


def _details(exc) -> str:
    return f"{getattr(exc, 'message', '') or exc} {getattr(exc, 'body', '') or ''}"


def _server_delay(exc, details: str):
    """Server aytgan kutish vaqti (Retry-After yoki retryDelay), soniyada."""
    headers = getattr(exc, "headers", None)
    if headers is None:
        headers = getattr(getattr(exc, "response", None), "headers", None)
    try:
        if headers is not None:
            ms = headers.get("x-server-retry-after-ms") or headers.get("retry-after-ms")
            if ms:
                return float(ms) / 1000
            ra = headers.get("retry-after")
            if ra:
                return float(ra)
    except (TypeError, ValueError):
        pass
    m = (re.search(r'retryDelay"?\s*[:=]\s*"?([\dhms.]+)', details)
         or re.search(r"retry in ([\dhms.]+)", details, re.I))
    return _parse_duration(m.group(1)) if m else None


def _parse_duration(text: str):
    """'37s', '2.5s', '6h7m11s', '7m' kabi vaqtlarni soniyaga aylantiradi."""
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*([hms])", text)
    if not parts:
        try:
            return float(text.rstrip("."))
        except ValueError:
            return None
    mult = {"h": 3600, "m": 60, "s": 1}
    return sum(float(v) * mult[u] for v, u in parts)


# ── Holat qatori: qayta urinishlar terminalni to'ldirmasligi uchun bir joyda yangilanadi ──
_status_handler = None
_status_lock = threading.Lock()
_status_dirty = False


def set_status_handler(fn):
    """Progress-bar bor paytda holat matni shu funksiyaga uzatiladi (None = oddiy qator)."""
    global _status_handler
    _status_handler = fn


def show_status(text: str):
    global _status_dirty
    handler = _status_handler
    if handler is not None:
        handler(text)
        return
    with _status_lock:
        sys.stdout.write("\r    " + text[:74].ljust(74))
        sys.stdout.flush()
        _status_dirty = True


def clear_status():
    global _status_dirty
    handler = _status_handler
    if handler is not None:
        handler("")
        return
    with _status_lock:
        if _status_dirty:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            _status_dirty = False


def log(text: str):
    """Muhim xabarni alohida qatorda chiqaradi (progress-bar bilan to'qnashmaydi)."""
    clear_status()
    try:
        from tqdm import tqdm

        tqdm.write(text)
    except Exception:  # noqa: BLE001
        print(text)


def _warn_once(key, text):
    if key not in _shown:
        _shown.add(key)
        log(text)


def _wait_cooldown():
    while True:
        with _cooldown_lock:
            left = _cooldown_until - time.time()
        if left <= 0:
            return
        time.sleep(min(left, 5))


def _set_cooldown(seconds):
    global _cooldown_until
    with _cooldown_lock:
        _cooldown_until = max(_cooldown_until, time.time() + seconds)


class DailyQuotaError(RuntimeError):
    pass


def call_with_retry(fn, *args, retries=None, **kwargs):
    """Vaqtinchalik xatolarda (429, 5xx, tarmoq) kutib qayta urinadi.
    Model baribir javob bermasa, FALLBACK_MODELS dagi zaxira modelga o'tadi."""
    model = kwargs.get("model")
    backup = FALLBACK_MODELS.get(model)
    if model in _switched and backup:
        return _retry_loop(fn, args, dict(kwargs, model=backup), retries)
    try:
        return _retry_loop(fn, args, kwargs, retries)
    except Exception as exc:  # noqa: BLE001
        if not backup or not _is_retriable(exc)[0]:
            raise
        with _cooldown_lock:
            first = model not in _switched
            _switched.add(model)  # shu ishga tushirish oxirigacha zaxira model ishlatiladi
        if first:
            log(f"    ! {model} hozir ishlamayapti: {_short_message(exc)}\n"
                f"      Qolgan qism zaxira model bilan davom etadi: {backup}")
        return _retry_loop(fn, args, dict(kwargs, model=backup), retries)


def _is_retriable(exc):
    code = _status(exc)
    details = _details(exc)
    name = type(exc).__name__
    retriable = (code in (408, 429) or (isinstance(code, int) and code >= 500)
                 or isinstance(exc, DailyQuotaError)
                 or any(m in f"{name} {details}" for m in _RETRY_MARKERS))
    return retriable, code, details


def _retry_loop(fn, args, kwargs, retries):
    model = kwargs.get("model", "")
    attempts = retries or 8
    waited = False
    for attempt in range(attempts):
        _wait_cooldown()
        try:
            result = fn(*args, **kwargs)
            if waited:
                clear_status()
            return result
        except Exception as exc:  # noqa: BLE001
            retriable, code, details = _is_retriable(exc)
            if not retriable:
                raise
            short = _short_message(exc)

            if code == 429:
                if "free_tier" in details:
                    _warn_once("free", "    ! DIQQAT: kalitingiz BEPUL (free tier) limitlarida ishlayapti. "
                                       "Oldindan to'lov qilingan loyihaning API kalitini config.py ga qo'ying, "
                                       "aks holda ish juda sekin bo'ladi.")
                if re.search(r"per[\s_-]?day", details, re.I):
                    # Kunlik limit: kutishdan foyda yo'q, darhol zaxira modelga o'tamiz
                    raise DailyQuotaError(f"{model}: kunlik limit tugadi. {short}") from exc
                _warn_once(("429", model), f"    ! {model}: so'rovlar limiti (429). Server javobi: {short}")
            elif isinstance(code, int) and code >= 500:
                _warn_once(("5xx", model), f"    ! {model}: Google serverlari band ({code}). "
                                           "Bu vaqtinchalik holat, kutib qayta urinaman.")

            if attempt == attempts - 1:
                raise
            if isinstance(code, int) and code >= 500 and attempt >= 3 and FALLBACK_MODELS.get(model):
                raise  # server uzoq band — zaxira modelga o'tish vaqti
            wait = min(90, 3 * 2 ** attempt) + random.uniform(0, 2)
            server = _server_delay(exc, details)
            if server and server > 300:
                # Server soatlab kutishni so'rasa, bu kunlik/umumiy limit tugagani
                raise DailyQuotaError(f"{model}: limit tugadi, server {server / 3600:.1f} soat "
                                      f"kutishni so'rayapti. {short}") from exc
            if server:
                wait = max(wait, server + 1)
            if code == 429:
                _set_cooldown(wait)  # boshqa oqimlar ham shu vaqt kutadi
            reason = "limit" if code == 429 else ("server band" if isinstance(code, int) else "tarmoq")
            show_status(f"{reason} ({code or type(exc).__name__}): {wait:.0f} s kutilmoqda, "
                        f"urinish {attempt + 1}/{attempts - 1}")
            waited = True
            time.sleep(wait)


def _get(obj, name, default=0):
    val = getattr(obj, name, None) if obj is not None else None
    return val if isinstance(val, (int, float)) else default


class CostTracker:
    """So'rovlardagi tokenlar asosida taxminiy xarajatni hisoblaydi."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.transcribe_minutes = 0.0
        self.text_in = self.text_out = 0
        self.tts_in = self.tts_out = 0
        self.tts_calls = 0

    def add_transcribe(self, minutes):
        with self.lock:
            self.transcribe_minutes += minutes

    def add_text(self, interaction):
        u = getattr(interaction, "usage", None)
        with self.lock:
            self.text_in += _get(u, "total_input_tokens")
            self.text_out += _get(u, "total_output_tokens") + _get(u, "total_thought_tokens")

    def add_tts(self, interaction, audio_seconds):
        u = getattr(interaction, "usage", None)
        out = _get(u, "total_output_tokens") or int(audio_seconds * 25)
        with self.lock:
            self.tts_in += _get(u, "total_input_tokens")
            self.tts_out += out
            self.tts_calls += 1

    def cost(self):
        c = self.transcribe_minutes * config.PRICE_TRANSCRIBE_PER_MIN
        c += self.text_in / 1e6 * config.PRICE_TEXT_IN_PER_M
        c += self.text_out / 1e6 * config.PRICE_TEXT_OUT_PER_M
        c += self.tts_in / 1e6 * config.PRICE_TTS_IN_PER_M
        c += self.tts_out / 1e6 * config.PRICE_TTS_OUT_PER_M
        return c

    def summary(self):
        lines = ["Taxminiy xarajat (shu ishga tushirishda):"]
        if self.transcribe_minutes:
            lines.append(f"  - Nutqni aniqlash: {self.transcribe_minutes:.1f} daqiqa")
        if self.text_in or self.text_out:
            lines.append(f"  - Tarjima: {self.text_in:,} kirish / {self.text_out:,} chiqish token")
        if self.tts_calls:
            lines.append(f"  - Ovoz: {self.tts_calls} ta so'rov, {self.tts_out:,} audio token")
        lines.append(f"  JAMI: ~${self.cost():.3f}")
        return "\n".join(lines)


tracker = CostTracker()
