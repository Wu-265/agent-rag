from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (
    rag_summarize, get_weather, get_user_location, get_user_id,
    get_current_month, fetch_external_data, fill_context_for_report,
    analyze_file,celsius_to_fahrenheit
)
from agent.tools.file_tools import workspace
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch

# 多轮记忆窗口：只保留最近 N 条历史消息传给模型，控制 token 增长
MEMORY_WINDOW = 12


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[rag_summarize, get_weather, get_user_location, get_user_id,
                   get_current_month, fetch_external_data, fill_context_for_report,
                   analyze_file,celsius_to_fahrenheit],
            middleware=[monitor_tool, log_before_model, report_prompt_switch]
        )

    def execute_stream(self, query: str, file_path: str = None, history: list = None):
        # 若本轮有上传文件，同步到文件工作区，供 analyze_file 使用
        if file_path:
            workspace.set_current_file(file_path)

        # 组装多轮消息：历史(仅 user/assistant 的最终回答) + 当前问题
        messages = []
        if history:
            for m in history[-MEMORY_WINDOW:]:
                role = m.get("role")
                content = m.get("content")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": query})

        input_dict = {"messages": messages}

        # stream_mode="updates"：按节点增量输出。
        # 只保留 model 节点产出的、且不带 tool_calls 的最终回答，
        # 从而把工具调用的中间过程（原始统计文本等）过滤掉，让聊天更干净。
        for chunk in self.agent.stream(input_dict, stream_mode="updates", context={"report": False}):
            update = chunk.get("model") or next(iter(chunk.values()), None)
            if not isinstance(update, dict):
                continue
            messages = update.get("messages", [])
            if not messages:
                continue
            msg = messages[-1]
            if isinstance(msg, AIMessage) and not msg.tool_calls and msg.content:
                yield msg.content.strip() + "\n"

    def execute_with_trace(self,query: str, file_path: str = None, history: list = None):
        """
        非流式执行，返回 (最终回答, 工具调用列表)。
        用于测试：捕获 agent 实际调用了哪些工具、传了什么参数。
        """
        #组装多轮消息（和execute_stream逻辑一致）
        messages = []
        if history:
            for m in history[-MEMORY_WINDOW:]:
                role = m.get("role")
                content = m.get("content")
                if role in ("user", "assistant") and content:
                    messages.append({"role":role, "content":content})
        messages.append({"role": "user", "content": query})
        print(f"本次传给模型的历史消息数：{len(messages)}")

        input_dict = {"messages": messages}

        # 非流式执行（invoke），获取完整结果状态
        result = self.agent.invoke(input_dict,context={"report": False})

        # 从结果的 messages 中提取工具调用和最终回答
        tool_calls = []
        final_answer = ""
        for msg in result.get("messages", []):
            # AIMessage 带 tool_calls = 模型决定调用工具
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "tool": tc.get("name"),
                        "args": tc.get("args"),
                    })
            # AIMessage 不带 tool_calls 且有内容 = 模型最终回答
            elif isinstance(msg, AIMessage) and not msg.tool_calls and msg.content:
                final_answer = msg.content

        return final_answer, tool_calls

if __name__ == '__main__':
    agent = ReactAgent()
    for chunk in agent.execute_stream("你好"):
        print(chunk, end="", flush=True)
    agent.execute_with_trace('你好', history=[{'role':'user','content':'我的密码是苹果'},{'role':'assistant','content':'好的'}])