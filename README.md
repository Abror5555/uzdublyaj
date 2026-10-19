# UzDublyaj

**Ingliz, rus va koreys tilidagi video darsliklarni o'zbek tiliga o'giruvchi dastur: subtitr va ovozli dublyaj.**

YouTube havolasini yoki kompyuterdagi video faylni berasiz, UzDublyaj esa videoni o'zbekcha
subtitr bilan yoki o'zbekcha ovoz bilan qaytaradi. Asosan dasturlash va IT darsliklari uchun
yaratilgan: kod, buyruqlar va texnik atamalar tarjimada buzilmaydi.

> **English:** UzDublyaj translates English, Russian and Korean video tutorials (YouTube links
> or local files) into Uzbek — with burned-in subtitles and/or an AI voice-over — using the Google Gemini API.

---

## Imkoniyatlar

- 🎬 **Manba** — YouTube havola yoki kompyuterdagi video fayl (mp4, mkv, mov va boshqalar)
- 🌐 **Video tili** — ingliz, rus yoki koreys tili; har safar menyuda tanlanadi
- 📝 **Subtitr** — o'zbekcha va asl tildagi `.srt` fayllar, subtitr chizilgan video
- 🎙️ **Dublyaj** — o'zbekcha ovoz; asl ovoz fonda past ovozda qoladi
- 💻 **IT atamalari** — `commit`, `Docker`, `router` kabi so'zlar va kod asl holida qoladi.
  Rus va koreys videolarida ham `коммит`, `파이썬` kabi talaffuzlar `commit`, `Python` deb yoziladi
- 💾 **Kesh** — har bir bosqich saqlanadi: to'xtab qolsa, tugagan joyidan davom etadi va
  tayyor qism uchun qayta to'lanmaydi
- 🚦 **Limitlarga moslashish** — Google limitlarida kutadi, zaxira modelga o'tadi va holatni
  bitta qatorda ko'rsatib turadi
- 💵 **Xarajat hisobi** — har ish oxirida taxminan qancha sarflanganini ko'rsatadi

## Qanday ishlaydi

```
Video / YouTube havola
   │  yt-dlp, ffmpeg
   ▼
Audio ──► Nutqni matnga aylantirish (gemini-3.5-transcribe, so'z vaqtlari bilan)
   ▼
Gaplarga bo'lish ──► O'zbekchaga tarjima (gemini-3.8-flash)
   │                 ingliz / rus / koreys → o'zbek
   ▼
 ├─► .srt subtitr ──► subtitr chizilgan video
 └─► o'zbekcha ovoz (gemini-3.8-flash-tts) ──► vaqtga moslash ──► dublyaj video
```

## Talablar

