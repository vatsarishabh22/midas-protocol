import unittest
from backend.memory import TokenBufferMemory

class TestMemory(unittest.TestCase):
    def setUp(self):
        # Use a small limit to trigger eviction easily
        self.memory = TokenBufferMemory(max_tokens=10)

    def test_add_and_retrieve(self):
        """Test basic storage."""
        self.memory.add_message("user", "Hi")
        history = self.memory.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "Hi")

    def test_eviction_logic(self):
        """Test that old messages are removed when limit is exceeded."""
        # "Hello" is ~1 token. We add enough to overflow 10 tokens.
        
        # 1. Fill the buffer
        self.memory.add_message("user", "Message 1") # ~2 tokens
        self.memory.add_message("assistant", "Message 2") # ~2 tokens
        self.memory.add_message("user", "Message 3") # ~2 tokens
        
        # 2. Add a massive message that forces eviction
        long_text = "This is a very long message that will force the older ones out."
        self.memory.add_message("user", long_text)
        
        history = self.memory.get_history()
        
        # 3. Verify Message 1 is GONE (FIFO eviction)
        self.assertNotIn("Message 1", [m["content"] for m in history])
        # 4. Verify the new message is THERE
        self.assertIn(long_text, [m["content"] for m in history])

    def test_clear(self):
        self.memory.add_message("user", "test")
        self.memory.clear()
        self.assertEqual(len(self.memory.get_history()), 0)