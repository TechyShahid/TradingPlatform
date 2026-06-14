from nselib import capital_market
import pandas as pd

def test():
    try:
        # bulk deal
        df = capital_market.bulk_deal_data(period="1M")
        print("Bulk deal columns:", df.columns.tolist() if df is not None else None)
        print("Bulk deal rows:", len(df) if df is not None else 0)
    except Exception as e:
        print("Error with bulk_deal_data:", e)

    try:
        # block deal
        df2 = capital_market.block_deals_data(period="1M")
        print("Block deal columns:", df2.columns.tolist() if df2 is not None else None)
        print("Block deal rows:", len(df2) if df2 is not None else 0)
    except Exception as e:
        print("Error with block_deals_data:", e)

if __name__ == "__main__":
    test()
