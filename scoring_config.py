"""
MindMate Scoring, Safeguarding, and Guidance Configuration.
Rule-based, transparent, and school-aligned configuration.
This module documents and implements:
1. Domain concern thresholds (Low, Medium, High).
2. Overall well-being indicator calculation (Doing Well, Moderate Concern, Needs Attention).
3. Urgent safeguarding triggers and calming student-facing messages.
4. Personalized guidance template mapping from concern tags.
5. Optional LLM provider hook (OFF by default).
"""

from typing import Dict, List, Any, Tuple, Optional
import re

# ─────────────────────────────────────────────────────────────
# Thresholds
# ─────────────────────────────────────────────────────────────

# Concern score per domain (range 0.0 to 1.0, where 0.0 = positive/thriving, 1.0 = severe concern)
DOMAIN_THRESHOLDS = {
    "low_max": 0.34,       # < 0.35 is "Low" concern
    "medium_max": 0.64,    # 0.35 - 0.64 is "Medium" concern
    "high_min": 0.65       # >= 0.65 is "High" concern
}

# Overall indicator rules:
# - "Doing Well": Average score < 0.30 and 0 domains in High Concern
# - "Moderate Concern": Average score 0.30 - 0.54 OR exactly 1 domain in High Concern
# - "Needs Attention": Average score >= 0.55 OR 2+ domains in High Concern OR any urgent trigger
OVERALL_THRESHOLDS = {
    "doing_well_max_score": 0.29,
    "moderate_max_score": 0.54,
    "high_concern_count_attention": 2
}

# ─────────────────────────────────────────────────────────────
# Safeguarding Configuration
# ─────────────────────────────────────────────────────────────

URGENT_KEYWORDS = [
    "hopeless",
    "hurt myself",
    "unsafe",
    "self harm",
    "self-harm",
    "end it",
    "suicide",
    "giving up",
    "want to disappear",
    "kill myself",
    "need help now",
    "threatened",
    "abused",
    "in danger",
    "cannot go on",
    "don't want to live",
    "dont want to live"
]

SAFEGUARDING_TEACHER_ALERT_MESSAGE = (
    "Speak with the student privately today, follow your school's safeguarding policy, "
    "and involve the designated safeguarding lead or school counsellor immediately."
)

DEFAULT_STUDENT_CALM_MESSAGE = (
    "Thank you for sharing with us. Your well-being matters to us deeply. "
    "If you are feeling overwhelmed, unsafe, or need support right now, please reach out to "
    "your mentor teacher or our school safeguarding team. You don't have to carry things alone."
)

DISCLAIMER_TEXT = (
    "This tool does not diagnose. It helps teachers notice when a student might need a caring conversation."
)

# ─────────────────────────────────────────────────────────────
# Personalized Guidance Templates
# ─────────────────────────────────────────────────────────────

