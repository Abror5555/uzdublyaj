"""
UzDublyaj — ingliz, rus va koreys tilidagi video darsliklarni o'zbekchaga o'giradi
(subtitr va dublyaj).

Ishlatish:
    python main.py                                  (menyu orqali)
    python main.py "https://youtu.be/..."           (inglizcha video, subtitr + dublyaj)
    python main.py "https://youtu.be/..." --lang ru (ruscha video)
    python main.py "C:\\Videos\\dars.mp4" --lang ko --mode sub
    python main.py link1 link2 --mode dub

Tillar (--lang):
    en   - ingliz tili (standart)
    ru   - rus tili
    ko   - koreys tili

Rejimlar:
    srt  - faqat .srt subtitr fayllari
    sub  - o'zbekcha subtitrli video
    dub  - o'zbekcha ovozli (dublyaj) video
    all  - subtitrli video + dublyaj video (standart)
"""
import argparse
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path


def _use_project_env():
    """Dastur loyihaning env muhitidan tashqaridagi Python bilan ishga tushirilsa
    (masalan, oddiy `python main.py`), o'zini env ichidagi Python bilan qayta ishga tushiradi.
    Aks holda env ga o'rnatilgan kutubxonalar (yt-dlp va boshqalar) topilmaydi."""
    root = Path(__file__).resolve().parent
    env_py = root / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not env_py.exists() or os.environ.get("UZDUB_ENV") == "1":
        return
    try:
        inside = Path(sys.prefix).resolve() == (root / "env").resolve()
    except OSError:
        inside = False
    if inside:
        return
    import signal
    import subprocess

    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ctrl+C ni ichki jarayon o'zi qabul qiladi
    child_env = dict(os.environ, UZDUB_ENV="1")
    sys.exit(subprocess.call([str(env_py), str(root / "main.py"), *sys.argv[1:]], env=child_env))


if __name__ == "__main__":
    _use_project_env()

import config  # noqa: E402
from core import ffmpeg_utils as ff  # noqa: E402
from core.downloader import prepare_source, safe_name  # noqa: E402
from core import languages  # noqa: E402
from core.gemini_client import get_client, tracker  # noqa: E402
from core.segmenter import build_segments  # noqa: E402
from core.subtitles import build_cues, write_srt  # noqa: E402
from core.transcriber import transcribe  # noqa: E402
from core.translator import translate_segments  # noqa: E402

MODES = {
    "1": ("srt", "Faqat subtitr fayllari (.srt)"),
    "2": ("sub", "O'zbekcha subtitrli video"),
    "3": ("dub", "O'zbekcha ovozli video (dublyaj)"),
    "4": ("all", "Subtitrli video + dublyaj (ikkalasi)"),
}

LANG_MENU = {"1": "en", "2": "ru", "3": "ko"}


def step(n, total, text):
    print(f"\n[{n}/{total}] {text}")


