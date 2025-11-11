# LangSmith Tracing Setup Guide

## Why You Weren't Seeing Traces

Your code was **NOT** showing traces in LangSmith because:

1. ❌ **No LangSmith configuration** - Missing environment variables
2. ❌ **Direct OpenAI client usage** - Using `OpenAI()` directly bypasses LangChain/LangSmith tracing
3. ❌ **Deprecated import** - Using old `langchain.chat_models.ChatOpenAI` instead of `langchain_openai.ChatOpenAI`
4. ❌ **No tracing decorators** - Functions weren't wrapped with `@traceable`

## What I Fixed

✅ Added `langsmith` and `langchain-openai` to `requirements.txt`
✅ Fixed deprecated `ChatOpenAI` import
✅ Wrapped OpenAI client with LangSmith's `wrap_openai()` in `tools.py`
✅ Added `@traceable` decorators to all key functions
✅ Added LangSmith configuration in all files
✅ Set up automatic tracing for LangChain components

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Your LangSmith API Key

1. Go to https://smith.langchain.com/
2. Sign up or log in
3. Go to Settings (top right) → API Keys
4. Create a new API key and copy it

### 3. Configure Environment Variables

Create a `.env` file in your project root with:

```env
# OpenAI API Key (Required)
OPENAI_API_KEY=your_openai_api_key_here

# LangSmith Configuration (Required for tracing)
LANGSMITH_API_KEY=your_langsmith_api_key_here

# LangChain Tracing Configuration
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=interview-agent
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# Optional: For EU region, use:
# LANGCHAIN_ENDPOINT=https://eu.api.smith.langchain.com
```

### 4. Verify Setup

When you start your FastAPI server, you should see:
```
✅ LangSmith tracing is ENABLED
```

If you see:
```
⚠️  LangSmith tracing is DISABLED - Set LANGSMITH_API_KEY in .env to enable
```

Then check your `.env` file.

### 5. View Traces

1. Go to https://smith.langchain.com/
2. Select your project: **interview-agent** (or whatever you set in `LANGCHAIN_PROJECT`)
3. You should see traces appearing in real-time as you use the API

## What Gets Traced

Now the following will be traced in LangSmith:

- ✅ All API endpoints (`start_interview`, `answer_question`)
- ✅ Background tasks (`bg_generate_first_question`, `bg_evaluate_answer`)
- ✅ LLM invocations (`_invoke_with_timeout`)
- ✅ Tool functions (`generate_question`, `evaluate_answer`, `check_relevant_input`)
- ✅ LangChain agent operations (via `ChatOpenAI`)

## Testing

1. Start your FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```

2. Make a request to start an interview:
   ```bash
   curl -X POST "http://127.0.0.1:8000/start_interview" \
     -H "Content-Type: application/json" \
     -d '{"job_description": "Software Engineer"}'
   ```

3. Check LangSmith dashboard - you should see traces appearing!

## Troubleshooting

**Still not seeing traces?**

1. Check that `LANGSMITH_API_KEY` is set correctly in `.env`
2. Verify the API key is valid at https://smith.langchain.com/settings
3. Check the console output when starting the server
4. Make sure you're looking at the correct project in LangSmith dashboard
5. Wait a few seconds - traces may take a moment to appear

**EU Region Users:**
If you signed up in the EU region, use:
```env
LANGCHAIN_ENDPOINT=https://eu.api.smith.langchain.com
```

