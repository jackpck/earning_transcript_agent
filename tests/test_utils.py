import pytest
from langchain_core.messages import HumanMessage

from system_prompts import prompts
from src import tools
from src import frontend_agent
from src import utils

OUTPUT_FOLDER_PATH = "./data/processed"

def test_get_filter_from_filename():
    stock_list, quarter_list, year_list = utils.get_filter_from_filename(OUTPUT_FOLDER_PATH)
    assert stock_list == ["nvda"]
    assert year_list == [2025]
    assert quarter_list == [1,2,3,4]


