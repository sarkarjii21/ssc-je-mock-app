import streamlit as st
from google import genai
from pypdf import PdfReader
import io
import json
import requests
import re

st.set_page_config(page_title="SSC JE CBT Mock Portal", layout="wide")

# Session state initialization
if "question_bank" not in st.session_state:
    st.session_state.question_bank = []
if "test_active" not in st.session_state:
    st.session_state.test_active = False
if "curr_idx" not in st.session_state:
    st.session_state.curr_idx = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}

# Function to download PDF from Google Drive public link
def get_pdf_from_drive(drive_url):
    file_id_match = re.search(r"/d/([a-zA-Z0-9_-]+)", drive_url) or re.search(r"id=([a-zA-Z0-9_-]+)", drive_url)
    if not file_id_match:
        return None
    file_id = file_id_match.group(1)
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    session = requests.Session()
    response = session.get(download_url, stream=True)
    for k, v in response.cookies.items():
        if k.startswith("download_warning"):
            response = session.get(f"{download_url}&confirm={v}", stream=True)
            break
    if response.status_code == 200:
        return io.BytesIO(response.content)
    return None

# Sidebar - Question Bank Manager
with st.sidebar:
    st.header("📂 Question Bank Manager")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.subheader("Add Questions")
    drive_link = st.text_input("Google Drive PDF Link")
    raw_text_input = st.text_area("Or Paste Text Directly (from PDF/Google Lens)", height=120)
    
    if st.button("Process & Add to Bank"):
        if not api_key:
            st.error("Please enter your Gemini API Key first!")
        else:
            extracted_text = ""
            
            # Case 1: Google Drive link provided
            if drive_link.strip():
                with st.spinner("Downloading and reading PDF from Google Drive..."):
                    pdf_bytes = get_pdf_from_drive(drive_link.strip())
                    if pdf_bytes:
                        try:
                            reader = PdfReader(pdf_bytes)
                            for page in reader.pages[:15]:
                                extracted_text += page.extract_text() or ""
                        except Exception as e:
                            st.error(f"Error reading PDF: {e}")
                    else:
                        st.error("Could not fetch file. Make sure Drive link permission is set to 'Anyone with the link'.")

            # Case 2: Raw text directly pasted
            if raw_text_input.strip():
                extracted_text += "\n" + raw_text_input.strip()

            if extracted_text.strip():
                with st.spinner("Processing questions via Gemini AI..."):
                    try:
                        client = genai.Client(api_key=api_key)
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
    "bengali_meaning": "বাংলা অর্থ"
  }}
]

Raw Text:
{extracted_text[:15000]}
"""
                        resp = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt
                        )
                        clean_json = resp.text.strip().removeprefix("```json").removesuffix("```").strip()
                        new_questions = json.loads(clean_json)
                        
                        if isinstance(new_questions, list):
                            st.session_state.question_bank.extend(new_questions)
                            st.success(f"Added {len(new_questions)} questions successfully!")
                    except Exception as e:
                        st.error(f"AI Processing failed: {e}")
            else:
                st.warning("Please provide a valid Drive link or paste text.")

    st.markdown("---")
    st.write(f"📚 **Total Questions in Bank:** {len(st.session_state.question_bank)}")

# Main Test Interface
st.title("⚡ SSC JE CBT Mock Test Portal")

if len(st.session_state.question_bank) == 0:
    st.info("Question Bank is empty. Add questions from sidebar using Google Drive link or direct text.")
else:
    if not st.session_state.test_active:
        if st.button("Start Test"):
            st.session_state.test_active = True
            st.session_state.curr_idx = 0
            st.session_state.user_answers = {}
            st.rerun()
    else:
        q_idx = st.session_state.curr_idx
        q_data = st.session_state.question_bank[q_idx]

        st.subheader(f"Question {q_idx + 1} of {len(st.session_state.question_bank)}")
        st.write(f"**{q_data.get('question')}**")
        st.caption(f"💡 বাংলা অর্থ: {q_data.get('bengali_meaning', '')}")

        selected = st.radio(
            "Select Answer:",
            q_data.get("options", []),
            index=None if q_idx not in st.session_state.user_answers else q_data.get("options", []).index(st.session_state.user_answers[q_idx]) if st.session_state.user_answers[q_idx] in q_data.get("options", []) else None,
            key=f"q_{q_idx}"
        )
        if selected:
            st.session_state.user_answers[q_idx] = selected

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous") and q_idx > 0:
                st.session_state.curr_idx -= 1
                st.rerun()
        with col2:
            if st.button("Next") and q_idx < len(st.session_state.question_bank) - 1:
                st.session_state.curr_idx += 1
                st.rerun()

        if st.button("End Test & Submit"):
            st.session_state.test_active = False
            correct_cnt = sum(1 for i, q in enumerate(st.session_state.question_bank) if st.session_state.user_answers.get(i) == q.get("correct_option"))
            st.success(f"Test Completed! Score: {correct_cnt} / {len(st.session_state.question_bank)}")
