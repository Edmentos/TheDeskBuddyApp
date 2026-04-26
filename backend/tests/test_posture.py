"""Tests for the posture state machine (PostureTracker)."""
from unittest.mock import patch

import pytest

from app.posture import PostureTracker


def make_tracker(**kwargs) -> PostureTracker:
    """Helper so tests don't repeat the default constructor args."""
    return PostureTracker(sitting_height_cm=80.0, standing_offset_cm=10.0, **kwargs)


# --- initial state ---

def test_starts_in_sitting():
    assert make_tracker().current_state == "sitting"


def test_standing_threshold_is_sum_of_heights():
    t = make_tracker()
    assert t.standing_threshold_cm == 90.0


def test_buffer_starts_empty():
    assert make_tracker().get_smoothed_distance() == 0.0


# --- transitions ---

def test_stays_sitting_when_below_threshold():
    t = make_tracker()
    t.min_duration_sec = 0
    for _ in range(10):
        t.process_distance(85.0)
    assert t.current_state == "sitting"


def test_transitions_to_standing():
    t = make_tracker()
    t.min_duration_sec = 0
    # need >= standing_threshold + hysteresis = 90 + 5 = 95
    for _ in range(10):
        t.process_distance(100.0)
    assert t.current_state == "standing"


def test_transitions_back_to_sitting():
    t = make_tracker()
    t.min_duration_sec = 0
    for _ in range(10):
        t.process_distance(100.0)
    assert t.current_state == "standing"
    # need <= standing_threshold - hysteresis = 90 - 5 = 85
    for _ in range(10):
        t.process_distance(60.0)
    assert t.current_state == "sitting"


# --- hysteresis ---

def test_hysteresis_prevents_flicker_when_standing():
    t = make_tracker()
    t.min_duration_sec = 0
    for _ in range(10):
        t.process_distance(100.0)
    assert t.current_state == "standing"

    # 88cm is between the two thresholds (85 < 88 < 95), should stay standing
    for _ in range(10):
        t.process_distance(88.0)
    assert t.current_state == "standing"


def test_hysteresis_prevents_flicker_when_sitting():
    t = make_tracker()
    t.min_duration_sec = 0
    # 92cm is above threshold but below standing gate (90 < 92 < 95)
    # so coming from sitting it should stay sitting
    for _ in range(10):
        t.process_distance(92.0)
    assert t.current_state == "sitting"


# --- minimum duration ---

def test_min_duration_delays_transition():
    t = make_tracker()
    # freeze time so the candidate timer never expires
    with patch('app.posture.time') as mock_time:
        mock_time.time.return_value = 1000.0
        for _ in range(10):
            t.process_distance(100.0)

    # candidate should be set, but state hasn't changed yet
    assert t.current_state == "sitting"
    assert t.candidate_state == "standing"


def test_state_confirms_after_min_duration():
    t = make_tracker()
    t.min_duration_sec = 1.0

    times = iter([1000.0, 1000.0, 1002.0])  # first two calls < 1s, third > 1s
    with patch('app.posture.time') as mock_time:
        mock_time.time.side_effect = lambda: next(times)
        t.process_distance(100.0)  # sets candidate at t=1000
        t.process_distance(100.0)  # still at 1000, no confirm
        t.process_distance(100.0)  # at 1002, 2s elapsed → confirms

    assert t.current_state == "standing"


# --- input validation ---

def test_ignores_negative_distance():
    t = make_tracker()
    t.process_distance(-1.0)
    assert len(t.distance_buffer) == 0
    assert t.current_state == "sitting"


def test_ignores_distance_above_400():
    t = make_tracker()
    t.process_distance(500.0)
    assert len(t.distance_buffer) == 0


def test_ignores_none():
    t = make_tracker()
    t.process_distance(None)
    assert t.current_state == "sitting"


def test_ignores_string_input():
    t = make_tracker()
    t.process_distance("tall")
    assert t.current_state == "sitting"


def test_returns_current_state_on_bad_input():
    t = make_tracker()
    result = t.process_distance(None)
    assert result == "sitting"


# --- smoothing ---

def test_smoothed_distance_is_average_of_buffer():
    t = make_tracker()
    t.process_distance(60.0)
    t.process_distance(80.0)
    assert t.get_smoothed_distance() == 70.0


def test_spike_is_smoothed_out():
    t = make_tracker()
    for _ in range(4):
        t.process_distance(70.0)
    t.process_distance(200.0)  # spike
    # average of [70, 70, 70, 70, 200] = 96, not 200
    assert t.get_smoothed_distance() < 120.0


def test_buffer_maxlen_is_5():
    t = make_tracker()
    for i in range(10):
        t.process_distance(float(i))
    # only last 5 values (5.0–9.0) should be in buffer
    assert len(t.distance_buffer) == 5
    assert t.get_smoothed_distance() == pytest.approx(7.0)


# --- callback ---

def test_callback_fires_on_state_change():
    changes = []
    t = PostureTracker(
        sitting_height_cm=80.0,
        standing_offset_cm=10.0,
        on_state_change=lambda old, new, ts: changes.append((old, new))
    )
    t.min_duration_sec = 0
    for _ in range(10):
        t.process_distance(100.0)
    assert changes == [("sitting", "standing")]


def test_callback_fires_again_on_return_to_sitting():
    changes = []
    t = PostureTracker(
        sitting_height_cm=80.0,
        standing_offset_cm=10.0,
        on_state_change=lambda old, new, ts: changes.append((old, new))
    )
    t.min_duration_sec = 0
    for _ in range(10):
        t.process_distance(100.0)
    for _ in range(10):
        t.process_distance(60.0)
    assert changes == [("sitting", "standing"), ("standing", "sitting")]


def test_callback_doesnt_fire_for_same_state():
    changes = []
    t = PostureTracker(
        sitting_height_cm=80.0,
        standing_offset_cm=10.0,
        on_state_change=lambda old, new, ts: changes.append((old, new))
    )
    t.min_duration_sec = 0
    for _ in range(20):
        t.process_distance(70.0)
    assert changes == []


# --- config ---

def test_update_thresholds():
    t = make_tracker()
    t.update_thresholds(sitting_height_cm=100.0, standing_offset_cm=15.0)
    assert t.sitting_height_cm == 100.0
    assert t.standing_offset_cm == 15.0
    assert t.standing_threshold_cm == 115.0


def test_get_config_returns_correct_values():
    t = make_tracker()
    config = t.get_config()
    assert config['sitting_height_cm'] == 80.0
    assert config['standing_offset_cm'] == 10.0
    assert config['standing_threshold_cm'] == 90.0
