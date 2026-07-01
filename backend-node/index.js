import express from 'express';
import cors from 'cors';
import { NseIndia } from 'stock-nse-india';

const app = express();
const PORT = 3000;
// Note: We do NOT instantiate NseIndia globally anymore to avoid stale sessions.

app.use(cors());
app.use(express.json());

// Get all stock symbols (optional, for search)
app.get('/api/symbols', async (req, res) => {
    try {
        const nseService = new NseIndia();
        const symbols = await nseService.getAllStockSymbols();
        res.json(symbols);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Get Quote (Live price)
app.get('/api/quote/:symbol', async (req, res) => {
    try {
        const nseService = new NseIndia();
        const symbol = req.params.symbol.toUpperCase();
        const data = await nseService.getEquityDetails(symbol);
        res.json(data);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Get Historical/Intraday Data for Chart
app.get('/api/chart/:symbol', async (req, res) => {
    try {
        const nseService = new NseIndia();
        const symbol = req.params.symbol.toUpperCase();
        const resolution = req.query.resolution || '1D';
        
        console.log(`[API] Fetching chart for ${symbol}, Resolution: ${resolution}`);

        let data = [];
        
        // Strict check for Intraday 
        if (resolution === '5m' || resolution === '15m' || resolution === '60m' || resolution === '1m') {
             console.log(`[API] Calling Intraday for ${symbol}`);
             const raw = await nseService.getEquityIntradayData(symbol);
             data = raw;
        } else {
            // Historical: 1D, 1W, 1M
            console.log(`[API] Calling Historical for ${symbol} (Fresh Instance + Chunking)`);
            
            const MAX_MONTHS = 24;
            const CHUNK_SIZE = 3; 
            const requests = [];

            for (let i = 0; i < MAX_MONTHS; i += CHUNK_SIZE) {
                const end = new Date();
                end.setMonth(end.getMonth() - i);
                
                const start = new Date();
                start.setMonth(start.getMonth() - (i + CHUNK_SIZE));
                
                requests.push(nseService.getEquityHistoricalData(symbol, { start, end }));
            }

            console.log(`[API] Firing ${requests.length} requests in parallel...`);
            
            try {
                const results = await Promise.all(requests);
                
                // Merge all result arrays
                let allCandles = [];
                results.forEach((res, index) => {
                     let list = [];
                     if (Array.isArray(res) && res.length > 0 && res[0].data) {
                         list = res[0].data;
                     }
                     console.log(`[API] Chunk ${index} returned ${list.length} candles`);
                     allCandles = [...allCandles, ...list];
                });

                // Deduplicate items based on unique timestamp
                const uniqueMap = new Map();
                allCandles.forEach(item => {
                    const globalTime = item.CH_TIMESTAMP || item.mtimestamp || item.date;
                    if (globalTime) uniqueMap.set(globalTime, item);
                });
                
                const uniqueList = Array.from(uniqueMap.values());
                
                // Sort by time ascending
                uniqueList.sort((a, b) => {
                    const getTime = (itm) => new Date(itm.CH_TIMESTAMP || itm.mtimestamp || itm.date).getTime();
                    return getTime(a) - getTime(b);
                });

                // Wrap in expected structure
                data = [{ data: uniqueList }];
                
                console.log(`[API] Total Merged History: ${uniqueList.length} candles.`);
                
            } catch (err) {
                console.error("[API] Error in parallel fetch:", err);
                throw err;
            }
        }

        res.json(data);
    } catch (error) {
        console.error("Error fetching chart data:", error);
        res.status(500).json({ error: error.message });
    }
});

// Market Status
app.get('/api/market-status', async (req, res) => {
    try {
        const nseService = new NseIndia();
        const status = await nseService.getMarketStatus();
        res.json(status);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
    console.log("-----------------------------------------");
    console.log("   Trading Platform Server v6.0 FreshSess");
    console.log("-----------------------------------------");
});
