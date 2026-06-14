const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api';

import { resampleDaily } from '../utils/resampleDaily';

// Fetch historical data for a symbol
// resolution: '1D', '1W', '1M'
export async function fetchHistoricalData(symbol, resolution = '1D') {
  try {
    const response = await fetch(`${API_URL}/chart/${symbol}?resolution=${resolution}`);
    if (!response.ok) throw new Error('Failed to fetch data');
    const rawData = await response.json();

    let candles = [];

    // NEW PARSING LOGIC: Handle multi-chunk response
    // Server now returns: [{data: [...]}, {data: [...]}, ...]
    if (Array.isArray(rawData)) {
      console.log(`[DataService] Received ${rawData.length} chunks from server`);

      // Merge all chunks
      rawData.forEach((chunk, idx) => {
        if (chunk.data && Array.isArray(chunk.data)) {
          console.log(`[DataService] Chunk ${idx}: ${chunk.data.length} candles`);
          chunk.data.forEach(item => {
            const dateStr = item.mtimestamp || item.date || item.CH_TIMESTAMP;
            const time = parseNseDate(dateStr);
            candles.push({
              time: time,
              open: item.chOpeningPrice || item.CH_OPENING_PRICE || item.open,
              high: item.chTradeHighPrice || item.CH_TRADE_HIGH_PRICE || item.high,
              low: item.chTradeLowPrice || item.CH_TRADE_LOW_PRICE || item.low,
              close: item.chClosingPrice || item.CH_CLOSING_PRICE || item.close,
              volume: item.chTotTradedQty || item.CH_TOT_TRADED_QTY || item.volume || 0,
            });
          });
        }
      });
    }

    // Sort by time ascending
    candles.sort((a, b) => a.time - b.time);

    console.log(`[DataService] Total candles after merging: ${candles.length}`);

    // Resample if needed
    if (resolution === '1W') candles = resampleDaily(candles, '1W');
    if (resolution === '1M') candles = resampleDaily(candles, '1M');

    return candles;

  } catch (error) {
    console.error(`Error fetching history for ${symbol}:`, error);
    return [];
  }
}

// Helper to parse "30-Jan-2026" or ISO strings
function parseNseDate(dateStr) {
  if (!dateStr) return 0;

  // Check if ISO format (YYYY-MM-DD...)
  if (dateStr.includes('T')) {
    const d = new Date(dateStr);
    // Extracted local Indian day using local methods, NOT UTC methods
    const year = d.getFullYear();
    const month = d.getMonth();
    const day = d.getDate();
    // Force to UTC midnight for charting
    return Date.UTC(year, month, day) / 1000;
  }

  // Common NSE string: "19-Feb-2026" or "19-Feb-2026 15:30:00"
  const months = {
    'Jan': 0, 'Feb': 1, 'Mar': 2, 'Apr': 3, 'May': 4, 'Jun': 5,
    'Jul': 6, 'Aug': 7, 'Sep': 8, 'Oct': 9, 'Nov': 10, 'Dec': 11
  };
  const parts = dateStr.split(/[- ]/);
  if (parts.length >= 3) {
    const day = parseInt(parts[0]);
    const monthStr = parts[1];
    const year = parseInt(parts[2]);

    if (months[monthStr] !== undefined && !isNaN(day) && !isNaN(year)) {
      // Force to UTC midnight
      return Date.UTC(year, months[monthStr], day) / 1000;
    }
  }

  // Fallback (try to extract local and force UTC)
  const d = new Date(dateStr);
  return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 1000;
}

// Fetch single quote for watchlist
export async function fetchQuote(symbol) {
  try {
    const response = await fetch(`${API_URL}/quote/${symbol}`);
    if (!response.ok) throw new Error('Failed to fetch quote');
    const data = await response.json();

    // Data usually has priceInfo object
    const priceInfo = data.priceInfo || {};
    const metadata = data.metadata || {};

    // Parse last update time "30-Jan-2026 16:00:00"
    let timestamp = 0;
    if (metadata.lastUpdateTime) {
      // Format: "30-Jan-2026 16:00:00"
      // parseNseDate handles date part, but we have time.
      // Let's standard parse this one as it usually works, or implement custom
      timestamp = new Date(metadata.lastUpdateTime).getTime() / 1000;
      if (isNaN(timestamp)) {
        // Fallback manual parse if needed
        timestamp = Date.now() / 1000;
      }
    }

    // Parse intraday high low if available
    const intraDayHighLow = priceInfo.intraDayHighLow || {};

    return {
      symbol: metadata.symbol || symbol,
      price: priceInfo.lastPrice || 0,
      change: priceInfo.change || 0,
      changePercent: priceInfo.pChange || 0,
      previousClose: priceInfo.previousClose || 0,
      open: priceInfo.open || 0,
      high: intraDayHighLow.max || priceInfo.lastPrice || 0,
      low: intraDayHighLow.min || priceInfo.lastPrice || 0,
      close: priceInfo.lastPrice || 0,
      volume: 0, // Quote endpoint typically omits full total intraday volume here, relying on list
      time: timestamp
    };
  } catch (error) {
    console.error(`Error fetching quote for ${symbol}:`, error);
    return null;
  }
}

// Setup live polling for a single symbol (chart updates)
export function subscribeToUpdates(symbol, callback) {
  let lastTime = 0;

  // Poll every 5 seconds
  const interval = setInterval(async () => {
    const quote = await fetchQuote(symbol);
    if (quote && quote.time > 0) {
      callback({
        time: quote.time,
        open: quote.open,
        high: quote.high,
        low: quote.low,
        close: quote.price,
        volume: quote.volume
      });
    }
  }, 5000);

  return () => clearInterval(interval);
}

// Poll watchlist
export function startWatchlistPolling(symbols, callback) {
  const poll = async () => {
    const promises = symbols.map(s => fetchQuote(s));
    const results = await Promise.all(promises);
    // Filter out nulls
    const valid = results.filter(r => r !== null);
    callback(valid);
  };

  poll(); // Initial run
  const interval = setInterval(poll, 10000); // Poll every 10 sec
  return () => clearInterval(interval);
}

export const DEFAULT_WATCHLIST = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'];
