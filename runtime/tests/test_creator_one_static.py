"""Static contracts for the creator /one smoke path."""

from __future__ import annotations

import pathlib


def _main_py() -> str:
    return (pathlib.Path(__file__).resolve().parents[1] / "src" / "main.py").read_text(
        encoding="utf-8"
    )


def test_creator_one_defaults_to_alphabet_recitation():
    source = _main_py()

    assert '@app.post("/creator/one")' in source
    assert '@app.post("/one")' in source
    assert '"A B C D E F G H I J K L M N O P Q R S T U V W X Y Z."' in source
