import streamlit as st
import requests
import os
import time
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from huggingface_hub import HfApi

@dataclass
class ProviderConfig:
    """
    Defines the capabilities of a provider.
    Future Proofing: Added 'models' list for granular selection.
    """
    key: str              # Internal ID (groq, gemini)
    display_name: str     # UI Label
    icon: str             # UI Icon
    default_model: str    
    available_models: List[str] = field(default_factory=list)

AVAILABLE_PROVIDERS = [
    ProviderConfig(
        key="groq", 
        display_name="Groq Cloud", 
        icon="⚡", 
        default_model="llama3-70b-8192",
        available_models=["llama3-70b-8192", "mixtral-8x7b-32768"]
    ),
    ProviderConfig(
        key="gemini", 
        display_name="Google Gemini", 
        icon="💎", 
        default_model="gemini-pro",
        available_models=["gemini-pro", "gemini-1.5-flash"]
    ),
]

@dataclass
class AppSettings:
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:7860/chat")
    backend_repo_id: str = os.getenv("BACKEND_REPO_ID", "")
    title: str = "Financial Multi-Agent System"

def ensure_backend_ready(settings: AppSettings):
    # Skip if we've already verified the backend this session
    if st.session_state.get("backend_ready", False):
        return

    health_url = settings.backend_url.rsplit('/', 1)[0] + "/docs"
    hf_token = os.environ.get("HF_TOKEN")
    
    with st.status("Verifying system health...", expanded=True) as status:
        try:
            # Step 1: Fast Ping
            status.write("Pinging backend services...")
            res = requests.get(health_url, timeout=5)
            res.raise_for_status()
            
            status.update(label="System is online and ready!", state="complete", expanded=False)
            st.session_state.backend_ready = True
            return
            
        except requests.exceptions.RequestException:
            status.write("Backend is unresponsive. Initiating auto-recovery...")

        # Step 2: Restart Sequence
        if not hf_token or not settings.backend_repo_id:
            status.update(label="Auto-recovery unavailable (Missing HF configs).", state="error")
            return

        try:
            status.write(f"Calling Hugging Face API to wake {settings.backend_repo_id}...")
            api = HfApi()
            api.restart_space(repo_id=settings.backend_repo_id, token=hf_token)
            status.write("Container restart initiated.")
        except Exception as e:
            status.update(label=f"Failed to trigger restart: {e}", state="error")
            return

        # Step 3: Active Polling
        status.write("Waiting for backend container to spin up (this may take 1-2 minutes)...")
        for attempt in range(1, 25): # 24 attempts * 5 seconds = 2 minutes max
            status.write(f"Polling attempt {attempt}/24...")
            try:
                res = requests.get(health_url, timeout=3)
                if res.status_code == 200:
                    status.update(label="Auto-recovery successful! System is ready.", state="complete", expanded=False)
                    st.session_state.backend_ready = True
                    return
            except requests.exceptions.RequestException:
                pass # Expected while booting
                
            time.sleep(5)

        status.update(label="System recovery timed out. Please refresh the page.", state="error")

class SessionManager:
    """
    Encapsulates all Streamlit Session State logic.
    """
    def __init__(self):
        if "messages" not in st.session_state: st.session_state.messages = []
        if "pending_query" not in st.session_state: st.session_state.pending_query = None
    
    @property
    def messages(self): return st.session_state.messages
    
    def add_message(self, role: str, content: str):
        st.session_state.messages.append({"role": role, "content": content})

    def get_api_key(self, provider_key: str) -> Optional[str]:
        return st.session_state.get(f"key_{provider_key}", None)

    def set_api_key(self, provider_key: str, key_value: str):
        st.session_state[f"key_{provider_key}"] = key_value

    def set_pending_query(self, query: str):
        st.session_state.pending_query = query

    def pop_pending_query(self) -> Optional[str]:
        q = st.session_state.pending_query
        st.session_state.pending_query = None
        return q

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def send_chat(self, query: str, provider: str, api_key: Optional[str]) -> Dict:
        try:
            # Future Proofing: Sending 'model' here requires updating backend first
            payload = {
                "query": query, 
                "provider": provider, 
                "api_key": api_key
            }
            res = requests.post(self.base_url, json=payload, timeout=120)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            # Return a consistent error structure
            return {"success": False, "error_type": "client_error", "message": str(e)}

class SidebarComponent:
    def render(self, providers: List[ProviderConfig]) -> tuple[Optional[str], ProviderConfig]:
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # Dynamic Provider Selection
            # This loops through config, making it extensible
            provider_names = [p.display_name for p in providers]
            selected_name = st.selectbox("Select Provider", provider_names)
            
            # Find the config object for the selected name
            active_config = next(p for p in providers if p.display_name == selected_name)
            
            # Dynamic Model Selection (Future Proofing)
            st.selectbox(f"{active_config.icon} Model", active_config.available_models)
            
            # API Key Input
            api_key = st.text_input(
                f"{active_config.display_name} Key", 
                type="password",
                help=f"Enter key for {active_config.key}"
            )
            
            st.divider()
            
            # Quick Actions (Could also be data-driven in future)
            st.caption("Quick Tests")
            if st.button("💰 TSLA Price Check"):
                st.session_state.pending_query = "Check Tesla price"
                
            return api_key, active_config

class ChatComponent:
    def render_history(self, messages):
        for msg in messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    def render_recovery_form(self, provider_key: str, message: str) -> Optional[str]:
        """
        Renders the 'Needs Key' form. Returns the new key if submitted.
        """
        with st.container():
            st.warning(f"⚠️ {message}")
            with st.form(f"fix_{provider_key}"):
                val = st.text_input(f"Enter {provider_key.upper()} Key:", type="password")
                if st.form_submit_button("Retry"):
                    return val
        return None

class Application:
    def __init__(self):
        self.settings = AppSettings()
        self.session = SessionManager()
        self.client = APIClient(self.settings.backend_url)
        self.sidebar = SidebarComponent()
        self.chat = ChatComponent()

    def run(self):
        st.set_page_config(page_title=self.settings.title, layout="wide")
        st.title(self.settings.title)

        ensure_backend_ready(self.settings)

        # 1. Sidebar
        user_key, config = self.sidebar.render(AVAILABLE_PROVIDERS)
        if user_key:
            self.session.set_api_key(config.key, user_key)

        # 2. History
        self.chat.render_history(self.session.messages)

        # 3. Input Handling
        query = self.session.pop_pending_query() or st.chat_input("Input query...")
        
        if query:
            self.process_query(query, config)

    def process_query(self, query: str, config: ProviderConfig):
        # Optimistic UI Update
        self.session.add_message("user", query)
        with st.chat_message("user"): st.markdown(query)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ *Thinking...*")

            # Resolve Key: User Input > Session Store
            # This allows the sidebar input to override everything
            final_key = self.session.get_api_key(config.key)

            # API Call
            response = self.client.send_chat(query, config.key, final_key)

            # Handle Response
            if response.get("success"):
                content = response["response"]
                placeholder.markdown(content)
                self.session.add_message("assistant", content)
            
            elif response.get("error_type") == "needs_key":
                placeholder.empty()
                new_key = self.chat.render_recovery_form(
                    response["required_provider"], 
                    response["message"]
                )
                if new_key:
                    # Save and Retry
                    self.session.set_api_key(response["required_provider"], new_key)
                    self.session.set_pending_query(query)
                    st.rerun()
            else:
                placeholder.error(f"❌ {response.get('message')}")

if __name__ == "__main__":
    app = Application()
    app.run()