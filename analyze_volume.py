import nselib
from nselib import capital_market
import yfinance as yf
import pandas as pd
import datetime
import time
import sys
import symbol_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

# In-memory cache for the running process (avoids even the SQLite read on repeat calls)
_SYMBOL_CACHE = []

def get_nifty_all_symbols():
    global _SYMBOL_CACHE
    if _SYMBOL_CACHE:
        return _SYMBOL_CACHE

    # Delegates to symbol_cache: downloads only on first run / every Monday,
    # otherwise reads from local SQLite DB instantly.
    symbols = symbol_cache.get_symbols()
    _SYMBOL_CACHE = symbols
    return symbols

# LIQUIDITY SETTINGS
MIN_AVG_5MIN_TURNOVER = 500000  # ₹5,00,000

def analyze_volumes(progress_callback=None, check_trend=False):
    results = {
        'matches': [],
        'top_spikes': [],
        'total_scanned': 0,
        'status': 'starting'
    }
    
    symbols = get_nifty_all_symbols()
    MAX_SYMBOLS = 2200
    symbols = symbols[:MAX_SYMBOLS]
    total_count = len(symbols)
    
    # RESOURCE CONTROL: We use a fixed number of workers and disable yfinance internal threads
    # to avoid "can't start new thread" errors (OS limit exhaustion).
    CHUNK_SIZE = 100 
    chunks = [symbols[i:i + CHUNK_SIZE] for i in range(0, total_count, CHUNK_SIZE)]
    
    all_processed_stats = []
    processed_count = 0
    
    def process_batch(batch_symbols):
        batch_results = []
        batch_matches = []
        yf_tickers = [f"{sym}.NS" for sym in batch_symbols]
        
        try:
            # IMPORTANT: Set threads=False here because we are already parallelized by ThreadPoolExecutor.
            # This prevents the "can't start new thread" error on macOS/Linux.
            data = yf.download(yf_tickers, period="5d", interval="5m", group_by='ticker', progress=False, threads=False, timeout=10)
            
            if not data.empty:
                for ticker in batch_symbols:
                    try:
                        yf_ticker = f"{ticker}.NS"
                        ticker_data = data[yf_ticker] if isinstance(data.columns, pd.MultiIndex) else data
                        
                        res = process_single_ticker(ticker, ticker_data, check_trend=check_trend)
                        if res:
                            batch_results.append(res)
                            if res['ratio'] > 2.0:
                                batch_matches.append(res)
                    except:
                        continue
        except Exception as e:
            pass # Keep moving on network errors
            
        return batch_results, batch_matches

    # Use 10 workers: 2200 stocks / 100 per batch = 22 batches. 
    # With 10 workers, we finish in ~2-3 rounds of networking (~10-15s total).
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_chunk = {executor.submit(process_batch, chunk): chunk for chunk in chunks}
        
        for future in as_completed(future_to_chunk):
            results_chunk, matches_chunk = future.result()
            all_processed_stats.extend(results_chunk)
            results['matches'].extend(matches_chunk)
            
            processed_count += len(future_to_chunk[future])
            if progress_callback:
                progress_callback(processed_count, total_count, f"Processing: {processed_count}/{total_count}")

    # Sort and finalize
    results['matches'].sort(key=lambda x: x['ratio'], reverse=True)
    all_processed_stats.sort(key=lambda x: x['ratio'], reverse=True)
    results['top_spikes'] = all_processed_stats[:20]
    results['total_scanned'] = total_count
    results['status'] = 'complete'
    
    return results

    # Sort results
    results['matches'].sort(key=lambda x: x['ratio'], reverse=True)
    all_processed_stats.sort(key=lambda x: x['ratio'], reverse=True)
    results['top_spikes'] = all_processed_stats[:20] # Return top 20
    results['total_scanned'] = total_count
    results['status'] = 'complete'
    
    return results


def process_single_ticker(symbol, df, check_trend=False):
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
    
    # Volume Trend Check (Last 15 minutes = last 3 candles of 5 mins each)
    if check_trend:
        if len(vol_series) < 3:
            return None
        # Check if volume is strictly increasing: Vol(t-2) < Vol(t-1) < Vol(t)
        v1, v2, v3 = vol_series.iloc[-3], vol_series.iloc[-2], vol_series.iloc[-1]
        if not (v1 < v2 < v3):
            return None

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

