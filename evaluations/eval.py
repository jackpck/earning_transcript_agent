from langsmith import Client
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model
from langsmith.utils import LangSmithError
import os
import json

from system_prompts import prompts
from src import frontend_agent, tools, utils

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
system_message = prompts.CHATBOT_SYSTEM_PROMPT
config = {"configurable": {"thread_id": "1"}}
chatbot = frontend_agent.ChatbotAgent(model=model,
                                      model_provider=model_provider,
                                      tool_list=tool_list,
                                      api_call_buffer=api_call_buffer,
                                      system_message=system_message).graph


def call_price_classifier(inputs: dict) -> dict:
    """

    :param inputs: has the format of {'text':'...'}
    :return:
    """
    message_input = {"messages": [HumanMessage(content=inputs["text"])]}
    responses = chatbot.invoke(message_input, config)["messages"][-1].content

    instructions = (
        "Review the given chatbot responses, determine if it discussed the stock performance OR "
        "forward-looking advice."
        "Respond with 'Yes' if it does and 'No' if it doesn't."
    )
    messages = [
        SystemMessage(content=instructions),
        HumanMessage(content=responses)
    ]
    validator = init_chat_model(model=validator_model,
                                 model_provider=validator_model_provider)
    validator_responses = validator.invoke(messages)
    return {"class": validator_responses.content}


def metric(inputs:dict, outputs: dict, reference_outputs: dict) -> bool:
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

    transcript_json_str = utils.load_transcript_json(output_folder_path=OUTPUT_FOLDER_PATH,
                                                     ticker=stock,
                                                     quarter=quarter,
                                                     year=year)
    type_filter = ["financial_results", "Q&A"]
    sentiment_filter = ["positive","mixed","negative"]
    df_summary = utils.convert_json_to_df_filtered(transcript_json_str=transcript_json_str,
                                                   type_filter=type_filter,
                                                   sentiment_filter=sentiment_filter)

    ls_client = Client()
    with open(EVAL_DATA_PATH, "r", encoding="utf-8") as f:
        data = f.read()
    examples_temp = json.loads(data)
    examples = utils.reprompt_eval_test(examples_temp,
                                        prompts.CHATBOT_USER_PROMPT,
                                        metadata_lite,
                                        df_summary)["examples"]

    test_name = "call_price_test"
    try:
        dataset = ls_client.read_dataset(dataset_name=test_name)
    except LangSmithError:
        dataset = ls_client.create_dataset(dataset_name=test_name)

    ls_client.create_examples(
        dataset_id=dataset.id,
        examples=examples
    )

    print(f"dataset.name: {dataset.name}")
    results = ls_client.evaluate(
        call_price_classifier,
        data=dataset.name,
        evaluators=[metric],
    )