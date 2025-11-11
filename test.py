import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

print("=" * 60)
print("LangSmith Tracing Configuration Check")
print("=" * 60)

# Required environment variables for LangSmith tracing
required_vars = {
    "OPENAI_API_KEY": "Required for OpenAI API calls",
    "LANGSMITH_API_KEY": "Required for LangSmith tracing",
}

# Optional but recommended
optional_vars = {
    "LANGCHAIN_TRACING_V2": "Should be 'true' to enable tracing",
    "LANGCHAIN_PROJECT": "Project name in LangSmith (default: 'interview-agent')",
    "LANGCHAIN_ENDPOINT": "LangSmith API endpoint (default: https://api.smith.langchain.com)",
}

print("\n📋 REQUIRED Variables:")
print("-" * 60)
all_required_set = True
for var, desc in required_vars.items():
    value = os.getenv(var)
    if value:
        masked = value[:10] + "..." + value[-4:] if len(value) > 14 else value[:10] + "..."
        print(f"✅ {var:25s} = {masked:30s} ({desc})")
    else:
        print(f"❌ {var:25s} = NOT SET!          ({desc})")
        all_required_set = False

print("\n📋 OPTIONAL Variables:")
print("-" * 60)
for var, desc in optional_vars.items():
    value = os.getenv(var)
    if value:
        print(f"✅ {var:25s} = {value:30s} ({desc})")
    else:
        print(f"⚠️  {var:25s} = NOT SET           ({desc})")

print("\n" + "=" * 60)
if all_required_set:
    # Check if tracing will be enabled
    if os.getenv("LANGSMITH_API_KEY"):
        print("✅ LangSmith tracing will be ENABLED")
        print("   Your LangChain components (ChatOpenAI, agents, tools) will be traced automatically!")
        project = os.getenv("LANGCHAIN_PROJECT", "interview-agent")
        print(f"   Project name: {project}")
        print(f"   View traces at: https://smith.langchain.com/")
    else:
        print("❌ LangSmith tracing will be DISABLED")
        print("   Set LANGSMITH_API_KEY in your .env file to enable tracing")
else:
    print("❌ Missing required environment variables!")
    print("   Please set all required variables in your .env file")

print("=" * 60)
