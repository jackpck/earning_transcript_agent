from langchain_core.tools import tool
import yfinance as yf
import pandas as pd

@tool
def get_stock_price(symbol: str,
                    startdate: str,
                    enddate: str) -> pd.DataFrame:
    """
    Get historical price of a stock

    :param symbol: ticker symbol of a stock
    :param startdate: start date of historical price extraction
    :param enddate: end date of historical price extraction
    :return: dataframe of historical daily close price and volume
    """
    interval='1d'
    df = yf.download(tickers=symbol, interval=interval,
                       start=startdate, end=enddate)

    return df[["Close","Volume"]]

if __name__ == "__main__":
    symbol = 'nvda'
    startdate = '2025-01-01'
    enddate = '2025-03-01'

    df = get_stock_price(symbol=symbol,
                         startdate=startdate,
                         enddate=enddate)

    print(df)
