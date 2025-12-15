from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any
import json
import logging

from memory import BaseMemory
from base_tool import BaseTool 
from llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger("AgentFramework")

@dataclass
class AgentResponse:
    content: str                  
    metadata: Dict[str, Any] = field(default_factory=dict) 

class BaseAgent(ABC):
    """
    The parent class for all agents. 
    Now accepts a clean list of 'BaseTool' objects.
    """
    def __init__(self, name: str, tools: List[BaseTool], system_prompt: str = "You are a helpful assistant."):
        self.name = name
        self.system_prompt = system_prompt
        
        # 1. Build the Registry (Map Name -> Function) for execution
        self.tool_registry = {tool.name: tool.run for tool in tools}
        
        # 2. Build the Definitions (List of Schemas) for the LLM
        self.tool_definitions = [tool.get_schema() for tool in tools]

    @abstractmethod
    def process_query(self, user_query: str, provider: LLMProvider) -> AgentResponse:
        pass


class SingleAgent(BaseAgent):
    """
    A standard worker agent that uses the provided BaseTools to answer queries.
    """
    def __init__(self, name: str, tools: List[BaseTool], system_prompt: str = "You are a helpful assistant."):
        # Pass the tool objects directly to the parent
        super().__init__(name, tools, system_prompt)

    def process_query(self, user_query: str, provider: LLMProvider) -> AgentResponse:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_query}
        ]

        logger.info(f"\n🚀 [{self.name}] Starting Loop...")

        for turn in range(5):
            logger.info(f"--- Turn {turn + 1} ---")
            
            # 1. Ask the Provider (Using the internally built definitions)
            response: LLMResponse = provider.get_response(messages, self.tool_definitions)

            # 2. Handle Tool Calls
            if response.tool_call:
                tool_name = response.tool_call["name"]
                tool_args = response.tool_call["args"]
                tool_id = response.tool_call.get("id", "call_default")
                
                logger.info(f"🤖 Agent Intent: Call `{tool_name}` with {tool_args}")

                if tool_name in self.tool_registry:
                    messages.append({
                        "role": "assistant",
                        "content": None, 
                        "tool_calls": [{"id": tool_id, "type": "function", "function": {"name": tool_name, "arguments": json.dumps(tool_args)}}]
                    })

                    try:
                        # Execution uses the registry built in __init__
                        tool_func = self.tool_registry[tool_name]
                        raw_result = tool_func(**tool_args)
                        result_str = json.dumps(raw_result) if not isinstance(raw_result, str) else raw_result
                        
                        logger.info(f"Tool Output: {result_str}")
                        messages.append({"role": "tool", "tool_call_id": tool_id, "name": tool_name, "content": result_str})

                    except Exception as e:
                        error_msg = f"Tool Execution Failed: {str(e)}"
                        logger.error(error_msg)
                        messages.append({"role": "tool", "tool_call_id": tool_id, "name": tool_name, "content": error_msg})
                    continue 
                else:
                    messages.append({"role": "tool", "tool_call_id": tool_id, "name": tool_name, "content": f"❌ Unknown tool '{tool_name}'"})
                    continue 

            # 3. Handle Final Answer
            if response.content:
                logger.info(f"[{self.name}] Final Answer: {response.content}")
                return AgentResponse(content=response.content, metadata={"final_answer": response.content})
            
        return AgentResponse(content="Agent timed out.", metadata={"error": "Timeout"})

class ManagerAgent(BaseAgent):
    """
    The Brain. 
    It treats its sub-agents as 'Tools' and dynamically decides which one to call.
    Now equipped with Short-Term Memory!
    """
    def __init__(self, name: str, sub_agents: Dict[str, SingleAgent], memory: BaseMemory, system_prompt: str = "You are a manager."):
        super().__init__(name, tools=[], system_prompt=system_prompt)
        self.sub_agents = sub_agents
        self.memory = memory
        self.delegation_definitions = self._build_delegation_definitions()

    def _build_delegation_definitions(self) -> List[Dict]:
        """
        Dynamically creates OpenAI-compatible function schemas for each sub-agent.
        """
        definitions = []
        for agent_name, agent in self.sub_agents.items():
            agent_desc = getattr(agent, "description", "A helper agent.")   
            schema = {
                "type": "function",
                "function": {
                    "name": f"delegate_to_{agent_name}",
                    "description": f"Delegate a query to the {agent_name}. Capability: {agent_desc}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string", 
                                "description": "The specific question or instruction for this worker."
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
            definitions.append(schema)
        return definitions

    def process_query(self, user_query: str, provider: LLMProvider) -> AgentResponse:
        """
        The Manager's Thinking Loop.
        It decides: Do I answer myself? Or do I call a worker?
        """

        # 1. Save User Query to Memory
        self.memory.add_message(role="user", content=user_query)

        # 2. Construct the Context (System Prompt + History)
        team_roster = ", ".join(self.sub_agents.keys())
        enhanced_system_prompt = (
            f"{self.system_prompt}\n"
            f"You manage a team of agents: [{team_roster}].\n"
            f"Delegate tasks to them using the available tools.\n"
            f"Combine their outputs into a comprehensive final answer."
            f"Use the conversation history to answer follow-up questions."
        )

        # Start with System Prompt
        messages = [{"role": "system", "content": enhanced_system_prompt}]

        # Add Conversation History
        history = self.memory.get_history()
        messages.extend(history)

        logger.info(f"👑 [{self.name}] Starting Orchestration Loop...")

        # 3. Start the Loop (Max 5 turns)
        for turn in range(5):
            logger.info(f"--- Manager Turn {turn + 1} ---")
            
            # A. Ask the Provider
            response: LLMResponse = provider.get_response(messages, self.delegation_definitions)

            # B. Handle "Virtual Tool" Calls (Delegation)
            if response.tool_call:
                tool_name = response.tool_call["name"]
                tool_args = response.tool_call["args"]
                tool_id = response.tool_call.get("id", "call_mgr")
                
                if tool_name.startswith("delegate_to_"):
                    agent_name = tool_name.replace("delegate_to_", "")
                    
                    if agent_name in self.sub_agents:
                        logger.info(f"👑 -> 👷 Delegating to {agent_name}: {tool_args.get('query')}")
                        
                        # Record the "Thought" (Tool Call)
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tool_id,
                                "type": "function",
                                "function": {"name": tool_name, "arguments": json.dumps(tool_args)}
                            }]
                        })

                        # EXECUTE THE WORKER
                        worker_agent = self.sub_agents[agent_name]
                        worker_query = tool_args.get("query")
                        
                        try:
                            # Worker runs its own loop (stateless for now)
                            worker_response = worker_agent.process_query(worker_query, provider)
                            worker_content = worker_response.content
                            logger.info(f"👷 -> 👑 {agent_name} replied.")

                        except Exception as e:
                            worker_content = f"Error from {agent_name}: {str(e)}"
                            logger.error(worker_content)

                        # Record the "Observation" (Tool Output)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": f"Output from {agent_name}:\n{worker_content}"
                        })
                        continue
                    else:
                        logger.warning(f"❌ Manager tried to call unknown agent: {agent_name}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": f"Error: Agent {agent_name} does not exist."
                        })
                        continue
            
            # C. Handle Final Answer (Synthesis)
            if response.content:
                logger.info(f"✅ [{self.name}] Final Synthesis: {response.content}")
                
                # 4. Save Assistant Answer to Memory
                self.memory.add_message(role="assistant", content=response.content)
                
                return AgentResponse(content=response.content)

        return AgentResponse(content="Manager timed out while coordinating agents.", metadata={"error": "timeout"})