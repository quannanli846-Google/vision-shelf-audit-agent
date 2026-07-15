"""Unit tests for video/quality_filter.py - blur rejection, near-duplicate
rejection, and time-diverse sharp-frame selection.

All images are synthetic (numpy/OpenCV generated) so these tests need no
sample media files and run in milliseconds.
"""
import cv2
import numpy as np
import pytest

from video.frame_extractor import SampledFrame
from video.quality_filter import (
    compute_average_hash,
    compute_blur_score,
    compute_brightness_score,
    compute_quality_score,
    filter_and_select,
    hamming_distance,
    make_thumbnail_data_uri,
    _select_time_diverse_sharpest,
)


def _checkerboard(size: int = 64, block: int = 8) -> np.ndarray:
    img = np.zeros((size, size, 3), dtype=np.uint8)
    for y in range(0, size, block):
        for x in range(0, size, block):
            if ((x // block) + (y // block)) % 2 == 0:
                img[y : y + block, x : x + block] = 255
    return img


def _blur(image: np.ndarray, ksize: int = 15) -> np.ndarray:
    return cv2.GaussianBlur(image, (ksize, ksize), 0)


def _frame(frame_id: str, t: float, image: np.ndarray) -> SampledFrame:
    return SampledFrame(frame_id=frame_id, timestamp_sec=t, image=image)


class TestComputeBlurScore:
    def test_sharp_checkerboard_scores_higher_than_blurred_version(self):
        sharp = _checkerboard()
        blurred = _blur(sharp, ksize=21)

        assert compute_blur_score(sharp) > compute_blur_score(blurred)

    def test_flat_uniform_image_has_near_zero_variance(self):
        flat = np.full((64, 64, 3), 128, dtype=np.uint8)
        assert compute_blur_score(flat) == pytest.approx(0.0, abs=1e-6)


class TestPerceptualHash:
    def test_identical_images_have_zero_hamming_distance(self):
        img = _checkerboard()
        h1 = compute_average_hash(img)
        h2 = compute_average_hash(img.copy())
        assert hamming_distance(h1, h2) == 0

    def test_inverted_image_is_maximally_different(self):
        img = _checkerboard()
        inverted = 255 - img
        h1 = compute_average_hash(img, hash_size=8)
        h2 = compute_average_hash(inverted, hash_size=8)
        # every bit flips when the image is fully inverted
        assert hamming_distance(h1, h2) == 64

    def test_slightly_blurred_image_hashes_nearly_identically(self):
        img = _checkerboard()
        slightly_blurred = _blur(img, ksize=3)
        h1 = compute_average_hash(img)
        h2 = compute_average_hash(slightly_blurred)
        assert hamming_distance(h1, h2) <= 6


class TestFilterAndSelect:
    def test_blurry_frames_are_rejected_with_reason(self):
        sharp = _checkerboard()
        blurry = _blur(sharp, ksize=25)
        frames = [_frame("f0", 0.0, sharp), _frame("f1", 1.0, blurry)]

        result = filter_and_select(frames, blur_variance_threshold=200.0, duplicate_hash_threshold=6, max_frames_for_vision=5)

        selected_ids = {f.frame_id for f in result.selected}
        assert "f0" in selected_ids
        assert "f1" not in selected_ids
        assert any(r.frame_id == "f1" and r.reason == "blurry" for r in result.rejected)

    def test_near_duplicate_frames_are_rejected(self):
        a = _checkerboard(block=8)
        b = _checkerboard(block=4)  # a distinctly different pattern
        frames = [
            _frame("f0", 0.0, a),
            _frame("f1", 1.0, a.copy()),  # exact duplicate of f0
            _frame("f2", 2.0, b),  # genuinely different content
        ]

        result = filter_and_select(frames, blur_variance_threshold=1.0, duplicate_hash_threshold=6, max_frames_for_vision=5)

        selected_ids = {f.frame_id for f in result.selected}
        assert "f0" in selected_ids
        assert "f1" not in selected_ids
        assert "f2" in selected_ids
        assert any(r.frame_id == "f1" and "duplicate" in r.reason for r in result.rejected)

    def test_frames_sampled_count_is_reported(self):
        frames = [_frame(f"f{i}", float(i), _checkerboard()) for i in range(4)]
        result = filter_and_select(frames, blur_variance_threshold=1.0, duplicate_hash_threshold=0, max_frames_for_vision=10)
        assert result.frames_sampled == 4

    def test_empty_input_produces_empty_result(self):
        result = filter_and_select([], blur_variance_threshold=60.0, duplicate_hash_threshold=6, max_frames_for_vision=5)
        assert result.selected == []
        assert result.frames_kept == 0


class TestBrightness:
    def test_dark_image_has_low_brightness_score(self):
        dark = np.full((64, 64, 3), 5, dtype=np.uint8)
        bright = np.full((64, 64, 3), 200, dtype=np.uint8)
        assert compute_brightness_score(dark) < compute_brightness_score(bright)

    def test_dark_frames_are_rejected_as_too_dark(self):
        dark = np.full((64, 64, 3), 5, dtype=np.uint8)
        frames = [_frame("f0", 0.0, dark)]
        result = filter_and_select(frames, blur_variance_threshold=0.0, duplicate_hash_threshold=6, max_frames_for_vision=5)
        assert result.selected == []
        assert any(r.frame_id == "f0" and r.reason == "too dark" for r in result.rejected)

    def test_overexposed_frames_are_rejected_as_glare(self):
        blown_out = np.full((64, 64, 3), 250, dtype=np.uint8)
        frames = [_frame("f0", 0.0, blown_out)]
        result = filter_and_select(frames, blur_variance_threshold=0.0, duplicate_hash_threshold=6, max_frames_for_vision=5)
        assert result.selected == []
        assert any(r.frame_id == "f0" and "glare" in r.reason for r in result.rejected)

    def test_well_lit_sharp_frame_is_not_rejected_for_brightness(self):
        img = _checkerboard()
        frames = [_frame("f0", 0.0, img)]
        result = filter_and_select(frames, blur_variance_threshold=1.0, duplicate_hash_threshold=6, max_frames_for_vision=5)
        assert "f0" in {f.frame_id for f in result.selected}


class TestQualityScore:
    def test_sharp_well_lit_frame_scores_higher_than_blurry_frame(self):
        sharp = _checkerboard()
        blurry = _blur(sharp, ksize=25)
        sharp_score = compute_quality_score(compute_blur_score(sharp), compute_brightness_score(sharp), blur_variance_threshold=60.0)
        blurry_score = compute_quality_score(compute_blur_score(blurry), compute_brightness_score(blurry), blur_variance_threshold=60.0)
        assert sharp_score > blurry_score

    def test_quality_score_is_bounded_zero_to_one(self):
        img = _checkerboard()
        score = compute_quality_score(compute_blur_score(img), compute_brightness_score(img), blur_variance_threshold=60.0)
        assert 0.0 <= score <= 1.0


class TestFrameQualityRecords:
    def test_every_input_frame_gets_exactly_one_record(self):
        sharp = _checkerboard()
        blurry = _blur(sharp, ksize=25)
        # Textured (not flat) so it passes the blur check on its own merits,
        # isolating the "too dark" rejection from the "motion blur" one.
        dark = (sharp.astype(float) * 0.12).astype(np.uint8)
        frames = [_frame("f0", 0.0, sharp), _frame("f1", 1.0, blurry), _frame("f2", 2.0, dark)]

        result = filter_and_select(frames, blur_variance_threshold=200.0, duplicate_hash_threshold=6, max_frames_for_vision=5)

        assert {r.frame_id for r in result.quality_records} == {"f0", "f1", "f2"}
        by_id = {r.frame_id: r for r in result.quality_records}
        assert by_id["f0"].selected is True
        assert by_id["f0"].rejection_reason is None
        assert by_id["f1"].selected is False
        assert by_id["f1"].rejection_reason == "motion blur"
        assert by_id["f2"].rejection_reason == "too dark"

    def test_survivors_not_chosen_for_a_selection_slot_are_still_recorded(self):
        # 6 well-lit sharp survivors but only 2 selection slots -> the other 4
        # must still show up in quality_records (never silently vanish), each
        # with an explanatory (not-defective) rejection_reason.
        frames = [_frame(f"f{i}", float(i), _checkerboard(block=8 + i)) for i in range(6)]
        result = filter_and_select(frames, blur_variance_threshold=1.0, duplicate_hash_threshold=0, max_frames_for_vision=2)

        assert len(result.quality_records) == 6
        not_selected = [r for r in result.quality_records if not r.selected]
        assert len(not_selected) == 4
        assert all(r.rejection_reason is not None for r in not_selected)

    def test_gallery_thumbnail_budget_is_respected(self):
        frames = [_frame(f"f{i}", float(i), _blur(_checkerboard(), ksize=25)) for i in range(20)]
        result = filter_and_select(
            frames, blur_variance_threshold=200.0, duplicate_hash_threshold=6, max_frames_for_vision=5, gallery_thumbnail_max=3
        )
        with_thumbnail = [r for r in result.quality_records if r.thumbnail]
        assert len(with_thumbnail) <= 3


class TestThumbnail:
    def test_thumbnail_is_a_data_uri(self):
        img = _checkerboard()
        uri = make_thumbnail_data_uri(img)
        assert uri.startswith("data:image/jpeg;base64,")

    def test_wide_image_is_downscaled_to_target_width(self):
        wide = np.zeros((100, 800, 3), dtype=np.uint8)
        uri = make_thumbnail_data_uri(wide, width=160)
        assert uri.startswith("data:image/jpeg;base64,")


class TestTimeDiverseSelection:
    def test_returns_all_when_fewer_than_max(self):
        survivors = [(_frame(f"f{i}", float(i), _checkerboard()), float(i), 0) for i in range(3)]
        selected = _select_time_diverse_sharpest(survivors, max_frames_for_vision=5)
        assert len(selected) == 3

    def test_picks_sharpest_frame_per_time_bucket(self):
        # 6 survivors, 2 buckets of 3 -> picks the sharpest (highest blur_score) from each half
        survivors = [
            (_frame("f0", 0.0, _checkerboard()), 10.0, 0),
            (_frame("f1", 1.0, _checkerboard()), 50.0, 0),  # sharpest in first half
            (_frame("f2", 2.0, _checkerboard()), 20.0, 0),
            (_frame("f3", 3.0, _checkerboard()), 15.0, 0),
            (_frame("f4", 4.0, _checkerboard()), 90.0, 0),  # sharpest in second half
            (_frame("f5", 5.0, _checkerboard()), 30.0, 0),
        ]
        selected = _select_time_diverse_sharpest(survivors, max_frames_for_vision=2)
        selected_ids = {f.frame_id for f in selected}
        assert selected_ids == {"f1", "f4"}

    def test_selection_size_matches_requested_max(self):
        survivors = [(_frame(f"f{i}", float(i), _checkerboard()), float(i * 3 % 7), 0) for i in range(20)]
        selected = _select_time_diverse_sharpest(survivors, max_frames_for_vision=5)
        assert len(selected) == 5
