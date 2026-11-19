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

- Windows 10/11, Linux yoki macOS
- [Python](https://www.python.org/downloads/) 3.10 yoki undan yangi versiya
  (Windows'da o'rnatishda **"Add python.exe to PATH"** belgisini qo'ying)
- Gemini API kaliti — [Google AI Studio](https://aistudio.google.com/apikey).
  Ovoz berish uchun to'lov ulangan (Tier 1 va undan yuqori) loyiha tavsiya etiladi.

ffmpeg alohida o'rnatilmaydi, u kutubxonalar bilan birga avtomatik keladi.

## O'rnatish

```
pip install uzdublyaj
```

Boshqa Python loyihalaringizga aralashmasligi uchun [pipx](https://pipx.pypa.io/) bilan
o'rnatish ham qulay: `pipx install uzdublyaj`.

**API kalit.** Birinchi ishga tushirishda dastur kalitni o'zi so'raydi va sozlamalar fayliga
saqlaydi. Boshqa yo'llar: `GEMINI_API_KEY` muhit o'zgaruvchisi yoki joriy papkadagi `.env`
fayli (`GEMINI_API_KEY=...`, namuna: [`.env.example`](.env.example)).

**Windows'da repo orqali (pip'siz):**

1. Loyihani yuklab oling:
   ```
   git clone https://github.com/Abror5555/uzdublyaj.git
   cd uzdublyaj
   ```
2. **`setup.bat`** ni ishga tushiring. U `env` virtual muhitini yaratadi va dasturni
   barcha kutubxonalari bilan o'rnatadi.
3. **`run.bat`** ni ishga tushiring. Bu usulda natijalar avvalgidek repo ichidagi `output/`
   papkasiga tushadi.

## Ishlatish

`uzdublyaj` buyrug'ini (yoki Windows'da **`run.bat`** ni) ishga tushiring, havola yoki fayl
yo'lini kiriting (faylni oynaga sudrab tashlasangiz ham bo'ladi), so'ng video tilini va
rejimni tanlang:

```
Video qaysi tilda?
  1) Ingliz tili
  2) Rus tili
  3) Koreys tili
```

Terminal orqali:

```
uzdublyaj "https://www.youtube.com/watch?v=..."
uzdublyaj "https://www.youtube.com/watch?v=..." --lang ru
uzdublyaj "C:\Videos\dars.mp4" --lang ko --mode sub
uzdublyaj havola1 havola2 --mode dub --output D:\Tarjimalar
```

Repo ichidan ishlatsangiz, `uzdublyaj` o'rniga `python main.py` yozasiz.

| Til (`--lang`) | Video tili |
|------|--------|
| `en` | ingliz tili (standart) |
| `ru` | rus tili |
| `ko` | koreys tili |

Standart tilni sozlamalardagi `SOURCE_LANGUAGE` bilan o'zgartirish mumkin.

| Rejim | Natija |
|-------|--------|
| `srt` | faqat `.uz.srt` va asl tildagi `.en.srt` / `.ru.srt` / `.ko.srt` fayllar |
| `sub` | o'zbekcha subtitr chizilgan video |
| `dub` | o'zbekcha ovozli video (ichida o'chirib-yoqsa bo'ladigan subtitr ham bor) |
| `all` | ikkala video ham (standart) |

**Natijalar** standart holatda uy papkangizdagi `UzDublyaj` papkasiga tushadi
(Windows'da `C:\Users\<ism>\UzDublyaj`, repo orqali ishlatilganda — `output/`).
Boshqa papka: `--output PAPKA` yoki sozlamalardagi `OUTPUT_DIR`.
- tayyor videolar — `<natijalar>/videos/`
- `.srt` va oraliq fayllar — `<natijalar>/<video nomi>/` (rus va koreys videolari uchun
  `<video nomi>/ru/` va `<video nomi>/ko/`, shunda tillar keshi aralashmaydi)

## Sozlamalar

Sozlamalar `config.json` faylida saqlanadi. Uning joyini ko'rish (yo'q bo'lsa, namuna bilan
yaratish) uchun:

```
uzdublyaj --config
```

Windows'da fayl `%LOCALAPPDATA%\uzdublyaj\config.json`, Linux va macOS'da
`~/.config/uzdublyaj/config.json` da bo'ladi. Faylga kerakli sozlamalarni yozasiz:

```json
{
  "GEMINI_API_KEY": "AIza...",
  "SOURCE_LANGUAGE": "ru",
  "TTS_VOICE": "Kore",
  "SUBTITLE_MODE": "soft"
}
```

Eng ko'p ishlatiladigan sozlamalar:

| Sozlama | Ma'nosi |
|---------|---------|
| `SOURCE_LANGUAGE` | standart video tili: `"en"`, `"ru"` yoki `"ko"` |
| `TTS_VOICE` | ovoz: `Charon`, `Kore`, `Puck`, `Iapetus`, `Sadaltager` va boshqalar |
| `ORIGINAL_VOLUME` | asl ovozning fondagi balandligi (`0` — butunlay o'chiq) |
| `SUBTITLE_MODE` | `"burn"` — videoga chiziladi, `"soft"` — alohida yo'lak (tezroq) |
| `KEEP_TERMS` | tarjima qilinmaydigan atamalar ro'yxati |
| `MAX_VIDEO_HEIGHT` | YouTube'dan yuklanadigan sifat (`720` — tezroq) |
| `CHUNK_MINUTES` | nutqni aniqlashda audio bo'lagi uzunligi, daqiqa |
| `OUTPUT_DIR` | natijalar papkasi |

Barcha sozlamalar va ularning standart qiymatlari:
[`src/uzdublyaj/config.py`](src/uzdublyaj/config.py). Qo'shimcha sozlamalar ham `config.json`
ga yoziladi:

```json
{
  "DUB_BLOCK_SECONDS": 20,
  "TTS_TIMEOUT": 180,
  "FALLBACK_MODELS": {"gemini-3.8-flash": "gemini-3.5-flash",
                      "gemini-3.8-flash-tts": "gemini-3.8-flash-lite-tts"}
}
```

`DUB_BLOCK_SECONDS` — nechta soniyalik gaplar bitta ovoz so'roviga yig'iladi (0 — har gap
alohida), `TTS_TIMEOUT` — bitta ovoz so'rovini maksimal kutish (soniya).

> Avval kalitni repo ichidagi `config.py` ga yozgan bo'lsangiz: endi u
> `uzdublyaj --config` ko'rsatgan faylga yoki `.env` ga yoziladi.

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
main.py               repo ichidan ishga tushirish (python main.py)
setup.bat / run.bat   o'rnatish va ishga tushirish (Windows)
src/uzdublyaj/
  cli.py              menyu, buyruq qatori va bosqichlar
  config.py           standart sozlamalar va config.json ni yuklash
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

## Ishlab chiqish

```
git clone https://github.com/Abror5555/uzdublyaj.git
cd uzdublyaj
pip install -e ".[dev]"
pytest          # internet va API kalitsiz testlar
```

## PyPI'ga chiqarish (muallif uchun)

Yangi versiya GitHub Actions orqali chiqariladi
([`.github/workflows/publish.yml`](.github/workflows/publish.yml)):
`src/uzdublyaj/__init__.py` dagi `__version__` ni oshiring va GitHub'da shu raqamli yangi
Release (masalan `v0.1.1`) chiqaring — testlar o'tsa, paket PyPI'ga avtomatik yuklanadi.

## Mualliflik huquqi haqida

UzDublyaj shaxsiy o'rganish uchun mo'ljallangan. Boshqalarning videolarini tarjima qilib qayta
joylashdan oldin muallifdan ruxsat oling va YouTube foydalanish shartlariga rioya qiling.

## Litsenziya

MIT — [LICENSE](LICENSE) fayliga qarang.
