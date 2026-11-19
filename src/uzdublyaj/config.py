"""
UzDublyaj sozlamalari.

Bu fayldagi qiymatlar — standart (default) sozlamalar. Ularni shu faylni
tahrirlamasdan, foydalanuvchining sozlamalar faylida o'zgartiring:

    Windows:        %LOCALAPPDATA%\\uzdublyaj\\config.json
    Linux / macOS:  ~/.config/uzdublyaj/config.json

Faylning aniq joyini `uzdublyaj --config` buyrug'i ko'rsatadi (fayl yo'q bo'lsa,
namuna bilan yaratadi). Unga KATTA HARFLI istalgan sozlamani yozish mumkin, masalan:

    {"GEMINI_API_KEY": "AIza...", "SOURCE_LANGUAGE": "ru", "TTS_VOICE": "Kore"}

API kalit quyidagi tartibda qidiriladi: config.json -> GEMINI_API_KEY muhit
o'zgaruvchisi -> joriy papkadagi .env fayli.
"""
import json
import os
import sys
from pathlib import Path


def _app_dir() -> Path:
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "uzdublyaj"
    base = os.getenv("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "uzdublyaj"


# ─────────────────────────────────────────────────────────────
# 1. API KALIT
# ─────────────────────────────────────────────────────────────
# Kalitni https://aistudio.google.com/apikey sahifasidan oling va config.json ga
# yozing (yoki birinchi ishga tushirishda dastur o'zi so'raydi va saqlaydi).
GEMINI_API_KEY = ""


def get_api_key() -> str:
    return (GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")).strip()


# ─────────────────────────────────────────────────────────────
# 2. PAPKALAR
# ─────────────────────────────────────────────────────────────
APP_DIR = _app_dir()                         # sozlamalar va ffmpeg shu yerda
CONFIG_FILE = Path(os.getenv("UZDUBLYAJ_CONFIG") or (APP_DIR / "config.json"))
# natijalar shu yerga tushadi (repo ichidagi main.py uchun standart: repo/output)
OUTPUT_DIR = Path(os.getenv("UZDUBLYAJ_DEFAULT_OUTPUT_DIR") or (Path.home() / "UzDublyaj"))
BIN_DIR = APP_DIR / "bin"                    # ffmpeg shu yerga avtomatik ko'chiriladi

# ─────────────────────────────────────────────────────────────
# 3. MODELLAR (nomlar yangilansa, faqat shu yerni o'zgartiring)
# ─────────────────────────────────────────────────────────────
TRANSCRIBE_MODEL = "gemini-3.5-transcribe"   # nutq -> matn (so'z vaqtlari bilan)
TRANSLATE_MODEL = "gemini-3.8-flash"         # ingliz/rus/koreys -> o'zbekcha
TTS_MODEL = "gemini-3.8-flash-tts"           # o'zbekcha matn -> ovoz
# Arzonroq ovoz uchun: TTS_MODEL = "gemini-3.8-flash-lite-tts"

# ─────────────────────────────────────────────────────────────
# 4. TIL
# ─────────────────────────────────────────────────────────────
# Videodagi til: "en" (ingliz), "ru" (rus), "ko" (koreys).
# Bu faqat standart qiymat: menyuda yoki --lang bilan har safar boshqasini tanlash mumkin.
# Tillar ro'yxati va ularning sozlamalari: uzdublyaj/languages.py
SOURCE_LANGUAGE = "en"

# ─────────────────────────────────────────────────────────────
# 5. YUKLAB OLISH (YouTube havola berilganda)
# ─────────────────────────────────────────────────────────────
MAX_VIDEO_HEIGHT = 1080     # 720 qilsangiz, tezroq yuklanadi va ishlanadi

# ─────────────────────────────────────────────────────────────
# 6. NUTQNI MATNGA AYLANTIRISH
# ─────────────────────────────────────────────────────────────
# So'z vaqtlari yoqilganda bitta so'rov 30 daqiqadan oshmasligi kerak,
# shuning uchun uzun audio bo'laklarga bo'linadi.
CHUNK_MINUTES = 20

# ─────────────────────────────────────────────────────────────
# 7. GAPLARGA BO'LISH
# ─────────────────────────────────────────────────────────────
MAX_SEGMENT_SECONDS = 12.0   # bitta tarjima bo'lagining maksimal uzunligi
MIN_SEGMENT_SECONDS = 1.2    # bundan qisqa gaplar keyingisiga qo'shiladi
PAUSE_SPLIT_SECONDS = 0.8    # shuncha jimlikda gap bo'linadi

# ─────────────────────────────────────────────────────────────
# 8. TARJIMA
# ─────────────────────────────────────────────────────────────
TRANSLATE_BATCH_SIZE = 40    # bitta so'rovda nechta gap tarjima qilinadi
THINKING_LEVEL = "low"       # "minimal" | "low" | "medium" | "high"
UZ_CHARS_PER_SECOND = 14.0   # o'zbekcha nutq tezligi (dublyaj uzunligini hisoblash uchun)

# Tarjima qilinmasdan, asl holida qoladigan atamalar
KEEP_TERMS = [
    "Python", "JavaScript", "TypeScript", "React", "Next.js", "Node.js",
    "Django", "FastAPI", "Flask", "API", "REST", "JSON", "HTML", "CSS",
    "Git", "GitHub", "Docker", "Linux", "Windows", "VS Code", "terminal",
    "frontend", "backend", "framework", "database", "SQL", "Postgres",
    "commit", "push", "pull request", "branch", "merge", "deploy",
]

# ─────────────────────────────────────────────────────────────
# 9. SUBTITR
# ─────────────────────────────────────────────────────────────
# "burn" — subtitr videoning ichiga chiziladi (har qanday pleyerda ko'rinadi,
#          lekin video qayta kodlanadi, protsessorda biroz vaqt oladi)
# "soft" — subtitr alohida yo'lak sifatida qo'shiladi (bir zumda tayyor,
#          VLC kabi pleyerlarda yoqib-o'chirsa bo'ladi)
SUBTITLE_MODE = "burn"
SUB_MAX_LINE_CHARS = 42      # bir qatordagi maksimal belgilar
SUB_FONT = "Arial"
SUB_FONT_SIZE = 18
VIDEO_PRESET = "veryfast"    # libx264 tezligi: ultrafast..veryslow
VIDEO_CRF = 22               # sifat: kichikroq = sifatliroq, fayl kattaroq

# ─────────────────────────────────────────────────────────────
# 10. DUBLYAJ (OVOZ BERISH)
# ─────────────────────────────────────────────────────────────
# Ovozlar: Charon (ma'lumot beruvchi, erkak), Kore (qat'iy), Puck (quvnoq),
# Iapetus (aniq), Sadaltager (bilimdon), Achird (samimiy) va boshqalar.
TTS_VOICE = "Charon"
TTS_STYLE = "clear and calm, like a teacher explaining a lesson"
TTS_LANGUAGE = None          # None = avtomatik aniqlash
TTS_WORKERS = 4              # bir vaqtda nechta ovoz so'rovi yuboriladi
MAX_SPEEDUP = 1.30           # ovoz vaqtga sig'masa, maksimal tezlashtirish
ORIGINAL_VOLUME = 0.12       # asl ovoz fonda qanchalik eshitiladi (0 = o'chiq)
DUB_SOFT_SUBTITLES = True    # dublyaj videosiga o'zbekcha subtitr yo'lagi qo'shish

# ─────────────────────────────────────────────────────────────
# 11. NARXLAR (taxminiy xarajatni ko'rsatish uchun, USD)
# ─────────────────────────────────────────────────────────────
PRICE_TRANSCRIBE_PER_MIN = 0.005          # $0.003 kirish + $0.002 chiqish
PRICE_TEXT_IN_PER_M = 0.75                # 1 mln token
PRICE_TEXT_OUT_PER_M = 3.75
PRICE_TTS_IN_PER_M = 0.50
PRICE_TTS_OUT_PER_M = 9.00                # flash-lite-tts uchun 6.00


# ─────────────────────────────────────────────────────────────
# 12. FOYDALANUVCHI SOZLAMALARINI YUKLASH
# ─────────────────────────────────────────────────────────────
_PATH_KEYS = ("OUTPUT_DIR", "BIN_DIR", "VIDEOS_DIR")


def _read_user_settings(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig") or "{}")
    except (OSError, ValueError) as exc:
        print(f"OGOHLANTIRISH: sozlamalar fayli o'qilmadi ({path}): {exc}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def load(path=None) -> None:
    """config.json va muhit o'zgaruvchilaridagi sozlamalarni shu modulga qo'llaydi."""
    path = Path(path) if path else CONFIG_FILE
    module = sys.modules[__name__]
    for key, value in _read_user_settings(path).items():
        if not key.isupper():
            continue
        if key in _PATH_KEYS and value:
            value = Path(os.path.expandvars(str(value))).expanduser()
        setattr(module, key, value)
    env_output = os.getenv("UZDUBLYAJ_OUTPUT_DIR")
    if env_output:
        module.OUTPUT_DIR = Path(env_output).expanduser()


def save_setting(key: str, value, path=None) -> Path:
    """Bitta sozlamani config.json ga yozadi (boshqa sozlamalar saqlanib qoladi)."""
    path = Path(path) if path else CONFIG_FILE
    data = _read_user_settings(path)
    data[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    setattr(sys.modules[__name__], key, value)
    return path


def ensure_config_file(path=None) -> Path:
    """Sozlamalar fayli yo'q bo'lsa, eng ko'p o'zgartiriladigan sozlamalar bilan yaratadi."""
    path = Path(path) if path else CONFIG_FILE
    if not path.exists():
        template = {
            "GEMINI_API_KEY": "",
            "SOURCE_LANGUAGE": SOURCE_LANGUAGE,
            "TTS_VOICE": TTS_VOICE,
            "SUBTITLE_MODE": SUBTITLE_MODE,
            "ORIGINAL_VOLUME": ORIGINAL_VOLUME,
            "MAX_VIDEO_HEIGHT": MAX_VIDEO_HEIGHT,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


load()
