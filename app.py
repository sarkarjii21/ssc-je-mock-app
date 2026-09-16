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

st.set_page_config(page_title="SSC JE CBT Mock Portal", layout="wide")

DB_FILE = "question_bank.json"
CONFIG_FILE = "app_config.json"

# --- स्थायी डेटाबेस एवं API Key हैंडलिंग ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
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

# --- सेशन स्टेट इनिशियलाइज़ेशन ---
if 'question_bank' not in st.session_state:
    st.session_state.question_bank = load_db()
if 'saved_api_key' not in st.session_state:
    st.session_state.saved_api_key = load_saved_key()
if 'test_active' not in st.session_state:
    st.session_state.test_active = False
if 'active_test_questions' not in st.session_state:
    st.session_state.active_test_questions = []
if 'curr_idx' not in st.session_state:
    st.session_state.curr_idx = 0
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}
if 'start_time' not in st.session_state:
    st.session_state.start_time = 0
if 'duration_seconds' not in st.session_state:
    st.session_state.duration_seconds = 0

st.title("⚡ SSC JE CBT Mock Portal")

# दो अलग-अलग पेज (टैब्स)
tab_test, tab_admin = st.tabs(["📝 Mock Test", "⚙️ Manage & Add Questions"])

# ==========================================
# टैब 1: केवल टेस्ट पोर्टल (साफ़ इंटरफेस)
# ==========================================
with tab_test:
    total_available = len(st.session_state.question_bank)

    if total_available == 0:
        st.info("Question bank is empty. 'Manage & Add Questions' टैब में जाकर सवाल जोड़ें।")
    else:
        if not st.session_state.test_active:
            st.subheader("Select Mock Test Mode")
            st.caption("Marking: +1.00 Correct | -0.25 Negative | 0.00 Unattempted")
            
            test_mode = st.radio(
                "Choose test length:",
                ["10 Questions Mock (12 Mins)", "100 Questions Mock (120 Mins)"]
            )
            target_count = 10 if "10 Questions" in test_mode else 100
            duration_mins = 12 if target_count == 10 else 120

            if st.button(f"🚀 Start Mock Test ({min(target_count, total_available)} Questions)", use_container_width=True):
                selected_count = min(target_count, total_available)
                st.session_state.active_test_questions = random.sample(st.session_state.question_bank, selected_count)
                st.session_state.test_active = True
                st.session_state.curr_idx = 0
                st.session_state.user_answers = {}
                st.session_state.start_time = time.time()
                st.session_state.duration_seconds = duration_mins * 60
                st.rerun()

        else:
            test_list = st.session_state.active_test_questions
            idx = st.session_state.curr_idx
            q_data = test_list[idx]

            # टाइमर कैलकुलेशन
            elapsed = time.time() - st.session_state.start_time
            remaining = max(0, int(st.session_state.duration_seconds - elapsed))
            rem_min = remaining // 60
            rem_sec = remaining % 60

            # टाइमर व सवाल नंबर
            col_t1, col_t2 = st.columns([2, 1])
            with col_t1:
                st.markdown(f"#### Question {idx + 1} of {len(test_list)}")
            with col_t2:
                if remaining == 0:
                    st.error("⏳ Time Up!")
                else:
                    st.warning(f"⏱️ {rem_min:02d}:{rem_sec:02d}")

            st.write(f"**{q_data['question']}**")
            if q_data.get('bengali_meaning'):
                st.caption(f"🧭 {q_data.get('bengali_meaning')}")

            current_selection = st.session_state.user_answers.get(idx)
            selected = st.radio(
                "Select Answer:",
                q_data['options'],
                index=q_data['options'].index(current_selection) if current_selection in q_data['options'] else None,
                key=f"active_q_{idx}"
            )
            if selected:
                st.session_state.user_answers[idx] = selected

            # मोबाइल-फ्रेंडली नैविगेशन बटन (कटेगा नहीं)
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if idx > 0 and st.button("⬅️ Previous", use_container_width=True):
                    st.session_state.curr_idx -= 1
                    st.rerun()
            with col_b2:
                if idx < len(test_list) - 1 and st.button("Next ➡️", use_container_width=True):
                    st.session_state.curr_idx += 1
                    st.rerun()

            st.markdown("---")
            if st.button("✅ Submit Test", use_container_width=True) or remaining == 0:
                correct = 0
                wrong = 0
                unattempted = 0

                for i, q in enumerate(test_list):
                    ans = st.session_state.user_answers.get(i)
                    if ans is None:
                        unattempted += 1
                    elif ans == q['correct_option']:
                        correct += 1
                    else:
                        wrong += 1

                raw_score = (correct * 1.0) - (wrong * 0.25)

                st.balloons()
                st.success("### 📊 Test Result Summary")
                st.markdown(f"""
- **Total Questions:** {len(test_list)}
- **Correct:** {correct} (+{correct * 1:.2f})
- **Wrong:** {wrong} (-{wrong * 0.25:.2f})
- **Unattempted:** {unattempted} (0.00)
- **🎯 Final Net Score:** `{raw_score:.2f}` / {len(test_list)}
                """)

                if st.button("Back to Test Home", use_container_width=True):
                    st.session_state.test_active = False
                    st.rerun()

