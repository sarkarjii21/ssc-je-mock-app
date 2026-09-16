import streamlit as st
import json
import os
import random
import time
import requests
from pypdf import PdfReader

st.set_page_config(page_title="SSC JE CBT Mock Portal", layout="wide")

DB_FILE = "question_bank.json"
CONFIG_FILE = "app_config.json"

# --- डेटाबेस और कॉन्फ़िग हेल्पर ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for q in data:
                    if "subject" not in q:
                        q["subject"] = "Technical"
                return data
        except Exception:
            return []
    return []

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_saved_key():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("api_key", "")
        except Exception:
            return ""
    return ""

def save_saved_key(key_str):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": key_str}, f)

# --- जेमिनी एपीआई सवाल पार्सर ---
def parse_raw_text_with_gemini(raw_text, api_key, subject="Technical"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    prompt = f"""
Extract all multiple-choice questions from the following text and return STRICTLY a JSON array of objects.
Each object must have these exact keys:
- "question": "The question text in English"
- "options": ["Option A", "Option B", "Option C", "Option D"] (Array of 4 options in English)
- "correct_option": "Exact string of the correct option matching one of the options"
- "bengali_meaning": "Precise and helpful Bengali translation or meaning hint for the question"
- "subject": "{subject}"

Do NOT include any markdown formatting, backticks, or extra text. Output only valid JSON.
Text to parse:
{raw_text}
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    
    if response.status_code == 200:
        res_data = response.json()
        generated_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if generated_text.startswith("```"):
            generated_text = generated_text.strip("`")
            if generated_text.startswith("json"):
                generated_text = generated_text[4:].strip()
        return json.loads(generated_text)
    elif response.status_code == 429:
        st.error("API Quota Exhausted (429)! फ़्री लिमिट पूरी हो चुकी है। कृपया सीधे question_bank.json में सवाल जोड़ें।")
        return None
    else:
        st.error(f"API Error {response.status_code}: {response.text}")
        return None

# --- सेशन स्टेट इनिशियलाइज़ेशन ---
if "api_key" not in st.session_state:
    st.session_state.api_key = load_saved_key()
if "test_started" not in st.session_state:
    st.session_state.test_started = False
if "test_submitted" not in st.session_state:
    st.session_state.test_submitted = False
if "current_questions" not in st.session_state:
    st.session_state.current_questions = []
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "start_time" not in st.session_state:
    st.session_state.start_time = 0
if "duration_mins" not in st.session_state:
    st.session_state.duration_mins = 12

# --- मुख्य यूआई (Tabs Layout) ---
st.title("⚡ SSC JE CBT Exam Portal")

tab_mock, tab_manage = st.tabs(["📝 Mock Test", "⚙️ Manage & Add Questions"])

# ==========================================
# TAB 1: MOCK TEST
# ==========================================
with tab_mock:
    bank = load_db()

    # टेस्ट शुरू नहीं हुआ है तो सेटअप स्क्रीन दिखाएँ
    if not st.session_state.test_started:
        st.subheader("🎯 Configure Your Test")
        
        tech_count = sum(1 for q in bank if q.get("subject") == "Technical")
        non_tech_count = sum(1 for q in bank if q.get("subject") == "Non-Technical")

        col1, col2 = st.columns(2)
        with col1:
            subject_mode = st.selectbox(
                "📚 Select Subject Mode:",
                [
                    f"Full Mock (Mixed) - {len(bank)} Available",
                    f"Technical Only - {tech_count} Available",
                    f"Non-Technical Only - {non_tech_count} Available"
                ]
            )
        
        with col2:
            test_mode = st.selectbox(
                "⏱️ Choose Test Size & Duration:",
                ["10 Questions (12 Minutes)", "100 Questions (120 Minutes)"]
            )
            
        num_q = 10 if "10 Questions" in test_mode else 100
        dur_mins = 12 if "12 Minutes" in test_mode else 120

        # सब्जेक्ट के अनुसार पूल फ़िल्टर
        if "Technical Only" in subject_mode:
            pool = [q for q in bank if q.get("subject") == "Technical"]
        elif "Non-Technical Only" in subject_mode:
            pool = [q for q in bank if q.get("subject") == "Non-Technical"]
        else:
            pool = bank

        if st.button("🚀 Start Mock Test", type="primary", use_container_width=True):
            if len(pool) == 0:
                st.error("चयनित विषय में कोई सवाल मौजूद नहीं है! पहले 'Manage & Add Questions' में जाकर सवाल जोड़ें।")
            else:
                selected = random.sample(pool, min(num_q, len(pool)))
                st.session_state.current_questions = selected
                st.session_state.user_answers = {i: None for i in range(len(selected))}
                st.session_state.start_time = time.time()
                st.session_state.duration_mins = dur_mins
                st.session_state.test_started = True
                st.session_state.test_submitted = False
                st.rerun()

    # टेस्ट चालू है
    elif st.session_state.test_started and not st.session_state.test_submitted:
        elapsed = time.time() - st.session_state.start_time
        total_time_sec = st.session_state.duration_mins * 60
        remaining_sec = max(0, int(total_time_sec - elapsed))

        rem_min = remaining_sec // 60
        rem_s = remaining_sec % 60

        st.markdown(
            f"""
            <div style="background-color:#1e293b; padding:12px; border-radius:8px; display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <span style="color:#38bdf8; font-size:18px; font-weight:bold;">Total Questions: {len(st.session_state.current_questions)}</span>
                <span style="color:{'#ef4444' if remaining_sec < 180 else '#22c55e'}; font-size:22px; font-weight:bold;">⏱️ {rem_min:02d}:{rem_s:02d}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        if remaining_sec == 0:
            st.warning("⚠️ Time Over! Test automatically submitted.")
            st.session_state.test_submitted = True
            st.rerun()

        for i, q in enumerate(st.session_state.current_questions):
            subj_tag = q.get("subject", "Technical")
            tag_color = "#3b82f6" if subj_tag == "Technical" else "#10b981"

            st.markdown(
                f"""
                <div style="margin-top:10px; margin-bottom:5px;">
                    <span style="background-color:{tag_color}; color:white; padding:3px 8px; border-radius:4px; font-size:12px; font-weight:bold;">{subj_tag}</span>
                    <span style="font-size:16px; font-weight:bold; margin-left:8px;">Q{i+1}. {q['question']}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

            if q.get("bengali_meaning"):
                with st.expander(f"🇧🇩 প্রশ্ন {i+1} এর বাংলা অর্থ (Show Meaning)"):
                    st.write(q["bengali_meaning"])

            current_choice = st.session_state.user_answers.get(i, None)
            default_index = None
            if current_choice in q["options"]:
                default_index = q["options"].index(current_choice)

            selected_opt = st.radio(
                f"Select answer for Q{i+1}:",
                q["options"],
                index=default_index,
                key=f"q_radio_{i}",
                label_visibility="collapsed"
            )
            st.session_state.user_answers[i] = selected_opt
            st.markdown("---")

        col_sub, col_quit = st.columns([2, 1])
        with col_sub:
            if st.button("✅ Final Submit Test", type="primary", use_container_width=True):
                st.session_state.test_submitted = True
                st.rerun()
        with col_quit:
            if st.button("❌ Quit Test", use_container_width=True):
                st.session_state.test_started = False
                st.session_state.test_submitted = False
                st.session_state.current_questions = []
                st.session_state.user_answers = {}
                st.rerun()

    # ==========================================
    # टेस्ट सबमिट हो गया - स्कोरकार्ड और मिस्टेक फ़िल्टर
    # ==========================================
    elif st.session_state.test_submitted:
        st.subheader("📊 Your Scorecard & Performance")

        correct_count = 0
        incorrect_count = 0
        unattempted_count = 0

        for i, q in enumerate(st.session_state.current_questions):
            ans = st.session_state.user_answers.get(i)
            if ans is None:
                unattempted_count += 1
            elif ans == q["correct_option"]:
                correct_count += 1
            else:
                incorrect_count += 1

        total_marks = (correct_count * 1.0) - (incorrect_count * 0.25)
        max_marks = len(st.session_state.current_questions) * 1.0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Marks", f"{total_marks:.2f} / {max_marks:.0f}")
        c2.metric("✅ Correct (+1.0)", correct_count)
        c3.metric("❌ Incorrect (-0.25)", incorrect_count)
        c4.metric("⚪ Unattempted", unattempted_count)

        st.markdown("---")

        # गलत सवाल छाँटने का फ़िल्टर
        st.subheader("🔍 Review & Practice Mistakes")
        review_filter = st.radio(
            "Show Questions:",
            [
                f"❌ Only Incorrect ({incorrect_count})",
                f"⚪ Only Unattempted ({unattempted_count})",
                f"📋 All Questions ({len(st.session_state.current_questions)})"
            ],
            horizontal=True
        )

        displayed_any = False
        for i, q in enumerate(st.session_state.current_questions):
            user_choice = st.session_state.user_answers.get(i)
            is_correct = (user_choice == q["correct_option"])
            subj_tag = q.get("subject", "Technical")

            # फ़िल्टर लॉजिक
            if "Only Incorrect" in review_filter and (user_choice is None or is_correct):
                continue
            if "Only Unattempted" in review_filter and user_choice is not None:
                continue

            displayed_any = True
            status_text = "✅ Correct" if is_correct else ("⚪ Unattempted" if user_choice is None else "❌ Wrong")
            status_color = "#22c55e" if is_correct else ("#94a3b8" if user_choice is None else "#ef4444")

            st.markdown(
                f"""
                <div style="background-color:#0f172a; border-left: 5px solid {status_color}; padding: 12px; border-radius: 6px; margin-top: 15px;">
                    <span style="background-color:#334155; color:white; padding:2px 8px; border-radius:3px; font-size:11px; font-weight:bold;">{subj_tag}</span>
                    <strong style="font-size:16px; margin-left:8px;">Q{i+1}: {q['question']}</strong><br/>
                    <div style="margin-top:8px;">
                        <span style="color:{status_color}; font-weight:bold;">Your Choice: {user_choice if user_choice else 'Not Attempted'}</span> | 
                        <span style="color:#22c55e; font-weight:bold;">Correct Answer: {q['correct_option']}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if q.get("bengali_meaning"):
                st.caption(f"🇧🇩 বাংলা অর্থ: {q['bengali_meaning']}")

        if not displayed_any:
            if "Only Incorrect" in review_filter:
                st.success("🎉 शाबाश! आपका एक भी सवाल गलत नहीं हुआ!")
            elif "Only Unattempted" in review_filter:
                st.info("आपने सारे सवाल हल किए थे, कोई भी सवाल छोड़ा नहीं था।")

        st.markdown("<br/>", unsafe_allow_html=True)
        if st.button("🔄 Take Another Test", type="primary", use_container_width=True):
            st.session_state.test_started = False
            st.session_state.test_submitted = False
            st.session_state.current_questions = []
            st.session_state.user_answers = {}
            st.rerun()

# ==========================================
# TAB 2: MANAGE & ADD QUESTIONS
# ==========================================
with tab_manage:
    st.subheader("🔑 Gemini API Settings")
    
    col_k1, col_k2 = st.columns([3, 1])
    with col_k1:
        new_key = st.text_input("Enter Gemini API Key:", value=st.session_state.api_key, type="password", placeholder="AIzaSy...")
    with col_k2:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("💾 Save Key", use_container_width=True):
            if new_key.strip():
                st.session_state.api_key = new_key.strip()
                save_saved_key(new_key.strip())
                st.success("Key Saved!")
                st.rerun()

    st.markdown("---")
    st.subheader("📥 Add Questions to Bank")

    selected_subject_to_add = st.radio(
        "🏷️ Choose Subject for New Questions:",
        ["Technical", "Non-Technical"],
        horizontal=True
    )

    pdf_file = st.file_uploader("Upload Question PDF (Optional):", type=["pdf"])
    raw_input_text = st.text_area("Or Paste Raw Text of Questions directly:", height=150, placeholder="Paste questions here...")

    if st.button("⚙️ Process & Add to Bank", type="primary", use_container_width=True):
        if not st.session_state.api_key:
            st.error("कृपया पहले ऊपर अपनी Gemini API Key दर्ज करें!")
        else:
            full_text = ""
            if pdf_file is not None:
                try:
                    reader = PdfReader(pdf_file)
                    for p in reader.pages:
                        full_text += p.extract_text() or ""
                except Exception as e:
                    st.error(f"PDF पढ़ने में त्रुटि: {e}")

            if raw_input_text.strip():
                full_text += "\n" + raw_input_text.strip()

            if not full_text.strip():
                st.warning("कृपया टेक्स्ट पेस्ट करें या PDF अपलोड करें!")
            else:
                with st.spinner(f"AI सवालों को {selected_subject_to_add} फ़ॉर्मेट में प्रोसेस कर रहा है..."):
                    extracted = parse_raw_text_with_gemini(full_text, st.session_state.api_key, selected_subject_to_add)
                    if extracted and isinstance(extracted, list):
                        current_db = load_db()
                        current_db.extend(extracted)
                        save_db(current_db)
                        st.success(f"सफलतापूर्वक {len(extracted)} नए सवाल ({selected_subject_to_add}) बैंक में जोड़ दिए गए!")
                        time.sleep(1)
                        st.rerun()

    st.markdown("---")
    current_stored = load_db()
    st.write(f"📚 **Total Stored Questions:** {len(current_stored)}")
    t_cnt = sum(1 for q in current_stored if q.get("subject") == "Technical")
    nt_cnt = sum(1 for q in current_stored if q.get("subject") == "Non-Technical")
    st.caption(f"⚡ Technical: **{t_cnt}** | 🧠 Non-Technical: **{nt_cnt}**")

    if st.button("🗑️ Reset / Clear Bank", help="सारे सवाल मिटा देगा"):
        save_db([])
        st.warning("क्वेश्चन बैंक खाली कर दिया गया।")
        st.rerun()
