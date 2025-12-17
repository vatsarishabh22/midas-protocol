from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from dataclasses import dataclass
from typing import Optional
from enum import Enum
from dotenv import load_dotenv

from memory import TokenBufferMemory
from agent_factory import AgentFactory
from base_agent import ManagerAgent
from tools import initialize_registry 
from llm_provider import GroqProvider, GeminiProvider, QuotaExhaustedError, ProviderDownError, ProviderError

import time
import uvicorn
import logging
import os
import sys

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("agent_debug.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SystemBackend")

class ChatRequest(BaseModel):
    query: str
    provider: Optional[str] = None  
    api_key: Optional[str] = None  

class ChatResponse(BaseModel):
    success: bool
    response: Optional[str] = None
    provider_used: Optional[str] = None
    agent_used: Optional[str] = None
    error_type: Optional[str] = None
    required_provider: Optional[str] = None 
    message: Optional[str] = None

app = FastAPI()
registry = initialize_registry()
factory = AgentFactory(registry)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YAML_PATH = os.path.join(BASE_DIR, "agents.yaml")
try:
    workers_map = factory.load_from_yaml(YAML_PATH)
    logger.info(f"✅ Successfully loaded agents: {list(workers_map.keys())}")
except FileNotFoundError:
    logger.critical("❌ 'agents.yaml' not found! Please create this configuration file.")
    sys.exit(1)

agent_memory = TokenBufferMemory(max_tokens=4096)

manager_agent = ManagerAgent(
    name="Manager", 
    sub_agents=workers_map,
    memory=agent_memory
    )


class ProviderStatus(Enum):
    ACTIVE = "Active"
    DOWN = "Down"
    QUOTA_EXHAUSTED = "QuotaExhausted"
    ERROR = "Error"

@dataclass
class ProviderState:
    name: str
    status: ProviderStatus
    reset_time: float

class ProviderManager:
    def __init__(self):
        self.providers = {
            "groq": ProviderState(name="groq", status=ProviderStatus.ACTIVE, reset_time=0.0),
            "gemini": ProviderState(name="gemini", status=ProviderStatus.ACTIVE, reset_time=0.0),
        }

    def update_status(self, provider_name: str, status: ProviderStatus):
        self.providers[provider_name].status = status
        if status == ProviderStatus.QUOTA_EXHAUSTED:
            self.providers[provider_name].reset_time = time.time() + (24 * 60 * 60) # 24 hours
        elif status == ProviderStatus.DOWN:
            self.providers[provider_name].reset_time = time.time() + 60 # 60 seconds

    def get_provider(self):
        for name, state in self.providers.items():
            if state.status == ProviderStatus.ACTIVE:
                return name
            elif state.status in [ProviderStatus.DOWN, ProviderStatus.QUOTA_EXHAUSTED]:
                if time.time() > state.reset_time:
                    state.status = ProviderStatus.ACTIVE
                    return name
        return None

    def is_provider_active(self, provider_name: str) -> bool:
        if provider_name not in self.providers:
            return False
        state = self.providers[provider_name]
        if state.status in [ProviderStatus.DOWN, ProviderStatus.QUOTA_EXHAUSTED]:
            if time.time() > state.reset_time:
                state.status = ProviderStatus.ACTIVE
                return True
            return False
            
        return state.status == ProviderStatus.ACTIVE

provider_manager = ProviderManager()

class RequestBody(BaseModel):
    query: str
    provider: Optional[str] = None 
    api_key: Optional[str] = None  

def has_server_key(name: str) -> bool:
    if name == "groq" and os.getenv("GROQ_API_KEY"): return True
    if name == "gemini" and os.getenv("GEMINI_API_KEY"): return True
    return False

def get_provider_instance(name: str, key: str):
    if name == "groq": return GroqProvider(api_key=key)
    elif name == "gemini": return GeminiProvider(api_key=key)
    raise ValueError(f"Unknown provider: {name}")


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    
    # CASE 1: MANUAL OVERRIDE (User specifically asked for a provider)
    if request.provider:
        target = request.provider.lower()
        
        # A. Check if valid/active
        if not provider_manager.is_provider_active(target):
            return ChatResponse(
                success=False, 
                error_type="provider_down", 
                required_provider=target,
                message=f"Requested provider '{target}' is currently unavailable (Down/Quota)."
            )

        # B. Resolve Key
        final_key = request.api_key if request.api_key else None
        if not final_key and has_server_key(target):
            final_key = os.getenv(f"{target.upper()}_API_KEY")
            
        if not final_key:
            return ChatResponse(
                success=False, 
                error_type="needs_key", 
                required_provider=target, 
                message=f"API Key missing for {target}."
            )

        # C. Execute (NO LOOP - Fail fast if user preference fails)
        try:
            logger.info(f"🔄 Executing User Preference: {target}")
            llm = get_provider_instance(target, final_key)
            result = manager_agent.process_query(request.query, llm)
            return ChatResponse(
                success=True, 
                response=result.content, 
                provider_used=target,
                agent_used=manager_agent.name
            )
        except (QuotaExhaustedError, ProviderDownError) as e:
            provider_manager.update_status(target, ProviderStatus.QUOTA_EXHAUSTED) # or check exception type
            return ChatResponse(success=False, error_type="provider_down", message=str(e))
        except Exception as e:
            logger.error(f"Server Error: {e}")
            return ChatResponse(success=False, error_type="server_error", message=str(e))

    # CASE 2: AUTO-PILOT (Loop through available providers)
    else:
        while True:
            current = provider_manager.get_provider()
            
            if not current:
                return ChatResponse(
                    success=False, 
                    error_type="all_down", 
                    message="All providers are currently down or exhausted."
                )
            
            # Check Key for the Auto-Selected candidate
            final_key = None
            if has_server_key(current):
                final_key = os.getenv(f"{current.upper()}_API_KEY")
            
            if not final_key:
                # If Auto-Router picks a provider we have no key for, we must ask the user.
                return ChatResponse(
                    success=False, 
                    error_type="needs_key", 
                    required_provider=current, 
                    message=f"Auto-switching to {current}, but API Key is missing."
                )

            try:
                logger.info(f"🔄 Auto-Routing via: {current}")
                llm = get_provider_instance(current, final_key)
                result = manager_agent.process_query(request.query, llm)
                return ChatResponse(
                    success=True, 
                    response=result.content, 
                    provider_used=current,
                    agent_used=manager_agent.name
                )
            except QuotaExhaustedError:
                provider_manager.update_status(current, ProviderStatus.QUOTA_EXHAUSTED)
                continue # Try next in loop
            except ProviderDownError:
                provider_manager.update_status(current, ProviderStatus.DOWN)
                continue # Try next in loop
            except Exception as e:
                logger.error(f"Critical Error: {e}")
                return ChatResponse(success=False, error_type="server_error", message=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860)) 
    uvicorn.run(app, host="0.0.0.0", port=port)