import streamlit as st
import json
import random
import time
from pypdf import PdfReader
from google import genai

st.set_page_config(page_title="SSC JE Mock Portal", page_icon="⚡", layout="wide")

# Custom CSS for styling buttons and timer
st.markdown("""
<style>
    div[data-testid="stButton"] button {
        width: 100%;
        text-align: left;
        padding: 12px;
        font-size: 15px;
        border-radius: 8px;
        margin-bottom: 6px;
    }
    .timer-box {
        background-color: #1e293b;
        color: #f8fafc;
        padding: 12px 18px;
        border-radius: 8px;
        font-size: 18px;
        font-weight: bold;
        text-align: center;
        border: 1px solid #334155;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Session State Variables
if "master_questions" not in st.session_state:
    st.session_state.master_questions = []
if "test_questions" not in st.session_state:
    st.session_state.test_questions = []
if "test_active" not in st.session_state:
    st.session_state.test_active = False
if "test_finished" not in st.session_state:
    st.session_state.test_finished = False
if "curr_idx" not in st.session_state:
    st.session_state.curr_idx = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "end_time" not in st.session_state:
    st.session_state.end_time = 0
if "time_limit_sec" not in st.session_state:
    st.session_state.time_limit_sec = 0

st.title("⚡ SSC JE CBT Mock Test Portal")

# Sidebar for PDF upload and settings
with st.sidebar:
    st.header("📂 Question Bank Manager")
    api_key = st.text_input("Gemini API Key", type="password")
    uploaded_files = st.file_uploader("Upload SSC JE PDFs (Hindi/English)", accept_multiple_files=True)
    
    if uploaded_files and api_key and st.button("Process & Add to Bank"):
        total_added = 0
        with st.spinner("Extracting, translating to English & generating Bengali helper..."):
            client = genai.Client(api_key=api_key)
            for uploaded_pdf in uploaded_files:
                try:
                    reader = PdfReader(uploaded_pdf)
                    text = ""
                    for p in reader.pages[:12]:
                        text += p.extract_text() or ""
                    
                    prompt = f"""
                    You are an SSC JE exam expert. Extract all multiple-choice questions from this raw exam key text.
                    Rules:
                    1. Translate any Hindi questions and options to pure standard ENGLISH.
                    2. Clean options (remove 1, 2, 3, 4, tick marks, red crosses).
                    3. Identify the exact string of the correct option (which had the green tick).
                    4. Add a concise Bengali translation/meaning of the question for guidance.

                    Output ONLY valid JSON array:
                    [
                      {{
                        "question": "Question in English",
                        "options": ["Option A", "Option B", "Option C", "Option D"],
                        "correct_option": "Matching Option",
                        "bengali_meaning": "বাংলা অর্থ"
                      }}
                    ]

                    Raw Text:
                    {text[:12000]}
                    """
                    resp = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    clean = resp.text.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(clean)
                    st.session_state.master_questions.extend(parsed)
                    total_added += len(parsed)
                except Exception as e:
                    st.error(f"Error reading {uploaded_pdf.name}: {e}")
            if total_added > 0:
                st.success(f"Added {total_added} questions to the bank!")

    st.markdown("---")
    st.write(f"📚 Total Questions in Bank: **{len(st.session_state.master_questions)}**")
    
    st.subheader("🎯 Configure Test")
    test_mode = st.radio("Select Question Count:", [10, 100], index=0)
    
    if st.button("🚀 Launch Test"):
        if len(st.session_state.master_questions) < test_mode:
            st.warning(f"Bank has only {len(st.session_state.master_questions)} questions. Upload more PDFs or start with available questions.")
            count = len(st.session_state.master_questions)
        else:
            count = test_mode

        if count > 0:
            st.session_state.test_questions = random.sample(st.session_state.master_questions, count)
            st.session_state.test_active = True
            st.session_state.test_finished = False
            st.session_state.curr_idx = 0
            st.session_state.user_answers = {}
            st.session_state.time_limit_sec = count * 40  # 40 seconds per question
            st.session_state.end_time = time.time() + st.session_state.time_limit_sec
            st.rerun()

# Timer Check logic
remaining_sec = 0
if st.session_state.test_active:
    remaining_sec = int(st.session_state.end_time - time.time())
    if remaining_sec <= 0:
        st.session_state.test_active = False
        st.session_state.test_finished = True
        st.warning("⏰ Time up! Your test has been submitted automatically.")
        st.rerun()

# Test Active Interface
if st.session_state.test_active and not st.session_state.test_finished:
    mins, secs = divmod(remaining_sec, 60)
    
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.caption(f"Question {st.session_state.curr_idx + 1} of {len(st.session_state.test_questions)}")
    with col_t2:
        st.markdown(f"<div class='timer-box'>⏳ {mins:02d}:{secs:02d}</div>", unsafe_allow_html=True)
    
    st.progress((st.session_state.curr_idx + 1) / len(st.session_state.test_questions))
    
    current_q = st.session_state.test_questions[st.session_state.curr_idx]
    
    # English Question
    st.subheader(current_q["question"])
    
    # Optional Bengali Expander
    if current_q.get("bengali_meaning"):
        with st.expander("🔍 বাংলা অর্থ দেখুন (Bengali Meaning)"):
            st.write(current_q["bengali_meaning"])
    
    idx = st.session_state.curr_idx
    answered = idx in st.session_state.user_answers
    selected_choice = st.session_state.user_answers.get(idx, None)
    
    # Display Options
    for opt in current_q["options"]:
        if not answered:
            if st.button(opt, key=f"q_{idx}_{opt}"):
                st.session_state.user_answers[idx] = opt
                st.rerun()
        else:
            # Immediate feedback color coding
            if opt == current_q["correct_option"]:
                st.success(f"✔ {opt} (Correct Answer)")
            elif opt == selected_choice:
                st.error(f"✖ {opt} (Your Choice - Wrong)")
            else:
                st.info(opt)

    # Controls
    c1, c2 = st.columns(2)
    with c1:
        if idx > 0 and st.button("⬅ Previous"):
            st.session_state.curr_idx -= 1
            st.rerun()
    with c2:
        if idx < len(st.session_state.test_questions) - 1:
            if st.button("Next ➡"):
                st.session_state.curr_idx += 1
                st.rerun()
        else:
            if st.button("🏁 Submit Test"):
                st.session_state.test_active = False
                st.session_state.test_finished = True
                st.rerun()

# Test Finished / Scorecard Interface
elif st.session_state.test_finished:
    st.header("📊 SSC JE Mock Result & Detailed Analysis")
    
    total_q = len(st.session_state.test_questions)
    correct_count = 0
    wrong_count = 0
    
    for i, q in enumerate(st.session_state.test_questions):
        user_choice = st.session_state.user_answers.get(i)
        if user_choice is not None:
            if user_choice == q["correct_option"]:
                correct_count += 1
            else:
                wrong_count += 1
                
    unattempted = total_q - (correct_count + wrong_count)
    
    # Marking Scheme: +1 for right, -0.333 for wrong
    positive_marks = correct_count * 1.0
    negative_marks = wrong_count * 0.333
    total_score = round(positive_marks - negative_marks, 2)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Score", f"{total_score} / {total_q}")
    col2.metric("Correct (+1)", f"{correct_count}")
    col3.metric("Wrong (-0.33)", f"{wrong_count}")
    col4.metric("Unattempted", f"{unattempted}")
    
    pct = (total_score / total_q) * 100 if total_q > 0 else 0
    if pct >= 65:
        st.balloons()
        st.success(f"Excellent work! You achieved {pct:.1f}%.")
    else:
        st.warning(f"You achieved {pct:.1f}%. Keep practicing!")
        
    if st.button("🔄 Take Another Test"):
        st.session_state.test_finished = False
        st.rerun()

else:
    st.info("👈 Open the sidebar to upload PDFs, select 10 or 100 questions, and start your timed mock test.")
