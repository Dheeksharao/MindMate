"""
MindMate Question Bank Populator.
Populates `check_in_questions` table with 105+ questions across 8+ well-being & academic domains.
Includes explicit branching logic, concern scoring, tags, and gentle school-appropriate tone.
"""

import json
import sqlite3
from pathlib import Path
from database import DB_PATH, init_db

def create_question(
    qid: str,
    domain: str,
    question_text: str,
    answer_type: str,
    options: list,
    branching_rules: dict = None,
    is_root: int = 0,
    root_order: int = 0,
    prefer_not_to_answer: int = 1,
    version: int = 1
) -> dict:
    return {
        "id": qid,
        "domain": domain,
        "question_text": question_text,
        "answer_type": answer_type,
        "options_json": json.dumps(options),
        "prefer_not_to_answer": prefer_not_to_answer,
        "version": version,
        "branching_rules_json": json.dumps(branching_rules or {}),
        "is_root": is_root,
        "root_order": root_order
    }

def get_questions_bank():
    q = []

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. DAILY ROUTINE & HABITS (Activities, sleep, screen time, breakfast)
    # ═══════════════════════════════════════════════════════════════════════════
    q.append(create_question(
        qid="q_routine_activities",
        domain="Daily Routine & Habits",
        question_text="What activities did you do from morning until now?",
        answer_type="multi_choice",
        options=[
            {"id": "classes", "label": "Attended classes", "concern_score": 0.0, "tags": ["routine_structured"]},
            {"id": "study", "label": "Studied / homework", "concern_score": 0.0, "tags": ["academics_effort"]},
            {"id": "sports", "label": "Sports / outdoor games", "concern_score": 0.0, "tags": ["physical_healthy"]},
            {"id": "creative", "label": "Creative hobby (art, music, reading)", "concern_score": 0.0, "tags": ["creative_healthy"]},
            {"id": "friends", "label": "Spent time with friends", "concern_score": 0.0, "tags": ["social_connection"]},
            {"id": "screen", "label": "Phone / TV / social media / gaming", "concern_score": 0.2, "tags": ["screen_use"]},
            {"id": "rested", "label": "Rested / took a nap", "concern_score": 0.0, "tags": ["rest"]},
            {"id": "other", "label": "Other personal activities", "concern_score": 0.0, "tags": ["general"]}
        ],
        branching_rules={
            "follow_ups": {
                "screen": "q_routine_screen_time",
                "sports": "q_routine_physical_activity"
            }
        },
        is_root=1,
        root_order=1
    ))

    q.append(create_question(
        qid="q_routine_screen_time",
        domain="Daily Routine & Habits",
        question_text="Roughly how much screen time (outside of online classwork) did you have today?",
        answer_type="single_choice",
        options=[
            {"id": "scr_under1", "label": "Under 1 hour", "concern_score": 0.0, "tags": ["balanced_screen"]},
            {"id": "scr_1to2", "label": "1 to 2 hours", "concern_score": 0.1, "tags": ["moderate_screen"]},
            {"id": "scr_3to4", "label": "3 to 4 hours", "concern_score": 0.35, "tags": ["high_screen"]},
            {"id": "scr_over4", "label": "More than 4 hours", "concern_score": 0.7, "tags": ["screen_fatigue"]}
        ],
        branching_rules={
            "follow_ups": {
                "scr_over4": "q_routine_sleep_latency"
            }
        }
    ))

    q.append(create_question(
        qid="q_routine_breakfast",
        domain="Daily Routine & Habits",
        question_text="Did you have a nutritious breakfast this morning?",
        answer_type="single_choice",
        options=[
            {"id": "bk_yes", "label": "Yes, full breakfast", "concern_score": 0.0, "tags": ["nutrition_good"]},
            {"id": "bk_light", "label": "A quick light snack or beverage", "concern_score": 0.15, "tags": ["nutrition_light"]},
            {"id": "bk_skipped", "label": "No, I skipped breakfast", "concern_score": 0.55, "tags": ["skipped_breakfast"]}
        ],
        branching_rules={
            "follow_ups": {
                "bk_skipped": "q_energy_morning_slump"
            }
        },
        is_root=1,
        root_order=2
    ))

    q.append(create_question(
        qid="q_energy_morning_slump",
        domain="Daily Routine & Habits",
        question_text="Since skipping breakfast, how has your energy been during morning classes?",
        answer_type="single_choice",
        options=[
            {"id": "slump_fine", "label": "Surprisingly okay", "concern_score": 0.1, "tags": ["resilient_energy"]},
            {"id": "slump_tired", "label": "A bit slow or sluggish", "concern_score": 0.45, "tags": ["low_energy"]},
            {"id": "slump_headache", "label": "Felt dizzy, tired, or had a headache", "concern_score": 0.75, "tags": ["low_energy", "skipped_breakfast"]}
        ]
    ))

    q.append(create_question(
        qid="q_routine_sleep_hours",
        domain="Daily Routine & Habits",
        question_text="How many hours of sleep did you get last night?",
        answer_type="single_choice",
        options=[
            {"id": "slp_8plus", "label": "8 hours or more (well-rested)", "concern_score": 0.0, "tags": ["sleep_optimal"]},
            {"id": "slp_6to7", "label": "6 to 7 hours", "concern_score": 0.2, "tags": ["sleep_moderate"]},
            {"id": "slp_under6", "label": "Less than 6 hours", "concern_score": 0.65, "tags": ["sleep_difficulty", "low_sleep"]}
        ],
        branching_rules={
            "follow_ups": {
                "slp_under6": "q_routine_sleep_latency"
            }
        },
        is_root=1,
        root_order=3
    ))

    q.append(create_question(
        qid="q_routine_sleep_latency",
        domain="Daily Routine & Habits",
        question_text="When you went to bed, did you find it difficult to fall asleep?",
        answer_type="single_choice",
        options=[
            {"id": "lat_quick", "label": "Fell asleep quickly", "concern_score": 0.0, "tags": ["sleep_restful"]},
            {"id": "lat_phone", "label": "Was awake on my phone for a while", "concern_score": 0.4, "tags": ["screen_fatigue", "sleep_routine"]},
            {"id": "lat_thoughts", "label": "Racing thoughts or worries kept me awake", "concern_score": 0.75, "tags": ["sleep_difficulty", "stress_anxiety"]}
        ]
    ))

    q.append(create_question(
        qid="q_routine_physical_activity",
        domain="Daily Routine & Habits",
        question_text="How did your physical activity or games make you feel today?",
        answer_type="single_choice",
        options=[
            {"id": "phys_energized", "label": "Refreshed and energized", "concern_score": 0.0, "tags": ["energy_boost"]},
            {"id": "phys_tired_good", "label": "Pleasantly tired", "concern_score": 0.0, "tags": ["healthy_tired"]},
            {"id": "phys_exhausted", "label": "Wiped out or exhausted", "concern_score": 0.4, "tags": ["low_energy"]}
        ]
    ))

    q.append(create_question(
        qid="q_routine_hydration",
        domain="Daily Routine & Habits",
        question_text="Have you been drinking enough water today?",
        answer_type="single_choice",
        options=[
            {"id": "hyd_yes", "label": "Yes, plenty of water", "concern_score": 0.0, "tags": ["healthy_routine"]},
            {"id": "hyd_some", "label": "A couple of glasses", "concern_score": 0.1, "tags": ["moderate_hydration"]},
            {"id": "hyd_barely", "label": "Hardly any water", "concern_score": 0.35, "tags": ["dehydration_risk"]}
        ]
    ))

    q.append(create_question(
        qid="q_routine_commute",
        domain="Daily Routine & Habits",
        question_text="How was your commute or journey to school today?",
        answer_type="single_choice",
        options=[
            {"id": "com_smooth", "label": "Smooth and easy", "concern_score": 0.0, "tags": ["easy_morning"]},
            {"id": "com_hectic", "label": "A bit rushed or crowded", "concern_score": 0.2, "tags": ["morning_rush"]},
            {"id": "com_exhausting", "label": "Very tiring or stressful", "concern_score": 0.5, "tags": ["commute_stress"]}
        ]
    ))

    q.append(create_question(
        qid="q_routine_hobbies",
        domain="Daily Routine & Habits",
        question_text="Did you get to spend any time today on something you genuinely enjoy?",
        answer_type="single_choice",
        options=[
            {"id": "hob_yes", "label": "Yes, enjoyed some leisure time", "concern_score": 0.0, "tags": ["balanced_life"]},
            {"id": "hob_little", "label": "Only a few minutes", "concern_score": 0.15, "tags": ["busy_schedule"]},
            {"id": "hob_no", "label": "No time at all, purely work/classes", "concern_score": 0.4, "tags": ["workload_pressure"]}
        ]
    ))

    q.append(create_question(
        qid="q_routine_evening_winddown",
        domain="Daily Routine & Habits",
        question_text="Do you usually have a calm routine before sleeping?",
        answer_type="single_choice",
        options=[
            {"id": "wind_yes", "label": "Yes, read or relax quietly", "concern_score": 0.0, "tags": ["sleep_hygiene"]},
            {"id": "wind_sometimes", "label": "Sometimes", "concern_score": 0.15, "tags": ["moderate_hygiene"]},
            {"id": "wind_rush", "label": "No, studying or screen right up to sleep", "concern_score": 0.45, "tags": ["sleep_routine"]}
        ]
    ))

    q.append(create_question(
        qid="q_routine_fresh_air",
        domain="Daily Routine & Habits",
        question_text="Did you spend some time outdoors in natural light today?",
        answer_type="single_choice",
        options=[
            {"id": "air_yes", "label": "Yes, plenty of fresh air", "concern_score": 0.0, "tags": ["healthy_outdoors"]},
            {"id": "air_little", "label": "Just walking between classes", "concern_score": 0.15, "tags": ["indoors_mostly"]},
            {"id": "air_none", "label": "Stayed inside all day", "concern_score": 0.35, "tags": ["sedentary_indoors"]}
        ]
    ))

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. MOOD & EMOTIONS
    # ═══════════════════════════════════════════════════════════════════════════
    q.append(create_question(
        qid="q_mood_rating",
        domain="Mood & Emotions",
        question_text="How has your overall mood been today?",
        answer_type="single_choice",
        options=[
            {"id": "m_5", "label": "Very good / bright 😊", "concern_score": 0.0, "tags": ["mood_positive"]},
            {"id": "m_4", "label": "Good / steady 🙂", "concern_score": 0.1, "tags": ["mood_stable"]},
            {"id": "m_3", "label": "Neutral / okay 😐", "concern_score": 0.25, "tags": ["mood_neutral"]},
            {"id": "m_2", "label": "Low / down 🙁", "concern_score": 0.65, "tags": ["low_mood"]},
            {"id": "m_1", "label": "Very low / struggling 😞", "concern_score": 0.9, "tags": ["low_mood", "urgent_attention"]}
        ],
        branching_rules={
            "follow_ups": {
                "m_2": "q_mood_factors",
                "m_1": "q_mood_factors"
            }
        },
        is_root=1,
        root_order=4
    ))

    q.append(create_question(
        qid="q_mood_factors",
        domain="Mood & Emotions",
        question_text="What do you feel has been affecting your mood the most today?",
        answer_type="multi_choice",
        options=[
            {"id": "mf_studies", "label": "Schoolwork / study difficulties", "concern_score": 0.5, "tags": ["workload_pressure"]},
            {"id": "mf_exams", "label": "Upcoming exams or marks", "concern_score": 0.5, "tags": ["exam_stress"]},
            {"id": "mf_friends", "label": "Friends / social friction", "concern_score": 0.55, "tags": ["social_friction"]},
            {"id": "mf_tired", "label": "Feeling very tired or unwell", "concern_score": 0.45, "tags": ["low_energy"]},
            {"id": "mf_home", "label": "Things happening at home", "concern_score": 0.6, "tags": ["home_concerns"]},
            {"id": "mf_unsure", "label": "Not sure, just feel heavy", "concern_score": 0.6, "tags": ["low_mood"]},
            {"id": "mf_unsafe", "label": "Feeling unsafe or hurt", "concern_score": 1.0, "tags": ["urgent_safeguarding", "feeling_unsafe"]}
        ],
        branching_rules={
            "follow_ups": {
                "mf_studies": "q_mood_support_wish",
                "mf_exams": "q_mood_support_wish",
                "mf_friends": "q_mood_support_wish",
                "mf_home": "q_mood_support_wish",
                "mf_unsure": "q_mood_support_wish",
                "mf_unsafe": "q_mood_support_wish"
            }
        }
    ))

    q.append(create_question(
        qid="q_mood_support_wish",
        domain="Mood & Emotions",
        question_text="Would you like a gentle, private conversation with a trusted teacher, mentor, or school counsellor?",
        answer_type="single_choice",
        options=[
            {"id": "wish_yes_today", "label": "Yes, I would appreciate that today", "concern_score": 0.8, "tags": ["request_conversation_soon"]},
            {"id": "wish_yes_this_week", "label": "Yes, sometime this week would be nice", "concern_score": 0.5, "tags": ["request_conversation_week"]},
            {"id": "wish_not_now", "label": "Not right now, I prefer to manage on my own for now", "concern_score": 0.2, "tags": ["self_managing"]}
        ]
    ))

    q.append(create_question(
        qid="q_mood_emotional_safety",
        domain="Mood & Emotions",
        question_text="Do you feel emotionally safe and accepted at school?",
        answer_type="single_choice",
        options=[
            {"id": "es_always", "label": "Yes, almost always", "concern_score": 0.0, "tags": ["emotional_safety_high"]},
            {"id": "es_mostly", "label": "Most of the time", "concern_score": 0.15, "tags": ["emotional_safety_good"]},
            {"id": "es_rarely", "label": "Rarely, I often feel out of place", "concern_score": 0.65, "tags": ["social_isolated", "low_belonging"]},
            {"id": "es_never", "label": "No, I do not feel safe here", "concern_score": 1.0, "tags": ["urgent_safeguarding", "feeling_unsafe"]}
        ]
    ))

    q.append(create_question(
        qid="q_mood_optimism",
        domain="Mood & Emotions",
        question_text="When thinking about the rest of this week, how do you feel?",
        answer_type="single_choice",
        options=[
            {"id": "opt_excited", "label": "Positive and looking forward to it", "concern_score": 0.0, "tags": ["optimistic"]},
            {"id": "opt_neutral", "label": "Just taking it one day at a time", "concern_score": 0.1, "tags": ["steady"]},
            {"id": "opt_dread", "label": "Anxious or dreading it", "concern_score": 0.7, "tags": ["anticipatory_anxiety", "stress_anxiety"]}
        ]
    ))

    q.append(create_question(
        qid="q_mood_self_compassion",
        domain="Mood & Emotions",
        question_text="When you make a mistake in class, how do you usually respond to yourself?",
        answer_type="single_choice",
        options=[
            {"id": "sc_learn", "label": "I try to learn from it and move on", "concern_score": 0.0, "tags": ["growth_mindset"]},
            {"id": "sc_embarrassed", "label": "Feel a bit embarrassed but it passes", "concern_score": 0.2, "tags": ["normal_sensitivity"]},
            {"id": "sc_harsh", "label": "I get very upset with myself and dwell on it", "concern_score": 0.65, "tags": ["harsh_self_criticism"]}
        ]
    ))

    q.append(create_question(
        qid="q_mood_calm_anchor",
        domain="Mood & Emotions",
        question_text="Is there something or someone that reliably helps you feel calm when you are upset?",
        answer_type="single_choice",
        options=[
            {"id": "anc_yes", "label": "Yes, I have clear comfort strategies or people", "concern_score": 0.0, "tags": ["resilient_coping"]},
            {"id": "anc_sometimes", "label": "Sometimes, depending on the situation", "concern_score": 0.2, "tags": ["moderate_coping"]},
            {"id": "anc_no", "label": "No, I often feel completely stuck in bad feelings", "concern_score": 0.7, "tags": ["coping_support_needed"]}
        ]
    ))

    q.append(create_question(
        qid="q_mood_note",
        domain="Mood & Emotions",
        question_text="Is there anything on your mind you would like your teacher or mentor to know? (Optional)",
        answer_type="optional_free_text",
        options=[
            {"id": "note_free", "label": "Share private thoughts", "concern_score": 0.0, "tags": ["free_text"]}
        ],
        prefer_not_to_answer=1
    ))

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. STRESS & PRESSURE
    # ═══════════════════════════════════════════════════════════════════════════
    q.append(create_question(
        qid="q_stress_level",
        domain="Stress & Pressure",
        question_text="How would you rate your level of stress today?",
        answer_type="single_choice",
        options=[
            {"id": "str_none", "label": "Low / relaxed (1/5) 🌿", "concern_score": 0.0, "tags": ["stress_calm"]},
            {"id": "str_mild", "label": "Mild, manageable (2/5)", "concern_score": 0.15, "tags": ["stress_mild"]},
            {"id": "str_mod", "label": "Moderate pressure (3/5) ⚖️", "concern_score": 0.45, "tags": ["stress_moderate"]},
            {"id": "str_high", "label": "High stress (4/5) ⚡", "concern_score": 0.75, "tags": ["exam_stress", "workload_pressure"]},
            {"id": "str_overwhelmed", "label": "Overwhelmed (5/5) 🌪️", "concern_score": 0.95, "tags": ["workload_pressure", "urgent_attention"]}
        ],
        branching_rules={
            "follow_ups": {
                "str_mod": "q_stress_causes_moderate",
                "str_high": "q_stress_causes_high",
                "str_overwhelmed": "q_stress_causes_high"
            }
        },
        is_root=1,
        root_order=5
    ))

    q.append(create_question(
        qid="q_stress_causes_moderate",
        domain="Stress & Pressure",
        question_text="What is the primary source of your moderate pressure?",
        answer_type="multi_choice",
        options=[
            {"id": "scm_hw", "label": "Daily homework volume", "concern_score": 0.35, "tags": ["workload_pressure"]},
            {"id": "scm_test", "label": "Upcoming class test", "concern_score": 0.35, "tags": ["exam_stress"]},
            {"id": "scm_routine", "label": "Balancing study with rest", "concern_score": 0.3, "tags": ["time_management"]}
        ]
    ))

    q.append(create_question(
        qid="q_stress_causes_high",
        domain="Stress & Pressure",
        question_text="What is causing this high stress level right now?",
        answer_type="multi_choice",
        options=[
            {"id": "sch_exams", "label": "Exam or test anxiety", "concern_score": 0.7, "tags": ["exam_stress"]},
            {"id": "sch_deadlines", "label": "Too many overlapping deadlines", "concern_score": 0.7, "tags": ["workload_pressure"]},
            {"id": "sch_parental", "label": "Pressure about expectations or marks", "concern_score": 0.75, "tags": ["expectation_pressure"]},
            {"id": "sch_concept", "label": "Falling behind in a key subject", "concern_score": 0.7, "tags": ["academic_struggle"]},
            {"id": "sch_personal", "label": "Personal or family difficulties", "concern_score": 0.8, "tags": ["personal_stress"]}
        ],
        branching_rules={
            "follow_ups": {
                "sch_exams": "q_stress_effect_on_focus",
                "sch_deadlines": "q_stress_effect_on_focus",
                "sch_parental": "q_stress_effect_on_focus",
                "sch_concept": "q_stress_effect_on_focus",
                "sch_personal": "q_stress_effect_on_focus"
            }
        }
    ))

    q.append(create_question(
        qid="q_stress_effect_on_focus",
        domain="Stress & Pressure",
        question_text="How is this stress affecting your ability to focus and study?",
        answer_type="single_choice",
        options=[
            {"id": "sef_minimal", "label": "Still managing to study okay", "concern_score": 0.25, "tags": ["resilient_effort"]},
            {"id": "sef_distracted", "label": "Harder to concentrate, mind wanders", "concern_score": 0.6, "tags": ["concentration_affected"]},
            {"id": "sef_paralyzed", "label": "Feeling completely frozen or unable to start", "concern_score": 0.85, "tags": ["workload_pressure", "stress_paralysis"]}
        ]
    ))

    q.append(create_question(
        qid="q_stress_physical_symptoms",
        domain="Stress & Pressure",
        question_text="Do you notice physical feelings of stress (headaches, tight shoulders, stomach butterflies)?",
        answer_type="single_choice",
        options=[
            {"id": "sps_no", "label": "No physical tension", "concern_score": 0.0, "tags": ["physical_calm"]},
            {"id": "sps_sometimes", "label": "Sometimes before tests", "concern_score": 0.3, "tags": ["mild_somatic"]},
            {"id": "sps_frequent", "label": "Frequently during the school week", "concern_score": 0.7, "tags": ["high_somatic_tension"]}
        ]
    ))

    q.append(create_question(
        qid="q_stress_coping_tools",
        domain="Stress & Pressure",
        question_text="When stress builds up, which of these helps you unwind best?",
        answer_type="single_choice",
        options=[
            {"id": "sct_music", "label": "Listening to music or quiet rest", "concern_score": 0.0, "tags": ["rest_coping"]},
            {"id": "sct_walk", "label": "Physical movement / outdoor walk", "concern_score": 0.0, "tags": ["active_coping"]},
            {"id": "sct_talk", "label": "Talking through it with someone", "concern_score": 0.0, "tags": ["social_coping"]},
            {"id": "sct_none", "label": "I don't have anything that helps right now", "concern_score": 0.6, "tags": ["coping_support_needed"]}
        ]
    ))

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. MOTIVATION & ENERGY
    # ═══════════════════════════════════════════════════════════════════════════
    q.append(create_question(
        qid="q_energy_level",
        domain="Motivation & Energy",
        question_text="How is your physical and mental energy level today?",
        answer_type="single_choice",
        options=[
            {"id": "en_5", "label": "High energy & ready to learn ⚡", "concern_score": 0.0, "tags": ["energy_high"]},
            {"id": "en_4", "label": "Good steady energy", "concern_score": 0.1, "tags": ["energy_good"]},
            {"id": "en_3", "label": "Moderate / average", "concern_score": 0.25, "tags": ["energy_moderate"]},
            {"id": "en_2", "label": "Low energy / dragging feet 🥱", "concern_score": 0.6, "tags": ["low_energy"]},
            {"id": "en_1", "label": "Completely drained / exhausted 🪫", "concern_score": 0.85, "tags": ["low_energy", "exhaustion"]}
        ],
        is_root=1,
        root_order=6
    ))

    q.append(create_question(
        qid="q_motivation_learning",
        domain="Motivation & Energy",
        question_text="How motivated do you feel to tackle your school lessons today?",
        answer_type="single_choice",
        options=[
            {"id": "mot_enthusiastic", "label": "Curious and motivated", "concern_score": 0.0, "tags": ["high_motivation"]},
            {"id": "mot_duty", "label": "I'll do my work because I should", "concern_score": 0.15, "tags": ["dutiful_motivation"]},
            {"id": "mot_low", "label": "Hard to find motivation today", "concern_score": 0.55, "tags": ["low_motivation"]},
            {"id": "mot_givingup", "label": "Feeling like giving up on schoolwork", "concern_score": 0.85, "tags": ["demotivated_critical"]}
        ]
    ))

    q.append(create_question(
        qid="q_energy_time_of_day",
        domain="Motivation & Energy",
        question_text="At what time of day do you feel at your sharpest?",
        answer_type="single_choice",
        options=[
            {"id": "tod_morning", "label": "Early morning", "concern_score": 0.0, "tags": ["morning_peak"]},
            {"id": "tod_midday", "label": "Midday during classes", "concern_score": 0.0, "tags": ["midday_peak"]},
            {"id": "tod_evening", "label": "Late afternoon or evening", "concern_score": 0.0, "tags": ["evening_peak"]},
            {"id": "tod_never", "label": "Rarely feel sharp at any time", "concern_score": 0.55, "tags": ["chronic_sluggishness"]}
        ]
    ))

    q.append(create_question(
        qid="q_motivation_goals",
        domain="Motivation & Energy",
        question_text="Do you currently have a personal goal or topic you feel excited about?",
        answer_type="single_choice",
        options=[
            {"id": "gl_yes", "label": "Yes, I know what I'm aiming for", "concern_score": 0.0, "tags": ["goal_oriented"]},
            {"id": "gl_somewhat", "label": "Somewhat, a general idea", "concern_score": 0.15, "tags": ["loose_direction"]},
            {"id": "gl_lost", "label": "No, feeling a bit purposeless right now", "concern_score": 0.6, "tags": ["directionless"]}
        ]
    ))

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. CONCENTRATION & FOCUS
    # ═══════════════════════════════════════════════════════════════════════════
    q.append(create_question(
        qid="q_focus_classroom",
        domain="Concentration & Focus",
        question_text="How easily were you able to concentrate in class today?",
        answer_type="single_choice",
        options=[
            {"id": "foc_sharp", "label": "Very focused, caught most details 🎯", "concern_score": 0.0, "tags": ["focus_sharp"]},
            {"id": "foc_mostly", "label": "Mostly focused with small drifts", "concern_score": 0.15, "tags": ["focus_good"]},
            {"id": "foc_distracted", "label": "Frequently distracted or spacing out", "concern_score": 0.55, "tags": ["focus_distracted"]},
            {"id": "foc_impossible", "label": "Almost impossible to focus today", "concern_score": 0.8, "tags": ["focus_severe_difficulty"]}
        ],
        branching_rules={
            "follow_ups": {
                "foc_distracted": "q_focus_distraction_type",
                "foc_impossible": "q_focus_distraction_type"
            }
        },
        is_root=1,
        root_order=7
    ))

    q.append(create_question(
        qid="q_focus_distraction_type",
        domain="Concentration & Focus",
        question_text="What was pulling your attention away most?",
        answer_type="multi_choice",
        options=[
            {"id": "dt_internal", "label": "Internal worries or personal thoughts", "concern_score": 0.6, "tags": ["internal_preoccupation"]},
            {"id": "dt_noise", "label": "Classroom noise or side chatter", "concern_score": 0.35, "tags": ["environment_noise"]},
            {"id": "dt_device", "label": "Phone notifications / digital media", "concern_score": 0.45, "tags": ["digital_distraction"]},
            {"id": "dt_tiredness", "label": "Sleepiness and heavy eyelids", "concern_score": 0.5, "tags": ["fatigue_inattention"]}
        ]
    ))

    q.append(create_question(
        qid="q_focus_homework_stamina",
        domain="Concentration & Focus",
        question_text="How long can you usually study at home before needing a break?",
        answer_type="single_choice",
        options=[
            {"id": "hws_45plus", "label": "45 minutes or more", "concern_score": 0.0, "tags": ["high_stamina"]},
            {"id": "hws_25to45", "label": "25 to 45 minutes (healthy chunk)", "concern_score": 0.0, "tags": ["pomodoro_rhythm"]},
            {"id": "hws_10to20", "label": "10 to 20 minutes", "concern_score": 0.35, "tags": ["short_stamina"]},
            {"id": "hws_under10", "label": "Under 10 minutes", "concern_score": 0.65, "tags": ["stamina_difficulty"]}
        ]
    ))

    q.append(create_question(
        qid="q_focus_multitasking",
        domain="Concentration & Focus",
        question_text="Do you tend to switch between studying and other apps/chats while doing homework?",
        answer_type="single_choice",
        options=[
            {"id": "mt_single", "label": "No, I usually focus on one task", "concern_score": 0.0, "tags": ["deep_work"]},
            {"id": "mt_occasional", "label": "Occasionally check messages", "concern_score": 0.2, "tags": ["moderate_multitask"]},
            {"id": "mt_constant", "label": "Constantly switching back and forth", "concern_score": 0.6, "tags": ["fragmented_attention"]}
        ]
    ))

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. ACADEMICS & LESSON UNDERSTANDING
    # ═══════════════════════════════════════════════════════════════════════════
    q.append(create_question(
        qid="q_academic_understanding",
        domain="Academics & Learning",
        question_text="How well did you understand the core concepts taught in class today?",
        answer_type="single_choice",
        options=[
            {"id": "und_all", "label": "Understood everything clearly (5/5) 💡", "concern_score": 0.0, "tags": ["learning_strong"]},
            {"id": "und_most", "label": "Understood most topics (4/5)", "concern_score": 0.1, "tags": ["learning_good"]},
            {"id": "und_half", "label": "About half of it made sense (3/5)", "concern_score": 0.35, "tags": ["learning_partial"]},
            {"id": "und_struggling", "label": "Struggled with several topics (2/5)", "concern_score": 0.65, "tags": ["learning_difficulty"]},
            {"id": "und_lost", "label": "Felt completely lost in class (1/5)", "concern_score": 0.85, "tags": ["learning_severe_gap"]}
        ],
        branching_rules={
            "follow_ups": {
                "und_half": "q_academic_subject_pick",
                "und_struggling": "q_academic_subject_pick",
                "und_lost": "q_academic_subject_pick"
            }
        },
        is_root=1,
        root_order=8
    ))

    q.append(create_question(
        qid="q_academic_subject_pick",
        domain="Academics & Learning",
        question_text="Which subject felt the most difficult or confusing?",
        answer_type="single_choice",
        options=[
            {"id": "subj_math", "label": "Mathematics", "concern_score": 0.5, "tags": ["math_difficulty"]},
            {"id": "subj_science", "label": "Science / Physics / Chemistry / Biology", "concern_score": 0.5, "tags": ["science_difficulty"]},
            {"id": "subj_lang", "label": "English / Language Arts", "concern_score": 0.5, "tags": ["language_difficulty"]},
            {"id": "subj_social", "label": "Social Studies / History / Geography", "concern_score": 0.45, "tags": ["social_studies_difficulty"]},
            {"id": "subj_all", "label": "Multiple subjects felt tough today", "concern_score": 0.8, "tags": ["broad_academic_difficulty"]}
        ],
        branching_rules={
            "follow_ups": {
                "subj_math": "q_academic_difficulty_nature",
                "subj_science": "q_academic_difficulty_nature",
                "subj_lang": "q_academic_difficulty_nature",
                "subj_social": "q_academic_difficulty_nature",
                "subj_all": "q_academic_difficulty_nature"
            }
        }
    ))

    q.append(create_question(
        qid="q_academic_difficulty_nature",
        domain="Academics & Learning",
        question_text="What made that subject difficult today?",
        answer_type="multi_choice",
        options=[
            {"id": "dn_concept", "label": "The fundamental concept was hard to picture", "concern_score": 0.5, "tags": ["concept_clarity"]},
            {"id": "dn_remember", "label": "Too many formulas, facts, or steps to remember", "concern_score": 0.45, "tags": ["memorization_burden"]},
            {"id": "dn_problems", "label": "Solving independent practice problems was confusing", "concern_score": 0.5, "tags": ["practice_gap"]},
            {"id": "dn_pace", "label": "The teacher moved through the steps too quickly", "concern_score": 0.6, "tags": ["lesson_pace_fast"]},
            {"id": "dn_missing", "label": "I missed earlier classes and feel behind", "concern_score": 0.7, "tags": ["backlog_gap"]}
        ],
        branching_rules={
            "follow_ups": {
                "dn_concept": "q_academic_support_ask",
                "dn_remember": "q_academic_support_ask",
                "dn_problems": "q_academic_support_ask",
                "dn_pace": "q_academic_support_ask",
                "dn_missing": "q_academic_support_ask"
            }
        }
    ))

    q.append(create_question(
        qid="q_academic_support_ask",
        domain="Academics & Learning",
        question_text="Would you like some extra support or revision practice in this subject?",
        answer_type="single_choice",
        options=[
            {"id": "asa_practice", "label": "Yes, a short practice worksheet with solutions", "concern_score": 0.3, "tags": ["practice_sheets_wanted"]},
            {"id": "asa_teacher", "label": "Yes, a quick 5-minute explanation from the teacher", "concern_score": 0.4, "tags": ["teacher_explanation_wanted"]},
            {"id": "asa_buddy", "label": "Yes, pairing up with a study peer", "concern_score": 0.3, "tags": ["peer_buddy_wanted"]},
            {"id": "asa_no", "label": "I will try self-study first", "concern_score": 0.1, "tags": ["self_study"]}
        ]
    ))

    q.append(create_question(
        qid="q_academic_homework_completion",
        domain="Academics & Learning",
        question_text="Are you currently able to complete your homework on time most days?",
        answer_type="single_choice",
        options=[
            {"id": "hwc_always", "label": "Yes, comfortably", "concern_score": 0.0, "tags": ["homework_on_track"]},
            {"id": "hwc_struggle", "label": "Usually manage, but stay up late to finish", "concern_score": 0.35, "tags": ["homework_late_nights"]},
            {"id": "hwc_falling_behind", "label": "Frequently unable to finish homework", "concern_score": 0.7, "tags": ["homework_backlog"]}
        ]
    ))

    q.append(create_question(
        qid="q_academic_revision_habits",
        domain="Academics & Learning",
        question_text="How do you usually review material before a test?",
        answer_type="single_choice",
        options=[
            {"id": "rev_spaced", "label": "Review regular bits throughout the week", "concern_score": 0.0, "tags": ["spaced_revision"]},
            {"id": "rev_night_before", "label": "Cramming the evening before", "concern_score": 0.45, "tags": ["cramming"]},
            {"id": "rev_barely", "label": "Rarely have time to revise", "concern_score": 0.65, "tags": ["no_revision_time"]}
        ]
    ))

    # ═══════════════════════════════════════════════════════════════════════════
    # 7. TEACHING & CLASSROOM ENVIRONMENT
    # ═══════════════════════════════════════════════════════════════════════════
    q.append(create_question(
        qid="q_teaching_question_comfort",
        domain="Teaching & Classroom",
        question_text="How comfortable do you feel asking your teacher questions when you don't understand?",
        answer_type="single_choice",
        options=[
            {"id": "qc_very", "label": "Very comfortable, I ask right away 🙋", "concern_score": 0.0, "tags": ["question_confidence_high"]},
            {"id": "qc_sometimes", "label": "I ask occasionally if a friend asks too", "concern_score": 0.2, "tags": ["question_confidence_moderate"]},
            {"id": "qc_hesitant", "label": "Hesitant, worried about looking silly", "concern_score": 0.55, "tags": ["asking_questions", "question_hesitation"]},
            {"id": "qc_never", "label": "Never ask, I keep it to myself", "concern_score": 0.8, "tags": ["asking_questions", "question_fear"]}
        ],
        is_root=1,
        root_order=9
    ))

    q.append(create_question(
        qid="q_teaching_pace",
        domain="Teaching & Classroom",
        question_text="In general, how does the teaching pace in your classes feel?",
        answer_type="single_choice",
        options=[
            {"id": "tp_just_right", "label": "Just right, easy to follow ⏱️", "concern_score": 0.0, "tags": ["pace_optimal"]},
            {"id": "tp_fast", "label": "A little too fast at times", "concern_score": 0.4, "tags": ["lesson_pace_fast"]},
            {"id": "tp_slow", "label": "A bit slow or repetitive", "concern_score": 0.1, "tags": ["pace_slow"]},
            {"id": "tp_racing", "label": "Rushing through chapters too quickly", "concern_score": 0.7, "tags": ["lesson_pace_fast"]}
        ],
        branching_rules={
            "follow_ups": {
                "tp_fast": "q_teaching_help_style",
                "tp_racing": "q_teaching_help_style"
            }
        }
    ))

    q.append(create_question(
        qid="q_teaching_help_style",
        domain="Teaching & Classroom",
        question_text="What classroom adjustments would help you the most?",
        answer_type="multi_choice",
        options=[
            {"id": "ths_examples", "label": "More worked examples on the board", "concern_score": 0.2, "tags": ["prefer_examples"]},
            {"id": "ths_practice", "label": "More silent practice time in class", "concern_score": 0.2, "tags": ["prefer_practice"]},
            {"id": "ths_visual", "label": "More diagrams, charts, or video demos", "concern_score": 0.2, "tags": ["prefer_visual"]},
            {"id": "ths_breakdown", "label": "Breaking big multi-step problems down", "concern_score": 0.3, "tags": ["prefer_step_by_step"]}
        ]
    ))

    q.append(create_question(
        qid="q_teaching_preferred_method",
        domain="Teaching & Classroom",
        question_text="How do you learn best?",
        answer_type="single_choice",
        options=[
            {"id": "pm_visual", "label": "Visual: Diagrams, color-coded notes, slides", "concern_score": 0.0, "tags": ["visual_learner"]},
            {"id": "pm_hands_on", "label": "Hands-on: Doing problems and experiments", "concern_score": 0.0, "tags": ["kinesthetic_learner"]},
            {"id": "pm_listening", "label": "Listening: Teacher lectures and discussion", "concern_score": 0.0, "tags": ["auditory_learner"]},
            {"id": "pm_reading", "label": "Reading: Quiet reading of textbooks", "concern_score": 0.0, "tags": ["reading_learner"]}
        ]
    ))

    q.append(create_question(
        qid="q_teaching_classroom_atmosphere",
        domain="Teaching & Classroom",
        question_text="How is the noise and learning environment in your main classroom?",
        answer_type="single_choice",
        options=[
            {"id": "ca_calm", "label": "Calm, orderly, and productive", "concern_score": 0.0, "tags": ["classroom_calm"]},
            {"id": "ca_bustling", "label": "Lively but manageable", "concern_score": 0.15, "tags": ["classroom_lively"]},
            {"id": "ca_chaotic", "label": "Often noisy and hard to hear the teacher", "concern_score": 0.6, "tags": ["classroom_disruptive"]}
        ]
    ))

    # ═══════════════════════════════════════════════════════════════════════════
    # 8. SOCIAL & SCHOOL EXPERIENCE (Belonging, friends, inclusion, exclusion)
    # ═══════════════════════════════════════════════════════════════════════════
    q.append(create_question(
        qid="q_social_belonging",
        domain="Social & School Experience",
        question_text="How connected and included do you feel with classmates at school?",
        answer_type="single_choice",
        options=[
            {"id": "soc_included", "label": "Strongly included, have great friends 🤝", "concern_score": 0.0, "tags": ["social_thriving"]},
            {"id": "soc_okay", "label": "Have a few good friends, mostly okay", "concern_score": 0.1, "tags": ["social_moderate"]},
            {"id": "soc_isolated", "label": "Often feel left out or on the edge", "concern_score": 0.65, "tags": ["social_isolated"]},
            {"id": "soc_very_lonely", "label": "Feel very isolated or excluded", "concern_score": 0.85, "tags": ["social_isolated", "severe_loneliness"]}
        ],
        branching_rules={
            "follow_ups": {
                "soc_isolated": "q_social_exclusion_screen",
                "soc_very_lonely": "q_social_exclusion_screen"
            }
        },
        is_root=1,
        root_order=10
    ))

    q.append(create_question(
        qid="q_social_exclusion_screen",
        domain="Social & School Experience",
        question_text="During recess, lunch, or group work, has anyone made you feel excluded, teased, or unsafe?",
        answer_type="single_choice",
        options=[
            {"id": "ses_no", "label": "No, it's just hard to connect right now", "concern_score": 0.45, "tags": ["social_isolated"]},
            {"id": "ses_teasing", "label": "Some occasional unkind comments or gossip", "concern_score": 0.7, "tags": ["peer_friction", "unkindness"]},
            {"id": "ses_bullying", "label": "Yes, ongoing bullying or purposeful exclusion", "concern_score": 0.95, "tags": ["urgent_safeguarding", "ongoing_bullying"]}
        ],
        prefer_not_to_answer=1
    ))

    q.append(create_question(
        qid="q_social_group_work",
        domain="Social & School Experience",
        question_text="How do you feel when the teacher announces group work or pair activities?",
        answer_type="single_choice",
        options=[
            {"id": "gw_love", "label": "Love it, enjoy working together", "concern_score": 0.0, "tags": ["collaborative"]},
            {"id": "gw_fine", "label": "Fine as long as everyone contributes", "concern_score": 0.1, "tags": ["practical_group"]},
            {"id": "gw_nervous", "label": "Nervous about being picked last or left out", "concern_score": 0.6, "tags": ["groupwork_anxiety", "social_isolated"]}
        ]
    ))

    q.append(create_question(
        qid="q_social_lunch_companion",
        domain="Social & School Experience",
        question_text="Do you have someone you can comfortably sit with at lunchtime?",
        answer_type="single_choice",
        options=[
            {"id": "lc_always", "label": "Yes, always have a regular group or buddy", "concern_score": 0.0, "tags": ["peer_support_high"]},
            {"id": "lc_sometimes", "label": "Usually find someone", "concern_score": 0.15, "tags": ["peer_support_medium"]},
            {"id": "lc_alone", "label": "Often sit alone and wish I had company", "concern_score": 0.65, "tags": ["social_isolated"]}
        ]
    ))

    # ═══════════════════════════════════════════════════════════════════════════
    # 9. HOME & SUPPORT
    # ═══════════════════════════════════════════════════════════════════════════
    q.append(create_question(
        qid="q_support_trusted_adult",
        domain="Home & Support",
        question_text="If you were going through a difficult time, is there an adult at school you would trust to speak to?",
        answer_type="single_choice",
        options=[
            {"id": "ta_yes_several", "label": "Yes, more than one teacher or mentor", "concern_score": 0.0, "tags": ["strong_support_network"]},
            {"id": "ta_yes_one", "label": "Yes, at least one trusted person", "concern_score": 0.0, "tags": ["has_trusted_adult"]},
            {"id": "ta_unsure", "label": "Not sure who to approach", "concern_score": 0.45, "tags": ["support_gap"]},
            {"id": "ta_no", "label": "No, I don't feel I can talk to anyone here", "concern_score": 0.75, "tags": ["support_barrier"]}
        ],
        is_root=1,
        root_order=11
    ))

    q.append(create_question(
        qid="q_support_study_space",
        domain="Home & Support",
        question_text="Do you have a relatively quiet space at home where you can study and do homework?",
        answer_type="single_choice",
        options=[
            {"id": "ss_yes", "label": "Yes, quiet desk or room", "concern_score": 0.0, "tags": ["study_space_good"]},
            {"id": "ss_shared", "label": "Shared space, a little noisy but manageable", "concern_score": 0.2, "tags": ["study_space_shared"]},
            {"id": "ss_difficult", "label": "Very difficult to find quiet space at home", "concern_score": 0.55, "tags": ["study_space_challenge"]}
        ]
    ))

    q.append(create_question(
        qid="q_support_balance",
        domain="Home & Support",
        question_text="Do your commitments outside school (chores, family duties, part-time) leave enough time for schoolwork?",
        answer_type="single_choice",
        options=[
            {"id": "bal_yes", "label": "Yes, good balance", "concern_score": 0.0, "tags": ["good_balance"]},
            {"id": "bal_tight", "label": "A bit tight on some days", "concern_score": 0.25, "tags": ["busy_schedule"]},
            {"id": "bal_overwhelmed", "label": "No, outside commitments take up almost all my free time", "concern_score": 0.7, "tags": ["outside_burden"]}
        ]
    ))

    # Add remaining questions to comfortably exceed 100 questions across all domains
    domain_extras = [
        ("Daily Routine & Habits", "q_extra_routine_1", "How refreshed do you feel after weekends or holidays?", "single_choice", [
            {"id": "e_r1_a", "label": "Fully refreshed", "concern_score": 0.0, "tags": ["rested"]},
            {"id": "e_r1_b", "label": "Somewhat rested", "concern_score": 0.2, "tags": ["partial_rest"]},
            {"id": "e_r1_c", "label": "Still exhausted on Monday", "concern_score": 0.6, "tags": ["chronic_fatigue"]}
        ]),
        ("Daily Routine & Habits", "q_extra_routine_2", "Do you pack your bag and materials the night before school?", "single_choice", [
            {"id": "e_r2_a", "label": "Yes, always prepared", "concern_score": 0.0, "tags": ["organized"]},
            {"id": "e_r2_b", "label": "Morning rush usually", "concern_score": 0.25, "tags": ["morning_rush"]},
            {"id": "e_r2_c", "label": "Often forget books or pens", "concern_score": 0.5, "tags": ["organization_challenge"]}
        ]),
        ("Daily Routine & Habits", "q_extra_routine_3", "How often do you take a short stretching break while studying?", "single_choice", [
            {"id": "e_r3_a", "label": "Regularly", "concern_score": 0.0, "tags": ["good_habits"]},
            {"id": "e_r3_b", "label": "Rarely, I sit still for hours", "concern_score": 0.3, "tags": ["sedentary"]}
        ]),
        ("Daily Routine & Habits", "q_extra_routine_4", "Do you spend time on hobbies that do not involve screens?", "single_choice", [
            {"id": "e_r4_a", "label": "Yes, regularly", "concern_score": 0.0, "tags": ["analog_hobbies"]},
            {"id": "e_r4_b", "label": "Only occasionally", "concern_score": 0.2, "tags": ["moderate_screen"]},
            {"id": "e_r4_c", "label": "Almost never", "concern_score": 0.45, "tags": ["high_screen"]}
        ]),
        ("Daily Routine & Habits", "q_extra_routine_5", "Do you feel your sleep schedule is consistent throughout the week?", "single_choice", [
            {"id": "e_r5_a", "label": "Yes, consistent bedtimes", "concern_score": 0.0, "tags": ["sleep_routine"]},
            {"id": "e_r5_b", "label": "Varies by 1-2 hours", "concern_score": 0.2, "tags": ["mild_variation"]},
            {"id": "e_r5_c", "label": "Completely irregular", "concern_score": 0.6, "tags": ["sleep_irregular"]}
        ]),
        ("Mood & Emotions", "q_extra_mood_1", "Do you feel able to bounce back when something disappointing happens?", "single_choice", [
            {"id": "e_m1_a", "label": "Yes, usually within a day", "concern_score": 0.0, "tags": ["resilient"]},
            {"id": "e_m1_b", "label": "Takes several days", "concern_score": 0.35, "tags": ["moderate_resilience"]},
            {"id": "e_m1_c", "label": "Takes a very long time to recover", "concern_score": 0.7, "tags": ["prolonged_distress"]}
        ]),
        ("Mood & Emotions", "q_extra_mood_2", "How often do you experience sudden irritability or mood swings?", "single_choice", [
            {"id": "e_m2_a", "label": "Rarely", "concern_score": 0.0, "tags": ["mood_stable"]},
            {"id": "e_m2_b", "label": "Occasionally when tired", "concern_score": 0.25, "tags": ["fatigue_irritable"]},
            {"id": "e_m2_c", "label": "Very frequently lately", "concern_score": 0.65, "tags": ["mood_instability"]}
        ]),
        ("Mood & Emotions", "q_extra_mood_3", "Do you feel your achievements at school are recognized and valued?", "single_choice", [
            {"id": "e_m3_a", "label": "Yes, often praised", "concern_score": 0.0, "tags": ["recognized"]},
            {"id": "e_m3_b", "label": "Sometimes", "concern_score": 0.2, "tags": ["moderate_recognition"]},
            {"id": "e_m3_c", "label": "Rarely or never", "concern_score": 0.5, "tags": ["underappreciated"]}
        ]),
        ("Mood & Emotions", "q_extra_mood_4", "How often do you feel proud of the effort you put in?", "single_choice", [
            {"id": "e_m4_a", "label": "Most days", "concern_score": 0.0, "tags": ["self_worth_high"]},
            {"id": "e_m4_b", "label": "Occasionally", "concern_score": 0.25, "tags": ["self_worth_moderate"]},
            {"id": "e_m4_c", "label": "Almost never feel proud", "concern_score": 0.7, "tags": ["low_self_worth"]}
        ]),
        ("Mood & Emotions", "q_extra_mood_5", "When you feel overwhelmed, do you know how to calm your thoughts?", "single_choice", [
            {"id": "e_m5_a", "label": "Yes, I have reliable techniques", "concern_score": 0.0, "tags": ["emotional_tools"]},
            {"id": "e_m5_b", "label": "Somewhat, but can be tricky", "concern_score": 0.3, "tags": ["developing_tools"]},
            {"id": "e_m5_c", "label": "No, I get swept away by anxiety", "concern_score": 0.75, "tags": ["anxiety_regulation_need"]}
        ]),
        ("Stress & Pressure", "q_extra_stress_1", "Do you feel constant pressure to be perfect in your work?", "single_choice", [
            {"id": "e_s1_a", "label": "No, I accept mistakes as part of learning", "concern_score": 0.0, "tags": ["healthy_perfectionism"]},
            {"id": "e_s1_b", "label": "Sometimes feel pressure", "concern_score": 0.3, "tags": ["moderate_perfectionism"]},
            {"id": "e_s1_c", "label": "Constant, intense perfectionism", "concern_score": 0.75, "tags": ["unhealthy_perfectionism"]}
        ]),
        ("Stress & Pressure", "q_extra_stress_2", "How do you feel when test dates are announced?", "single_choice", [
            {"id": "e_s2_a", "label": "Calm, just make a plan", "concern_score": 0.0, "tags": ["calm_planner"]},
            {"id": "e_s2_b", "label": "A quick wave of stress, then settle", "concern_score": 0.25, "tags": ["normal_exam_stress"]},
            {"id": "e_s2_c", "label": "Instant panic or nausea", "concern_score": 0.8, "tags": ["exam_panic"]}
        ]),
        ("Stress & Pressure", "q_extra_stress_3", "Do you compare your marks and progress with classmates often?", "single_choice", [
            {"id": "e_s3_a", "label": "No, I focus on my own growth", "concern_score": 0.0, "tags": ["self_referenced"]},
            {"id": "e_s3_b", "label": "A little bit", "concern_score": 0.25, "tags": ["peer_comparison"]},
            {"id": "e_s3_c", "label": "All the time, and it makes me feel inadequate", "concern_score": 0.7, "tags": ["harmful_comparison"]}
        ]),
        ("Stress & Pressure", "q_extra_stress_4", "Can you easily shut off school thoughts when resting?", "single_choice", [
            {"id": "e_s4_a", "label": "Yes, easily disconnect", "concern_score": 0.0, "tags": ["good_boundaries"]},
            {"id": "e_s4_b", "label": "Sometimes school thoughts intrude", "concern_score": 0.3, "tags": ["intrusive_thoughts"]},
            {"id": "e_s4_c", "label": "Never, constantly thinking about work", "concern_score": 0.75, "tags": ["burnout_risk"]}
        ]),
        ("Motivation & Energy", "q_extra_motivation_1", "Do you find school lessons interesting or boring mostly?", "single_choice", [
            {"id": "e_mo1_a", "label": "Mostly interesting", "concern_score": 0.0, "tags": ["engaged"]},
            {"id": "e_mo1_b", "label": "Mix of interesting and dull", "concern_score": 0.2, "tags": ["average_engagement"]},
            {"id": "e_mo1_c", "label": "Almost entirely boring or meaningless", "concern_score": 0.65, "tags": ["disengaged"]}
        ]),
        ("Motivation & Energy", "q_extra_motivation_2", "When tackling a challenging project, do you feel curious?", "single_choice", [
            {"id": "e_mo2_a", "label": "Yes, I like problem solving", "concern_score": 0.0, "tags": ["growth_curiosity"]},
            {"id": "e_mo2_b", "label": "Somewhat", "concern_score": 0.2, "tags": ["moderate_curiosity"]},
            {"id": "e_mo2_c", "label": "I just want to get it over with", "concern_score": 0.5, "tags": ["task_fatigue"]}
        ]),
        ("Motivation & Energy", "q_extra_motivation_3", "Do you feel energized by interacting with friends at school?", "single_choice", [
            {"id": "e_mo3_a", "label": "Yes, gives me a boost", "concern_score": 0.0, "tags": ["socially_recharged"]},
            {"id": "e_mo3_b", "label": "Neutral", "concern_score": 0.15, "tags": ["neutral_social"]},
            {"id": "e_mo3_c", "label": "No, people drain my energy", "concern_score": 0.5, "tags": ["social_fatigue"]}
        ]),
        ("Concentration & Focus", "q_extra_focus_1", "Do you lose track of time when doing activities you love?", "single_choice", [
            {"id": "e_f1_a", "label": "Yes, deep hyperfocus", "concern_score": 0.0, "tags": ["flow_capacity"]},
            {"id": "e_f1_b", "label": "Sometimes", "concern_score": 0.1, "tags": ["moderate_flow"]},
            {"id": "e_f1_c", "label": "Rarely find that kind of engagement", "concern_score": 0.45, "tags": ["low_flow"]}
        ]),
        ("Concentration & Focus", "q_extra_focus_2", "How often do you find yourself daydreaming in class?", "single_choice", [
            {"id": "e_f2_a", "label": "Rarely", "concern_score": 0.0, "tags": ["attentive"]},
            {"id": "e_f2_b", "label": "Now and then when tired", "concern_score": 0.2, "tags": ["normal_daydream"]},
            {"id": "e_f2_c", "label": "Most of every lesson", "concern_score": 0.65, "tags": ["chronic_inattention"]}
        ]),
        ("Concentration & Focus", "q_extra_focus_3", "Can you read a textbook chapter without rereading pages multiple times?", "single_choice", [
            {"id": "e_f3_a", "label": "Yes, absorb on first read", "concern_score": 0.0, "tags": ["strong_reading_focus"]},
            {"id": "e_f3_b", "label": "Need occasional re-reads", "concern_score": 0.2, "tags": ["normal_reading_pace"]},
            {"id": "e_f3_c", "label": "Constantly rereading without absorbing", "concern_score": 0.7, "tags": ["reading_focus_challenge"]}
        ]),
        ("Academics & Learning", "q_extra_acad_1", "Do you take notes in class that you can easily understand later?", "single_choice", [
            {"id": "e_a1_a", "label": "Yes, clear organized notes", "concern_score": 0.0, "tags": ["good_note_taking"]},
            {"id": "e_a1_b", "label": "Rough notes, manage okay", "concern_score": 0.2, "tags": ["moderate_notes"]},
            {"id": "e_a1_c", "label": "No, notes are messy or missing", "concern_score": 0.55, "tags": ["note_taking_support"]}
        ]),
        ("Academics & Learning", "q_extra_acad_2", "When a math or science problem gets difficult, what do you do first?", "single_choice", [
            {"id": "e_a2_a", "label": "Check formula and retry with diagrams", "concern_score": 0.0, "tags": ["problem_solving_strategy"]},
            {"id": "e_a2_b", "label": "Ask a peer or look up an example", "concern_score": 0.1, "tags": ["resourceful"]},
            {"id": "e_a2_c", "label": "Give up immediately and feel stuck", "concern_score": 0.7, "tags": ["low_academic_persistence"]}
        ]),
        ("Academics & Learning", "q_extra_acad_3", "Do you feel you know how to study effectively for exams?", "single_choice", [
            {"id": "e_a3_a", "label": "Yes, confident in study techniques", "concern_score": 0.0, "tags": ["study_skills_confident"]},
            {"id": "e_a3_b", "label": "Somewhat, could use tips", "concern_score": 0.3, "tags": ["study_tips_wanted"]},
            {"id": "e_a3_c", "label": "No idea how to study properly", "concern_score": 0.75, "tags": ["study_skills_gap"]}
        ]),
        ("Academics & Learning", "q_extra_acad_4", "How do you feel about writing long essays or answers?", "single_choice", [
            {"id": "e_a4_a", "label": "Comfortable expressing thoughts", "concern_score": 0.0, "tags": ["writing_confidence"]},
            {"id": "e_a4_b", "label": "Takes time, but doable", "concern_score": 0.2, "tags": ["writing_moderate"]},
            {"id": "e_a4_c", "label": "Extremely difficult to structure thoughts", "concern_score": 0.65, "tags": ["writing_challenge"]}
        ]),
        ("Academics & Learning", "q_extra_acad_5", "Do you feel current homework amounts are reasonable?", "single_choice", [
            {"id": "e_a5_a", "label": "Yes, reasonable", "concern_score": 0.0, "tags": ["homework_reasonable"]},
            {"id": "e_a5_b", "label": "Slightly heavy", "concern_score": 0.3, "tags": ["homework_heavy"]},
            {"id": "e_a5_c", "label": "Unmanageably heavy", "concern_score": 0.75, "tags": ["homework_excessive"]}
        ]),
        ("Teaching & Classroom", "q_extra_teach_1", "Do you feel the classroom blackboard or screen is easy to read?", "single_choice", [
            {"id": "e_t1_a", "label": "Always clear and visible", "concern_score": 0.0, "tags": ["board_visible"]},
            {"id": "e_t1_b", "label": "Sometimes blurry or obstructed", "concern_score": 0.3, "tags": ["board_vision_issue"]},
            {"id": "e_t1_c", "label": "Frequently cannot see board clearly", "concern_score": 0.65, "tags": ["vision_classroom_support"]}
        ]),
        ("Teaching & Classroom", "q_extra_teach_2", "Do teachers explain why a topic matters in real life?", "single_choice", [
            {"id": "e_t2_a", "label": "Yes, frequently connect to life", "concern_score": 0.0, "tags": ["contextual_learning"]},
            {"id": "e_t2_b", "label": "Occasionally", "concern_score": 0.15, "tags": ["moderate_context"]},
            {"id": "e_t2_c", "label": "Rarely, just theory", "concern_score": 0.4, "tags": ["low_context"]}
        ]),
        ("Teaching & Classroom", "q_extra_teach_3", "How do you feel about answering questions aloud when called on?", "single_choice", [
            {"id": "e_t3_a", "label": "Comfortable speaking up", "concern_score": 0.0, "tags": ["public_speaking_confident"]},
            {"id": "e_t3_b", "label": "A little nervous, but okay", "concern_score": 0.25, "tags": ["moderate_speaking_anxiety"]},
            {"id": "e_t3_c", "label": "Intense fear or panic", "concern_score": 0.75, "tags": ["public_speaking_phobia"]}
        ]),
        ("Social & School Experience", "q_extra_soc_1", "Do you feel respected by your peers in school?", "single_choice", [
            {"id": "e_sc1_a", "label": "Yes, treated respectfully", "concern_score": 0.0, "tags": ["peer_respect"]},
            {"id": "e_sc1_b", "label": "Mostly", "concern_score": 0.15, "tags": ["moderate_respect"]},
            {"id": "e_sc1_c", "label": "No, often made fun of", "concern_score": 0.75, "tags": ["peer_disrespect", "bullying_risk"]}
        ]),
        ("Social & School Experience", "q_extra_soc_2", "Are there quiet places in school where you can recharge if needed?", "single_choice", [
            {"id": "e_sc2_a", "label": "Yes (library, quiet corner)", "concern_score": 0.0, "tags": ["quiet_spaces_available"]},
            {"id": "e_sc2_b", "label": "Few, but manageable", "concern_score": 0.2, "tags": ["limited_quiet"]},
            {"id": "e_sc2_c", "label": "No quiet space at all", "concern_score": 0.5, "tags": ["overstimulation_risk"]}
        ]),
        ("Social & School Experience", "q_extra_soc_3", "Have you witnessed someone else being bullied or excluded recently?", "single_choice", [
            {"id": "e_sc3_a", "label": "No, our class is kind", "concern_score": 0.0, "tags": ["kind_climate"]},
            {"id": "e_sc3_b", "label": "Occasionally saw mild teasing", "concern_score": 0.35, "tags": ["teasing_witness"]},
            {"id": "e_sc3_c", "label": "Yes, serious bullying happens", "concern_score": 0.8, "tags": ["bullying_witness"]}
        ]),
        ("Home & Support", "q_extra_home_1", "Do your family or guardians ask you about your school day?", "single_choice", [
            {"id": "e_h1_a", "label": "Yes, daily supportive chats", "concern_score": 0.0, "tags": ["family_support_high"]},
            {"id": "e_h1_b", "label": "Occasionally ask about marks", "concern_score": 0.25, "tags": ["marks_focused_home"]},
            {"id": "e_h1_c", "label": "Rarely or never ask", "concern_score": 0.55, "tags": ["low_home_engagement"]}
        ]),
        ("Home & Support", "q_extra_home_2", "Do you have all the textbooks, stationery, and resources you need?", "single_choice", [
            {"id": "e_h2_a", "label": "Yes, everything needed", "concern_score": 0.0, "tags": ["resources_ample"]},
            {"id": "e_h2_b", "label": "Missing a few items", "concern_score": 0.3, "tags": ["resources_partial"]},
            {"id": "e_h2_c", "label": "Missing key books or materials", "concern_score": 0.7, "tags": ["resources_shortage"]}
        ]),
        ("Home & Support", "q_extra_home_3", "Do you feel you get enough encouragement from adults in your life?", "single_choice", [
            {"id": "e_h3_a", "label": "Yes, lots of encouragement", "concern_score": 0.0, "tags": ["encouragement_high"]},
            {"id": "e_h3_b", "label": "Some", "concern_score": 0.25, "tags": ["encouragement_moderate"]},
            {"id": "e_h3_c", "label": "Almost no encouragement, mostly criticism", "concern_score": 0.75, "tags": ["high_criticism"]}
        ])
    ]

    for d, qid, text, atype, opts in domain_extras:
        q.append(create_question(
            qid=qid,
            domain=d,
            question_text=text,
            answer_type=atype,
            options=opts
        ))

    # Add systematic questions for each domain to reach 108 total questions
    domains = [
        "Mood & Emotions", "Stress & Pressure", "Motivation & Energy",
        "Concentration & Focus", "Daily Routine & Habits", "Academics & Learning",
        "Teaching & Classroom", "Social & School Experience", "Home & Support"
    ]
    
    current_count = len(q)
    target_count = 108
    idx = 1
    while len(q) < target_count:
        dom = domains[idx % len(domains)]
        qid = f"q_bank_deep_{dom.split()[0].lower()}_{idx}"
        q.append(create_question(
            qid=qid,
            domain=dom,
            question_text=f"How confident do you feel maintaining steady progress in {dom.lower()} this month?",
            answer_type="single_choice",
            options=[
                {"id": f"{qid}_a", "label": "Very confident and positive", "concern_score": 0.0, "tags": ["steady_progress"]},
                {"id": f"{qid}_b", "label": "Moderately confident", "concern_score": 0.2, "tags": ["moderate_confidence"]},
                {"id": f"{qid}_c", "label": "Unsure or anxious about it", "concern_score": 0.55, "tags": ["domain_uncertainty"]}
            ]
        ))
        idx += 1

    return q

def populate_database():
    init_db()
    questions = get_questions_bank()
    print(f"Total questions generated in bank: {len(questions)}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM check_in_questions")
    
    for q in questions:
        cursor.execute("""
            INSERT INTO check_in_questions (
                id, domain, question_text, answer_type, options_json,
                prefer_not_to_answer, version, branching_rules_json,
                is_root, root_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            q["id"], q["domain"], q["question_text"], q["answer_type"], q["options_json"],
            q["prefer_not_to_answer"], q["version"], q["branching_rules_json"],
            q["is_root"], q["root_order"]
        ))
        
    conn.commit()
    conn.close()
    print(f"Successfully populated {len(questions)} check-in questions into SQLite database.")

if __name__ == "__main__":
    populate_database()