GUIDANCE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "exam_stress": {
        "title": "Exam Calm & Focus Technique",
        "category": "Stress Management",
        "action": "Try the 4-7-8 breathing method before revision: inhale for 4 counts, hold for 7, and exhale gently for 8. Break revision into 25-minute Pomodoro sprints with 5-minute movement breaks."
    },
    "workload_pressure": {
        "title": "Priority Chunking Strategy",
        "category": "Time Management",
        "action": "List top 3 priorities for each day. Focus on completing one single task before looking at the rest. Ask your mentor teacher to help adjust deadlines if assignments overlap."
    },
    "sleep_difficulty": {
        "title": "Evening Wind-Down Routine",
        "category": "Daily Routine & Rest",
        "action": "Dim screens 45 minutes before bedtime. Keep your sleeping space cool and dark. Even an extra 30 minutes of rest significantly sharpens focus the next morning."
    },
    "screen_fatigue": {
        "title": "Digital Eye & Mind Reset",
        "category": "Daily Routine",
        "action": "Follow the 20-20-20 rule: every 20 minutes of screen use, look at something 20 feet away for 20 seconds. Take an evening walk without mobile devices to reset your mind."
    },
    "skipped_breakfast": {
        "title": "Morning Brain Fuel",
        "category": "Daily Routine & Energy",
        "action": "Your brain uses 20% of your body's energy. Even a light snack (fruit, nuts, toast, or milk) within an hour of waking stabilizes energy and attention through morning lessons."
    },
    "low_energy": {
        "title": "Gentle Energy Boosters",
        "category": "Physical Well-being",
        "action": "Drink a glass of cool water, stretch your shoulders, and step outside for 5 minutes of natural sunlight during recess. Physical hydration directly lifts afternoon fatigue."
    },
    "low_mood": {
        "title": "Self-Compassion & Gentle Step",
        "category": "Emotional Support",
        "action": "It is completely normal to have days when you feel low or drained. Be kind to yourself today: do one small thing that brings comfort, and talk to someone you trust."
    },
    "social_isolated": {
        "title": "Low-Pressure Peer Connection",
        "category": "Social & Belonging",
        "action": "You don't need a huge group to feel connected. Try sharing a quick smile or asking one classmate about their homework. Your mentor teacher is also available to help connect you with study buddies."
    },
    "lesson_pace_fast": {
        "title": "Active Clarification Strategy",
        "category": "Academic Strategy",
        "action": "Jot down the exact minute or topic where the explanation felt too fast. Ask your teacher during quiet work: 'Could you give one more example of this step?' Teachers appreciate curious questions!"
    },
    "math_difficulty": {
        "title": "Step-by-Step Math Foundation",
        "category": "Academic Support",
        "action": "In Mathematics, master one formula or example before trying five practice problems. Redo worked examples without looking at the solution to build procedural confidence."
    },
    "science_difficulty": {
        "title": "Visual Concept Mapping",
        "category": "Academic Support",
        "action": "Sketch science processes as flowcharts or labeled diagrams. Explaining a concept out loud in plain words is the most reliable way to cement understanding."
    },
    "language_difficulty": {
        "title": "Active Vocabulary & Reading",
        "category": "Academic Support",
        "action": "Read one short article or page per day and underline unfamiliar words. Discussing character motivations with a classmate sharpens analytical thinking."
    },
    "asking_questions": {
        "title": "Comfort with Classroom Questions",
        "category": "Classroom Confidence",
        "action": "If raising your hand in front of everyone feels daunting, write your question on a sticky note for the teacher at the end of class, or ask during individual practice time."
    },
    "general_thriving": {
        "title": "Sustained Balance & Curiosity",
        "category": "Growth & Enrichment",
        "action": "You are showing steady habits and balanced well-being! Keep protecting your rest schedule and consider mentoring a peer or exploring an extra-curricular project you enjoy."
    }
}

# ─────────────────────────────────────────────────────────────
# Optional LLM Hook
# ─────────────────────────────────────────────────────────────

LLM_GUIDANCE_ENABLED = False  # OFF by default. Strictly preserves student privacy when off.

def generate_llm_guidance_hook(domain_scores: Dict[str, float], tags: List[str]) -> Optional[List[Dict[str, str]]]:
    """
    Optional LLM provider hook. Disabled by default.
    NEVER sends student names, roll numbers, identifiers, or free-text notes.
    Only anonymized numerical domain scores and tags can be passed if enabled in the future.
    """
    if not LLM_GUIDANCE_ENABLED:
        return None
    # Stub for future secure plug-in
    return None

# ─────────────────────────────────────────────────────────────
# Scoring Logic Functions
# ─────────────────────────────────────────────────────────────

def calculate_domain_concern_level(avg_score: float) -> str:
    """Classifies a domain average (0.0 to 1.0) into Low, Medium, or High."""
    if avg_score <= DOMAIN_THRESHOLDS["low_max"]:
        return "Low"
    elif avg_score <= DOMAIN_THRESHOLDS["medium_max"]:
        return "Medium"
    else:
        return "High"

