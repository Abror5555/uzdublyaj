"""Internet va API kalitsiz ishlaydigan testlar."""

import json
import os
from pathlib import Path

import pytest

from uzdublyaj import cli, config, downloader, gemini_client, languages, segmenter, subtitles


# ── Tillar ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value, expected", [
    ("en", "en"), ("en-US", "en"), ("Ruscha", "ru"), ("ko-KR", "ko"), ("koreys", "ko"), (None, "en"),
])
def test_normalize_language(value, expected):
    assert languages.normalize(value) == expected


def test_unknown_language():
    with pytest.raises(ValueError):
        languages.normalize("de")


# ── Gaplarga bo'lish ───────────────────────────────────────────────────────

def _w(word, start, end):
    return {"w": word, "s": start, "e": end}


def test_segments_split_on_sentence_end_and_long_pause():
    words = [
        _w("Hello", 0.0, 0.5), _w("world.", 0.6, 1.6),
        _w("Next", 1.7, 2.0), _w("part", 2.1, 2.5),
        _w("after", 5.0, 5.4), _w("pause", 5.5, 6.0),
    ]
    segs = segmenter.build_segments(words)
    assert [s["src"] for s in segs] == ["Hello world.", "Next part", "after pause"]
    assert segs[0]["start"] == 0.0 and segs[0]["end"] == 1.6
    assert [s["id"] for s in segs] == [1, 2, 3]


def test_segments_empty():
    assert segmenter.build_segments([]) == []


# ── Subtitrlar ─────────────────────────────────────────────────────────────

def test_fmt_ts():
    assert subtitles.fmt_ts(0) == "00:00:00,000"
    assert subtitles.fmt_ts(3725.5) == "01:02:05,500"
    assert subtitles.fmt_ts(-1) == "00:00:00,000"


def test_wrap_and_split_respect_width():
    text = "bu juda uzun gap bo'lib, ekranga bitta qatorda sig'maydi va bo'linishi kerak"
    assert all(len(line) <= 20 for line in subtitles.wrap(text, 20))
    chunks = subtitles.split_text(text, 30)
    assert " ".join(chunks) == text
    assert all(len(c) <= 30 for c in chunks)


def test_build_cues_and_write_srt(tmp_path):
    segs = [
        {"start": 0.0, "end": 2.0, "uz": "Salom, dunyo!"},
        {"start": 2.5, "end": 4.0, "uz": ""},
        {"start": 5.0, "end": 6.0, "uz": "Keyingi gap."},
    ]
    cues = subtitles.build_cues(segs, "uz")
    assert [c[2] for c in cues] == ["Salom, dunyo!", "Keyingi gap."]
    assert cues[0][1] <= 2.5  # keyingi gap boshlanishidan oshib ketmaydi
    out = subtitles.write_srt(cues, tmp_path / "a.srt")
    text = Path(out).read_text(encoding="utf-8")
    assert text.startswith("1\n00:00:00,000 --> ")
    assert "2\n00:00:05,000 --> " in text


# ── Manba ──────────────────────────────────────────────────────────────────

def test_safe_name_and_is_url():
    assert downloader.safe_name("Python darsi: 1-qism!") == "Python_darsi_1-qism"
    assert downloader.safe_name("???") == "video"
    assert downloader.is_url("https://youtu.be/abc")
    assert downloader.is_url("youtube.com/watch?v=1")
    assert not downloader.is_url(r"C:\Videos\dars.mp4")


def test_prepare_local_file(tmp_path):
    video = tmp_path / "Mening darsim.mp4"
    video.write_bytes(b"x")
    path, title, workdir = downloader.prepare_source(f'"{video}"')
    assert path == video.resolve()
    assert title == "Mening darsim"
    assert workdir == config.OUTPUT_DIR / "Mening_darsim" and workdir.is_dir()


def test_prepare_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        downloader.prepare_source(str(tmp_path / "yoq.mp4"))


# ── Sozlamalar ─────────────────────────────────────────────────────────────

def test_load_user_settings(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "TTS_VOICE": "Kore", "SOURCE_LANGUAGE": "ru", "OUTPUT_DIR": str(tmp_path / "natija"),
        "lowercase": "e'tiborsiz qoldiriladi",
    }), encoding="utf-8")
    config.load(cfg)
    assert config.TTS_VOICE == "Kore"
    assert config.SOURCE_LANGUAGE == "ru"
    assert config.OUTPUT_DIR == tmp_path / "natija"
    assert not hasattr(config, "lowercase")

    monkeypatch.setenv("UZDUBLYAJ_OUTPUT_DIR", str(tmp_path / "env"))
    config.load(cfg)
    assert config.OUTPUT_DIR == tmp_path / "env"


