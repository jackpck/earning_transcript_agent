from langchain.chat_models import init_chat_model
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import SystemMessage, HumanMessage
import os
import time
import json
from src import utils
from src.state import BackEndState

class BackEndAgent:
    def __init__(self,
                 model: str,
                 model_provider: str,
                 system_prompt,
                 transcript_folder_path,
                 api_call_buffer: int):

        self.model = init_chat_model(model=model,
                                     model_provider=model_provider)
        self.system_prompt = system_prompt
        self.transcript_folder_path = transcript_folder_path.rstrip('/')
        self.api_call_buffer = api_call_buffer # set buffer second to stay within the free version RPM limit
        self._setup_graph()

    def read_raw_txt(self, state: BackEndState) -> str:
        """
        Get the earning call transcript from the transcript path specified by the user
        :param state: state of the agent
        :return: str of earning call transcript for further preprocessing
        """
        transcript_path = (f"{self.transcript_folder_path}"
        f"/{state.ticker}_Q{state.quarter}_{state.year}.txt")
        if os.path.exists(transcript_path):
            with open(transcript_path, "r", encoding='utf-8') as f:
                earning_call_transcript = f.read()
            return {"transcript": earning_call_transcript}
        else:
            raise Exception("Transcript folder does not exist.")

    def preprocess_llm(self, state: BackEndState) -> str:
        """
        Structure earning call transcript in a format specified by the system_prompt
        :param state: state of the agent
        :return: string of json of the structured earning call transcript
        """
        messages = [
            SystemMessage(content=self.system_prompt.PREPROCESS_SYSTEM_PROMPT),
            HumanMessage(content=state.transcript)
        ]
        response = self.model.invoke(messages)

        return {"transcript_json": response.content}

    def analyze_llm(self, state: BackEndState) -> str:
        """
        Analyze the sentiment in each speech. Instruction
        given by system_analysis_prompt
        :param state: state of the agent
        :return: string of json of the structured earning call transcript with sentiment
        """
        transcript_json_tmp = utils.clean_json_str(state.transcript_json)
        transcript_json = json.loads(transcript_json_tmp)
        for i, section in enumerate(transcript_json["sections"]):
            messages = [
                SystemMessage(content=self.system_prompt.ANALYSIS_SYSTEM_PROMPT),
                HumanMessage(content=section["statement"])
            ]
            response_content = self.model.invoke(messages).content
            response_content_clean = utils.clean_json_str(response_content)
            transcript_json["sections"][i]["statement"] = json.loads(response_content_clean)
            time.sleep(self.api_call_buffer) # ensure RPM < 10. Only for free tier gemini-2.5-flash

        return {"transcript_json": json.dumps(transcript_json)}

    def _setup_graph(self):
        graph = StateGraph(BackEndState)
        graph.add_node("read_raw_txt", self.read_raw_txt)
        graph.add_node("preprocess_llm", self.preprocess_llm)
        graph.add_node("analyze_llm", self.analyze_llm)

        graph.add_edge(START, "read_raw_txt")
        graph.add_edge("read_raw_txt", "preprocess_llm")
        graph.add_edge("preprocess_llm", "analyze_llm")
        graph.add_edge("analyze_llm", END)

        self.graph = graph.compile()


if __name__ == "__main__":
    from dotenv import load_dotenv
    from system_prompts import prompts

    os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"].rstrip()
    load_dotenv("../venv")

    config = {"configurable": {"thread_id": "1"}}
    model = "gemini-2.5-flash"
    model_provider = "google_genai"
    api_call_buffer = 0  # need this when running backend agent
    TRANSCRIPT_FOLDER_PATH = "./data/raw"
    OUTPUT_FOLDER_PATH = "./data/processed"
    agent = BackEndAgent(model=model,
                         model_provider=model_provider,
                         system_prompt=prompts,
                         transcript_folder_path=TRANSCRIPT_FOLDER_PATH,
                         api_call_buffer=api_call_buffer)

    stock = "NVDA"
    context = {"ticker": stock.lower(),
               "year": 2025,
               "quarter": 4,
               }
    final_state = agent.graph.invoke(context, config)
    transcript_json = final_state["transcript_json"]

    print(transcript_json)


