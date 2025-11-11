#main.py
from fastapi import FastAPI
import os
from dotenv import load_dotenv
from api import router

# Load environment variables
load_dotenv()

# ====== Configure LangSmith Tracing ======
# Set these environment variables in your .env file:
# LANGSMITH_API_KEY=your_api_key_here
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_PROJECT=interview-agent (or your project name)
# LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if not os.getenv("LANGCHAIN_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = "interview-agent"
    if not os.getenv("LANGCHAIN_ENDPOINT"):
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    print("✅ LangSmith tracing is ENABLED")
else:
    print("⚠️  LangSmith tracing is DISABLED - Set LANGSMITH_API_KEY in .env to enable")

app = FastAPI(title="AI Mock Interview Agent (OpenAI GPT-4o-mini)")

# include your API router
app.include_router(router)

# add root route to avoid 404
@app.get("/")
def read_root():
    return {"message": "Welcome to AI Mock Interview Agent. Use /docs for API documentation."}
