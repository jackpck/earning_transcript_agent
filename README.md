# Agentic AI: Earnings call transcript chatbot

## Introduction

The goal of the agentic chatbot is to provide asset management analyst a way to summarize topics mentioned
in an earnings call. The consolidation of topics and emerging risks mentioned is useful when assessing the 
risks of a portfolio (mutual fund, ETF), which is critical in order to ensure product risk is aligned with
customer KYC (risk tolerence, exposure etc).


### Design philosophy

Essentially, this is a chatbot that provides a summary of what the user want to know based on a company
earnings call. Instead of using a RAG, we use in-context information retrieval. The biggest advantage is 
the ease of implementation and require less fine-tuning, which is typically required for a performant RAG.
Also, in-context chatbot tends to have lower latency due to less LLM (just one) used. The shortcoming of
in-context retrieval compared to RAG is the limitation of the context window and the risk of 
context window stuffing, i.e. chatbot becomes less aware of the content as the size of the input increases.

To get around this issue, we developed a backend preprocessing agent to progressingly structure the earning 
transcripts as much as possible. For example, tagging with metadata, splitting statements into logical 
sub-statements with coherent theme and sentiment, and summarizing a statement into one sentence that explain 
the sentiment of the statement. All these preprocessings allow the frontend chatbot agent to answer questions 
much more effectively as answer is generated based on a list of condensed sentences instead of the full 
transcript.

Separating the backend preprocessing agent from the frontend chatbot improves response time and therefore
user experience. The preprocessed transcripts are further persisted, removing the need to run the
extraction and preprocessing everytime.

## Agent graph

### Backend agent
- Run this to extract and process all the stocks you want to analyze their earnings call transcripts
- Once run, the preprocessed json will be saved under `/data/processed`. The app will only populate the
filter for those in the folder

![Alt text](./static/backend_agent_graph.png)

### Frontend agent 
- An agentic chatbot answering user's question based on the processed earning call statements of the selected
  stock. The agentic chatbot can call stock price API if necessary to answer user's query.

![Alt text](./static/frontend_agent_graph.png)

### Overall agent workflow

![Alt text](./static/full_agent_graph.png)

## Run the chatbot (frontend) app

Streamlit is choice of app for user interaction with the analyzer. To run the app locally, run 
`streamlit run app.py` inside folder `src`

Select from the stock, year and quarter dropdowns. If the preprocessed json (contains the LLM generated 
sentiment and risk analysis) of the selected stock is not available, the agentic workflow will run to 
preprocess and analyze from the raw transcript text. See the agent workflow graph above. Therefore, the
user might encounter long wait time if the preprocessed json is not already available.

## How to use the chatbot?

The chatbot that allows user ask any questions from the transcript. Instead of using RAG, the transcript
and the user query are both processed in-context. To mitigate context-stuffing (loss of accuracy due to
long input), further filters are provided to further trim down the json for the chatbot to consider
when answering user's questions.

Some questions the user might consider asking:
- summarize the main themes mentioned in the responses. Return
  1. number of themes
  2. name and short description of each theme
  3. describe how each theme might have affected the stock performance of the following quarter
   
## Instructions
- To load the virtual environment: `source venv/Scripts/activate`
- To set env variable `GOOGLE_API_KEY`, go to `config` and run `source set_api_key.sh`  
- To run the app locally, go to `/src` and run `streamlit run app.py`
- To create a docker image: `docker build -t earning_call_agent .`
- To run a docker container: `docker run -p 8501:8501 -e GOOGLE_API_KEY=$GOOGLE_API_KEY 
  earning_call_agent`. Since no API KEY info is included in the docker image, the
  API KEY will remain local and be manually passed on when running a docker container
- To run a docker container on another machine:
    - tag the image: `docker tag earning_call_agent dockerhub_username/earning_call_agent:latest`
    - log in to docker hub: `docker login`
    - push the image: `docker push dockerhub_username/earning_call_agent:latest`
    - on another machine, pull the image: `docker pull dockerhub/earning_call_agent:latest`
    - run the container: use the *To run a docker container* command above
- To run pytest:
    - go to root directory, run `python -m pytest -v tests/`. Using `python -m`
    avoids using `python` and `pytest` from different locations
- CI/CD:
  - the CI pipeline will be triggered when PR or push to the `main` branch, as specified
  by `.github/workflows/ci.yml`. The CI pipeline has two parts
    - pytest
    - build and push docker image
  - user credentials and API keys are saved under *Actions secrets and variables* on Github


