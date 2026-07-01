import yfinance as yf
import sqlite3
import pandas as pd
from database import get_db_connection, init_db
import time

def fetch_fundamentals(symbols):
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    total = len(symbols)
    
    for idx, symbol in enumerate(symbols):
        print(f"[{idx+1}/{total}] Fetching fundamentals for {symbol}...")
        try:
            yf_symbol = f"{symbol}.NS"
            ticker = yf.Ticker(yf_symbol)
            
            # Fetch financials (Income Statement)
            financials = ticker.financials
            # Fetch balance sheet
            balance_sheet = ticker.balance_sheet
            
            if financials is None or financials.empty:
                print(f"No financials found for {symbol}. Skipping.")
                continue
                
            # Iterate through columns (which are dates/years)
            for date_col in financials.columns:
                year = str(date_col)[:4] # Extract year
                
                # Get metrics with fallbacks
                try:
                    total_revenue = float(financials.loc['Total Revenue', date_col]) if 'Total Revenue' in financials.index else 0.0
                except: total_revenue = 0.0
                
                try:
                    net_income = float(financials.loc['Net Income', date_col]) if 'Net Income' in financials.index else 0.0
                except: net_income = 0.0
                
                try:
                    ebitda = float(financials.loc['EBITDA', date_col]) if 'EBITDA' in financials.index else 0.0
                except: ebitda = 0.0
                
                total_assets = 0.0
                total_liabilities = 0.0
                
                if balance_sheet is not None and not balance_sheet.empty and date_col in balance_sheet.columns:
                    try:
                        total_assets = float(balance_sheet.loc['Total Assets', date_col]) if 'Total Assets' in balance_sheet.index else 0.0
                    except: pass
                    
                    try:
                        total_liabilities = float(balance_sheet.loc['Total Liabilities Net Minority Interest', date_col]) if 'Total Liabilities Net Minority Interest' in balance_sheet.index else 0.0
                    except: pass

                # Insert into DB
                try:
                    cursor.execute('''
                        INSERT INTO fundamentals 
                        (symbol, year, total_revenue, net_income, ebitda, total_assets, total_liabilities)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(symbol, year) DO UPDATE SET
                            total_revenue=excluded.total_revenue,
                            net_income=excluded.net_income,
                            ebitda=excluded.ebitda,
                            total_assets=excluded.total_assets,
                            total_liabilities=excluded.total_liabilities
                    ''', (symbol, year, total_revenue, net_income, ebitda, total_assets, total_liabilities))
                except Exception as e:
                    print(f"DB Error for {symbol} {year}: {e}")
                    
            conn.commit()
            print(f"Successfully stored data for {symbol}.")
            time.sleep(1) # Prevent rate limiting
            
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")

    conn.close()
    print("Finished fetching fundamentals.")

if __name__ == '__main__':
    # Sample list for testing. To scan all, you can use nselib.equity_list()
    test_symbols = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", 
        "HUL", "ITC", "SBI", "LENSKART", "ZOMATO"
    ]
    fetch_fundamentals(test_symbols)