def evaluate_adaptive_checkin_scoring(
    domain_scores: Dict[str, float],
    answers: Dict[str, Any],
    urgent_flag: bool = False
) -> Dict[str, Any]:
    """
    Computes domain concern levels, overall indicator, reasons, and recommendations.
    Returns:
    {
        "wellbeing_indicator": "Doing Well" | "Moderate Concern" | "Needs Attention",
        "indicator_reasons": List[str],
        "domain_levels": Dict[str, str], # domain -> "Low" | "Medium" | "High"
        "overall_score": float, # 0.0 to 1.0
        "recommendations": List[Dict[str, str]],
        "urgent_flag": bool
    }
    """
    if not domain_scores:
        return {
            "wellbeing_indicator": "Doing Well",
            "indicator_reasons": ["No domain concerns recorded"],
            "domain_levels": {},
            "overall_score": 0.0,
            "recommendations": [GUIDANCE_TEMPLATES["general_thriving"]],
            "urgent_flag": urgent_flag
        }

    domain_levels: Dict[str, str] = {}
    high_domains: List[str] = []
    medium_domains: List[str] = []

    for dom, score in domain_scores.items():
        lvl = calculate_domain_concern_level(score)
        domain_levels[dom] = lvl
        if lvl == "High":
            high_domains.append(dom)
        elif lvl == "Medium":
            medium_domains.append(dom)

    overall_avg = round(sum(domain_scores.values()) / max(len(domain_scores), 1), 2)
    reasons: List[str] = []

    # Indicator determination
    if urgent_flag:
        indicator = "Needs Attention"
        reasons.append("Urgent safeguarding trigger flagged")
    elif len(high_domains) >= OVERALL_THRESHOLDS["high_concern_count_attention"] or overall_avg >= OVERALL_THRESHOLDS["moderate_max_score"]:
        indicator = "Needs Attention"
        if len(high_domains) >= OVERALL_THRESHOLDS["high_concern_count_attention"]:
            reasons.append(f"Elevated concern across {len(high_domains)} domains: {', '.join(high_domains)}")
        else:
            reasons.append(f"Overall concern index {overall_avg:.2f}/1.0 is elevated")
    elif len(high_domains) == 1 or overall_avg >= OVERALL_THRESHOLDS["doing_well_max_score"]:
        indicator = "Moderate Concern"
        if len(high_domains) == 1:
            reasons.append(f"Specific concern flagged in {high_domains[0]}")
        if medium_domains:
            reasons.append(f"Moderate indicators in: {', '.join(medium_domains[:2])}")
        if not reasons:
            reasons.append(f"Moderate overall concern index {overall_avg:.2f}/1.0")
    else:
        indicator = "Doing Well"
        reasons.append(f"Balanced indicators across all {len(domain_scores)} domains (average index {overall_avg:.2f})")

    # Generate personalized recommendations
    all_tags = set()
    for ans_data in answers.values():
        if isinstance(ans_data, dict):
            tags = ans_data.get("tags") or []
            all_tags.update(tags)

    recommendations: List[Dict[str, str]] = []
    for tag in all_tags:
        if tag in GUIDANCE_TEMPLATES:
            tpl = GUIDANCE_TEMPLATES[tag]
            if tpl not in recommendations:
                recommendations.append(tpl)

    # Subject specific recommendations if academic difficulties flagged
    for q_id, ans in answers.items():
        if isinstance(ans, dict) and "subject" in ans:
            subj = str(ans["subject"]).lower()
            if "math" in subj and GUIDANCE_TEMPLATES["math_difficulty"] not in recommendations:
                recommendations.append(GUIDANCE_TEMPLATES["math_difficulty"])
            elif "science" in subj and GUIDANCE_TEMPLATES["science_difficulty"] not in recommendations:
                recommendations.append(GUIDANCE_TEMPLATES["science_difficulty"])
            elif any(s in subj for s in ["english", "hindi", "language"]) and GUIDANCE_TEMPLATES["language_difficulty"] not in recommendations:
                recommendations.append(GUIDANCE_TEMPLATES["language_difficulty"])

    if not recommendations:
        if indicator == "Doing Well":
            recommendations.append(GUIDANCE_TEMPLATES["general_thriving"])
        else:
            recommendations.append(GUIDANCE_TEMPLATES["low_mood"])
            recommendations.append(GUIDANCE_TEMPLATES["workload_pressure"])

    return {
        "wellbeing_indicator": indicator,
        "indicator_reasons": reasons,
        "domain_levels": domain_levels,
        "overall_score": overall_avg,
        "recommendations": recommendations,
        "urgent_flag": urgent_flag
    }

def check_text_for_safeguarding(text: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Checks free text for safety keywords with word boundary matching."""
    if not text:
        return False, None
    lower_text = text.lower()
    for kw in URGENT_KEYWORDS:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, lower_text):
            return True, kw
    return False, None
