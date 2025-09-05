from pydantic import BaseModel
from typing import List, Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

class AgentState(BaseModel):
    ticker: str
    quarter: int
    year: int
    transcript_folder_path: str
    output_folder_path: str
    transcript: str = None
    transcript_json: str = None

class FrontEndState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


__all__ = [
    "AgentState",
    "FrontEndState"
]