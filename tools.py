#tools.py
import os
import json
import traceback
import time
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from openai import OpenAI
from langsmith.wrappers import wrap_openai

# Initialize OpenAI client (loads key from .env automatically)
load_dotenv()

# ====== Configure LangSmith Tracing ======
# Enable tracing if API key is set
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if not os.getenv("LANGCHAIN_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = "interview-agent"
    if not os.getenv("LANGCHAIN_ENDPOINT"):
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    
    # Wrap OpenAI client to enable automatic tracing
    _openai_client = OpenAI()
    client = wrap_openai(_openai_client)
else:
    # Use unwrapped client if LangSmith is not configured
    client = OpenAI()

llm = True  # flag to preserve compatibility with your existing logic

# Configurable timeout (seconds) for LLM invocations
LLM_INVOKE_TIMEOUT = int(os.getenv("LLM_INVOKE_TIMEOUT", "120"))
LLM_INVOKE_RETRIES = int(os.getenv("LLM_INVOKE_RETRIES", "2"))
LLM_BACKOFF_FACTOR = float(os.getenv("LLM_BACKOFF_FACTOR", "2.0"))


def _invoke_with_timeout(prompt: str, timeout: int = None):
    """Invoke OpenAI GPT-4o-mini model with timeout and retry/backoff logic."""
    timeout = timeout or LLM_INVOKE_TIMEOUT

    def _call():
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content

    attempts = 1 + max(0, LLM_INVOKE_RETRIES)
    for attempt in range(1, attempts + 1):
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_call)
            try:
                resp = fut.result(timeout=timeout)
                return resp
            except FuturesTimeoutError:
                fut.cancel()
                if attempt < attempts:
                    backoff = (LLM_BACKOFF_FACTOR ** (attempt - 1))
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"LLM call timed out after {timeout} seconds (attempts={attempts})")
            except Exception as e:
                fut.cancel()
                if attempt < attempts:
                    print(f"⚠️ LLM invocation error (attempt {attempt}/{attempts}): {e}. Retrying...")
                    backoff = (LLM_BACKOFF_FACTOR ** (attempt - 1))
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"LLM invocation failed after {attempt} attempts: {e}")


def generate_question(job_description: str) -> str:
    """Generate the next interview question based on the job description or topic."""
    if not llm:
        raise RuntimeError("LLM not initialized. Ensure OpenAI API key is set.")

    try:
        prompt = (
            f"You are an expert interviewer.\nGiven the following job description, extract the fields: "
            f"role, seniority, skills, job_type, location, and then produce ONE concise, relevant interview question "
            f"tailored to the role.\nReturn a JSON object with keys: "
            f"\"role\", \"seniority\", \"skills\", \"job_type\", \"location\", \"question\" and nothing else.\n\n"
            f"Job Description:\n{job_description}\n\nRespond with JSON only."
        )
        resp = _invoke_with_timeout(prompt)
        text = getattr(resp, 'content', resp)
        text = (text or '').strip()

        from re import search
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            m = search(r"\{[\s\S]*\}", text)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parsed = None

        if not parsed:
            parsed = {
                "role": job_description.split('\n')[0][:60],
                "seniority": "unspecified",
                "skills": "",
                "job_type": "unspecified",
                "location": "unspecified",
                "question": f"Based on the job description, can you tell me about your experience related to {job_description.split()[0]}?"
            }

        question = parsed.get('question') if isinstance(parsed.get('question'), str) else str(parsed.get('question', '')).strip()
        return {"question": question, "parsed": parsed}

    except Exception as e:
        print("⚠️ Error in generate_question:", traceback.format_exc())
        raise RuntimeError(f"Failed to generate question: {e}")


def evaluate_answer(question: str, answer: str) -> str:
    """Evaluate candidate's answer for relevance, depth, and clarity."""
    if not llm:
        raise RuntimeError("LLM not initialized properly. Please check if OpenAI key is valid.")

    def _extract_json(text: str):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, str):
                try:
                    return json.loads(parsed)
                except Exception:
                    return None
            return parsed
        except Exception:
            pass

        try:
            if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
                unq = text[1:-1]
                unq = unq.encode('utf-8').decode('unicode_escape')
                try:
                    return json.loads(unq)
                except Exception:
                    pass
        except Exception:
            pass

        import re
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            cand = m.group(0)
            try:
                return json.loads(cand)
            except Exception:
                try:
                    cand2 = cand.encode('utf-8').decode('unicode_escape')
                    return json.loads(cand2)
                except Exception:
                    pass
        return None

    def _validate_feedback(d: dict):
        out = {}
        try:
            out['rating'] = int(d.get('rating')) if d.get('rating') is not None else None
        except Exception:
            out['rating'] = None

        def _ensure_list(v):
            import re as _re
            if v is None:
                return []
            if isinstance(v, list):
                return v
            if isinstance(v, str):
                parts = [s.strip() for s in _re.split(r"[\n;,]", v) if s.strip()]
                return parts
            return [str(v)]

        out['strengths'] = _ensure_list(d.get('strengths'))
        out['weaknesses'] = _ensure_list(d.get('weaknesses'))
        out['suggestions'] = _ensure_list(d.get('suggestions'))
        return out

    try:
        eval_prompt = (
            f"You are an expert interviewer and evaluator.\nQuestion: {question}\nCandidate Answer: {answer}\n\n"
            "Return ONLY valid JSON with the exact keys: rating (0-10 integer), strengths (list of short strings), "
            "weaknesses (list of short strings), suggestions (list of short strings). Do not include any other text."
        )
        response = _invoke_with_timeout(eval_prompt)
        text = (getattr(response, 'content', response) or '').strip()

        parsed = _extract_json(text)
        if parsed is None:
            retry_prompt = (
                f"Please provide the same JSON output, and wrap it between <JSON> and </JSON> tags with no other text.\n"
                f"Question: {question}\nCandidate Answer: {answer}\n\nReturn only: <JSON>{{...}}</JSON>"
            )
            resp2 = _invoke_with_timeout(retry_prompt)
            text2 = (getattr(resp2, 'content', resp2) or '').strip()
            import re
            m = re.search(r"<JSON>([\s\S]*?)</JSON>", text2)
            if m:
                parsed = _extract_json(m.group(1))

        if parsed is None:
            print("LLM raw output (failed JSON parse):", repr(text))
            return {"raw_feedback": text}

        validated = _validate_feedback(parsed)
        validated['raw'] = parsed
        return validated

    except Exception as e:
        print("⚠️ Error in evaluate_answer:", traceback.format_exc())
        raise RuntimeError(f"Failed to evaluate answer: {e}")