def process(inp: str, mode: str, lang: str = "en"):
    t0 = time.time()
    tracker.reset()
    lang = languages.set_current(lang)
    total_steps = {"srt": 4, "sub": 5, "dub": 5, "all": 6}[mode]

    step(1, total_steps, "Manba tayyorlanmoqda")
    video, title, workdir = prepare_source(inp)
    if lang != "en":
        # Har bir til uchun kesh alohida papkada: bitta videoni boshqa til bilan qayta
        # ishlasangiz, eski transkripsiya va tarjima aralashib ketmaydi.
        # Inglizcha natijalar avvalgidek asosiy papkada qoladi.
        workdir = workdir / lang
        workdir.mkdir(parents=True, exist_ok=True)
    print(f"  Video tili: {languages.current()['uz']} tili")
    info = ff.probe(video)
    total = info["duration"]
    if not info["has_audio"]:
        raise RuntimeError("Videoda ovoz yo'q, tarjima qilib bo'lmaydi.")
    print(f"  {title}  ({total / 60:.1f} daqiqa)")
    print(f"  Natijalar papkasi: {workdir}")

    step(2, total_steps, "Nutq matnga aylantirilmoqda")
    words = transcribe(video, workdir, total)
    seg_file = workdir / "segments.json"
    if seg_file.exists():
        segments = json.loads(seg_file.read_text(encoding="utf-8"))
        for s in segments:  # eski versiyada asl matn "en" maydonida saqlangan
            if "src" not in s:
                s["src"] = s.pop("en", "")
    else:
        segments = build_segments(words)
        seg_file.write_text(json.dumps(segments, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {len(words)} so'z, {len(segments)} gap.")
    if not segments:
        raise RuntimeError("Videoda nutq topilmadi.")

    step(3, total_steps, "O'zbekchaga tarjima qilinmoqda")
    segments = translate_segments(segments, workdir, title)

    step(4, total_steps, "Subtitr fayllari yozilmoqda")
    base = safe_name(title, 50)
    src_srt = write_srt(build_cues(segments, "src"), workdir / f"{base}.{lang}.srt")
    uz_srt = write_srt(build_cues(segments, "uz"), workdir / f"{base}.uz.srt")
    videos_dir = getattr(config, "VIDEOS_DIR", config.OUTPUT_DIR / "videos")
    videos_dir.mkdir(parents=True, exist_ok=True)
    outputs = [uz_srt, src_srt]
    n = 4

    if mode in ("sub", "all"):
        n += 1
        out = _final_path(videos_dir, workdir, f"{base}_uz_subtitr.mp4")
        if out.exists() and _same_subs(uz_srt):
            step(n, total_steps, "Subtitrli video avval tayyorlangan, qayta ishlanmaydi")
        elif config.SUBTITLE_MODE == "burn":
            step(n, total_steps, "Subtitr videoga chizilmoqda (bir necha daqiqa olishi mumkin)")
            ff.burn_subtitles(video, uz_srt, out)
        else:
            step(n, total_steps, "Subtitr yo'lagi videoga qo'shilmoqda")
            ff.add_soft_subtitles(video, uz_srt, out)
        uz_srt.with_suffix(".burned").write_text(uz_srt.read_text(encoding="utf-8"), encoding="utf-8")
        outputs.append(out)

    if mode in ("dub", "all"):
        n += 1
        step(n, total_steps, "O'zbekcha ovoz berilmoqda (dublyaj)")
        from core.dubber import build_dub_track

        track = build_dub_track(segments, workdir, total)
        dub_srt = uz_srt if config.DUB_SOFT_SUBTITLES else None
        out = _final_path(videos_dir, workdir, f"{base}_uz_dublyaj.mp4")
        print("  Video bilan birlashtirilmoqda...")
        ff.mux_dub(video, track, out, config.ORIGINAL_VOLUME, info["has_audio"], dub_srt, duration=total)
        outputs.append(out)

    print("\n" + "=" * 60)
    print(f"TAYYOR! ({(time.time() - t0) / 60:.1f} daqiqa)")
    print(f"  Tayyor videolar papkasi: {videos_dir}")
    for p in outputs:
        print(f"  -> {p.name}" if p.parent == videos_dir else f"  -> {p}")
    print(tracker.summary())
    print("=" * 60)


def _final_path(videos_dir, workdir, name):
    """Tayyor video output\\videos ga yoziladi. Oldingi versiyada ish papkasida qolgan
    tayyor video bo'lsa, u ham shu yerga ko'chiriladi."""
    target = videos_dir / name
    legacy = workdir / name
    if legacy.exists() and not target.exists():
        shutil.move(str(legacy), str(target))
    return target


def _same_subs(uz_srt):
    """Subtitr matni oxirgi chizilgan video bilan bir xilmi (o'zgargan bo'lsa, qayta chiziladi)."""
    stamp = uz_srt.with_suffix(".burned")
    current = uz_srt.read_text(encoding="utf-8")
    return stamp.exists() and stamp.read_text(encoding="utf-8") == current


def interactive():
    print("=" * 60)
    print("  UzDublyaj — videolarni o'zbekchaga o'girish (ingliz, rus, koreys)")
    print("=" * 60)
    inp = input("\nYouTube havola yoki video fayl yo'lini kiriting\n"
                "(faylni shu oynaga sudrab tashlasangiz ham bo'ladi):\n> ").strip()
    if not inp:
        return None, None, None
    default_lang = languages.normalize(getattr(config, "SOURCE_LANGUAGE", "en"))
    default_key = next((k for k, v in LANG_MENU.items() if v == default_lang), "1")
    print("\nVideo qaysi tilda?")
    for k, code in LANG_MENU.items():
        print(f"  {k}) {languages.LANGUAGES[code]['uz'].capitalize()} tili")
    choice = input(f"Tanlang [{default_key}]: ").strip() or default_key
    lang = LANG_MENU.get(choice, default_lang)
    print("\nNima tayyorlaymiz?")
    for k, (_, label) in MODES.items():
        print(f"  {k}) {label}")
    choice = input("Tanlang [4]: ").strip() or "4"
    mode = MODES.get(choice, MODES["4"])[0]
    return [inp], mode, lang


def disable_quickedit():
    """Windows konsolida sichqoncha bilan bosilganda dastur to'xtab qolmasligi uchun
    QuickEdit rejimini o'chiradi (aks holda chiqish bloklanib, dastur "qotib qoladi")."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, (mode.value & ~0x0040) | 0x0080)
    except Exception:  # noqa: BLE001
        pass


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    disable_quickedit()

    parser = argparse.ArgumentParser(
        description="Ingliz, rus va koreys tilidagi videolarni o'zbekchaga tarjima qilish")
    parser.add_argument("inputs", nargs="*", help="YouTube havola(lar) yoki video fayl(lar)")
    parser.add_argument("--mode", choices=["srt", "sub", "dub", "all"], default="all")
    parser.add_argument("--lang", choices=list(languages.LANGUAGES), default=None,
                        help="videodagi til: en (ingliz), ru (rus), ko (koreys). "
                             "Standart: config.py dagi SOURCE_LANGUAGE")
    parser.add_argument("--debug", action="store_true", help="xato bo'lsa to'liq ma'lumot chiqarish")
    args = parser.parse_args()

    if args.inputs:
        inputs, mode = args.inputs, args.mode
        lang = args.lang or languages.normalize(getattr(config, "SOURCE_LANGUAGE", "en"))
    else:
        inputs, mode, lang = interactive()
        if not inputs:
            print("Hech narsa kiritilmadi.")
            return

    get_client()  # API kalitni boshida tekshiramiz
    failed = 0
    for inp in inputs:
        print(f"\n>>> {inp}")
        try:
            process(inp, mode, lang)
        except KeyboardInterrupt:
            print("\nTo'xtatildi. Qayta ishga tushirsangiz, tugagan bosqichlar qaytadan bajarilmaydi.",
                  flush=True)
            os._exit(130)  # fondagi so'rovlarni kutmasdan darhol chiqamiz (natijalar saqlangan)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"\nXATO: {exc}")
            if args.debug:
                traceback.print_exc()
            print("Qayta ishga tushirsangiz, tugagan bosqichlar keshdan olinadi.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
