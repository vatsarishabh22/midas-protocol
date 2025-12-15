import yfinance as yf
from typing import Dict, Any, List
from base_tool import BaseTool
from registry import ToolRegistry

import logging
logger = logging.getLogger("FinancialAgent")


# backend/tools.py

# backend/tools.py

from typing import Dict, Any, List
# import BaseTool if it's in a separate file, or assume it's available

class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Perform basic arithmetic operations. Use this for calculating differences, ratios, or percentages."
    categories = ["utils"]  

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["add", "subtract", "multiply", "divide"],
                            "description": "The math operation to perform."
                        },
                        "x": {
                            "type": "number",
                            "description": "The first number."
                        },
                        "y": {
                            "type": "number",
                            "description": "The second number."
                        }
                    },
                    "required": ["operation", "x", "y"]
                }
            }
        }

    def run(self, operation: str, x: float, y: float) -> Any:
        try:
            # Ensure numbers are floats (in case string is passed)
            x, y = float(x), float(y)
            
            if operation == "add":
                return {"result": x + y}
            elif operation == "subtract":
                return {"result": x - y}
            elif operation == "multiply":
                return {"result": x * y}
            elif operation == "divide":
                if y == 0:
                    return {"error": "Error: Division by zero"}
                return {"result": x / y}
            else:
                return {"error": f"Unknown operation: {operation}"}
        except Exception as e:
            return {"error": f"Math execution failed: {str(e)}"}


class StockPriceTool(BaseTool):
    name = "get_stock_price"
    description = "Get the current price of a stock using its Ticker Symbol."
    categories = ["finance"]

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker_symbol": {"type": "string", "description": "The stock ticker (e.g., AAPL)"}
                    },
                    "required": ["ticker_symbol"]
                }
            }
        }

    def run(self, ticker_symbol: str) -> Dict:
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.fast_info
            return {"ticker": ticker_symbol, "price": info.last_price, "currency": info.currency}
        except Exception as e:
            return {"error": str(e)}


class CompanyNewsTool(BaseTool):
    name = "get_company_news"
    description = "Get the latest news summaries about a company."
    categories = ["news"]

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker_symbol": {"type": "string", "description": "The stock ticker"},
                        "num_stories": {"type": "integer", "description": "Number of stories"}
                    },
                    "required": ["ticker_symbol", "num_stories"]
                }
            }
        }

    def run(self, ticker_symbol: str, num_stories: int = 5) -> Dict:
        try:
            ticker = yf.Ticker(ticker_symbol)
            news = ticker.news[:num_stories] if ticker.news else []
            if len(news) == 0:
                return {"error": f'HTTP Error 404: ${ticker_symbol}: possibly delisted; Quote not found for symbol'}
            return {"ticker": ticker_symbol, "news": [n['content']['title'] for n in news], "storiesFetched": len(news)}
        except Exception as e:
            return {"error": str(e)}

def initialize_registry() -> ToolRegistry:
    registry = ToolRegistry()
    tools_list = [
        StockPriceTool(),
        CompanyNewsTool(),
        CalculatorTool() 
    ]
    for tool in tools_list:
        registry.register(tool)
    return registry


if __name__ == "__main__":

    pass