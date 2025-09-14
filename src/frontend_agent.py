from langchain.chat_models import init_chat_model
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import SystemMessage, ToolMessage
from typing import List
import os
import time
import ast
import json
from src.state import AgentState, FrontEndState

class ChatbotAgent:
    def __init__(self,
                 model: str,
                 model_provider: str,
                 tool_list: List,
                 api_call_buffer: int,
                 system_message: str):

        self.model = init_chat_model(model=model,
                                     model_provider=model_provider).bind_tools(tool_list)
        self.tools = {t.name: t for t in tool_list}
        self.api_call_buffer = api_call_buffer # set buffer second to stay within the free version RPM limit
        self._setup_graph(system_message=system_message)

    def _setup_graph(self, system_message):
        graph = StateGraph(FrontEndState)
        graph.add_node("llm", self.call_llm)
        graph.add_node("tools", self.call_tools)
        graph.add_conditional_edges(
            "llm",
            self.should_call_tools,
            ["tools", END]
        )
        graph.add_edge("tools", "llm")
        graph.add_edge(START, "llm")
        self.graph = graph.compile()
        self.system_message = system_message

    def call_llm(self, state: FrontEndState):
        messages = state["messages"]
        if self.system_message:
            messages = [SystemMessage(content=self.system_message)] + messages
        message = self.model.invoke(messages)
        return {"messages": [message]}

    def call_tools(self, state: FrontEndState):
        tool_calls = state["messages"][-1].tool_calls
        results = []
        for t in tool_calls:
            result = self.tools[t["name"]].invoke(t["args"])
            results.append(ToolMessage(tool_call_id=t["id"],
                                       name=t["name"],
                                       content=str(result)))
        return {"messages": results}

    def should_call_tools(self, state: FrontEndState):
        result = state["messages"][-1]
        return "tools" if len(result.tool_calls) > 0 else END


