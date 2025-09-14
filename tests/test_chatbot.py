import pytest
import os
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable

from system_prompts import prompts
from src import tools
from src import frontend_agent
from src import utils

os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"].rstrip()
os.environ["LANGSMITH_API_KEY"] = os.environ["LANGSMITH_API_KEY"].rstrip()
os.environ["LANGSMITH_WORKSPACE_ID"] = os.environ["LANGSMITH_WORKSPACE_ID"].rstrip()
os.environ["LANGSMITH_ENDPOINT"] = os.environ["LANGSMITH_ENDPOINT"].rstrip()
os.environ["LANGSMITH_PROJECT"] = os.environ["LANGSMITH_PROJECT"].rstrip()
os.environ["LANGSMITH_TRACING"] = os.environ["LANGSMITH_TRACING"].rstrip()
os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] = os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"].rstrip()

OUTPUT_FOLDER_PATH = "./data/processed"
config = {"configurable": {"thread_id": "1"}}
stock = 'nvda'
quarter = 1
year = 2025
metadata_lite = {"stock": stock,
                 "year": year,
                 "quarter": quarter}

transcript_json_str = utils.load_transcript_json(output_folder_path=OUTPUT_FOLDER_PATH,
                                                 ticker=stock,
                                                 quarter=quarter,
                                                 year=year)

@pytest.fixture
def my_df_summary():
    type_filter = ["financial_results", "Q&A"]
    sentiment_filter = ["positive","mixed","negative"]
    df_summary = utils.convert_json_to_df_filtered(transcript_json_str=transcript_json_str,
                                                   type_filter=type_filter,
                                                   sentiment_filter=sentiment_filter)
    return df_summary

@pytest.fixture
def my_chatbot():
    model = "gemini-2.5-flash"
    model_provider = "google_genai"
    tool_list = [tools.get_stock_price, tools.get_today_date]
    api_call_buffer = 0
    system_message = prompts.CHATBOT_SYSTEM_PROMPT
    chatbot = frontend_agent.ChatbotAgent(model=model,
                                          model_provider=model_provider,
                                          tool_list=tool_list,
                                          api_call_buffer=api_call_buffer,
                                          system_message=system_message).graph
    return chatbot

def test_no_tool_call(my_df_summary, my_chatbot):
    """
    Test if the given user prompt has no request for stock data,
    the stock price tool should NOT be called
    """
    test_prompt = """
    Summarize top 3 themes from the given list of responses
    """
    human_message = prompts.CHATBOT_USER_PROMPT.format(metadata_lite,
                                                       my_df_summary.values,
                                                       test_prompt)
    message_input = {"messages": [HumanMessage(content=human_message)]}
    responses = my_chatbot.invoke(message_input, config)["messages"]

    # if tool_call ever exists in one of the AIMessage, test case fails
    tool_call_checksum = 0
    for response in responses:
        if isinstance(response, AIMessage):
            tool_call_checksum += int(bool(getattr(response, "tool_calls", None)))
    assert tool_call_checksum == 0

    for response in responses:
        assert "tool_calls" not in response

def test_tool_call(my_chatbot):
    """
    Test if the given user prompt has a request for stock data,
    the stock price tool should be called
    """
    test_prompt = """
    QUESTION:
    What is the performance of Nvidia in 2025 Q1?
    """
    response_prompt = """
    No response given.
    """
    human_message = prompts.CHATBOT_USER_PROMPT.format(metadata_lite,
                                                       response_prompt,
                                                       test_prompt)
    message_input = {"messages": [HumanMessage(content=human_message)]}
    responses = my_chatbot.invoke(message_input, config)["messages"]

    # if tool_call does not exist in any of the AIMessage, test case fails
    tool_call_checksum = 0
    for response in responses:
        if isinstance(response, AIMessage):
            tool_call_checksum += int(bool(getattr(response, "tool_calls", None)))
    assert tool_call_checksum != 0

