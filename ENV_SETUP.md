# Environment Variables Setup for LangSmith Tracing

## Quick Setup

Just set these environment variables in your `.env` file and LangChain will **automatically trace** everything!

## Required Variables

```env
# Your OpenAI API Key
OPENAI_API_KEY=sk-...

# Your LangSmith API Key (get it from https://smith.langchain.com/settings)
LANGSMITH_API_KEY=ls_...
```

## Optional (but recommended)

```env
# Enable tracing (automatically set to 'true' if LANGSMITH_API_KEY is set)
LANGCHAIN_TRACING_V2=true

# Project name in LangSmith dashboard (default: 'interview-agent')
LANGCHAIN_PROJECT=interview-agent

# LangSmith API endpoint (default: https://api.smith.langchain.com)
# For EU region: https://eu.api.smith.langchain.com
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

## Verify Your Setup

Run the test script to check if everything is configured correctly:

```bash
python test.py
```

You should see:
```
✅ LangSmith tracing will be ENABLED
   Your LangChain components (ChatOpenAI, agents, tools) will be traced automatically!
```

## What Gets Traced Automatically

Once environment variables are set, these will be traced **automatically**:

- ✅ `ChatOpenAI` calls (in `interview_agent.py`)
- ✅ `create_react_agent` operations
- ✅ `Tool` usage
- ✅ All LangChain components

## View Your Traces

1. Go to https://smith.langchain.com/
2. Select your project (default: `interview-agent`)
3. You'll see all traces appearing in real-time!

## No Code Changes Needed!

The code automatically detects your environment variables and enables tracing. No decorators or manual tracing code required! 🎉