def evaluate_answer_safe(question: str, answer: str) -> dict:
    """Safe wrapper around evaluate_answer that always returns a structured dict."""
    try:
        fb = evaluate_answer(question, answer)
    except Exception as e:
        print(f"⚠️ evaluate_answer raised an exception: {e}")
        fb = None

    if not fb or not isinstance(fb, dict):
        return {
            "rating": None,
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "raw_feedback": f"LLM failed or returned invalid JSON for answer: {str(answer)[:200]}"
        }

    fb.setdefault('rating', None)
    fb.setdefault('strengths', [])
    fb.setdefault('weaknesses', [])
    fb.setdefault('suggestions', [])
    fb.setdefault('raw_feedback', None)
    return fb


def evaluate_answer_quick(question: str, answer: str) -> dict:
    """Fast heuristic evaluator that returns structured feedback quickly."""
    try:
        text = (answer or "").strip()
        rating = None
        strengths, weaknesses, suggestions = [], [], []

        if len(text) == 0:
            rating = 1
            weaknesses.append("No answer provided")
            suggestions.append("Provide a concise answer describing your approach or example.")
            return {"rating": rating, "strengths": strengths, "weaknesses": weaknesses, "suggestions": suggestions, "raw_feedback": None}

        keywords = [
            "design", "scale", "latency", "throughput", "test", "monitor", "debug", "optimiz",
            "performance", "deploy", "ci", "cd", "api", "database", "cache", "security", "team", "lead"
        ]
        lowered = text.lower()
        hits = [k for k in keywords if k in lowered]
        if hits:
            strengths.extend([f"Mentions: {h}" for h in hits[:5]])

        if len(text.split()) > 40:
            strengths.append("Answer has good detail")
            length_score = 7
        elif len(text.split()) > 15:
            strengths.append("Answer is reasonably detailed")
            length_score = 5
        else:
            weaknesses.append("Answer is short; add an example or more specifics")
            length_score = 3

        star_keywords = ["situation", "task", "action", "result", "impact", "resulted", "led to", "we"]
        if any(w in lowered for w in star_keywords):
            strengths.append("Uses STAR-style structure or gives concrete impact")

        rating = min(10, max(1, int((len(hits) * 1.5) + (length_score or 0))))

        if "%" not in text and not any(w in lowered for w in ["percent", "%", "x times", "increase", "decrease"]):
            suggestions.append("Include measurable impact (e.g., reduced latency by 30%).")
        if not any(w in lowered for w in ["example", "we", "i", "led", "implemented", "built"]):
            suggestions.append("Add a concrete example with steps and outcome.")

        return {
            "rating": rating,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
            "raw_feedback": None
        }
    except Exception as e:
        return {
            "rating": None,
            "strengths": [],
            "weaknesses": ["Quick evaluator failed"],
            "suggestions": ["Try again or wait for full evaluation."],
            "raw_feedback": f"quick-eval-exception: {e}"
        }


def check_relevant_input(user_input: str) -> bool:
    """Quick heuristic to determine if the input seems like a job description."""
    if not user_input or len(user_input.strip()) < 20:
        return False

    keywords = [
        "engineer", "developer", "analyst", "manager", "lead", "senior", "junior", "data",
        "software", "role", "responsibilities", "requirements", "skills"
    ]
    lowered = user_input.lower()
    if any(k in lowered for k in keywords):
        return True

    if llm:
        try:
            prompt = f"Is the following text a job description for a role (answer yes or no)?\n\n{user_input}\n\nAnswer only 'yes' or 'no'."
            resp = _invoke_with_timeout(prompt)
            return (getattr(resp, 'content', resp) or '').strip().lower().startswith('y')
        except Exception:
            return False

    return False
