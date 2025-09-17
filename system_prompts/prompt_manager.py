from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
import os
from langchain.chat_models import init_chat_model
import argparse
import json

from system_prompts import prompts

os.environ["LANGSMITH_API_KEY"] = os.environ["LANGSMITH_API_KEY"].rstrip()
os.environ["LANGSMITH_WORKSPACE_ID"] = os.environ["LANGSMITH_WORKSPACE_ID"].rstrip()
os.environ["LANGSMITH_ENDPOINT"] = os.environ["LANGSMITH_ENDPOINT"].rstrip()
os.environ["LANGSMITH_PROJECT"] = os.environ["LANGSMITH_PROJECT"].rstrip()
os.environ["LANGSMITH_TRACING"] = os.environ["LANGSMITH_TRACING"].rstrip()
os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] = os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"].rstrip()

parser = argparse.ArgumentParser()
parser.add_argument("--action", type=str, required=True)
args = parser.parse_args()

action = args.action

PROMPT_METADATA_PATH = "./system_prompts/prompt_metadata.json"
with open(PROMPT_METADATA_PATH, "r", encoding="utf-8") as f:
    data = f.read()
prompt_metadata_dict = json.loads(data)

client = Client()

if action == "push":
    for prompt_name, prompt_metadata in prompt_metadata_dict.items():
        prompt_identifier = prompt_metadata["prompt_identifier"]
        prompt_type = prompt_identifier.split("-")[1]
        if prompt_type == "system":
            message = SystemMessage(content=getattr(prompts, prompt_name))
        elif prompt_type == "user":
            message = HumanMessage(content=getattr(prompts, prompt_name))
        else:
            raise ValueError("prompt_type must be 'system' or 'user'")
        prompt = ChatPromptTemplate.from_messages([message])
        client.push_prompt(prompt_identifier=prompt_identifier,
                           object=prompt,
                           description=prompt_metadata["description"],
                           tags=prompt_metadata["tag_list"])
elif action == "pull":
    # below is a demonstration of passing the pulled prompt to an LLM

    prompt_list = client.list_prompts()
    prompt_dict = {}
    for p in prompt_list.repos:
        prompt_name = f"{p.repo_handle}:{p.last_commit_hash[:8]}"
        print(prompt_name)
        # added below to avoid pulling random prompts that do not belong. Probably a bug from langsmith
        try:
            prompt_dict[p.description] = client.pull_prompt(prompt_name)
        except:
            break

    #print({k: v.format_messages()[0].content for k,v in prompt_dict.items()})

    test_prompt_name = "EVAL_INSTRUCTION_PROMPT"
    prompt_dict[f"{test_prompt_name}"].extend([HumanMessage(content="Buy nvda!")])
    formatted_prompt = prompt_dict[f"{test_prompt_name}"].format_messages() # need to format before passing into invoke()

    os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"].rstrip()
    model = "gemini-2.5-flash"
    model_provider = "google_genai"
    chatbot = init_chat_model(model=model,
                              model_provider=model_provider)
    validator_responses = chatbot.invoke(formatted_prompt)
    print(f"validator_responses\n{validator_responses}")
else:
    print("action must be either 'push' or 'pull'")
