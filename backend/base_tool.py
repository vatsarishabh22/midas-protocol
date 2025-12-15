from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseTool(ABC):
    """
    The universal contract for any capability.
    Enforces structure so the Agent Loader can handle any tool automatically.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier (e.g., 'get_stock_price')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Natural language instruction for the LLM."""
        pass

    @property
    @abstractmethod
    def categories(self) -> List[str]:
        """Tags for the Registry (e.g., ['finance', 'public_api'])."""
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Returns the JSON schema for LLM function calling."""
        pass

    @abstractmethod
    def run(self, **kwargs) -> Any:
        """Executes the tool logic."""
        pass