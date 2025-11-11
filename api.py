#api.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
import logging
from pydantic import BaseModel
import uuid
import os
from dotenv import load_dotenv
from tools import generate_question, evaluate_answer_safe, _invoke_with_timeout

# Load environment variables
load_dotenv()

# ====== Configure LangSmith Tracing ======
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if not os.getenv("LANGCHAIN_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = "interview-agent"
    if not os.getenv("LANGCHAIN_ENDPOINT"):
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

router = APIRouter()
INTERVIEW_SESSIONS: dict = {}

# configure simple logger
logger = logging.getLogger("interview_api")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class StartInterviewRequest(BaseModel):
    job_description: str


class StartInterviewResponse(BaseModel):
    session_id: str
    question: str


class AnswerRequest(BaseModel):
    session_id: str
    question: str
    answer: str


@router.post("/start_interview", response_model=StartInterviewResponse)
def start_interview(req: StartInterviewRequest, background_tasks: BackgroundTasks):
    job_description = req.job_description or ""
    if not job_description.strip():
        raise HTTPException(status_code=400, detail="Please provide a job description or topic for a mock interview.")

    session_id = str(uuid.uuid4())
    INTERVIEW_SESSIONS[session_id] = {
        "job_description": job_description,
        "parsed": None,
        "questions": [],
        "answers": [],
        "log": [],
        "status": "pending",
        "error": None,
        "evaluation": {
            "status": "idle",
            "last_feedback": None,
            "next_question": None,
            "error": None
        }
    }

    # schedule background task to generate first question
    background_tasks.add_task(_bg_generate_first_question, session_id)

    return {"session_id": session_id, "question": ""}


def _bg_generate_first_question(session_id: str):
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session:
        return
    try:
        session['log'].append('bg_generate_first_question: start')
        job_description = session.get("job_description", "")
        # use _invoke_with_timeout internally from tools.py
        qobj = generate_question(job_description)
        question = qobj.get('question') if isinstance(qobj, dict) else str(qobj)
        parsed = qobj.get('parsed') if isinstance(qobj, dict) else None

        session['parsed'] = parsed
        session['questions'].append(question)
        session['status'] = 'ready'
        session['evaluation']['status'] = 'idle'
        session['log'].append(f'bg_generate_first_question: question ready ({len(question or "")} chars)')
    except Exception as e:
        session['status'] = 'error'
        session['error'] = str(e)
        try:
            session['log'].append(f'bg_generate_first_question: exception: {e}')
        except Exception:
            pass


@router.post("/answer_question/")
def answer_question(req: AnswerRequest, background_tasks: BackgroundTasks):
    logger.info(f"Received answer_question request: session_id={req.session_id} question_len={len(req.question or '')}")
    session = INTERVIEW_SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session['evaluation']['status'] = 'pending'
    session['evaluation']['error'] = None
    background_tasks.add_task(_bg_evaluate_answer, req.session_id, req.question, req.answer)

    return {"message": "evaluation_scheduled", "session_id": req.session_id}


def _bg_evaluate_answer(session_id: str, question: str, answer: str):
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session:
        return
    try:
        session['log'].append('bg_evaluate_answer: start')
        feedback = evaluate_answer_safe(question, answer)
        session['log'].append('bg_evaluate_answer: evaluator returned')
        raw_fb = feedback.get('raw_feedback') if isinstance(feedback, dict) else None
        if raw_fb:
            session['log'].append(f'raw_feedback_snippet: {str(raw_fb)[:400]}')
    except Exception as e:
        session['evaluation']['status'] = 'error'
        session['evaluation']['error'] = str(e)
        try:
            session['log'].append(f'bg_evaluate_answer: exception: {e}')
        except Exception:
            pass
        return

    session["answers"].append({
        "question": question,
        "answer": answer,
        "feedback": feedback
    })

    try:
        next_qobj = generate_question(session.get('job_description') or "")
        next_question = next_qobj.get('question') if isinstance(next_qobj, dict) else str(next_qobj)
    except Exception:
        next_question = None

    session["questions"].append(next_question)
    session['evaluation']['status'] = 'ready'
    session['evaluation']['last_feedback'] = feedback
    session['evaluation']['next_question'] = next_question
    try:
        session['log'].append('bg_evaluate_answer: finished, evaluation ready')
    except Exception:
        pass


@router.get("/status/{session_id}")
def status(session_id: str):
    session = INTERVIEW_SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "status": session.get('status', 'pending'),
        "question": session['questions'][-1] if session.get('questions') else None,
        "error": session.get('error'),
        "evaluation": session.get('evaluation', {}),
        "log": session.get('log', [])
    }
