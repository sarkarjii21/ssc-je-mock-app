import io
import json
import os
import random
import re
import time
import requests
import streamlit as st
from google import genai
from pypdf import PdfReader

# --- पेज का नाम, लोगो और कॉन्फ़िगरेशन (Centered Layout for Mobile Perfection) ---
st.set_page_config(
    page_title="Omega",
    page_icon="Untitled47_20260917013309.png",
    layout="centered"
)

DB_FILE = "question_bank.json"
CONFIG_FILE = "app_config.json"

# --- स्थायी डेटाबेस एवं API Key हैंडलिंग ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {"questions": data}
                elif isinstance(data, dict) and "questions" in data:
                    return data
        except Exception:
            pass
    return {
        "questions": [
            {
                "id": 1,
                "subject": "Electrical Engineering",
                "question": "Which of the following motors has the highest starting torque?",
                "options": ["Squirrel cage induction motor", "Slip ring induction motor", "Series motor", "Shunt motor"],
                "answer": "Series motor",
                "explanation": "DC series motor produces very high starting torque because torque is proportional to the square of armature current (T ∝ Ia²).",
                "bengali_meaning": "DC series motor-এ starting torque সবথেকে বেশি হয় কারণ এটি armature current-এর square-এর সমানুপাতিক।"
            },
            {
                "id": 2,
                "subject": "Reasoning",
                "question": "If CAT is coded as 24, how is DOG coded?",
                "options": ["26", "27", "28", "29"],
                "answer": "26",
                "explanation": "Sum of alphabetical positions: C(3) + A(1) + T(20) = 24. Similarly for DOG: D(4) + O(15) + G(7) = 26.",
                "bengali_meaning": "alphabetical position-গুলির যোগফল করা হয়েছে: C=3, A=1, T=20 যোগ করলে 24 হয়। তেমনি DOG = 4+15+7 = 26।"
            }
        ]
    }

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"gemini_api_key": ""}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

if "db" not in st.session_state or not isinstance(st.session_state.db, dict) or "questions" not in st.session_state.db:
    st.session_state.db = load_db()

if "config" not in st.session_state:
    st.session_state.config = load_config()

# --- सेशन स्टेट वेरिएबल ---
if "test_started" not in st.session_state:
    st.session_state.test_started = False
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "test_questions" not in st.session_state:
    st.session_state.test_questions = []
if "start_time" not in st.session_state:
    st.session_state.start_time = 0
if "time_limit" not in st.session_state:
    st.session_state.time_limit = 10

# --- साइडबार मेनू ---
st.sidebar.title("⚡ Omega Portal")
menu = st.sidebar.radio("Navigation", ["Take Mock Test", "Manage & Add Questions"])

