from dotenv import load_dotenv
import os
from urllib.error import URLError
import streamlit as st
import plotly.express as px
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import Client
import pandas as pd
import asyncio

import tools
import utils
from frontend_agent import ChatbotAgent
from system_prompts import prompts

load_dotenv("../venv")

# Set GOOGLE_API_KEY by first source set_api_key.sh in config. Use this for docker
os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"].rstrip()
os.environ["LANGSMITH_API_KEY"] = os.environ["LANGSMITH_API_KEY"].rstrip()
os.environ["LANGSMITH_WORKSPACE_ID"] = os.environ["LANGSMITH_WORKSPACE_ID"].rstrip()
os.environ["LANGSMITH_ENDPOINT"] = os.environ["LANGSMITH_ENDPOINT"].rstrip()
os.environ["LANGSMITH_PROJECT"] = os.environ["LANGSMITH_PROJECT"].rstrip()
os.environ["LANGSMITH_TRACING"] = os.environ["LANGSMITH_TRACING"].rstrip()
os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] = os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"].rstrip()

config = {"configurable": {"thread_id": "1"}}
model = "gemini-2.5-flash"
model_provider = "google_genai"
api_call_buffer = 0

tool_list = [tools.get_stock_price, tools.get_today_date]

# Load prompts
print(f"Load prompts from langsmith")
client = Client()
prompt_list = client.list_prompts(is_public=False)
prompt_dict = {}
for p in prompt_list.repos:
    prompt_name = f"{p.repo_handle}:{p.last_commit_hash[:8]}"
    prompt_dict[p.description] = client.pull_prompt(prompt_name)

chatbot_user_prompt = prompt_dict["CHATBOT_USER_PROMPT"].format_messages()[0].content


TRANSCRIPT_FOLDER_PATH = "./data/raw"
OUTPUT_FOLDER_PATH = "./data/processed"

# uncomment below if want to run backend agent at runtime
#backend_agent = TranscriptPrepAgent(model=model,
#                         model_provider=model_provider,
#                         system_prompt=prompts,
#                         api_call_buffer=api_call_buffer)

try:
    ticker_list, quarter_list, year_list = utils.get_filter_from_filename(OUTPUT_FOLDER_PATH)

    ## 0. Set stock selection filters
    st.subheader("Earning call transcript chatbot")
    col1, col2, col3 = st.columns(3)

    with col1:
        stock = st.selectbox(
            "Choose stock", ticker_list
        ).lower()
    with col2:
        year = st.selectbox(
            "Choose year", year_list
        )
    with col3:
        quarter = st.selectbox(
            "Choose quarter", quarter_list
        )

    if not (stock or year or quarter):
        st.error("Please select a stock, year and quarter.")
    else:
        # to ensure the output file exists. uncomment below if want to run backend agent at runtime
        #context = {"ticker": stock,
        #           "year": year,
        #           "quarter": quarter,
        #           "transcript_folder_path": TRANSCRIPT_FOLDER_PATH,
        #           "output_folder_path": OUTPUT_FOLDER_PATH}
        # backend_agent.graph.invoke(context, config)

        metadata_lite = {"stock": stock,
                         "year": year,
                         "quarter": quarter}

        ## 1. select transcripts and prepare df
        col_type_filter, col_sentiment_filter = st.columns(2)
        with col_type_filter:
            type_filter = st.multiselect(
                "Choose statement type",
                ["financial results","Outlook","Q&A", "Other"],
                ["financial results"]
            )
            if not col_type_filter:
                st.error("Please select at least one type.")
        with col_sentiment_filter:
            sentiment_filter = st.multiselect(
                "Choose statement sentiment",
                ["positive","negative","mixed","netural"],
                ["positive","negative"]
            )
            if not sentiment_filter:
                st.error("Please select at least one sentiment.")

        transcript_json_str = utils.load_transcript_json(output_folder_path=OUTPUT_FOLDER_PATH,
                                                         ticker=stock,
                                                         quarter=quarter,
                                                         year=year)

        df_summary = utils.convert_json_to_df_filtered(transcript_json_str=transcript_json_str,
                                                       type_filter=type_filter,
                                                       sentiment_filter=sentiment_filter)

        ## 2. chatbot
        chatbot = ChatbotAgent(model=model,
                               model_provider=model_provider,
                               tool_list=tool_list,
                               api_call_buffer=api_call_buffer,
                               system_message=prompt_dict["CHATBOT_SYSTEM_PROMPT"]).graph

        if "model" not in st.session_state:
            st.session_state["model"] = model

        if "model_provider" not in st.session_state:
            st.session_state["model_provider"] = model_provider

        # initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # display chat messages from history and rerun
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("AMA about the selected earning call transcript!"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                user_messages = chatbot_user_prompt.format(metadata_lite,
                                                           df_summary.values,
                                                           st.session_state.messages[-1]["content"])
                message_input = [HumanMessage(content=user_messages)]

                async def get_stream_response():
                    """
                    this function is used to extract content from the async_generator produced by
                    chatbot.astream()
                    """
                    stream = chatbot.astream({"messages": message_input})
                    async for chunk in stream:
                        try:
                            # require 1) it's an llm response and 2) it doesn't call tools anymore
                            if chunk["llm"]:
                                if "tool_calls" not in chunk["llm"]["messages"][0]:
                                    yield chunk["llm"]["messages"][0].content.replace("$","\$")
                        except:
                            pass

                response = st.write_stream(get_stream_response())

            st.session_state.messages.append({"role": "assistant", "content": response.replace("$","\$")})

        if st.button("Reset chat"):
            st.session_state.clear()


        ## 3. show transcript df
        #st.subheader("Structured transcript")
        #st.dataframe(df)


except URLError as e:
    st.error(f"This demo requires internet access. Connection error: {e.reason}")