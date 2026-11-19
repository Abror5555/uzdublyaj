import os
import tempfile

# Testlar foydalanuvchining haqiqiy sozlamalariga tegmasligi uchun (import'dan oldin)
_TMP = tempfile.mkdtemp(prefix="uzdublyaj-test-")
os.environ["UZDUBLYAJ_CONFIG"] = os.path.join(_TMP, "config.json")
os.environ.pop("UZDUBLYAJ_OUTPUT_DIR", None)
os.environ.pop("GEMINI_API_KEY", None)

import pytest  # noqa: E402

from uzdublyaj import config  # noqa: E402


@pytest.fixture(autouse=True)
def restore_config(tmp_path):
    """Har bir testdan keyin config modulidagi sozlamalarni asl holiga qaytaradi."""
    saved = {k: v for k, v in vars(config).items() if k.isupper()}
    config.OUTPUT_DIR = tmp_path / "output"
    config.BIN_DIR = tmp_path / "bin"
    yield
    for k in [k for k in vars(config) if k.isupper()]:
        if k not in saved:
            delattr(config, k)
    for k, v in saved.items():
        setattr(config, k, v)