# ==========================================
# 1. MOCK TEST SECTION
# ==========================================
if menu == "Take Mock Test":
    st.title("🎯 Omega - CBT Mock Test")
    st.markdown("अपनी तैयारी को परखिए और हर सवाल का सही विश्लेषण देखिए।")

    if not st.session_state.test_started:
        st.subheader("⚙️ Test Configuration")
        
        all_qs = st.session_state.db["questions"]
        
        # डायनामिक सब्जेक्ट्स निकालना
        available_subjects = list(set([q.get("subject", "General") for q in all_qs]))
        subject_options = ["Full Mock (Mixed)"] + available_subjects

        subject_mode = st.selectbox("Select Subject Mode", subject_options)
        num_q = st.slider("Number of Questions", min_value=1, max_value=max(1, len(all_qs)), value=min(10, len(all_qs)))

        st.markdown(f"📊 *Available Question Bank:* Total = {len(all_qs)}")

        if st.button("🚀 Start Test", type="primary"):
            if subject_mode == "Full Mock (Mixed)":
                filtered = all_qs
            else:
                filtered = [q for q in all_qs if q.get("subject") == subject_mode]

            if not filtered:
                st.warning("⚠️ इस कैटेगरी में कोई सवाल उपलब्ध नहीं है।")
            else:
                selected = random.sample(filtered, min(num_q, len(filtered)))
                st.session_state.test_questions = selected
                st.session_state.user_answers = {}
                st.session_state.submitted = False
                st.session_state.test_started = True
                st.session_state.start_time = time.time()
                st.rerun()

    else:
        questions = st.session_state.test_questions
        elapsed_time = int(time.time() - st.session_state.start_time)
        time_left_sec = (st.session_state.time_limit * 60) - elapsed_time

        if time_left_sec > 0:
            mins, secs = divmod(time_left_sec, 60)
            st.info(f"⏱️ Time Remaining: **{mins:02d}:{secs:02d}**")
        else:
            st.error("⏰ Time's up!")
            st.session_state.submitted = True

        st.success(f"📝 Active Test Mode | Total Questions: {len(questions)}")
        st.markdown("---")

        with st.form("mock_test_form"):
            for idx, q in enumerate(questions):
                st.markdown(f"### Q{idx+1}: {q['question']}")
                st.caption(f"📌 Subject: {q.get('subject', 'General')}")

                if q.get("bengali_meaning"):
                    st.markdown(f"💡 *Bengali Meaning:* {q['bengali_meaning']}")

                options = q["options"]
                default_val = st.session_state.user_answers.get(idx, None)
                
                choice = st.radio(
                    f"Choose your answer for Q{idx+1}:",
                    options,
                    index=options.index(default_val) if default_val in options else None,
                    key=f"q_{idx}"
                )
                
                if choice:
                    st.session_state.user_answers[idx] = choice

                st.markdown("---")

            submit_btn = st.form_submit_button("📤 Submit Test", type="primary")
            if submit_btn:
                st.session_state.submitted = True
                st.rerun()

        if st.session_state.submitted:
            st.header("📊 Test Results & Analysis")
            
            score = 0
            incorrect_list = []

            for idx, q in enumerate(questions):
                user_ans = st.session_state.user_answers.get(idx, "Not Answered")
                correct_ans = q["answer"]

                if user_ans == correct_ans:
                    score += 1
                    st.markdown(f"✅ **Q{idx+1}: {q['question']}**")
                    st.markdown(f"Your Answer: `{user_ans}` (Correct)")
                else:
                    incorrect_list.append((idx, q, user_ans))
                    st.markdown(f"❌ **Q{idx+1}: {q['question']}**")
                    st.markdown(f"Your Answer: `{user_ans}` | Correct Answer: `{correct_ans}`")
                
                if q.get("explanation"):
                    st.markdown(f"💡 *Explanation:* {q['explanation']}")
                st.markdown("---")

            st.subheader(f"🎯 Final Score: {score} / {len(questions)}")

            if incorrect_list:
                st.markdown("### ⚠️ Mistakes Review (Only Incorrect)")
                for idx, q, user_ans in incorrect_list:
                    with st.expander(f"Review Q{idx+1}: {q['question']}"):
                        st.markdown(f"❌ **Your Answer:** {user_ans}")
                        st.markdown(f"✅ **Correct Answer:** {q['answer']}")
                        if q.get("explanation"):
                            st.markdown(f"💡 **Explanation:** {q['explanation']}")
                        if q.get("bengali_meaning"):
                            st.markdown(f"💡 **Bengali Meaning:** {q['bengali_meaning']}")

            if st.button("🔄 Take Another Test"):
                st.session_state.test_started = False
                st.session_state.submitted = False
                st.session_state.user_answers = {}
                st.rerun()

# ==========================================
# 2. MANAGE & ADD QUESTIONS SECTION
# ==========================================
else:
    st.title("🛠️ Omega - Question Bank Manager")
    st.markdown("यहाँ से आप नए सवाल जोड़ सकते हैं और क्वेश्चन बैंक को मैनेज कर सकते हैं।")

    api_key_input = st.text_input(
        "Gemini API Key (Required for AI features)",
        value=st.session_state.config.get("gemini_api_key", ""),
        type="password"
    )
    if st.button("Save API Key"):
        st.session_state.config["gemini_api_key"] = api_key_input
        save_config(st.session_state.config)
        st.success("API Key saved securely!")

    st.markdown("---")
    st.subheader("➕ Add New Question Manually")

    with st.form("add_question_form"):
        new_subject = st.selectbox("Subject Category", ["Electrical Engineering", "Reasoning", "General Knowledge", "Non-Technical"])
        new_q_text = st.text_area("Question Text")
        
        op1 = st.text_input("Option A")
        op2 = st.text_input("Option B")
        op3 = st.text_input("Option C")
        op4 = st.text_input("Option D")

        correct_op = st.selectbox("Correct Option", [op1, op2, op3, op4] if op1 or op2 else ["Option A", "Option B"])
        explanation = st.text_area("Explanation")
        bengali_meaning = st.text_input("Bengali Meaning Hint (Optional)")

        add_submitted = st.form_submit_button("📥 Add Question to Bank")
        if add_submitted:
            if not new_q_text or not correct_op:
                st.error("Please fill in the question and correct option!")
            else:
                new_item = {
                    "id": len(st.session_state.db["questions"]) + 1,
                    "subject": new_subject,
                    "question": new_q_text,
                    "options": [op1, op2, op3, op4],
                    "answer": correct_op,
                    "explanation": explanation,
                    "bengali_meaning": bengali_meaning
                }
                st.session_state.db["questions"].append(new_item)
                save_db(st.session_state.db)
                st.success("🎉 Question added successfully to Omega Database!")

    st.markdown("---")
    st.subheader("📚 Current Question Bank Statistics")
    total_q = len(st.session_state.db["questions"])
    st.info(f"Total Questions Stored: **{total_q}**")

    if st.checkbox("Show Raw JSON Database"):
        st.json(st.session_state.db)
