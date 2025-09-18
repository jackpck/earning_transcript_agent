import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langsmith import Client

from src.backend_agent import BackEndAgent
from src.frontend_agent import ChatbotAgent
from src import utils
from src import tools

os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"].rstrip()
os.environ["LANGSMITH_API_KEY"] = os.environ["LANGSMITH_API_KEY"].rstrip()
os.environ["LANGSMITH_WORKSPACE_ID"] = os.environ["LANGSMITH_WORKSPACE_ID"].rstrip()
os.environ["LANGSMITH_ENDPOINT"] = os.environ["LANGSMITH_ENDPOINT"].rstrip()
os.environ["LANGSMITH_PROJECT"] = os.environ["LANGSMITH_PROJECT"].rstrip()
os.environ["LANGSMITH_TRACING"] = os.environ["LANGSMITH_TRACING"].rstrip()
os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] = os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"].rstrip()
load_dotenv("../venv")


def run_backend(stock, year, quarter, agent):
    context = {"ticker": stock.lower(),
               "year": year,
               "quarter": quarter,
               }
    final_state = agent.graph.invoke(context, config)

    return final_state

def run_frontend(backend_final_state,
                 type_filter,
                 sentiment_filter,
                 chatbot_user_prompt: str,
                 user_prompt: str,
                 agent):

    transcript_json = backend_final_state["transcript_json"]
    df_summary = utils.convert_json_to_df_filtered(transcript_json_str=transcript_json,
                                                   type_filter=type_filter,
                                                   sentiment_filter=sentiment_filter)
    metadata_lite = {"stock": backend_final_state["ticker"],
                     "year": backend_final_state["year"],
                     "quarter": backend_final_state["quarter"]}
    human_message = chatbot_user_prompt.format(metadata_lite,
                                               df_summary.values,
                                               user_prompt)
    message_input = {"messages": [HumanMessage(content=human_message)]}
    response = agent.graph.invoke(message_input, config)["messages"][-1].content

    return response


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "1"}}
    model = "gemini-2.5-flash"
    model_provider = "google_genai"
    api_call_buffer = 0  # need this when running backend agent

    TRANSCRIPT_FOLDER_PATH = "./data/raw"
    type_filter = ["financial_results", "Q&A"]
    sentiment_filter = ["positive", "mixed", "negative"]
    stock = 'nvda'
    year = 2025
    quarter = 2
    tool_list = [tools.get_stock_price, tools.get_today_date]

    # Load prompts
    print(f"Load prompts from langsmith")
    client = Client()
    prompt_list = client.list_prompts(is_public=False)
    prompt_dict = {}
    for p in prompt_list.repos:
        prompt_name = f"{p.repo_handle}:{p.last_commit_hash[:8]}"
        prompt_dict[p.description] = client.pull_prompt(prompt_name)

    user_prompt = """
    summarize the responses in less than 4 themes. Return:
    1) name of each theme
    2) short description of each theme
    3) compare with the stock performance over the same period 
    """

    backendagent = BackEndAgent(model=model,
                                model_provider=model_provider,
                                system_prompt=prompt_dict,
                                transcript_folder_path=TRANSCRIPT_FOLDER_PATH,
                                api_call_buffer=api_call_buffer)

    chatbot = ChatbotAgent(model=model,
                           model_provider=model_provider,
                           tool_list=tool_list,
                           api_call_buffer=api_call_buffer,
                           system_message=prompt_dict["CHATBOT_SYSTEM_PROMPT"])

    print(f"Run backend agent")
    backend_final_state = run_backend(stock=stock,
                                      year=year,
                                      quarter=quarter,
                                      agent=backendagent)

    print(f"Run frontend agent")
    response = run_frontend(backend_final_state=backend_final_state,
                            type_filter=type_filter,
                            sentiment_filter=sentiment_filter,
                            chatbot_user_prompt=prompt_dict["CHATBOT_USER_PROMPT"].format_messages()[0].content,
                            user_prompt=user_prompt,
                            agent=chatbot)

    print(response)

