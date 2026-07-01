import yfinance as yf
import sqlite3
import pandas as pd
from database import get_db_connection, init_db
import time
from datetime import datetime

def analyze_fundamental_drivers(symbol, bs_summary, is_summary):
    """ Call local Llama 3 to analyze balance sheet drivers """
    import urllib.request
    import json
    
    prompt = f"""
You are an expert quantitative fundamental analyst. Analyze the following 3-year financial summary for {symbol}.
Determine the primary driving factor for its consistent profit growth over the last 3 years based ONLY on this data.

Income Statement Summary:
{is_summary}

Balance Sheet Summary:
{bs_summary}

Provide your analysis in exactly 1-2 concise sentences focusing on the underlying financial drivers (e.g., margin expansion, debt reduction, massive revenue growth, operating leverage).
"""

    data = {
        "model": "llama3:latest",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3
        }
    }
    
    req = urllib.request.Request(
        'http://localhost:11434/api/generate',
        data=json.dumps(data).encode('utf-8'),
        method='POST'
    )
    req.add_header('Content-Type', 'application/json')

    try:
        response = urllib.request.urlopen(req, timeout=120)
        result = json.loads(response.read().decode('utf-8'))
        return result['response'].strip().replace('\n', ' ')
    except Exception as e:
        print(f"Error calling Ollama for {symbol}: {e}")
        return "Strong financial execution and favorable operating metrics."

def fetch_and_analyze_compounders():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all unique symbols from our deals database to scan
    cursor.execute('''
        SELECT DISTINCT symbol FROM bulk_deals
        UNION
        SELECT DISTINCT symbol FROM block_deals
    ''')
    rows = cursor.fetchall()
    symbols = [r['symbol'] for r in rows]
    
    # Optional: limit to a manageable test batch if there are hundreds
    # symbols = symbols[:50]
    
    total = len(symbols)
    print(f"Scanning {total} stocks for 3-year consistent compounders...")
    
    for idx, symbol in enumerate(symbols):
        print(f"[{idx+1}/{total}] Checking {symbol}...")
        try:
            yf_symbol = f"{symbol}.NS"
            ticker = yf.Ticker(yf_symbol)
            
            financials = ticker.financials
            if financials is None or financials.empty or len(financials.columns) < 4:
                continue
                
            # Get Net Income for the last 4 available periods (Year 0 is latest, Year 3 is oldest)
            net_income_series = []
            try:
                for col in financials.columns[:4]:
                    val = financials.loc['Net Income', col]
                    if pd.isna(val):
                        break
                    net_income_series.append(float(val))
            except:
                continue
                
            if len(net_income_series) < 4:
                continue
                
            # Ensure profitable for all 4 years
            if any(ni <= 0 for ni in net_income_series):
                continue
                
            # Calculate YoY growths (remember index 0 is most recent)
            # year1_growth is from year 1 to year 0
            y1_growth = ((net_income_series[0] / net_income_series[1]) - 1) * 100
            y2_growth = ((net_income_series[1] / net_income_series[2]) - 1) * 100
            y3_growth = ((net_income_series[2] / net_income_series[3]) - 1) * 100
            
            avg_growth = (y1_growth + y2_growth + y3_growth) / 3
            
            # Condition: Average growth > 10% AND the most recent year > 10%
            if avg_growth > 10.0 and y1_growth > 10.0:
                print(f"  -> {symbol} is a Compounder! Avg Growth: {avg_growth:.2f}%")
                
                # Extract summary for AI
                bs = ticker.balance_sheet
                bs_summary = ""
                is_summary = ""
                
                # Build Income Statement summary
                for col in financials.columns[:4]:
                    yr = str(col)[:4]
                    rev = financials.loc['Total Revenue', col] if 'Total Revenue' in financials.index else "N/A"
                    ni = financials.loc['Net Income', col] if 'Net Income' in financials.index else "N/A"
                    is_summary += f"Year {yr} - Revenue: {rev}, Net Income: {ni}\n"
                    
                # Build Balance Sheet summary
                if bs is not None and not bs.empty:
                    for col in bs.columns[:4]:
                        yr = str(col)[:4]
                        debt = bs.loc['Total Debt', col] if 'Total Debt' in bs.index else "N/A"
                        cash = bs.loc['Cash And Cash Equivalents', col] if 'Cash And Cash Equivalents' in bs.index else "N/A"
                        assets = bs.loc['Total Assets', col] if 'Total Assets' in bs.index else "N/A"
                        bs_summary += f"Year {yr} - Total Debt: {debt}, Cash: {cash}, Total Assets: {assets}\n"
                
                print(f"  -> Asking Llama 3 to analyze drivers...")
                ai_driver = analyze_fundamental_drivers(symbol, bs_summary, is_summary)
                print(f"  -> AI: {ai_driver}")
                
                cursor.execute('''
                    INSERT INTO consistent_compounders 
                    (symbol, avg_3yr_growth_pct, ai_driving_factor, last_updated)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        avg_3yr_growth_pct=excluded.avg_3yr_growth_pct,
                        ai_driving_factor=excluded.ai_driving_factor,
                        last_updated=excluded.last_updated
                ''', (symbol, avg_growth, ai_driver, datetime.now().isoformat()))
                conn.commit()
                
            time.sleep(0.5) # Rate limiting
            
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    conn.close()
    print("Finished scanning for consistent compounders.")

if __name__ == '__main__':
    fetch_and_analyze_compounders()
