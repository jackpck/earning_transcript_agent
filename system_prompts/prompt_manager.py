from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
import os
from langchain.chat_models import init_chat_model
import argparse

from system_prompts import prompts

os.environ["LANGSMITH_API_KEY"] = os.environ["LANGSMITH_API_KEY"].rstrip()
os.environ["LANGSMITH_WORKSPACE_ID"] = os.environ["LANGSMITH_WORKSPACE_ID"].rstrip()
os.environ["LANGSMITH_ENDPOINT"] = os.environ["LANGSMITH_ENDPOINT"].rstrip()
os.environ["LANGSMITH_PROJECT"] = os.environ["LANGSMITH_PROJECT"].rstrip()
os.environ["LANGSMITH_TRACING"] = os.environ["LANGSMITH_TRACING"].rstrip()
os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] = os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"].rstrip()

parser = argparse.ArgumentParser()
parser.add_argument("--action", type=str, required=True)
parser.add_argument("--prompt_identifier", type=str, required=True)
parser.add_argument("--prompt_commit_tag", type=str)
args = parser.parse_args()

action = args.action
prompt_identifier = args.prompt_identifier
prompt_commit_tag = args.prompt_commit_tag

client = Client()
tag_list = ["dev"]
# start prompt identifier with eval-, backend- or chatbot-
# e.g. prompt_identifier = "eval-instructions"
prompt_to_save = prompts.EVAL_INSTRUCTION_PROMPT

if action == "push":
    description = ""
    prompt = ChatPromptTemplate.from_messages([SystemMessage(content=prompt_to_save)])
    client.push_prompt(prompt_identifier=prompt_identifier,
                       object=prompt,
                       description=description,
                       tags=tag_list)
elif action == "pull":
    # below is a demonstration of passing the pulled prompt to an LLM
    prompt = client.pull_prompt(f"eval-instructions:{prompt_commit_tag}")
    prompt.extend([HumanMessage(content="{question}")])
    formatted_prompt = prompt.format_messages(question="Hello world!") # need to format before passing into invoke()

    os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"].rstrip()
    model = "gemini-2.5-flash"
    model_provider = "google_genai"
    chatbot = init_chat_model(model=model,
                              model_provider=model_provider)
    responses = "Buy nvda!"
    validator_responses = chatbot.invoke(formatted_prompt)
    print(validator_responses)
else:
    print("action must be either 'push' or 'pull'")
