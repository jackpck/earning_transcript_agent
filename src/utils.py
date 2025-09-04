import pandas as pd
import json
import copy
import os

def get_filter_from_filename(path_to_files: str):
    quarter_set = set()
    year_set = set()
    stock_set = set()
    for filename in os.listdir(path_to_files):
        filename_var = filename.split("_")
        stock_set.add(filename_var[0])
        quarter_set.add(int(filename_var[1][1]))
        year_set.add(int(filename_var[2]))
    stock_list = list(stock_set)
    quarter_list = list(quarter_set)
    year_list = list(year_set)
    stock_list.sort()
    quarter_list.sort()
    year_list.sort()
    return stock_list, quarter_list, year_list


def clean_json_str(transcript_json_str):
    return transcript_json_str.strip() \
        .removeprefix("```json") \
        .removeprefix("```") \
        .removesuffix("```")

def convert_json_to_df(transcript_json_str):
    transcript_json = json.loads(transcript_json_str)
    df = pd.DataFrame(transcript_json["sections"])
    return df

def filter_json(transcript_json_str: str,
                filter_dict: dict) -> str:
    transcript_json = json.loads(transcript_json_str)
    filtered_section = [s for s in transcript_json["sections"] if
                        all(
                            (not filter_dict[k]) or s[k] in filter_dict[k]
                            for k in filter_dict
                        )]
    filtered_transcript_json = copy.copy(transcript_json)
    filtered_transcript_json["sections"] = filtered_section
    return json.dumps(filtered_transcript_json)

def load_transcript_json(output_folder_path,
                         ticker,
                         quarter,
                         year):
    output_path = (f"{output_folder_path.rstrip('/')}"
                   f"/{ticker}_Q{quarter}_{year}_preprocessed.json")
    with open(output_path, "r", encoding="utf-8") as f:
        transcript_json_str = f.read()
    return transcript_json_str

def convert_json_to_df_filtered(transcript_json_str: str,
                                type_filter: list,
                                sentiment_filter: list):

    """
    convert transcript in json str format, filter by type and sentiment, and return a df capturing
    the sentiment summary of each statement
    """
    df = convert_json_to_df(transcript_json_str)
    df_statements = df[df["type"].isin(type_filter)]["statement"]
    df_summary = pd.DataFrame()
    for s in df_statements:
        if isinstance(s, list):
            df_summary = pd.concat([df_summary, pd.DataFrame(s)])
        else:
            df_summary = pd.concat([df_summary, pd.DataFrame([s])])

    df_summary = df_summary[df_summary["sentiment"].isin(sentiment_filter)]["sentiment summary"]
    return df_summary


if __name__ == "__main__":
    output_folder_path = "../data/processed"

    stock, quarter, year = get_filter_from_filename(output_folder_path)
