"""Frame quality filtering: drop blurry/dark/overexposed/duplicate frames,
then pick a small, time-diverse, high-sharpness set of frames to send to the
(expensive) vision model.

Every sampled frame - selected, rejected, or simply outcompeted by a sharper
frame in the same time window - gets a `FrameQualityRecord` so the "Analyzed
Media" trace/UI can show the *complete* picture of what was captured, not
just a curated highlight reel.

Kept as pure numpy/OpenCV functions with no file I/O so this module is
trivially unit-testable with synthetic images.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from video.frame_extractor import SampledFrame

DARK_BRIGHTNESS_THRESHOLD = 40.0
OVEREXPOSED_BRIGHTNESS_THRESHOLD = 215.0
GALLERY_THUMBNAIL_MAX = 12
THUMBNAIL_WIDTH = 160


def compute_blur_score(image: np.ndarray) -> float:
    """Laplacian-variance sharpness score. Lower = blurrier."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_brightness_score(image: np.ndarray) -> float:
    """Mean pixel intensity, 0 (black) - 255 (white). Used to catch both
    underexposed (dark) frames and overexposed/glare-washed-out frames -
    either extreme makes label text unreadable regardless of sharpness."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(gray.mean())


def compute_quality_score(blur_score: float, brightness_score: float, blur_variance_threshold: float) -> float:
    """Composite [0,1] "how usable is this frame" score, independent of any
    pass/fail threshold - meaningful to display even for frames that passed
    (e.g. to rank "used" frames in the UI), unlike the raw pass/fail reject
    reasons below.
    """
    normalized_blur = min(blur_score / max(blur_variance_threshold * 2.0, 1e-6), 1.0)
    brightness_goodness = max(0.0, 1.0 - abs(brightness_score - 127.5) / 127.5)
    return round(0.6 * normalized_blur + 0.4 * brightness_goodness, 3)


def make_thumbnail_data_uri(image: np.ndarray, width: int = THUMBNAIL_WIDTH, quality: int = 60) -> str:
    """Small JPEG thumbnail as a base64 data URI, for inline display in the
    processing trace without a separate media-serving round trip."""
    h, w = image.shape[:2]
    if w > width:
        new_h = max(int(h * (width / w)), 1)
        image = cv2.resize(image, (width, new_h), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def compute_average_hash(image: np.ndarray, hash_size: int = 8) -> int:
    """Simple perceptual hash used to detect near-duplicate frames."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    avg = resized.mean()
    bits = (resized > avg).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


@dataclass
class RejectedFrame:
    frame_id: str
    timestamp_sec: float
    reason: str
    blur_score: float


@dataclass
class FrameQualityRecord:
    """One record per sampled frame - selected, defect-rejected, or simply
    outcompeted for a selection slot - so nothing sampled from the source
    video silently disappears from the trace."""

    frame_id: str
    timestamp_sec: float
    blur_score: float
    brightness_score: float
    quality_score: float
    selected: bool
    rejection_reason: Optional[str] = None
    thumbnail: Optional[str] = None

    def to_dict(self) -> dict:
        record = {
            "frame_id": self.frame_id,
            "timestamp_sec": round(self.timestamp_sec, 2),
            "blur_score": round(self.blur_score, 1),
            "brightness_score": round(self.brightness_score, 1),
            "quality_score": self.quality_score,
            "selected": self.selected,
            "rejection_reason": self.rejection_reason,
        }
        if self.thumbnail:
            record["thumbnail"] = self.thumbnail
        return record


@dataclass
class QualityFilterResult:
    selected: list[SampledFrame]
    rejected: list[RejectedFrame] = field(default_factory=list)
    frames_sampled: int = 0
    quality_records: list[FrameQualityRecord] = field(default_factory=list)

    @property
    def frames_kept(self) -> int:
        return len(self.selected)

    def to_trace_dict(self) -> dict:
        return {
            "frames_sampled": self.frames_sampled,
            "frames_kept": self.frames_kept,
            "frames_selected_for_vision": [f.frame_id for f in self.selected],
            "frames_rejected": [
                {"frame_id": r.frame_id, "timestamp_sec": r.timestamp_sec, "reason": r.reason, "blur_score": round(r.blur_score, 1)}
                for r in self.rejected
            ],
            "frame_quality_records": [r.to_dict() for r in self.quality_records],
        }


