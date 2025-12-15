import ruamel.yaml as yaml  
from typing import Dict
from base_agent import SingleAgent
from registry import ToolRegistry

class AgentFactory:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.parser = yaml.YAML(typ='safe')
        self.parser.pure = True 

    def load_from_yaml(self, config_path: str) -> Dict[str, SingleAgent]:
        """
        Reads YAML and returns a dictionary of built Agents.
        """
        with open(config_path, "r") as f:
            config = self.parser.load(f)
        
        agents_dict = {}

        for agent_conf in config["agents"]:
            name = agent_conf["name"]
            subscriptions = agent_conf.get("subscriptions", [])
            sys_prompt = agent_conf.get("system_prompt", "You are a helpful assistant.")
            
            unique_tools = set()
            for category in subscriptions:
                tools = self.registry.get_tools_by_category(category)
                for t in tools:
                    unique_tools.add(t)

            agent_tools_list = list(unique_tools)

            new_agent = SingleAgent(
                name=name,
                tools=agent_tools_list,
                system_prompt=sys_prompt
            )
            agents_dict[name] = new_agent
        
        return agents_dict
        