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

provider_manager = ProviderManager()

class RequestBody(BaseModel):
    query: str
    provider: Optional[str] = None 


def get_provider_instance(provider_name: str):
    if provider_name == "groq":
        return GroqProvider(api_key=os.getenv("GROQ_API_KEY"))
    elif provider_name == "gemini":
        return GeminiProvider(api_key=os.getenv("GEMINI_API_KEY"))
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


@app.post("/chat")
async def chat_endpoint(request: RequestBody):
    
    while True:
        current_provider_name = provider_manager.get_provider()
        if current_provider_name is None:
            raise HTTPException(status_code=503, detail="All LLM providers are down or exhausted.")
            
        try:
            logger.info(f"🔄 Routing request via Provider: {current_provider_name}")
            provider = get_provider_instance(current_provider_name)
            final_response = manager_agent.process_query(request.query, provider)
            return {
                "provider_used": current_provider_name,
                "agent_used": manager_agent.name,
                "query": request.query,
                "response": final_response.content
            }
        except QuotaExhaustedError:
            logger.warning(f"Provider {current_provider_name} Quota Exhausted. Switching...")
            provider_manager.update_status(current_provider_name, ProviderStatus.QUOTA_EXHAUSTED)
            continue

        except ProviderDownError:
            logger.warning(f"Provider {current_provider_name} is Down. Switching...")
            provider_manager.update_status(current_provider_name, ProviderStatus.DOWN)
            continue

        except ProviderError as pe:
            logger.error(f"Provider '{current_provider_name}' Error: {pe}")
            provider_manager.update_status(current_provider_name, ProviderStatus.DOWN)
            continue

        except Exception as e:
            logger.error(f"Critical Server Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860)) 
    uvicorn.run(app, host="0.0.0.0", port=port)