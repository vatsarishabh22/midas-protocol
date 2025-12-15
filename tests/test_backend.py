import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.application import app, provider_manager, ProviderStatus, QuotaExhaustedError

class TestBackendAPI(unittest.TestCase):
    def setUp(self):
        # TestClient runs the FastAPI app in memory
        self.client = TestClient(app)

    # --- TEST 1: SUCCESSFUL CHAT ---
    @patch("backend.application.provider_manager")
    @patch("backend.application.manager_agent")      
    @patch("backend.application.get_provider_instance") 
    def test_chat_success(self, mock_get_instance, mock_manager, mock_prov_manager):
        """
        Scenario: Standard successful request using the first available provider.
        """
        # 1. Setup the Provider Manager to return "groq"
        mock_prov_manager.get_provider.return_value = "groq"
        
        # 2. Setup the Factory to return a fake provider object
        mock_provider = MagicMock()
        mock_get_instance.return_value = mock_provider

        # 3. Setup the Manager Agent to return a success response
        # The backend expects an AgentResponse object with a .content attribute
        mock_response_obj = MagicMock()
        mock_response_obj.content = "Manager Report: Market is bullish."
        mock_manager.process_query.return_value = mock_response_obj
        
        # Mock the name attribute since backend access manager_agent.name
        mock_manager.name = "Manager"

        # 4. Make the Request
        payload = {"query": "How is AAPL?"}
        response = self.client.post("/chat", json=payload)

        # 5. Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify the content
        self.assertEqual(data["response"], "Manager Report: Market is bullish.")
        self.assertEqual(data["provider_used"], "groq")
        self.assertEqual(data["agent_used"], "Manager") # New field verification
        
        # Verify we called the MANAGER, not the single agent
        mock_manager.process_query.assert_called_once()

    # --- TEST 2: ALL PROVIDERS DOWN ---
    @patch("backend.application.provider_manager")
    def test_service_unavailable(self, mock_prov_manager):
        """
        Scenario: All providers are down (get_provider returns None).
        """
        mock_prov_manager.get_provider.return_value = None

        response = self.client.post("/chat", json={"query": "Hello"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("All LLM providers are down", response.json()["detail"])

    # --- TEST 3: FAILOVER LOGIC ---
    @patch("backend.application.provider_manager")
    @patch("backend.application.manager_agent")      # <--- CHANGED: Mocking Manager
    @patch("backend.application.get_provider_instance")
    def test_failover_logic(self, mock_get_instance, mock_manager, mock_prov_manager):
        """
        Scenario: Groq fails with QuotaExhausted, loop retries with Gemini.
        """
        # 1. Manager Sequence: 
        # First call -> "groq", Second call -> "gemini"
        mock_prov_manager.get_provider.side_effect = ["groq", "gemini"]

        # 2. Agent Sequence:
        # First call (Groq) -> Raises QuotaExhaustedError
        # Second call (Gemini) -> Returns Success
        mock_success_response = MagicMock()
        mock_success_response.content = "Gemini to the rescue!"
        
        mock_manager.process_query.side_effect = [
            QuotaExhaustedError("Rate limit hit"), # 1st try
            mock_success_response                  # 2nd try
        ]
        mock_manager.name = "Manager"

        # 3. Execute
        response = self.client.post("/chat", json={"query": "Heavy load"})

        # 4. Assertions
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider_used"], "gemini")
        self.assertEqual(response.json()["response"], "Gemini to the rescue!")

        # CRITICAL: Verify that the Provider Manager marked Groq as exhausted
        mock_prov_manager.update_status.assert_called_with("groq", ProviderStatus.QUOTA_EXHAUSTED)

if __name__ == "__main__":
    unittest.main()