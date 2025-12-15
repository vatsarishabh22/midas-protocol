from typing import Dict, List
from base_tool import BaseTool

class ToolRegistry:
    def __init__(self):
        # Index 1: Look up by Name (for execution)
        self._tools_by_name: Dict[str, BaseTool] = {}
        
        # Index 2: Look up by Category (for subscription)
        self._tools_by_category: Dict[str, List[BaseTool]] = {}

    def register(self, tool: BaseTool):
        if tool.name in self._tools_by_name:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        
        # 1. Add to Main Index
        self._tools_by_name[tool.name] = tool

        # 2. Add to Category Index
        for category in tool.categories:
            if category not in self._tools_by_category:
                self._tools_by_category[category] = []
            self._tools_by_category[category].append(tool)

    def get_tool(self, name: str) -> BaseTool:
        return self._tools_by_name.get(name)

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        return self._tools_by_category.get(category, [])