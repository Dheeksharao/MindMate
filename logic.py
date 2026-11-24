import re
from typing import List, Dict, Any, Tuple, Optional

# Rule E: Safety keywords configuration
SAFETY_KEYWORDS = [
    "hopeless",
    "hurt myself",
    "unsafe",
    "self harm",
    "end it",
    "suicide",
    "giving up",
    "want to disappear"
]

SAFEGUARDING_MESSAGE = "Speak with the student privately today, follow your school's safeguarding policy and involve the counsellor."

DISCLAIMER_TEXT = "This tool does not diagnose. It helps teachers notice when a student might need a caring conversation."

def calculate_checkin_score(mood: int, stress: int, sleep: int, focus: int, belonging: int) -> float:
    """
    Rule A: Check-in score = (mood + (6 − stress) + sleep + focus + belonging) / 5.
    Stress is inverted: 1 (calm) -> (6-1)=5 (high positive), 5 (overwhelmed) -> (6-5)=1 (low).
    All inputs 1-5. Output 1.0 to 5.0.
    """
    for val, name in [(mood, "mood"), (stress, "stress"), (sleep, "sleep"), (focus, "focus"), (belonging, "belonging")]:
        if not (1 <= val <= 5):
            raise ValueError(f"{name} must be between 1 and 5 (got {val})")
            
    raw_score = (mood + (6 - stress) + sleep + focus + belonging) / 5.0
    return round(raw_score, 2)

def evaluate_support_level(scores_chronological: List[float]) -> Dict[str, Any]:
    """
    Rule B: Support level from the average of the last 3 check-ins:
    - average below 3.0, or (below 3.5 and falling by more than 0.4 versus the previous 3) -> "May benefit from support"
    - below 3.7 -> "Doing okay"
    - otherwise -> "Thriving"
    Show the reason, e.g. "Average 2.8/5 over last 3 check-ins, trend -0.5".
    """
    if not scores_chronological:
        return {
            "level": "No data",
            "reason": "No check-ins recorded yet",
            "avg_last3": None,
            "trend": None,
            "badge_class": "badge-neutral"
        }
    
    last3 = scores_chronological[-3:]
    avg_last3 = round(sum(last3) / len(last3), 2)
    
    # Calculate trend if we have previous check-ins before the last 3
    trend: Optional[float] = None
    if len(scores_chronological) >= 4:
        # Check up to 3 check-ins preceding the last 3
        prev_slice = scores_chronological[-6:-3]
        if prev_slice:
            avg_prev = sum(prev_slice) / len(prev_slice)
            trend = round(avg_last3 - avg_prev, 2)
            
    # Decision logic
    is_falling_sharply = (trend is not None and trend < -0.4)
    
    if avg_last3 < 3.0 or (avg_last3 < 3.5 and is_falling_sharply):
        level = "May benefit from support"
        badge_class = "badge-coral"
    elif avg_last3 < 3.7:
        level = "Doing okay"
        badge_class = "badge-amber"
    else:
        level = "Thriving"
        badge_class = "badge-green"
        
    # Reason formatting
    if trend is not None:
        sign = "+" if trend > 0 else ""
        reason = f"Average {avg_last3:.1f}/5 over last {len(last3)} check-in{'s' if len(last3)>1 else ''}, trend {sign}{trend:.1f}"
    else:
        reason = f"Average {avg_last3:.1f}/5 over last {len(last3)} check-in{'s' if len(last3)>1 else ''}"
        
    return {
        "level": level,
        "reason": reason,
        "avg_last3": avg_last3,
        "trend": trend,
        "badge_class": badge_class
    }

def evaluate_learning_gaps(assessments_chronological: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rule C: Learning gap:
    A subject is flagged if:
    - the latest score is below 40%, OR
    - it dropped by more than 15 points compared with the previous assessment.
    """
    # Group assessments by subject
    by_subject: Dict[str, List[Dict[str, Any]]] = {}
    for a in assessments_chronological:
        subj = a["subject"]
        if subj not in by_subject:
            by_subject[subj] = []
        by_subject[subj].append(a)
        
    gaps = []
    for subj, records in by_subject.items():
        if not records:
            continue
        # Ensure chronological order by date/id
        sorted_records = sorted(records, key=lambda x: (x.get("date", ""), x.get("id", 0)))
        latest = sorted_records[-1]
        
        latest_max = latest.get("max_score") or 100.0
        latest_pct = round((latest["score"] / latest_max) * 100.0, 1)
        
        has_gap = False
        reasons = []
        
        if latest_pct < 40.0:
            has_gap = True
            reasons.append(f"Latest score ({latest_pct}%) is below the 40% benchmark")
            
        if len(sorted_records) >= 2:
            prev = sorted_records[-2]
            prev_max = prev.get("max_score") or 100.0
            prev_pct = round((prev["score"] / prev_max) * 100.0, 1)
            drop = round(prev_pct - latest_pct, 1)
            if drop > 15.0:
                has_gap = True
                reasons.append(f"Dropped {drop} points from previous score ({prev_pct}% → {latest_pct}%)")
                
        if has_gap:
            gaps.append({
                "subject": subj,
                "latest_pct": latest_pct,
                "reason": " & ".join(reasons),
                "reasons": reasons
            })
            
    return gaps

def check_safety_keywords(note: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Rule E: Safety keyword rule.
    Returns (is_urgent, matched_keyword).
    """
    if not note:
        return False, None
    lower_note = note.lower()
    for kw in SAFETY_KEYWORDS:
        # Word boundary or phrase check
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, lower_note):
            return True, kw
    return False, None

def generate_recommendations(support_info: Dict[str, Any], learning_gaps: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Rule F: Recommendations:
    - For each gap: suggest a short practice set for that subject
    - For "may benefit from support": suggest a gentle one-to-one chat and a buddy study session
    - Warm, strength-based wording.
    """
    recommendations = []
    
    # Well-being recommendation
    if support_info.get("level") == "May benefit from support":
        recommendations.append({
            "category": "Well-being",
            "type": "support",
            "title": "Gentle 1-on-1 Check-in & Peer Connection",
            "action": "Schedule a quiet, low-pressure 5-minute conversation to listen and validate their experience. Pair them with an encouraging buddy for collaborative classroom activities to nurture social belonging."
        })
    elif support_info.get("level") == "Doing okay":
        recommendations.append({
            "category": "Well-being",
            "type": "nurture",
            "title": "Check-in Reassurance",
            "action": "Offer positive reinforcement on their daily effort and keep open communication available whenever they feel stressed."
        })
        
    # Academic learning gap recommendations
    for gap in learning_gaps:
        subj = gap["subject"]
        recommendations.append({
            "category": f"Academic: {subj}",
            "type": "academic",
            "title": f"Targeted Practice Set in {subj}",
            "action": f"Provide a bite-sized, 10-minute foundational practice set in {subj} to rebuild confidence on core concepts. Celebrate small wins to foster growth mindset."
        })
        
    if not recommendations:
        recommendations.append({
            "category": "General",
            "type": "positive",
            "title": "Continued Growth & Mentorship",
            "action": "The student is demonstrating balanced well-being and steady academic progress. Continue encouraging their natural curiosity and consider inviting them to help mentor peers."
        })
        
    return recommendations
