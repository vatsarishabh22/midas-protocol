import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from groq import Groq
from google import genai
from google.genai import types


class ProviderError(Exception):
    """Base class for all provider issues."""
    pass

class QuotaExhaustedError(ProviderError):
    """Raised when we run out of credits/limit."""
    pass

class ProviderDownError(ProviderError):
    """Raised when the provider is temporarily broken (500, 429)."""
    pass


class LLMResponse(BaseModel):
    content: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None


class LLMProvider(ABC):
    @abstractmethod
    def get_response(self, messages: List[Dict[str, str]], tools: List[Dict]) -> LLMResponse:
        """
        Args:
            messages: Full conversation history [{"role": "user", "content": "..."}, ...]
            tools: JSON Schema definitions for tools.
        """
        pass


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = 'llama-3.1-8b-instant'):
        self.client = Groq(api_key=api_key)
        self.model_name = model_name

    def get_response(self, messages: List[Dict[str, str]], tools: List[Dict]) -> LLMResponse:
        try:
            # Groq/OpenAI native format
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.1
            )

            candidate = response.choices[0]
            
            # Check for tool calls
            if candidate.message.tool_calls:
                # We take the first tool call
                tool_call_data = candidate.message.tool_calls[0]
                return LLMResponse(
                    tool_call={
                        "name": tool_call_data.function.name,
                        "args": json.loads(tool_call_data.function.arguments),
                        "id": tool_call_data.id # Store ID for history tracking
                    }
                )
            
            # Return text content
            return LLMResponse(content=candidate.message.content)

        except Exception as e:
            error_msg = str(e).lower()
            if "resource_exhausted" in error_msg or "quota" in error_msg:
                raise QuotaExhaustedError("Groq Quota Exhausted")
            else:
                raise ProviderDownError(f"Groq Error: {e}")


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str = 'gemini-2.0-flash'):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def _map_tools(self, tools: List[Dict]) -> List[types.Tool]:
        """
        Converts OpenAI/Groq-style tool definitions into Gemini types.Tool objects.
        """
        gemini_tools = []
        for t in tools:
            # Check if it matches the OpenAI schema {"type": "function", "function": {...}}
            if t.get("type") == "function":
                func_def = t["function"]
                
                # Create the Gemini-specific FunctionDeclaration
                fn_decl = types.FunctionDeclaration(
                    name=func_def["name"],
                    description=func_def.get("description"),
                    parameters=func_def.get("parameters")
                )
                
                # Wrap it in a Tool object
                gemini_tools.append(types.Tool(function_declarations=[fn_decl]))
        return gemini_tools

    def _default_history_format(self, messages: List[Dict]) -> str:
         formatted_prompt = ""
         for msg in messages:
             role = msg["role"]
             content = msg.get("content", "") or ""
             if role == "system":
                 formatted_prompt += f"System Instruction: {content}\n\n"
             elif role == "user":
                 formatted_prompt += f"User: {content}\n"
             elif role == "assistant":
                 if "tool_calls" in msg:
                     tc = msg["tool_calls"][0]
                     formatted_prompt += f"Assistant (Thought): I will call tool '{tc['function']['name']}' with args {tc['function']['arguments']}.\n"
                 else:
                     formatted_prompt += f"Assistant: {content}\n"
             elif role == "tool":
                 formatted_prompt += f"Tool Output ({msg.get('name')}): {content}\n"
         formatted_prompt += "\nBased on the history above, provide the next response or tool call."
         return formatted_prompt

    def get_response(self, messages: List[Dict[str, str]], tools: List[Dict]) -> LLMResponse:
        try:
            # 1. Translate History
            full_prompt = self._default_history_format(messages)
            
            gemini_messages = [
                types.Content(role="user", parts=[types.Part(text=full_prompt)])
            ]

            # 2. Translate Tools 
            mapped_tools = self._map_tools(tools)

            config = types.GenerateContentConfig(
                tools=mapped_tools, 
                temperature=0.0
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=gemini_messages,
                config=config,
            )
            
            candidate = response.candidates[0]
            function_call_part = None
            for part in candidate.content.parts:
                if part.function_call:
                    function_call_part = part
                    break
            
            if function_call_part:
                return LLMResponse(
                    tool_call={
                        "name": function_call_part.function_call.name,
                        "args": function_call_part.function_call.args
                    }
                )
            
            return LLMResponse(content=candidate.content.parts[0].text)

        except Exception as e:
            error_msg = str(e).lower()
            if "resource_exhausted" in error_msg or "quota" in error_msg:
                raise QuotaExhaustedError("Gemini Quota Exhausted")
            else:
                raise ProviderDownError(f"Gemini Error: {e}")