- Windows 10/11 (Linux va macOS da ham ishlaydi, pastga qarang)
- [Python](https://www.python.org/downloads/) 3.10 yoki undan yangi versiya
  (o'rnatishda **"Add python.exe to PATH"** belgisini qo'ying)
- Gemini API kaliti — [Google AI Studio](https://aistudio.google.com/apikey).
  Ovoz berish uchun to'lov ulangan (Tier 1 va undan yuqori) loyiha tavsiya etiladi.

ffmpeg alohida o'rnatilmaydi, u kutubxonalar bilan birga avtomatik keladi.

## O'rnatish

1. Loyihani yuklab oling:
   ```
   git clone https://github.com/Abror5555/uzdublyaj.git
   cd uzdublyaj
   ```
2. **`setup.bat`** ni ishga tushiring. U `env` virtual muhitini yaratadi va barcha
   kutubxonalarni o'rnatadi.
3. API kalitni yozing. Buning ikki yo'li bor:
   - `config.py` ni ochib, `GEMINI_API_KEY = "API Kalitinigizs"` qatoriga kalitingizni qo'ying;
   - yoki `.env.example` dan nusxa olib, nomini **`.env`** qiling va unga `GEMINI_API_KEY=...`
     deb yozing. Bu yo'l xavfsizroq: `.env` fayli GitHub'ga yuklanmaydi.

   ⚠️ O'z kalitingiz yozilgan `config.py` ni GitHub'ga yuklamang.

**Linux / macOS:**
```
python3 -m venv env
env/bin/pip install -r requirements.txt
env/bin/python main.py
```

## Ishlatish

**`run.bat`** ni ishga tushiring, havola yoki fayl yo'lini kiriting (faylni oynaga sudrab
tashlasangiz ham bo'ladi), so'ng video tilini va rejimni tanlang:

```
Video qaysi tilda?
  1) Ingliz tili
  2) Rus tili
  3) Koreys tili
```

Terminal orqali:

```
python main.py "https://www.youtube.com/watch?v=..."
python main.py "https://www.youtube.com/watch?v=..." --lang ru
python main.py "C:\Videos\dars.mp4" --lang ko --mode sub
python main.py havola1 havola2 --mode dub
```

| Til (`--lang`) | Video tili |
|------|--------|
| `en` | ingliz tili (standart) |
| `ru` | rus tili |
| `ko` | koreys tili |

Standart tilni `config.py` dagi `SOURCE_LANGUAGE` bilan o'zgartirish mumkin.

| Rejim | Natija |
|-------|--------|
| `srt` | faqat `.uz.srt` va asl tildagi `.en.srt` / `.ru.srt` / `.ko.srt` fayllar |
| `sub` | o'zbekcha subtitr chizilgan video |
| `dub` | o'zbekcha ovozli video (ichida o'chirib-yoqsa bo'ladigan subtitr ham bor) |
| `all` | ikkala video ham (standart) |

`main.py` qaysi Python bilan ochilmasin, o'zini loyihaning `env` muhitida qayta ishga tushiradi.

**Natijalar:**
- tayyor videolar — `output/videos/`
- `.srt` va oraliq fayllar — `output/<video nomi>/` (rus va koreys videolari uchun
  `output/<video nomi>/ru/` va `output/<video nomi>/ko/`, shunda tillar keshi aralashmaydi)

## Sozlamalar

Barcha sozlamalar `config.py` da:

| Sozlama | Ma'nosi |
|---------|---------|
| `SOURCE_LANGUAGE` | standart video tili: `"en"`, `"ru"` yoki `"ko"` |
| `TTS_VOICE` | ovoz: `Charon`, `Kore`, `Puck`, `Iapetus`, `Sadaltager` va boshqalar |
| `ORIGINAL_VOLUME` | asl ovozning fondagi balandligi (`0` — butunlay o'chiq) |
| `SUBTITLE_MODE` | `"burn"` — videoga chiziladi, `"soft"` — alohida yo'lak (tezroq) |
| `KEEP_TERMS` | tarjima qilinmaydigan atamalar ro'yxati |
| `MAX_VIDEO_HEIGHT` | YouTube'dan yuklanadigan sifat (`720` — tezroq) |
| `CHUNK_MINUTES` | nutqni aniqlashda audio bo'lagi uzunligi, daqiqa |

Qo'shimcha sozlamalarni `config.py` oxiriga yozish mumkin:

```python
DUB_BLOCK_SECONDS = 20   # nechta soniyalik gaplar bitta ovoz so'roviga yig'iladi (0 — har gap alohida)
TTS_TIMEOUT = 180        # bitta ovoz so'rovini maksimal kutish, soniya
FALLBACK_MODELS = {"gemini-3.8-flash": "gemini-3.5-flash",
                   "gemini-3.8-flash-tts": "gemini-3.8-flash-lite-tts"}
```

## Xarajat va limitlar

Taxminiy xarajat (2026-yil narxlari bo'yicha), 10 daqiqalik video uchun:

| | Narx |
|---|---|
| Subtitr (nutqni aniqlash + tarjima) | ~$0.07 |
| Dublyaj (qo'shimcha) | ~$0.15 |

Google har bir model uchun so'rovlar sonini cheklaydi. Masalan, Tier 1 da ovoz modellari
uchun limit **daqiqasiga 10 va kuniga 100 so'rov**. Bu cheklov hisobdagi pulga bog'liq emas.
Kunlik limit Toshkent vaqti bilan soat 12:00 da (Tinch okeani vaqti bilan yarim tunda)
yangilanadi. Limit tugasa, UzDublyaj zaxira modelga o'tadi; u ham tugasa, tayyor qismni saqlab
to'xtaydi. Limitlaringizni AI Studio'dagi
[Rate limit](https://aistudio.google.com/rate-limit) sahifasida ko'rasiz.

## Loyiha tuzilmasi

```
main.py               asosiy fayl: menyu va bosqichlar
config.py             sozlamalar
setup.bat / run.bat   o'rnatish va ishga tushirish (Windows)
core/
  downloader.py       YouTube'dan yuklash (yt-dlp) yoki mahalliy fayl
  transcriber.py      nutqni matnga aylantirish, so'z vaqtlari bilan
  segmenter.py        so'zlarni gaplarga bo'lish
  languages.py        video tillari (ingliz, rus, koreys) va ularning sozlamalari
  translator.py       o'zbekchaga tarjima va qisqartirish
  subtitles.py        .srt fayllar
  dubber.py           ovoz berish, vaqtga moslash va audio yig'ish
  gemini_client.py    Gemini API, qayta urinishlar, limitlar va xarajat hisobi
  ffmpeg_utils.py     ffmpeg buyruqlari
```

## Cheklovlar

- Rus va koreys tillarida nutqni aniqlash sifati videoning ovoziga bog'liq. Shovqinli yoki
  musiqali videolarda ba'zi so'zlar noto'g'ri eshitilishi mumkin; tarjimon ularni kontekstdan
  to'g'rilashga harakat qiladi.
- Koreys tilida o'zbekcha tarjima ko'pincha asl gapdan uzunroq chiqadi, shuning uchun
  dublyajda tezlashtirish va qisqartirish ko'proq uchrashi mumkin.
- Sun'iy ovoz asl nutqqa to'liq mos kelmasligi mumkin: o'zbekcha matn odatda uzunroq bo'ladi,
  shuning uchun ba'zi joylar biroz tezlashtiriladi yoki qisqartiriladi.
- Ovoz ~20 soniyalik bloklar bilan beriladi. Blok ichida nutq asl gapdan 1–2 soniya
  oldin yoki keyin ketishi mumkin, har yangi blokda esa video bilan qayta tenglashadi.
- Uzun videolarda ovoz modellarining kunlik limiti yetmasligi mumkin. Unda ish keyingi kuni
  qolgan joyidan davom ettiriladi.

## Mualliflik huquqi haqida

UzDublyaj shaxsiy o'rganish uchun mo'ljallangan. Boshqalarning videolarini tarjima qilib qayta
joylashdan oldin muallifdan ruxsat oling va YouTube foydalanish shartlariga rioya qiling.

## Litsenziya

MIT — [LICENSE](LICENSE) fayliga qarang.
