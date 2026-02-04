import requests
import nselib
from nselib import capital_market
import yfinance as yf
import pandas as pd
import datetime
import time
import sys
import io

def get_nifty_all_symbols():
    print("Fetching ALL NSE equity symbols...")
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        }
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            symbols = df['SYMBOL'].tolist()
            return [s for s in symbols if isinstance(s, str) and len(s) > 0]
    except Exception as e:
        print(f"Error fetching symbols: {e}")
    
    return ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN']

# LIQUIDITY SETTINGS
MIN_AVG_5MIN_TURNOVER = 500000  # ₹5,00,000

def analyze_volumes(progress_callback=None):
    results = {
        'matches': [],
        'top_spikes': [],
        'total_scanned': 0,
        'status': 'starting'
    }
    
    symbols = get_nifty_all_symbols()
    
    # PERFORMANCE OPTIMIZATION: Larger batches reduce request overheads
    BATCH_SIZE = 50 
    MAX_SYMBOLS = 2000
    symbols = symbols[:MAX_SYMBOLS]
    total_count = len(symbols)
    
    all_processed_stats = []
    
    for i in range(0, total_count, BATCH_SIZE):
        batch = symbols[i:i+BATCH_SIZE]
        yf_tickers = [f"{sym}.NS" for sym in batch]
        
        if progress_callback:
            progress_callback(i, total_count, f"Analyzing {i}-{min(i+BATCH_SIZE, total_count)}...")
        
        try:
            # group_by='ticker' is faster for large batches
            data = yf.download(yf_tickers, period="5d", interval="5m", group_by='ticker', progress=False, threads=True)
            
            if not data.empty:
                for ticker in batch:
                    try:
                        yf_ticker = f"{ticker}.NS"
                        ticker_data = data[yf_ticker] if len(batch) > 1 else data
                        
                        res = process_single_ticker(ticker, ticker_data)
                        if res:
                            all_processed_stats.append(res)
                            if res['ratio'] > 2.0:
                                results['matches'].append(res)
                    except:
                        continue
            
            # SMARTER DELAY: Half-second sleep is usually enough for these batch sizes
            time.sleep(0.5) 
                        
        except Exception as e:
            if "Rate limited" in str(e):
                if progress_callback:
                    progress_callback(i, total_count, "Rate limited. Waiting 15s...")
                time.sleep(15)
            else:
                time.sleep(1)

    # Sort results
    results['matches'].sort(key=lambda x: x['ratio'], reverse=True)
    all_processed_stats.sort(key=lambda x: x['ratio'], reverse=True)
    results['top_spikes'] = all_processed_stats[:20] # Return top 20
    results['total_scanned'] = total_count
    results['status'] = 'complete'
    
    return results


def process_single_ticker(symbol, df):
    if df.empty or 'Volume' not in df.columns or 'Close' not in df.columns:
        return None
        
    # Drop rows where volume or close is missing
    clean_df = df.dropna(subset=['Volume', 'Close'])
    
    if len(clean_df) < 10: 
        return None
        
    # Liquidity Check (Turnover = Price * Volume)
    # We calculate average 5-minute turnover over the 5-day window
    avg_turnover = (clean_df['Close'] * clean_df['Volume']).mean()
    
    if avg_turnover < MIN_AVG_5MIN_TURNOVER:
        return None
        
    vol_series = clean_df['Volume']
    current_vol = float(vol_series.iloc[-1])
    avg_vol = float(vol_series.mean())
    
    if avg_vol == 0:
        return None
        
    ratio = float(current_vol / avg_vol)
    
    return {
        'symbol': symbol,
        'current_vol': current_vol,
        'avg_vol': avg_vol,
        'ratio': ratio,
        'avg_turnover': float(avg_turnover)
    }



if __name__ == "__main__":
    analyze_volumes()

