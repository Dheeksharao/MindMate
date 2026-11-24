import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logic import (
    calculate_checkin_score,
    evaluate_support_level,
    evaluate_learning_gaps,
    check_safety_keywords,
    generate_recommendations,
    SAFEGUARDING_MESSAGE
)

def test_rule_a_checkin_score():
    # Stress is inverted: (6 - stress).
    # If mood=5, stress=1 (calm), sleep=5, focus=5, belonging=5:
    # 5 + (6 - 1) + 5 + 5 + 5 = 25 / 5 = 5.0
    score = calculate_checkin_score(mood=5, stress=1, sleep=5, focus=5, belonging=5)
    assert score == 5.0

    # If mood=1, stress=5 (high stress), sleep=1, focus=1, belonging=1:
    # 1 + (6 - 5) + 1 + 1 + 1 = 5 / 5 = 1.0
    score_low = calculate_checkin_score(mood=1, stress=5, sleep=1, focus=1, belonging=1)
    assert score_low == 1.0

    # Typical mix: mood=3, stress=4, sleep=3, focus=2, belonging=4:
    # 3 + (6 - 4) + 3 + 2 + 4 = 14 / 5 = 2.8
    score_mid = calculate_checkin_score(mood=3, stress=4, sleep=3, focus=2, belonging=4)
    assert score_mid == 2.8

def test_rule_b_support_level_below_3():
    # Average < 3.0 -> "May benefit from support"
    scores = [2.5, 2.7, 2.8]
    res = evaluate_support_level(scores)
    assert res["level"] == "May benefit from support"
    assert "2.7/5" in res["reason"]

def test_rule_b_support_level_falling_trend():
    # Scores: previous 3 avg was 3.8, last 3 avg is 3.3.
    # avg_last3 = 3.3 (< 3.5), trend = 3.3 - 3.8 = -0.5 (falling by > 0.4)
    # -> "May benefit from support"
    scores = [3.8, 3.8, 3.8, 3.3, 3.3, 3.3]
    res = evaluate_support_level(scores)
    assert res["level"] == "May benefit from support"
    assert res["trend"] == -0.5
    assert "-0.5" in res["reason"]

def test_rule_b_support_level_doing_okay():
    # avg 3.4, previous 3.5 -> trend -0.1 (not > 0.4 drop) -> "Doing okay"
    scores = [3.5, 3.5, 3.5, 3.4, 3.4, 3.4]
    res = evaluate_support_level(scores)
    assert res["level"] == "Doing okay"
    
    # avg 3.65 -> "Doing okay"
    scores2 = [3.6, 3.7, 3.65]
    res2 = evaluate_support_level(scores2)
    assert res2["level"] == "Doing okay"

def test_rule_b_support_level_thriving():
    # avg >= 3.7 -> "Thriving"
    scores = [4.0, 4.2, 4.1]
    res = evaluate_support_level(scores)
    assert res["level"] == "Thriving"
    assert "4.1/5" in res["reason"]

def test_rule_c_learning_gap_below_40():
    assessments = [
        {"subject": "Math", "score": 35, "max_score": 100, "date": "2026-10-01", "id": 1}
    ]
    gaps = evaluate_learning_gaps(assessments)
    assert len(gaps) == 1
    assert gaps[0]["subject"] == "Math"
    assert "below the 40% benchmark" in gaps[0]["reason"]

def test_rule_c_learning_gap_dropped_more_than_15_points():
    assessments = [
        {"subject": "Science", "score": 80, "max_score": 100, "date": "2026-10-01", "id": 1},
        {"subject": "Science", "score": 62, "max_score": 100, "date": "2026-10-15", "id": 2}
    ]
    # Dropped 18 points (80 -> 62)
    gaps = evaluate_learning_gaps(assessments)
    assert len(gaps) == 1
    assert gaps[0]["subject"] == "Science"
    assert "Dropped 18.0 points" in gaps[0]["reason"]

def test_rule_c_no_learning_gap_when_stable():
    assessments = [
        {"subject": "English", "score": 75, "max_score": 100, "date": "2026-10-01", "id": 1},
        {"subject": "English", "score": 72, "max_score": 100, "date": "2026-10-15", "id": 2}
    ]
    # Dropped only 3 points and score is 72% (>40%)
    gaps = evaluate_learning_gaps(assessments)
    assert len(gaps) == 0

def test_rule_e_safety_keywords():
    is_urgent, kw = check_safety_keywords("I feel completely hopeless about the future.")
    assert is_urgent is True
    assert kw == "hopeless"

    is_urgent2, kw2 = check_safety_keywords("Sometimes I want to hurt myself.")
    assert is_urgent2 is True
    assert kw2 == "hurt myself"

    is_urgent3, kw3 = check_safety_keywords("I feel unsafe walking home.")
    assert is_urgent3 is True
    assert kw3 == "unsafe"

    is_urgent_safe, _ = check_safety_keywords("I really enjoyed math class today!")
    assert is_urgent_safe is False

def test_rule_f_recommendations():
    support_info = {"level": "May benefit from support"}
    gaps = [{"subject": "Math", "reason": "Latest score 35% is below 40%"}]
    recs = generate_recommendations(support_info, gaps)
    categories = [r["category"] for r in recs]
    assert "Well-being" in categories
    assert "Academic: Math" in categories
    assert any("buddy" in r["action"].lower() for r in recs)
    assert any("practice set" in r["action"].lower() for r in recs)