# ==========================================
# टैब 2: सेटिंग्स और प्रश्न जोड़ने का पेज
# ==========================================
with tab_admin:
    st.subheader("🔑 Gemini API Settings")
    if not st.session_state.saved_api_key:
        input_key = st.text_input("Enter Gemini API Key", type="password")
        if st.button("Save API Key Permanently", use_container_width=True):
            if input_key.strip():
                save_saved_key(input_key.strip())
                st.session_state.saved_api_key = input_key.strip()
                st.success("API Key saved permanently!")
                st.rerun()
    else:
        st.success("✅ Gemini API Key is Saved")
        col_k1, col_k2 = st.columns(2)
        with col_k1:
            if st.button("Change Key", use_container_width=True):
                st.session_state.saved_api_key = ""
                st.rerun()
        with col_k2:
            if st.button("Remove Key", use_container_width=True):
                save_saved_key("")
                st.session_state.saved_api_key = ""
                st.warning("API Key removed.")
                st.rerun()

    st.markdown("---")
    st.subheader("📥 Add Questions to Bank")
    gdrive_link = st.text_input("Google Drive PDF Link")
    raw_text_input = st.text_area("Or Paste Text Directly (Hindi/English)", height=140)

    if st.button("Process & Add to Bank", use_container_width=True):
        active_key = st.session_state.saved_api_key
        if not active_key:
            st.error("पहले ऊपर Gemini API Key सेव करें।")
        else:
            extracted_text = ""
            if gdrive_link:
                file_id_match = re.search(r'[-\w]{25,}', gdrive_link)
                if file_id_match:
                    file_id = file_id_match.group(0)
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                    try:
                        with st.spinner("Downloading PDF..."):
                            resp = requests.get(download_url)
                            if resp.status_code == 200:
                                reader = PdfReader(io.BytesIO(resp.content))
                                for page in reader.pages[:15]:
                                    t = page.extract_text()
                                    if t:
                                        extracted_text += t + "\n"
                    except Exception as e:
                        st.error(f"Download Error: {e}")

            if raw_text_input.strip():
                extracted_text += "\n" + raw_text_input.strip()

            if extracted_text.strip():
                with st.spinner("AI Processing via Gemini-3.6-flash..."):
                    try:
                        client = genai.Client(api_key=active_key)
                        prompt = f"""
You are an SSC JE exam expert. Extract all multiple-choice questions from this raw text.
Rules:
1. Translate Hindi questions and options to clear standard English.
2. Clean options (remove 1, 2, 3, 4, tick marks, red crosses).
3. Identify the exact correct option.
4. Add a concise Bengali translation/meaning of the question for guidance.

Output ONLY valid JSON array with format:
[
  {{
    "question": "Question in English",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_option": "Matching Option",
    "bengali_meaning": "বাংলা अर्थ"
  }}
]

Raw Text:
{extracted_text[:15000]}
"""
                        resp = client.models.generate_content(
                            model='gemini-3.6-flash',
                            contents=prompt
                        )
                        clean_json = resp.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                        new_q = json.loads(clean_json)

                        if isinstance(new_q, list):
                            st.session_state.question_bank.extend(new_q)
                            save_db(st.session_state.question_bank)
                            st.success(f"Added {len(new_q)} questions permanently!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"AI Error: {e}")
            else:
                st.warning("सवाल टेक्स्ट या लिंक दर्ज करें।")

    st.markdown("---")
    st.write(f"💾 **Total Stored Questions:** {len(st.session_state.question_bank)}")
    if len(st.session_state.question_bank) > 0:
        if st.button("🗑️ Delete All Stored Questions", use_container_width=True):
            st.session_state.question_bank = []
            save_db([])
            st.session_state.test_active = False
            st.rerun()
