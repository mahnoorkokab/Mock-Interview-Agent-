#streamlitapp.py
import streamlit as st
import requests
import time

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="AI Mock Interview Agent", page_icon="🤖")
st.title("AI-Powered Mock Interview Agent")

if "session_id" not in st.session_state:
    st.session_state.session_id = None
    st.session_state.current_question = ""

job_description = st.text_area("Enter Job Description:", "")
user_answer = st.text_area("Your Answer:", "")

# ---------------- START INTERVIEW ----------------
if st.button("Start Mock Interview"):
    if job_description.strip() == "":
        st.warning("Please enter a job description!")
    else:
        try:
            with st.spinner("Starting interview (question will be prepared in background)..."):
                resp = requests.post(f"{API_BASE}/start_interview", json={"job_description": job_description}, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.session_id = data.get("session_id")
                st.info("Session created. Waiting for question generation...")

                # Poll for first question
                poll_timeout = 300  # 5 minutes
                poll_interval = 5
                elapsed = 0
                question = None
                with st.spinner("Generating first question..."):
                    while elapsed < poll_timeout:
                        status_resp = requests.get(f"{API_BASE}/status/{st.session_state.session_id}", timeout=60)
                        if status_resp.status_code == 200:
                            status_data = status_resp.json()
                            if status_data.get('status') == 'ready' and status_data.get('question'):
                                question = status_data.get('question')
                                break
                            if status_data.get('status') == 'error':
                                st.error(f"Error generating question: {status_data.get('error')}")
                                break
                        time.sleep(poll_interval)
                        elapsed += poll_interval

                if question:
                    st.session_state.current_question = question
                    st.success("First question ready:")
                    st.write(question)
                else:
                    st.error("Timed out waiting for question. Try again later.")
            else:
                st.error(f"Error starting interview: {resp.status_code} - {resp.text}")
        except requests.exceptions.Timeout:
            st.error("Request timed out while contacting the backend.")
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to the backend. Is the API server running on http://127.0.0.1:8000 ?")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

# ---------------- SUBMIT ANSWER ----------------
if st.button("Submit Answer"):
    if not st.session_state.session_id:
        st.warning("No active session. Start an interview first.")
    elif st.session_state.current_question == "":
        st.warning("No question to answer yet.")
    elif user_answer.strip() == "":
        st.warning("Please enter your answer before submitting.")
    else:
        payload = {
            "session_id": st.session_state.session_id,
            "question": st.session_state.current_question,
            "answer": user_answer
        }
        feedback = None
        next_q = None
        try:
            with st.spinner("Submitting your answer — evaluation will run in background..."):
                resp = requests.post(f"{API_BASE}/answer_question/", json=payload, timeout=60)
            if resp.status_code == 200:
                st.info("Answer submitted. Full evaluation will appear when ready.")

                # Poll for evaluation result
                poll_timeout = 300
                poll_interval = 5
                elapsed = 0
                while elapsed < poll_timeout:
                    status_resp = requests.get(f"{API_BASE}/status/{st.session_state.session_id}", timeout=60)
                    if status_resp.status_code == 200:
                        status_data = status_resp.json()
                        eval_state = status_data.get('evaluation', {})
                        if eval_state.get('status') == 'ready':
                            feedback = eval_state.get('last_feedback')
                            next_q = eval_state.get('next_question')
                            break
                        if eval_state.get('status') == 'error':
                            st.error(f"Evaluation error: {eval_state.get('error')}")
                            break
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                if feedback is None:
                    st.error("Timed out waiting for evaluation. Try again later.")
            else:
                st.error(f"Error submitting answer: {resp.status_code} - {resp.text}")
        except requests.exceptions.Timeout:
            st.error("Request timed out while contacting the backend.")
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to the backend. Is the API server running on http://127.0.0.1:8000 ?")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

        # ---------------- DISPLAY FEEDBACK ----------------
        if feedback:
            if isinstance(feedback, dict):
                rating = feedback.get('rating')
                if rating is not None:
                    st.markdown(f"**Rating:** {rating}/10")

                for label in ('strengths', 'weaknesses', 'suggestions'):
                    items = feedback.get(label) or []
                    if items:
                        st.markdown(f"**{label.capitalize()}:**")
                        for it in items:
                            st.markdown(f"- {it}")

                # Show raw JSON if available
                if feedback.get('raw'):
                    with st.expander("Raw evaluator JSON"):
                        st.json(feedback.get('raw'))

                if feedback.get('raw_feedback') and not feedback.get('raw'):
                    st.subheader("Raw feedback")
                    st.code(feedback.get('raw_feedback'))

            else:
                st.write(feedback)

            # Update session with next question
            if next_q:
                st.session_state.current_question = next_q
                st.subheader("Next question:")
                st.write(next_q)
