from nselib import capital_market
import pandas as pd

def test():
    try:
        print("Fetching financial results for the last 1 month...")
        df = capital_market.financial_results_for_equity(period="1M", fin_period="Quarterly")
        if df is not None and not df.empty:
            print("Columns:", df.columns.tolist())
            print("First row:", df.iloc[0].to_dict())
            print("Total rows:", len(df))
        else:
            print("No data returned or empty DataFrame.")
    except Exception as e:
        print("Error fetching financial results:", e)

if __name__ == "__main__":
    test()
