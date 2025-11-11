#interview_agent.py
from langchain.agents import create_react_agent, Tool
from tools import generate_question, evaluate_answer_safe, check_relevant_input, _invoke_with_timeout
from langchain_core.prompts import PromptTemplate
from openai import OpenAI
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os

# ====== Load Environment Variables ======
load_dotenv()

# ====== Configure LangSmith Tracing ======
# Set these environment variables in your .env file:
# LANGSMITH_API_KEY=your_api_key_here
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_PROJECT=interview-agent (or your project name)
# LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# Enable tracing if API key is set
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if not os.getenv("LANGCHAIN_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = "interview-agent"
    if not os.getenv("LANGCHAIN_ENDPOINT"):
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

# ====== Initialize LangChain ChatOpenAI (will be traced automatically) ======
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# ====== Initialize OpenAI Client (GPT-4o-mini) ======
# Note: Direct OpenAI client calls won't be traced unless wrapped with LangSmith
client = OpenAI()

def llm_invoke(prompt: str):
    """Helper for invoking GPT-4o-mini."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# ====== DEFINE TOOLS FOR AGENT ======
tools = [
    Tool(
        name="Question Generator",
        func=lambda job_description: generate_question(job_description),
        description="Generates the next relevant interview question based on the job description or topic."
    ),
    Tool(
        name="Answer Evaluator",
        func=lambda input: evaluate_answer_safe(input['question'], input['answer']),
        description="Evaluates the candidate's answer, providing feedback and a score."
    ),
    Tool(
        name="Input Relevance Checker",
        func=lambda user_input: check_relevant_input(user_input),
        description="Checks if the user's input is relevant for a mock interview."
    )
]

# ====== ReAct-Style Prompt ======
react_template = '''Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}'''

prompt = PromptTemplate.from_template(react_template)

# ====== Create the Agent ======
# (We can pass None as llm if your app never calls it directly)
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt,
)

# ====== MOCK INTERVIEW FUNCTION ======
def run_mock_interview(job_description: str, user_answers: list[str]):
    """
    Run a mock interview based on a job description or topic.

    Args:
        job_description (str): The job description or topic for the mock interview.
        user_answers (list[str]): List of candidate answers in order.

    Returns:
        dict: Feedback for each question-answer and a final summary.
    """
    feedback_list = []
    qobj = generate_question(job_description)
    question = qobj.get('question') if isinstance(qobj, dict) else str(qobj)

    for answer in user_answers:
        feedback = evaluate_answer_safe(question, answer)
        feedback_list.append({
            "question": question,
            "answer": answer,
            "feedback": feedback
        })

    # Generate next question
    qobj = generate_question(job_description)
    question = qobj.get('question') if isinstance(qobj, dict) else str(qobj)

    # Generate overall summary
    history_text = "\n".join(
        f"Q: {item['question']}\nA: {item['answer']}\nFeedback: {item['feedback']}"
        for item in feedback_list
    )
    summary_prompt = f"Based on this interview:\n{history_text}\nProvide an overall evaluation, highlighting strengths and areas of improvement."

    try:
        resp = _invoke_with_timeout(summary_prompt)
        final_summary = (getattr(resp, 'content', resp) or '').strip()
    except Exception:
        try:
            final_summary = llm_invoke(summary_prompt)
        except Exception:
            final_summary = "Summary unavailable due to LLM error."

    return {"feedback_list": feedback_list, "summary": final_summary}
