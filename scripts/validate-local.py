#!/usr/bin/env python3
"""Cross-platform local validation pipeline for pre-commit."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATION_ROOT = "/tmp/god-validation"
CONTAINER = os.getenv("GOD_RUNTIME_CONTAINER", "god-runtime")


def run(command: list[str], name: str) -> None:
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"[validate] {name} failed with exit code {result.returncode}")


def docker_cp(source: Path, target: str, name: str) -> None:
    run(["docker", "cp", f"{source}{os.sep}.", f"{CONTAINER}:{target}"], name)


def main() -> int:
    print("[validate] compose config", flush=True)
    run(["docker", "compose", "--project-directory", str(ROOT), "config", "--quiet"], "compose config")

    print("[validate] runtime tests", flush=True)
    run(
        [
            "docker",
            "exec",
            CONTAINER,
            "sh",
            "-lc",
            (
                f"rm -rf {VALIDATION_ROOT} && "
                f"mkdir -p {VALIDATION_ROOT}/suite/src "
                f"{VALIDATION_ROOT}/suite/runtime-tests "
                f"{VALIDATION_ROOT}/observer/src"
            ),
        ],
        "prepare runtime test dir",
    )

    try:
        docker_cp(ROOT / "runtime" / "src", f"{VALIDATION_ROOT}/suite/src", "copy runtime src")
        run(
            [
                "docker",
                "cp",
                str(ROOT / "runtime" / "workflows"),
                f"{CONTAINER}:{VALIDATION_ROOT}/suite/workflows",
            ],
            "copy runtime workflows",
        )
        run(
            [
                "docker",
                "cp",
                str(ROOT / "runtime" / "seed_utterances"),
                f"{CONTAINER}:{VALIDATION_ROOT}/suite/seed_utterances",
            ],
            "copy seed utterances",
        )
        docker_cp(
            ROOT / "runtime" / "tests",
            f"{VALIDATION_ROOT}/suite/runtime-tests",
            "copy runtime tests",
        )
        run(["docker", "cp", str(ROOT / "scripts"), f"{CONTAINER}:{VALIDATION_ROOT}/scripts"], "copy scripts")
        run(
            [
                "docker",
                "cp",
                str(ROOT / "docker-compose.vast.yml"),
                f"{CONTAINER}:{VALIDATION_ROOT}/docker-compose.vast.yml",
            ],
            "copy vast compose override",
        )
        run(
            [
                "docker",
                "cp",
                str(ROOT / "observer" / "stage.html"),
                f"{CONTAINER}:{VALIDATION_ROOT}/observer/stage.html",
            ],
            "copy observer stage",
        )
        run(
            [
                "docker",
                "cp",
                str(ROOT / "observer" / "assets"),
                f"{CONTAINER}:{VALIDATION_ROOT}/observer/assets",
            ],
            "copy observer assets",
        )
        docker_cp(ROOT / "observer" / "src", f"{VALIDATION_ROOT}/observer/src", "copy observer src")
        run(
            [
                "docker",
                "exec",
                "-e",
                f"PYTHONPATH={VALIDATION_ROOT}/suite/src",
                "-e",
                "VOICE_SYNTHESIS_ENABLED=false",
                CONTAINER,
                "python",
                "-m",
                "pytest",
                f"{VALIDATION_ROOT}/suite/runtime-tests",
            ],
            "runtime tests",
        )
    finally:
        subprocess.run(["docker", "exec", CONTAINER, "rm", "-rf", VALIDATION_ROOT], cwd=ROOT)

    print("[validate] complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
