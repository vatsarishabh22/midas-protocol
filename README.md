This is the final touch of professionalism. A great `README.md` is the difference between a "script" and a "product."

Here is a comprehensive, developer-focused `README.md` for the root of your repository. It synthesizes every architectural decision, pattern, and feature we have built.

### **Action Plan**

1. **Copy** the content below.
2. **Overwrite** your current root `README.md`.
3. **Commit & Push:** `git add README.md`, `git commit -m "docs: update global readme"`, `git push`.

---

# 🦁 Midas Protocol

**A Production-Grade Financial Multi-Agent System**

## 📖 Overview

**Midas Protocol** is a resilient, decoupled Microservices architecture designed to orchestrate autonomous AI Agents for financial analysis. Unlike standard chatbot wrappers, Midas implements a custom **ReAct Reasoning Engine** capable of coordinating specialized workers (Price Analysts, News Reporters) to solve complex user queries.

It features a **Circuit Breaker** architecture to handle LLM API failures (Rate Limits, Downtime) and a **Dynamic Negotiation Protocol** that allows the system to recover from missing credentials in real-time without crashing.

---

## 🏗️ System Architecture

The project follows a **Client-Server Microservices** pattern, deployed via a Monorepo structure.

### 1. The Brain (Backend)

* **Framework:** FastAPI (Python 3.11)
* **Orchestration:** Custom `ManagerAgent` implementing the **Composite Pattern**.
* **Reasoning:** Recursive delegation loop. The Manager treats Sub-Agents as "Tools" and can delegate tasks dynamically.
* **Resilience:**
* **Circuit Breaker:** Tracks provider health (`ACTIVE`, `DOWN`, `QUOTA_EXHAUSTED`).
* **Auto-Routing:** Automatically switches from Groq (Llama-3) to Gemini (Pro) if rate limits are hit.
* **Request-Scoped Auth:** API Keys are injected per request to prevent cross-user state pollution in serverless environments.



### 2. The Face (Frontend)

* **Framework:** Streamlit
* **Role:** State Management & User Interface.
* **Recovery Flow:** Intercepts `needs_key` errors from the backend and renders specific input forms to ask the user for missing credentials on the fly.

### 3. The DevOps Pipeline

* **CI/CD:** GitHub Actions (Native Shell Scripts).
* **Strategy:** "Monorepo Mirroring".
* Detects changes in `backend/` or `frontend/`.
* Dynamically initializes a temporary git repo for the subfolder.
* Force-pushes the specific folder to its corresponding **Hugging Face Space** (`midas-backend` or `midas-frontend`).


* **Optimization:** Uses `ARG CACHEBUST` in Docker to force strict code updates on cloud providers.

---

## 📂 Project Structure

```text
midas-protocol/
├── .github/workflows/   # CI/CD Pipelines
│   └── deploy.yml       # The "Split & Push" automation script
├── backend/             # The FastAPI Logic Core
│   ├── agents.yaml      # Declarative Agent Definitions
│   ├── agent_factory.py # Factory Pattern for loading agents
│   ├── application.py   # FastAPI App & Circuit Breaker Logic
│   ├── base_agent.py    # Abstract Base Classes (Manager/Worker)
│   ├── llm_provider.py  # Strategy Pattern (Groq/Gemini wrappers)
│   ├── memory.py        # TokenBufferMemory (FIFO Eviction)
│   ├── tools.py         # Financial Tool Implementations
│   └── Dockerfile       # Python 3.11 Container Def
├── frontend/            # The Streamlit UI
│   ├── app.py           # UI Logic & Session State
│   └── requirements.txt # UI Dependencies
└── tests/               # Unit Testing Suite
    ├── test_agents.py   # Agent ReAct Loop Verification
    ├── test_backend.py  # API Endpoint & Mock Testing
    └── test_memory.py   # Token Counting & Eviction Logic

```

---

## ⚡ Key Features & Patterns

### 🧠 Agentic Patterns

* **Composite Pattern:** `ManagerAgent` is composed of `SingleAgent` workers. The Manager builds its own "Tool Definitions" based on the team roster.
* **Factory Pattern:** Agents are decoupled from their creation logic. `AgentFactory` reads `yaml` configs and injects dependencies (Tools, Prompts) at runtime.
* **Token-Aware Memory:** `TokenBufferMemory` uses `tiktoken` to enforce strict context windows (4096 tokens), preventing overflow errors.

### 🛡️ Resilience Patterns

* **Strategy Pattern:** `LLMProvider` abstract base class allows hot-swapping between `GroqProvider` and `GeminiProvider`.
* **Failover Logic:** If the primary provider fails (503/429), the system marks it as `DOWN` and immediately retries with the next available provider in the pool.
* **Soft Error Handling:** Tool failures (e.g., "Ticker not found") are caught and returned as observations, allowing the Agent to self-correct rather than crashing.

---

## 🚀 Getting Started

### Prerequisites

* Python 3.11+
* Docker (Optional)
* API Keys: Groq Cloud (Llama-3) or Google AI Studio (Gemini).

### Local Development

1. **Clone the Repository**
```bash
git clone https://github.com/your-username/midas-protocol.git
cd midas-protocol

```


2. **Run the Backend**
```bash
cd backend
pip install -r requirements.txt
# Create .env file with keys (optional, or pass via UI)
uvicorn application:app --reload --port 7860

```


3. **Run the Frontend** (In a new terminal)
```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py

```


4. **Access:** Open `http://localhost:8501`.

### Running Tests

We use `unittest` with extensive mocking to simulate LLM behavior without spending API credits.

```bash
# From the root directory
python -m unittest discover tests

```

---

## ☁️ Deployment (CI/CD)

The project uses a custom **GitHub Actions** workflow to sync this Monorepo to two separate Hugging Face Spaces.

**Workflow Logic (`deploy.yml`):**

1. **Trigger:** Push to `main`.
2. **Job 1 (Backend):** Moves into `backend/`, initializes a fresh git repo, and force-pushes to the `midas-backend` HF Space.
3. **Job 2 (Frontend):** Moves into `frontend/`, initializes a fresh git repo, and force-pushes to the `midas-frontend` HF Space.

**Environment Secrets Required (GitHub):**

* `HF_TOKEN`: Hugging Face Write Token.

---

## 🗺️ Roadmap

* [x] **Phase 1: Foundation:** Decoupled Architecture, Basic Agents, CI/CD.
* [x] **Phase 2: Reliability:** Circuit Breakers, Auto-Recovery, Unit Testing.
* [ ] **Phase 3: Intelligence:** RAG Integration (Vector DB) for long-term memory.
* [ ] **Phase 4: Observability:** LangSmith/Arize Phoenix integration for tracing.

---