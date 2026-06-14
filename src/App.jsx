import { useState, useEffect, useRef } from 'react';
import ChartContainer from './components/ChartContainer';
import Watchlist from './components/Watchlist';
import { fetchHistoricalData, subscribeToUpdates, startWatchlistPolling, DEFAULT_WATCHLIST, fetchQuote } from './services/dataService';
import './styles/App.css';
import { Layout, Activity } from 'lucide-react';

function App() {
  const [symbol, setSymbol] = useState('RELIANCE');
  const [chartData, setChartData] = useState([]);
  const [resolution, setResolution] = useState('1D');
  const lastCandleRef = useRef(null);

  // Advanced Watchlist State
  const [watchlists, setWatchlists] = useState(() => {
    // Load from local storage or default
    const saved = localStorage.getItem('watchlists');
    return saved ? JSON.parse(saved) : {
      'Default': DEFAULT_WATCHLIST,
      'Tech': ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM'],
      'Banks': ['HDFCBANK', 'ICICIBANK', 'SBIN', 'AXISBANK', 'KOTAKBANK']
    };
  });
  const [activeWatchlistName, setActiveWatchlistName] = useState(() => {
    return localStorage.getItem('activeWatchlistName') || 'Default';
  });

  // Derived state for the current valid stocks data
  // We store the *data* (price/change) separate from the *list of symbols*
  // to avoid complex syncing. We just poll whatever is visible.
  const [watchlistData, setWatchlistData] = useState([]);

  // Indicators State - OFF by default
  const [activeIndicators, setActiveIndicators] = useState({
    volume: false,
    sma: false,
    ema: false,
    bb: false,
    rsi: false
  });
  const [showIndicatorsMenu, setShowIndicatorsMenu] = useState(false);

  const chartRef = useRef(null);

  // Persist state
  useEffect(() => {
    localStorage.setItem('watchlists', JSON.stringify(watchlists));
    localStorage.setItem('activeWatchlistName', activeWatchlistName);
    // Also persist API URL for the standalone analyzer.html in public/
    localStorage.setItem('VITE_API_URL', import.meta.env.VITE_API_URL || 'http://localhost:3000/api');
  }, [watchlists, activeWatchlistName]);

  // Load initial chart data
  useEffect(() => {
    setChartData([]);
    lastCandleRef.current = null;
    fetchHistoricalData(symbol, resolution).then(data => {
      setChartData(data);
      if (data && data.length > 0) {
        lastCandleRef.current = data[data.length - 1]; // Store the last historical candle
      }
    });
  }, [symbol, resolution]);

  // Subscribe to live updates for Chart
  useEffect(() => {
    const unsubscribe = subscribeToUpdates(symbol, (newTick) => {
      if (chartRef.current && lastCandleRef.current) {

        // Lightweight Charts 1D resolution expects Midnight UTC timestamps
        // Evaluate if this newTick belongs to the SAME day or a NEW day
        const lastCandleDate = new Date(lastCandleRef.current.time * 1000);
        const newTickDate = new Date(newTick.time * 1000);

        const isSameDay = lastCandleDate.getUTCFullYear() === newTickDate.getUTCFullYear() &&
          lastCandleDate.getUTCMonth() === newTickDate.getUTCMonth() &&
          lastCandleDate.getUTCDate() === newTickDate.getUTCDate();

        let mergedCandle;

        if (isSameDay) {
          // STILL CURRENT DAY: update the existing candle's bounds
          mergedCandle = {
            time: lastCandleRef.current.time,      // Keep exact chart interval tick time (Midnight UTC)
            open: lastCandleRef.current.open,      // Keep original open
            high: Math.max(lastCandleRef.current.high, newTick.high), // Update high
            low: Math.min(lastCandleRef.current.low, newTick.low),   // Update low
            close: newTick.close,                  // Update current trailing close
            volume: newTick.volume > 0 ? newTick.volume : lastCandleRef.current.volume
          };
        } else {
          // NEW TRADING DAY: Start a fresh candle
          // Snap the live tick to Midnight UTC for Lightweight Charts compatibility
          const midnightUTC = Date.UTC(newTickDate.getUTCFullYear(), newTickDate.getUTCMonth(), newTickDate.getUTCDate()) / 1000;

          mergedCandle = {
            time: midnightUTC,
            open: newTick.open || newTick.close,
            high: newTick.high || newTick.close,
            low: newTick.low || newTick.close,
            close: newTick.close,
            volume: newTick.volume || 0
          };
        }

        // Update the chart
        chartRef.current.update(mergedCandle);

        // Save back for next tick
        lastCandleRef.current = mergedCandle;
      }
    });
    return () => unsubscribe();
  }, [symbol]);

  // Watchlist Polling for ACTIVE list
  useEffect(() => {
    // Get symbols for active list
    const symbols = watchlists[activeWatchlistName] || [];

    // Initial fill with empty data to avoid flicker or show loading
    setWatchlistData(symbols.map(s => ({
      symbol: s, price: 0, change: 0, changePercent: 0
    })));

    const unsubscribe = startWatchlistPolling(symbols, (updatedData) => {
      // updatedData is array of quotes.
      // We need to merge this order with the symbols order if we want to preserve it,
      // or just show what we got.

      // Let's create a map for easy lookup
      const dataMap = {};
      updatedData.forEach(d => dataMap[d.symbol] = d);

      const merged = symbols.map(s => {
        return dataMap[s] || { symbol: s, price: 0, change: 0, changePercent: 0 };
      });

      setWatchlistData(merged);
    });
    return () => unsubscribe();
  }, [watchlists, activeWatchlistName]);

  // Handlers
  const handleAddStock = async (newSymbol) => {
    // Optional: Verify if valid symbol via API
    // For now, we trust user or check if quote returns valid
    // But to be snappy, we just add it to list.
    // Better: Fetch quote once to verify.
    const quote = await fetchQuote(newSymbol);
    if (!quote || quote.price === 0) {
      alert(`Could not find symbol: ${newSymbol}`);
      return;
    }

    setWatchlists(prev => ({
      ...prev,
      [activeWatchlistName]: [...prev[activeWatchlistName], newSymbol]
    }));
  };

  const handleRemoveStock = (symbolToRemove) => {
    setWatchlists(prev => ({
      ...prev,
      [activeWatchlistName]: prev[activeWatchlistName].filter(s => s !== symbolToRemove)
    }));
  };

  const handleCreateWatchlist = (name) => {
    if (watchlists[name]) {
      alert("List already exists");
      return;
    }
    setWatchlists(prev => ({
      ...prev,
      [name]: []
    }));
    setActiveWatchlistName(name);
  };

  const handleDeleteWatchlist = (name) => {
    // Don't delete last one
    const keys = Object.keys(watchlists);
    if (keys.length <= 1) return;

    const newLists = { ...watchlists };
    delete newLists[name];
    setWatchlists(newLists);

    if (activeWatchlistName === name) {
      setActiveWatchlistName(Object.keys(newLists)[0]);
    }
  };

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="logo">
          <Layout className="logo-icon" size={24} />
          <span>ProTrade</span>
        </div>
        <div className="symbol-info">
          <span className="current-symbol">{symbol}</span>
          <div className="timeframe-selector">
            {['1D', '1W', '1M'].map(res => (
              <button
                key={res}
                className={`tf-btn ${resolution === res ? 'active' : ''}`}
                onClick={() => setResolution(res)}
              >
                {res}
              </button>
            ))}
          </div>
          <span className="status-indicator">Market Open</span>
        </div>
        <div className="controls">
          <div className="indicators-menu-container">
            <button
              className="menu-btn"
              onClick={() => setShowIndicatorsMenu(!showIndicatorsMenu)}
            >
              fx Indicators
            </button>
            {showIndicatorsMenu && (
              <div className="indicators-dropdown">
                <label>
                  <input
                    type="checkbox"
                    checked={activeIndicators.volume}
                    onChange={(e) => setActiveIndicators(p => ({ ...p, volume: e.target.checked }))}
                  /> Volume
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={activeIndicators.sma}
                    onChange={(e) => setActiveIndicators(p => ({ ...p, sma: e.target.checked }))}
                  /> SMA (20)
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={activeIndicators.ema}
                    onChange={(e) => setActiveIndicators(p => ({ ...p, ema: e.target.checked }))}
                  /> EMA (20)
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={activeIndicators.bb}
                    onChange={(e) => setActiveIndicators(p => ({ ...p, bb: e.target.checked }))}
                  /> Bollinger Bands
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={activeIndicators.rsi}
                    onChange={(e) => setActiveIndicators(p => ({ ...p, rsi: e.target.checked }))}
                  /> RSI (14)
                </label>
              </div>
            )}
          </div>
          <a
            href="/TradingPlatform/analyzer.html"
            className="menu-btn secondary-btn"
            title="NSE Volume Spike Radar"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none' }}
          >
            <Activity size={18} />
            Scanner
          </a>
        </div>
      </header>

      <main className="main-content">
        <div className="chart-section" onClick={() => setShowIndicatorsMenu(false)}>
          {chartData.length > 0 &&
            <ChartContainer
              ref={chartRef}
              data={chartData}
              volumeData={chartData}
              symbol={symbol}
              activeIndicators={activeIndicators}
            />
          }
        </div>
        <aside className="sidebar" onClick={() => setShowIndicatorsMenu(false)}>
          <Watchlist
            stocks={watchlistData}
            onSelectStock={setSymbol}
            currentSymbol={symbol}

            watchlists={watchlists}
            activeWatchlist={activeWatchlistName}
            onSelectWatchlist={setActiveWatchlistName}
            onCreateWatchlist={handleCreateWatchlist}
            onDeleteWatchlist={handleDeleteWatchlist}
            onAddStock={handleAddStock}
            onRemoveStock={handleRemoveStock}
          />
        </aside>
      </main>
    </div>
  );
}

export default App;
