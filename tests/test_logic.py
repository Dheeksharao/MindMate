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

# ====================================================================
# Tests for scoring_config.py (Phase 5: Scoring, Safeguarding, Guidance)
# ====================================================================
from scoring_config import (
    calculate_domain_concern_level,
    evaluate_adaptive_checkin_scoring,
    check_text_for_safeguarding,
    GUIDANCE_TEMPLATES,
    DISCLAIMER_TEXT,
    SAFEGUARDING_TEACHER_ALERT_MESSAGE,
    DEFAULT_STUDENT_CALM_MESSAGE
)

def test_classify_domain_concern():
    # Low concern < 0.35
    assert calculate_domain_concern_level(0.0) == "Low"
    assert calculate_domain_concern_level(0.2) == "Low"
    assert calculate_domain_concern_level(0.34) == "Low"
    # Medium concern 0.35 - 0.64
    assert calculate_domain_concern_level(0.35) == "Medium"
    assert calculate_domain_concern_level(0.50) == "Medium"
    assert calculate_domain_concern_level(0.64) == "Medium"
    # High concern >= 0.65
    assert calculate_domain_concern_level(0.65) == "High"
    assert calculate_domain_concern_level(0.90) == "High"
    assert calculate_domain_concern_level(1.0) == "High"

def test_evaluate_adaptive_checkin_scoring_doing_well():
    low_scores = {"mood": 0.1, "stress": 0.2, "academic": 0.15, "social": 0.1}
    res = evaluate_adaptive_checkin_scoring(low_scores, {})
    assert res["wellbeing_indicator"] == "Doing Well"
    assert res["urgent_flag"] is False
    assert res["overall_score"] < 0.30

def test_evaluate_adaptive_checkin_scoring_moderate_concern():
    # Exactly 1 high concern
    one_high = {"mood": 0.1, "stress": 0.1, "academic": 0.8}
    res = evaluate_adaptive_checkin_scoring(one_high, {})
    assert res["wellbeing_indicator"] == "Moderate Concern"
    assert res["domain_levels"]["academic"] == "High"

    # Moderate average
    mid_scores = {"mood": 0.4, "stress": 0.35, "academic": 0.45}
    res2 = evaluate_adaptive_checkin_scoring(mid_scores, {})
    assert res2["wellbeing_indicator"] == "Moderate Concern"

def test_evaluate_adaptive_checkin_scoring_needs_attention():
    # 2 high concerns
    two_high = {"mood": 0.8, "stress": 0.75, "academic": 0.2}
    res = evaluate_adaptive_checkin_scoring(two_high, {})
    assert res["wellbeing_indicator"] == "Needs Attention"

    # Urgent trigger elevates directly to Needs Attention
    low_scores = {"mood": 0.1, "stress": 0.1}
    res_urgent = evaluate_adaptive_checkin_scoring(low_scores, {}, urgent_flag=True)
    assert res_urgent["wellbeing_indicator"] == "Needs Attention"
    assert res_urgent["urgent_flag"] is True

def test_check_text_for_safeguarding():
    has_urgent, kw = check_text_for_safeguarding("I feel like giving up on everything.")
    assert has_urgent is True
    assert kw == "giving up"

    has_urgent2, kw2 = check_text_for_safeguarding("I feel unsafe at home.")
    assert has_urgent2 is True
    assert kw2 == "unsafe"

    has_urgent_safe, _ = check_text_for_safeguarding("Just tired after football practice.")
    assert has_urgent_safe is False

def test_guidance_templates_and_disclaimer():
    assert "caring conversation" in DISCLAIMER_TEXT.lower()
    assert "designated safeguarding lead" in SAFEGUARDING_TEACHER_ALERT_MESSAGE.lower()
    assert "reach out to your mentor teacher" in DEFAULT_STUDENT_CALM_MESSAGE.lower()
    assert "exam_stress" in GUIDANCE_TEMPLATES
    assert "sleep_difficulty" in GUIDANCE_TEMPLATES
    assert "skipped_breakfast" in GUIDANCE_TEMPLATES
