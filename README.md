# Financial Multi-Agent System 💸

A professional Multi-Agent system orchestrated by Llama 3 (via Groq) or Gemini Pro.

## Architecture
- **Backend:** FastAPI, Custom Agent Framework (Manager -> Workers), Tool Registry.
- **Frontend:** Streamlit with SOLID principles and 'Bring Your Own Key' security.
- **Agents:**
  - Manager Agent (Orchestrator)
  - Price Worker (YFinance + Calculator)
  - News Worker (DuckDuckGo / YFinance News)

## Features
- **Smart Routing:** Auto-switches between providers.
- **Tool Use:** Agents can use calculators and stock APIs.
- **Memory:** Token-buffered conversation history.
- **Resilience:** Automatic error handling and retries.

## How to Run Locally
1. **Backend:** \`cd backend && pip install -r requirements.txt && python application.py\`
2. **Frontend:** \`cd frontend && pip install -r requirements.txt && streamlit run app.py\`
3. **Tests:** \`pip install pytest && pytest tests\`