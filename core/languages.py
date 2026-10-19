"""Video (manba) tillari: ingliz, rus, koreys.

Yangi til qo'shish uchun LANGUAGES ga bitta yozuv qo'shish kifoya.
"""
import config

LANGUAGES = {
    "en": {
        "code": "en-US",              # nutqni aniqlash uchun BCP-47 kodi
        "name": "English",            # tarjimon modelga til nomi
        "uz": "ingliz",               # menyuda ko'rinadigan nom
        "fillers": "um, uh, you know, like, so yeah, I mean",
        "notes": "",
    },
    "ru": {
        "code": "ru-RU",
        "name": "Russian",
        "uz": "rus",
        "fillers": "ну, вот, как бы, это самое, типа, значит, короче, э-э",
        "notes": (
            "The speaker often says IT terms and brand names in Cyrillic transliteration "
            "(e.g. коммит, пуш, деплой, фреймворк, Пайтон, Джанго, Гитхаб). Write them in their "
            "original Latin form (commit, push, deploy, framework, Python, Django, GitHub). "
            "Never leave Cyrillic letters in the Uzbek text."
        ),
    },
    "ko": {
        "code": "ko-KR",
        "name": "Korean",
        "uz": "koreys",
        "fillers": "어, 음, 그, 저기, 뭐, 이제, 약간, 그러니까",
        "notes": (
            "The speaker often says IT terms and brand names in Hangul transliteration "
            "(e.g. 파이썬, 리액트, 깃허브, 커밋, 서버, 데이터베이스). Write them in their original Latin "
            "form (Python, React, GitHub, commit, server, database). Korean speech levels and "
            "honorifics have no direct equivalent: always use a natural, polite Uzbek teacher tone "
            "addressing the viewer as 'siz'. Korean often omits the subject; add it in Uzbek when "
            "needed for a clear sentence. Never leave Hangul letters in the Uzbek text."
        ),
    },
}

# Eski config.py da SOURCE_LANGUAGE = "en-US" kabi to'liq kod yozilgan bo'lishi mumkin
_ALIASES = {
    "en-us": "en", "en-gb": "en", "english": "en", "ingliz": "en", "inglizcha": "en",
    "ru-ru": "ru", "russian": "ru", "rus": "ru", "ruscha": "ru",
    "ko-kr": "ko", "korean": "ko", "kr": "ko", "koreys": "ko", "koreyscha": "ko",
}

_current = None


def normalize(lang) -> str:
    key = str(lang or "en").strip().lower()
    key = _ALIASES.get(key, key)
    if key not in LANGUAGES:
        raise ValueError(f"Noma'lum til: {lang}. Mavjudlari: {', '.join(LANGUAGES)}")
    return key


def set_current(lang) -> str:
    """Joriy ish uchun video tilini belgilaydi va uning qisqa kodini qaytaradi (en/ru/ko)."""
    global _current
    _current = normalize(lang)
    return _current


def current_key() -> str:
    if _current is None:
        return normalize(getattr(config, "SOURCE_LANGUAGE", "en"))
    return _current


def current() -> dict:
    return LANGUAGES[current_key()]
