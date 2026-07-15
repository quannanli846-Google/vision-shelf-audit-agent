"""Extracts a set of representative candidate frames from an uploaded video.

Pure sampling only - no quality judgement here (that's `quality_filter.py`),
which keeps each stage independently testable and reasonable about.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class SampledFrame:
    frame_id: str
    timestamp_sec: float
    image: np.ndarray  # BGR, as returned by OpenCV

    def to_jpeg_bytes(self, quality: int = 90) -> bytes:
        ok, buf = cv2.imencode(".jpg", self.image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            raise ValueError(f"Failed to encode frame {self.frame_id} as JPEG")
        return bytes(buf)


def extract_frames(video_path: str | Path, sample_fps: float = 1.0, max_frames: int = 40) -> list[SampledFrame]:
    """Sample frames from `video_path` at approximately `sample_fps`, capped at `max_frames`."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    try:
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if source_fps <= 0:
            source_fps = 30.0
        frame_interval = max(1, round(source_fps / max(sample_fps, 0.01)))

        sampled: list[SampledFrame] = []
        frame_index = 0
        while len(sampled) < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % frame_interval == 0:
                timestamp_sec = frame_index / source_fps
                sampled.append(
                    SampledFrame(
                        frame_id=f"frame_{len(sampled):03d}_t{timestamp_sec:.2f}s",
                        timestamp_sec=timestamp_sec,
                        image=frame,
                    )
                )
            frame_index += 1
        return sampled
    finally:
        cap.release()
