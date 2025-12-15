import unittest
from unittest.mock import MagicMock

from backend.base_agent import SingleAgent, ManagerAgent, AgentResponse
from backend.base_tool import BaseTool
from backend.llm_provider import LLMResponse

class MockTool(BaseTool):
    """A simple fake tool for testing."""
    @property
    def name(self): return "mock_tool"
    @property
    def description(self): return "A mock tool."
    @property
    def categories(self): return ["test"]
    
    def get_schema(self):
        return {"name": "mock_tool", "parameters": {}}
    
    def run(self, arg1: str):
        return f"Executed with {arg1}"

class TestSingleAgent(unittest.TestCase):
    def setUp(self):
        # 1. Create a dummy tool
        self.tool = MockTool()
        
        # 2. Initialize Agent with the dummy tool
        self.agent = SingleAgent(
            name="TestWorker", 
            tools=[self.tool], 
            system_prompt="You are a test bot."
        )
        
        # 3. Create a Mock Provider
        self.mock_provider = MagicMock()

    def test_direct_answer(self):
        """Test the simplest case: LLM answers without using tools."""
        # Setup: Provider returns a simple text response
        self.mock_provider.get_response.return_value = LLMResponse(content="Hello World")
        
        response = self.agent.process_query("Hi", self.mock_provider)
        
        # Assertions
        self.assertEqual(response.content, "Hello World")
        self.assertEqual(self.mock_provider.get_response.call_count, 1)

    def test_tool_execution_loop(self):
        """
        Test the multi-step loop:
        1. LLM requests tool -> Agent runs tool -> 2. LLM sees result -> Agent returns answer.
        """
        # Setup: Define the sequence of responses from the Provider
        
        # Turn 1: LLM asks to call 'mock_tool'
        turn_1 = LLMResponse(
            content=None,
            tool_call={"name": "mock_tool", "args": {"arg1": "test_val"}, "id": "call_1"}
        )
        
        # Turn 2: LLM receives the tool output and gives final answer
        turn_2 = LLMResponse(content="Final Answer")
        
        self.mock_provider.get_response.side_effect = [turn_1, turn_2]

        # Execution
        response = self.agent.process_query("Run tool", self.mock_provider)

        # Assertions
        self.assertEqual(response.content, "Final Answer")
        self.assertEqual(self.mock_provider.get_response.call_count, 2)
        
        # Verify the tool was actually run
        # We can't easily spy on the tool method unless we wrap it, 
        # but we can check the logs or the message history passed to the provider.
        
        # Inspect the messages passed to the provider in the SECOND call
        # It should contain the tool result
        second_call_args = self.mock_provider.get_response.call_args_list[1]
        messages_sent = second_call_args[0][0] # 1st arg is 'messages'
        
        # Look for the 'tool' role message
        tool_msg = next((m for m in messages_sent if m["role"] == "tool"), None)
        self.assertIsNotNone(tool_msg)
        self.assertIn("Executed with test_val", tool_msg["content"])

class TestManagerAgent(unittest.TestCase):
    def setUp(self):
        # 1. Create fake workers
        self.price_worker = MagicMock()
        self.price_worker.process_query.return_value = AgentResponse(content="Price is $100")
        
        sub_agents = {"PriceWorker": self.price_worker}
        
        # 2. Create a Mock Memory (The new dependency!)
        self.mock_memory = MagicMock()
        self.mock_memory.get_history.return_value = [] # Return empty history by default
        
        # 3. Initialize Manager with Memory
        self.manager = ManagerAgent(
            name="TestManager", 
            sub_agents=sub_agents, 
            memory=self.mock_memory  # <--- INJECTED
        )
        self.mock_provider = MagicMock()

    def test_manager_uses_memory(self):
        """Test that Manager reads from and writes to memory."""
        # Setup the LLM to return a simple answer
        self.mock_provider.get_response.return_value = LLMResponse(content="Final Answer")
        
        self.manager.process_query("Hello", self.mock_provider)
        
        # Verify it added the user query
        self.mock_memory.add_message.assert_any_call(role="user", content="Hello")
        
        # Verify it fetched history
        self.mock_memory.get_history.assert_called()
        
        # Verify it saved the final answer
        self.mock_memory.add_message.assert_any_call(role="assistant", content="Final Answer")

if __name__ == "__main__":
    unittest.main()