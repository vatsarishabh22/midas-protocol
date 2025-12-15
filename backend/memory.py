import tiktoken
from abc import ABC, abstractmethod
from typing import List, Dict
import logging

logger = logging.getLogger("FinancialAgent")

class BaseMemory(ABC):
    """
    Abstract Base Class for memory management.
    """
    @abstractmethod
    def add_message(self, role: str, content: str):
        pass

    @abstractmethod
    def get_history(self) -> List[Dict[str, str]]:
        pass

    @abstractmethod
    def clear(self):
        pass

class TokenBufferMemory(BaseMemory):
    """
    Memory that keeps conversation within a strict token limit.
    Uses a FIFO (First-In-First-Out) eviction strategy when full.
    """
    def __init__(self, max_tokens: int = 4096, encoding_name: str = "cl100k_base"):
        self.max_tokens = max_tokens
        self.messages = []
        # cl100k_base is the encoding for GPT-4 and acts as a good standard proxy
        self.tokenizer = tiktoken.get_encoding(encoding_name) 

    def _count_tokens(self, text: str) -> int:
        """Helper to count tokens in a string."""
        try:
            return len(self.tokenizer.encode(text))
        except Exception:
            # Fallback for empty strings or weird encoding errors
            return 0

    def _evict_if_needed(self):
        """
        Removes oldest messages until we are under the token limit.
        Safety: Never deletes the most recent message (index -1), 
        so we always have at least the latest context.
        """
        while len(self.messages) > 1:  
            current_buffer_tokens = sum(self._count_tokens(m["content"]) for m in self.messages)
            
            if current_buffer_tokens <= self.max_tokens:
                break
            
            # Remove the oldest message
            removed = self.messages.pop(0)
            logger.info(f"🧹 Memory Full. Evicted message: {removed['role']} ({len(removed['content'])} chars)")

    def add_message(self, role: str, content: str):
        """Adds a message and triggers eviction check."""
        self.messages.append({"role": role, "content": content})
        self._evict_if_needed()

    def get_history(self) -> List[Dict[str, str]]:
        return self.messages

    def clear(self):
        self.messages = []