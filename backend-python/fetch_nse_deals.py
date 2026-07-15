import os
import pandas as pd
import sqlite3
from nselib import capital_market
from database import get_db_connection, init_db

def convert_to_numeric(val):
    try:
        # Remove commas if any
        if isinstance(val, str):
            val = val.replace(',', '')
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def convert_to_int(val):
    try:
        if isinstance(val, str):
            val = val.replace(',', '')
        return int(val)
    except (ValueError, TypeError):
        return 0

def fetch_and_store_deals(period="1M"):
    """
    Fetches bulk and block deals for the given period and stores them in the database.
    Returns a dict with counts of new deals inserted.
    """
    print(f"Fetching data for period: {period}")
    
    # Ensure DB is initialized
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    new_bulk_deals = 0
    new_block_deals = 0
    
    try:
        # Fetch Bulk Deals
        print("Fetching Bulk Deals...")
        bulk_df = capital_market.bulk_deal_data(period=period)
        if bulk_df is not None and not bulk_df.empty:
            for _, row in bulk_df.iterrows():
                try:
                    cursor.execute('''
                        INSERT INTO bulk_deals 
                        (deal_date, symbol, security_name, client_name, buy_sell, quantity_traded, trade_price, remarks)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['Date'],
                        row['Symbol'],
                        row['SecurityName'],
                        row['ClientName'],
                        row['Buy/Sell'],
                        convert_to_int(row['QuantityTraded']),
                        convert_to_numeric(row['TradePrice/Wght.Avg.Price']),
                        row['Remarks']
                    ))
                    new_bulk_deals += 1
                except sqlite3.IntegrityError:
                    # Ignore duplicates based on UNIQUE constraint
                    pass
            conn.commit()
            print(f"Inserted {new_bulk_deals} new bulk deals.")
        else:
            print("No bulk deals found.")
            
    except Exception as e:
        print("Error fetching bulk deals:", e)

    try:
        # Fetch Block Deals
        print("Fetching Block Deals...")
        block_df = capital_market.block_deals_data(period=period)
        if block_df is not None and not block_df.empty:
            for _, row in block_df.iterrows():
                try:
                    cursor.execute('''
                        INSERT INTO block_deals 
                        (deal_date, symbol, security_name, client_name, buy_sell, quantity_traded, trade_price, remarks)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['Date'],
                        row['Symbol'],
                        row['SecurityName'],
                        row['ClientName'],
                        row['Buy/Sell'],
                        convert_to_int(row['QuantityTraded']),
                        convert_to_numeric(row['TradePrice/Wght.Avg.Price']),
                        row['Remarks']
                    ))
                    new_block_deals += 1
                except sqlite3.IntegrityError:
                    # Ignore duplicates based on UNIQUE constraint
                    pass
            conn.commit()
            print(f"Inserted {new_block_deals} new block deals.")
        else:
            print("No block deals found.")
            
    except Exception as e:
        print("Error fetching block deals:", e)
        
    finally:
        conn.close()
        print("Done fetching and storing deals.")
    
    return {
        'new_bulk_deals': new_bulk_deals,
        'new_block_deals': new_block_deals
    }

if __name__ == '__main__':
    # Initial fetch for the last 1 month
    fetch_and_store_deals(period="1M")