def test_broken_config_is_ignored(tmp_path, capsys):
    cfg = tmp_path / "config.json"
    cfg.write_text("{buzilgan json", encoding="utf-8")
    voice = config.TTS_VOICE
    config.load(cfg)
    assert config.TTS_VOICE == voice
    assert "o'qilmadi" in capsys.readouterr().err


def test_save_setting_keeps_other_keys(tmp_path):
    cfg = tmp_path / "sub" / "config.json"
    config.save_setting("TTS_VOICE", "Puck", cfg)
    config.save_setting("GEMINI_API_KEY", "k" * 39, cfg)
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data == {"TTS_VOICE": "Puck", "GEMINI_API_KEY": "k" * 39}
    assert config.GEMINI_API_KEY == "k" * 39


def test_ensure_config_file_creates_template(tmp_path):
    cfg = config.ensure_config_file(tmp_path / "c.json")
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["GEMINI_API_KEY"] == "" and data["SOURCE_LANGUAGE"] == config.SOURCE_LANGUAGE
    cfg.write_text('{"TTS_VOICE": "Kore"}', encoding="utf-8")
    config.ensure_config_file(cfg)  # mavjud faylni o'zgartirmaydi
    assert json.loads(cfg.read_text(encoding="utf-8")) == {"TTS_VOICE": "Kore"}


# ── Gemini mijozi ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, seconds", [
    ("37s", 37), ("2.5s", 2.5), ("6h7m11s", 6 * 3600 + 7 * 60 + 11), ("7m", 420), ("12", 12.0), ("abc", None),
])
def test_parse_duration(text, seconds):
    assert gemini_client._parse_duration(text) == seconds


def test_key_from_env_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert gemini_client._key_from_env_file() == ""
    (tmp_path / ".env").write_text('GEMINI_API_KEY="abc123"\n', encoding="utf-8")
    assert gemini_client._key_from_env_file() == "abc123"
    (tmp_path / ".env").write_text("GEMINI_API_KEY=bu_yerga_kalitingizni_yozing\n", encoding="utf-8")
    assert gemini_client._key_from_env_file() == ""


def test_missing_key_without_terminal_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gemini_client, "_client", None)
    monkeypatch.setattr(gemini_client.sys.stdin, "isatty", lambda: False, raising=False)
    config.GEMINI_API_KEY = ""
    with pytest.raises(SystemExit) as exc:
        gemini_client.get_client()
    assert "API kalit topilmadi" in str(exc.value)


# ── Buyruq qatori ──────────────────────────────────────────────────────────

def test_cli_config_flag(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "cfg" / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    cli.main(["--config"])
    assert cfg.is_file()
    assert str(cfg) in capsys.readouterr().out


def test_cli_parser_defaults():
    args = cli.build_parser().parse_args(["https://youtu.be/x", "--lang", "ru", "--mode", "sub"])
    assert args.inputs == ["https://youtu.be/x"] and args.lang == "ru" and args.mode == "sub"
    assert cli.build_parser().parse_args([]).mode == "all"


# ── ffmpeg (kutubxona bilan keladigan nusxa) ───────────────────────────────

def test_ffmpeg_probe_and_mux(tmp_path, monkeypatch):
    from uzdublyaj import ffmpeg_utils as ff

    monkeypatch.setattr(ff, "_FFMPEG", None)
    exe = ff.ffmpeg_path()
    assert Path(exe).parent == config.BIN_DIR and os.access(exe, os.X_OK)

    video = tmp_path / "v.mp4"
    ff.run(["-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-f", "lavfi", "-i", "color=c=black:s=160x120:d=2",
            "-shortest", "-c:v", "libx264", "-c:a", "aac", video])
    info = ff.probe(video)
    assert 1.8 < info["duration"] < 2.3 and info["has_audio"] and info["has_video"]

    srt = subtitles.write_srt([(0.0, 1.5, "Salom")], tmp_path / "s.srt")
    soft = tmp_path / "soft.mp4"
    ff.add_soft_subtitles(video, srt, soft)
    assert ff.probe(soft)["has_video"]

    wav = tmp_path / "dub.wav"
    ff.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=2", "-ac", "1", "-ar", "24000", wav])
    dub = tmp_path / "dub.mp4"
    ff.mux_dub(video, wav, dub, original_volume=0.12, srt=srt, duration=2.0)
    assert ff.probe(dub)["has_audio"]


def test_key_prompt_saves_key(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    monkeypatch.setattr(gemini_client.sys.stdin, "isatty", lambda: True, raising=False)
    key = "AIza" + "x" * 35
    monkeypatch.setattr("builtins.input", lambda prompt="": f"  {key}  ")
    assert gemini_client._ask_and_save_key() == key
    assert json.loads(cfg.read_text(encoding="utf-8"))["GEMINI_API_KEY"] == key

    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert gemini_client._ask_and_save_key() == ""
