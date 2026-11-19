"""
Repo ichidan ishga tushirish uchun: python main.py [havola yoki fayl] [--lang ru] [--mode sub]

Dasturni pip orqali o'rnatgan bo'lsangiz, buning o'rniga shunchaki `uzdublyaj` buyrug'ini
ishlating. Bu fayl loyihaning env muhiti bo'lsa, o'zini o'sha muhitda qayta ishga tushiradi.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _use_project_env():
    """Dastur env muhitidan tashqaridagi Python bilan ishga tushirilsa (masalan, oddiy
    `python main.py`), o'zini env ichidagi Python bilan qayta ishga tushiradi."""
    env_py = ROOT / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not env_py.exists() or os.environ.get("UZDUB_ENV") == "1":
        return
    try:
        inside = Path(sys.prefix).resolve() == (ROOT / "env").resolve()
    except OSError:
        inside = False
    if inside:
        return
    import signal
    import subprocess

    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ctrl+C ni ichki jarayon o'zi qabul qiladi
    child_env = dict(os.environ, UZDUB_ENV="1")
    sys.exit(subprocess.call([str(env_py), str(ROOT / "main.py"), *sys.argv[1:]], env=child_env))


if __name__ == "__main__":
    _use_project_env()
    sys.path.insert(0, str(ROOT / "src"))
    # Repo ichidan ishlatilganda natijalar avvalgidek repo/output papkasiga tushadi
    os.environ.setdefault("UZDUBLYAJ_DEFAULT_OUTPUT_DIR", str(ROOT / "output"))
    from uzdublyaj.cli import main

    main()
