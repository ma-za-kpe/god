#!/usr/bin/env python3
"""Evaluate an AI4AnimationPy-style NPZ motion export against GOD's pose contract.

This script intentionally does not import AI4AnimationPy. It validates the data
boundary that an optional research sidecar must satisfy before `/one` can use it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "runtime" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avatar.pose_stream import (  # noqa: E402
    iter_pose_stream_ndjson,
    load_npz_pose_stream,
    pose_stream_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--npz", required=True, help="Motion NPZ file exported from a motion tool")
    parser.add_argument("--agent-id", default="", help="Agent identifier to stamp into the stream")
    parser.add_argument("--max-frames", type=int, default=600, help="Maximum frames to emit")
    parser.add_argument("--stride", type=int, default=1, help="Frame stride for long clips")
    parser.add_argument("--fps", type=float, default=30.0, help="Fallback FPS when timestamps are absent")
    parser.add_argument(
        "--format",
        choices=("summary", "json", "ndjson"),
        default="summary",
        help="Output format",
    )
    parser.add_argument("--out", help="Write output to this path instead of stdout")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stream = load_npz_pose_stream(
        args.npz,
        agent_id=args.agent_id,
        max_frames=args.max_frames,
        stride=args.stride,
        fps=args.fps,
    )

    if args.format == "summary":
        output = json.dumps(pose_stream_summary(stream), indent=2, sort_keys=True) + "\n"
    elif args.format == "json":
        output = json.dumps(stream.to_dict(), indent=2, sort_keys=True) + "\n"
    else:
        output = "\n".join(iter_pose_stream_ndjson(stream)) + "\n"

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
