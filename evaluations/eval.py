from langsmith import Client
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model
from langsmith.utils import LangSmithError
import os
import json

from system_prompts import prompts
from src import tools, utils
from src.frontend_agent import ChatbotAgent
from src.backend_agent import BackEndAgent

os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"].rstrip()
os.environ["LANGSMITH_API_KEY"] = os.environ["LANGSMITH_API_KEY"].rstrip()
os.environ["LANGSMITH_WORKSPACE_ID"] = os.environ["LANGSMITH_WORKSPACE_ID"].rstrip()
os.environ["LANGSMITH_ENDPOINT"] = os.environ["LANGSMITH_ENDPOINT"].rstrip()
os.environ["LANGSMITH_PROJECT"] = os.environ["LANGSMITH_PROJECT"].rstrip()
os.environ["LANGSMITH_TRACING"] = os.environ["LANGSMITH_TRACING"].rstrip()
os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] = os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"].rstrip()

model = "gemini-2.5-flash"
model_provider = "google_genai"
validator_model = "gemini-2.5-flash"
validator_model_provider = "google_genai"
tool_list = [tools.get_stock_price, tools.get_today_date]
api_call_buffer = 0
CONFIG = {"configurable": {"thread_id": "1"}}
TRANSCRIPT_FOLDER_PATH = "./data/raw"


def run_backend(stock, year, quarter, agent):
    context = {"ticker": stock.lower(),
               "year": year,
               "quarter": quarter,
               }
    final_state = agent.graph.invoke(context, CONFIG)

    return final_state

def run_frontend(backend_final_state,
                 type_filter,
                 sentiment_filter,
                 user_prompt,
                 agent):

    transcript_json = backend_final_state["transcript_json"]
    df_summary = utils.convert_json_to_df_filtered(transcript_json_str=transcript_json,
                                                   type_filter=type_filter,
                                                   sentiment_filter=sentiment_filter)
    metadata_lite = {"stock": backend_final_state["ticker"],
                     "year": backend_final_state["year"],
                     "quarter": backend_final_state["quarter"]}
    human_message = prompts.CHATBOT_USER_PROMPT.format(metadata_lite,
                                                       df_summary.values,
                                                       user_prompt)
    message_input = {"messages": [HumanMessage(content=human_message)]}
    response = agent.graph.invoke(message_input, CONFIG)["messages"][-1].content

    return response

def call_eval_with_instruction(eval_prompt_identifier: str, **kwargs):
    def call_eval(inputs: dict) -> dict:
        """
        :param inputs: has the format of {'text':'...'}
        :return:
        """
        responses = run_frontend(backend_final_state=kwargs["backend_final_state"],
                                type_filter=kwargs["type_filter"],
                                sentiment_filter=kwargs["sentiment_filter"],
                                user_prompt=inputs["text"],
                                agent=kwargs["chatbot"])

        instructions = client.pull_prompt(eval_prompt_identifier)
        instructions.extend([HumanMessage(content="{responses}")])
        validator_input = instructions.format_messages(responses=responses)
        validator = init_chat_model(model=validator_model,
                                     model_provider=validator_model_provider)
        validator_responses = validator.invoke(validator_input)

        return {"class": validator_responses.content}

    return call_eval

def accuracy_metric(inputs:dict, outputs: dict, reference_outputs: dict) -> bool:
    return outputs["class"] == reference_outputs["label"]


if __name__ == "__main__":
    EVAL_DATA_PATH = "./data/evaluation/1_call_price_example.json"
    OUTPUT_FOLDER_PATH = "./data/processed"
    stock = 'nvda'
    quarter = 1
    year = 2025
    metadata_lite = {"stock": stock,
                     "year": year,
                     "quarter": quarter}
    type_filter = ["financial_results", "Q&A"]
    sentiment_filter = ["positive","mixed","negative"]

    client = Client()

    # Load data
    with open(EVAL_DATA_PATH, "r", encoding="utf-8") as f:
        data = f.read()
    examples = json.loads(data)["examples"]

    test_name = "call_price_test"
    try:
        dataset = client.read_dataset(dataset_name=test_name)
    except LangSmithError:
        dataset = client.create_dataset(dataset_name=test_name)

    client.create_examples(
        dataset_id=dataset.id,
        examples=examples
    )

    # Load prompts
    prompt_commit_tag = "7e3878c6"
    eval_prompt_identifier = f"eval-instructions:{prompt_commit_tag}"

    # Load agents
    backendagent = BackEndAgent(model=model,
                                model_provider=model_provider,
                                system_prompt=prompts,
                                transcript_folder_path=TRANSCRIPT_FOLDER_PATH,
                                api_call_buffer=api_call_buffer)

    chatbot = ChatbotAgent(model=model,
                           model_provider=model_provider,
                           tool_list=tool_list,
                           api_call_buffer=api_call_buffer,
                           system_message=prompts.CHATBOT_SYSTEM_PROMPT)

    state_snapshot_path = f"./data/state_snapshot/{stock}_{year}_Q{quarter}_backend_final_state.json"
    if os.path.exists(state_snapshot_path):
        print(f"{state_snapshot_path} exists. Read from file")
        with open(state_snapshot_path, "r", encoding="utf-8") as f:
            backend_final_state = json.loads(f.read())
    else:
        print(f"{state_snapshot_path} does not exist. Run backend agent")
        backend_final_state = run_backend(stock=stock,
                                          year=year,
                                          quarter=quarter,
                                          agent=backendagent)
        with open(state_snapshot_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(backend_final_state))

    agent_config = {
        "type_filter": type_filter,
        "sentiment_filter": sentiment_filter,
        "chatbot": chatbot,
        "backend_final_state": backend_final_state
    }

    # Run evaluation
    results = client.evaluate(
        call_eval_with_instruction(eval_prompt_identifier=eval_prompt_identifier, **agent_config),
        data=dataset.name,
        evaluators=[accuracy_metric],
    )