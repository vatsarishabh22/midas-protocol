import streamlit as st
import requests
import os
from typing import Optional, Dict, List
from dataclasses import dataclass

@dataclass
class AppConfig:
    PAGE_TITLE: str = "Financial Agent Team"
    PAGE_ICON: str = "📈"
    # Use the environment variable or default to localhost
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:7860/chat")
    TIMEOUT: int = 120

@dataclass
class UserSession:
    """Handles session state safely."""
    @property
    def messages(self) -> List[Dict[str, str]]:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        return st.session_state.messages

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
    
    # NEW: Handling Pending Actions from Callbacks
    @property
    def pending_query(self) -> Optional[str]:
        return st.session_state.get("pending_query", None)
    
    def set_pending_query(self, query: str):
        st.session_state.pending_query = query
        
    def clear_pending_query(self):
        if "pending_query" in st.session_state:
            del st.session_state.pending_query

class BackendClient:
    def __init__(self, base_url: str, timeout: int):
        self.base_url = base_url
        self.timeout = timeout

    def send_query(self, query: str, provider: str, api_key: str) -> Dict:
        headers = {
            "Content-Type": "application/json",
            f"x-{provider.lower()}-api-key": api_key
        }
        payload = {"query": query, "provider": provider.lower()}

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                return {"error": f"API Error: {e.response.json().get('detail', str(e))}"}
            except:
                return {"error": f"HTTP Error: {str(e)}"}
        except requests.exceptions.ConnectionError:
            return {"error": "Connection failed. Is the backend running?"}
        except Exception as e:
            return {"error": f"Unexpected Error: {str(e)}"}

class SidebarUI:
    def __init__(self, session: UserSession):
        self.session = session

    def render(self) -> tuple[str, str]:
        with st.sidebar:
            st.header("🔑 Authentication")
            provider = st.radio("Select Provider", ["Groq", "Gemini"], index=0)
            api_key = st.text_input(f"{provider} API Key", type="password")
            
            st.divider()
            st.header("⚡ Quick Actions")
            
            # CALLBACK PATTERN: 
            # We use 'on_click' to set the state immediately.
            # 'use_container_width=True' makes the button full width (clickable area).
            
            st.button(
                "💰 Tesla vs Google Diff", 
                on_click=self.session.set_pending_query,
                args=("Get the current share price of Tesla and Google, and calculate the price difference between them.",),
                use_container_width=True
            )
            
            st.button(
                "📰 Apple News Summary",
                on_click=self.session.set_pending_query,
                args=("Summarize the latest news headlines for Apple.",),
                use_container_width=True
            )
                
            st.divider()
            return api_key, provider

class ChatUI:
    def render_header(self, provider: str):
        st.title("💸 Financial Multi-Agent System")
        
        # DYNAMIC ARCHITECTURE DIAGRAM TEXT
        # Displays the flow based on the selected provider
        if provider == "Groq":
            arch_text = "Architecture: Manager (Llama-3) → [Price Worker, News Worker] → Groq Cloud"
        else:
            arch_text = "Architecture: Manager (Gemini Pro) → [Price Worker, News Worker] → Google AI"
            
        st.caption(arch_text)
        
        # Visual Divider
        st.markdown("---")

    def render_messages(self, messages: List[Dict[str, str]]):
        for msg in messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

class FinancialApp:
    def __init__(self):
        self.config = AppConfig()
        self.session = UserSession()
        self.client = BackendClient(self.config.BACKEND_URL, self.config.TIMEOUT)
        self.sidebar = SidebarUI(self.session)
        self.chat_ui = ChatUI()

        st.set_page_config(
            page_title=self.config.PAGE_TITLE,
            page_icon=self.config.PAGE_ICON,
            layout="wide"
        )

    def run(self):
        # 1. Render Sidebar
        api_key, provider = self.sidebar.render()

        # 2. Render Header (Dynamic)
        self.chat_ui.render_header(provider)

        # 3. Render History
        self.chat_ui.render_messages(self.session.messages)

        # 4. Handle Input sources
        # Priority: Pending Callback Query > Chat Input
        active_query = self.session.pending_query
        
        # If no pending query, check chat input
        if not active_query:
            active_query = st.chat_input("Ask a financial question...")

        # 5. Process Query
        if active_query:
            # Clear pending state so we don't loop
            self.session.clear_pending_query()
            
            self.handle_interaction(active_query, api_key, provider)
            
            # Force refresh to show the result
            st.rerun()

    def handle_interaction(self, query: str, api_key: str, provider: str):
        if not api_key:
            st.warning(f"⚠️ Please enter your {provider} API Key in the sidebar.")
            return

        # 1. Optimistic Update (Show user question immediately)
        self.session.add_message("user", query)
        with st.chat_message("user"):
            st.markdown(query)
        
        # 2. Backend Call
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("🕵️ *Manager is coordinating agents...*")
            
            result = self.client.send_query(query, provider, api_key)
            
            if "error" in result:
                placeholder.error(result["error"])
            else:
                final_response = result.get("response", "No response received.")
                placeholder.markdown(final_response)
                self.session.add_message("assistant", final_response)

if __name__ == "__main__":
    app = FinancialApp()
    app.run()