def filter_and_select(
    frames: list[SampledFrame],
    blur_variance_threshold: float = 60.0,
    duplicate_hash_threshold: int = 6,
    max_frames_for_vision: int = 5,
    dark_brightness_threshold: float = DARK_BRIGHTNESS_THRESHOLD,
    overexposed_brightness_threshold: float = OVEREXPOSED_BRIGHTNESS_THRESHOLD,
    gallery_thumbnail_max: int = GALLERY_THUMBNAIL_MAX,
) -> QualityFilterResult:
    """Defect rejection (blur -> dark -> overexposed -> near-duplicate) ->
    time-bucketed sharpness selection. Every input frame ends up with exactly
    one `FrameQualityRecord`, whether it was defect-rejected, outcompeted for
    a selection slot, or ultimately sent to the vision model.
    """
    rejected: list[RejectedFrame] = []
    survivors: list[tuple[SampledFrame, float, int]] = []
    records: dict[str, FrameQualityRecord] = {}

    last_kept_hash: int | None = None
    for frame in frames:
        blur_score = compute_blur_score(frame.image)
        brightness_score = compute_brightness_score(frame.image)
        quality_score = compute_quality_score(blur_score, brightness_score, blur_variance_threshold)

        if blur_score < blur_variance_threshold:
            rejected.append(RejectedFrame(frame.frame_id, frame.timestamp_sec, "blurry", blur_score))
            records[frame.frame_id] = FrameQualityRecord(
                frame.frame_id, frame.timestamp_sec, blur_score, brightness_score, quality_score, selected=False, rejection_reason="motion blur"
            )
            continue

        if brightness_score < dark_brightness_threshold:
            rejected.append(RejectedFrame(frame.frame_id, frame.timestamp_sec, "too dark", blur_score))
            records[frame.frame_id] = FrameQualityRecord(
                frame.frame_id, frame.timestamp_sec, blur_score, brightness_score, quality_score, selected=False, rejection_reason="too dark"
            )
            continue

        if brightness_score > overexposed_brightness_threshold:
            rejected.append(RejectedFrame(frame.frame_id, frame.timestamp_sec, "overexposed (glare)", blur_score))
            records[frame.frame_id] = FrameQualityRecord(
                frame.frame_id, frame.timestamp_sec, blur_score, brightness_score, quality_score, selected=False, rejection_reason="overexposed (glare)"
            )
            continue

        phash = compute_average_hash(frame.image)
        if last_kept_hash is not None and hamming_distance(phash, last_kept_hash) <= duplicate_hash_threshold:
            rejected.append(RejectedFrame(frame.frame_id, frame.timestamp_sec, "near-duplicate of previous frame", blur_score))
            records[frame.frame_id] = FrameQualityRecord(
                frame.frame_id, frame.timestamp_sec, blur_score, brightness_score, quality_score, selected=False, rejection_reason="near-duplicate frame"
            )
            continue

        survivors.append((frame, blur_score, phash))
        last_kept_hash = phash
        records[frame.frame_id] = FrameQualityRecord(
            frame.frame_id, frame.timestamp_sec, blur_score, brightness_score, quality_score, selected=False, rejection_reason=None
        )

    selected = _select_time_diverse_sharpest(survivors, max_frames_for_vision)
    selected_ids = {f.frame_id for f in selected}

    for survivor_frame, _, _ in survivors:
        record = records[survivor_frame.frame_id]
        if survivor_frame.frame_id in selected_ids:
            record.selected = True
        else:
            record.rejection_reason = "not selected - a sharper frame was chosen from this time window"

    _assign_gallery_thumbnails(frames, records, selected_ids, gallery_thumbnail_max)

    ordered_records = sorted(records.values(), key=lambda r: r.timestamp_sec)
    return QualityFilterResult(selected=selected, rejected=rejected, frames_sampled=len(frames), quality_records=ordered_records)


def _assign_gallery_thumbnails(
    frames: list[SampledFrame],
    records: dict[str, FrameQualityRecord],
    selected_ids: set[str],
    gallery_thumbnail_max: int,
) -> None:
    """Thumbnails are only worth generating (and shipping over the wire) for
    a bounded "gallery" subset - every selected frame first (there are at
    most `max_frames_for_vision` of those), then the earliest rejected
    frames up to the remaining budget - rather than for potentially dozens
    of raw sampled frames.
    """
    gallery_ids = list(selected_ids)
    remaining_budget = max(gallery_thumbnail_max - len(gallery_ids), 0)
    if remaining_budget > 0:
        rejected_by_time = sorted((r for r in records.values() if r.frame_id not in selected_ids), key=lambda r: r.timestamp_sec)
        gallery_ids.extend(r.frame_id for r in rejected_by_time[:remaining_budget])

    frame_by_id = {f.frame_id: f for f in frames}
    for frame_id in gallery_ids:
        frame = frame_by_id.get(frame_id)
        if frame is not None:
            records[frame_id].thumbnail = make_thumbnail_data_uri(frame.image)


def _select_time_diverse_sharpest(
    survivors: list[tuple[SampledFrame, float, int]], max_frames_for_vision: int
) -> list[SampledFrame]:
    if len(survivors) <= max_frames_for_vision:
        return [f for f, _, _ in survivors]

    # Split the time-ordered survivors into N buckets, pick the sharpest frame per bucket,
    # so the final selection stays spread across the video instead of clustering.
    bucket_count = max_frames_for_vision
    bucket_size = len(survivors) / bucket_count
    selected: list[SampledFrame] = []
    for i in range(bucket_count):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size) if i < bucket_count - 1 else len(survivors)
        bucket = survivors[start:end]
        if not bucket:
            continue
        sharpest = max(bucket, key=lambda item: item[1])
        selected.append(sharpest[0])
    return selected
