from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import get_current_month
from langchain.messages import AIMessage

class MyMiniAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[get_current_month]
        )
    def run(self,query: str) -> str:
        result = self.agent.invoke({"messages":[{"role":"user","content":query}]})
        final_answer = ""
        for msg in result.get("messages",[]):
            if isinstance(msg,AIMessage) and not msg.tool_calls and msg.content:
                final_answer = msg.content
        return final_answer

if __name__ == '__main__':
    agent = MyMiniAgent()
    print(agent.run("今天是几月？"))