from __future__ import annotations

import argparse
import asyncio
import subprocess
import tempfile
from pathlib import Path

import edge_tts
import imageio_ffmpeg


FRAME_DURATIONS = [
    ("01-initial.png", 22),
    ("02-risk.png", 38),
    ("03-artifacts.png", 30),
    ("04-decision.png", 28),
    ("05-writeback.png", 32),
]


async def synthesize(text: str, output: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="-4%")
    await communicate.save(str(output))


def build_video(frames_dir: Path, narration: Path, output: Path, voice: str) -> None:
    missing = [name for name, _ in FRAME_DURATIONS if not (frames_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing video frames: {', '.join(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="changeguard-video-") as temp_dir:
        temp_path = Path(temp_dir)
        audio_path = temp_path / "narration.mp3"
        concat_path = temp_path / "frames.txt"

        text = narration.read_text(encoding="utf-8").strip()
        asyncio.run(synthesize(text, audio_path, voice))

        lines = []
        for name, duration in FRAME_DURATIONS:
            frame = (frames_dir / name).resolve().as_posix()
            lines.extend([f"file '{frame}'", f"duration {duration}"])
        final_frame = (frames_dir / FRAME_DURATIONS[-1][0]).resolve().as_posix()
        lines.append(f"file '{final_frame}'")
        concat_path.write_text("\n".join(lines), encoding="utf-8")

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        command = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-i",
            str(audio_path),
            "-vf",
            (
                "scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white,format=yuv420p"
            ),
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output),
        ]
        subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--narration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice", default="en-US-GuyNeural")
    args = parser.parse_args()
    build_video(args.frames, args.narration, args.output, args.voice)


if __name__ == "__main__":
    main()
