import "./global.css";
import { StatusBar } from 'expo-status-bar';
import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, ScrollView, SafeAreaView, ActivityIndicator, TextInput } from 'react-native';
import Papa from 'papaparse';

// --- UTILS ---
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const FALLBACK_SYMBOLS = [
  "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
  "TATAMOTORS.NS", "ITC.NS", "BHARTIARTL.NS", "LICI.NS", "HINDUNILVR.NS", "BAJFINANCE.NS",
  "ADANIENT.NS", "ADANIPORTS.NS", "MARUTI.NS", "SUNPHARMA.NS", "AXISBANK.NS", "TITAN.NS"
];

const fetchAllSymbols = async () => {
  try {
    const url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv";
    const response = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
    const text = await response.text();
    return new Promise((resolve) => {
      Papa.parse(text, {
        header: true,
        complete: (results) => {
          const symbols = results.data
            .map(row => row.SYMBOL)
            .filter(s => s && s.length > 0)
            .map(s => `${s}.NS`);
          resolve(symbols);
        },
        error: () => resolve(FALLBACK_SYMBOLS)
      });
    });
  } catch (e) { return FALLBACK_SYMBOLS; }
};

const fetchStockDataNSE = async (symbol) => {
  try {
    const ticker = symbol.replace('.NS', '');
    const url = `https://www.nseindia.com/api/chart-databyindex?index=${ticker}`;

    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': `https://www.nseindia.com/get-quotes/equity?symbol=${ticker}`,
      }
    });

    const json = await response.json();
    const grapthData = json.grapthData || [];

    if (grapthData.length < 5) return null;

    const cleanData = grapthData.map(p => ({
      price: p[1],
      time: p[0]
    }));

    return { symbol, data: cleanData };
  } catch (e) {
    return null;
  }
};

const analyzeStockNSE = (symbol, data, trendFilter) => {
  if (!data || data.length < 5) return null;

  const currentPrice = data[data.length - 1].price;
  const prevPrice = data[data.length - 2].price;
  const startPrice = data[0].price;

  const priceMove = ((currentPrice / prevPrice) - 1) * 100;
  const totalTrend = ((currentPrice / startPrice) - 1) * 100;

  if (trendFilter) {
    const p1 = data[data.length - 3].price;
    const p2 = data[data.length - 2].price;
    const p3 = data[data.length - 1].price;
    if (!(p1 < p2 && p2 < p3)) return null;
  }

  if (Math.abs(priceMove) > 0.4 || Math.abs(totalTrend) > 1.2) {
    return {
      symbol: symbol.replace('.NS', ''),
      price: currentPrice.toFixed(2),
      move: priceMove.toFixed(2),
      total: totalTrend.toFixed(2)
    };
  }
  return null;
};

export default function App() {
  const [loading, setLoading] = useState(false);
  const [processedCount, setProcessedCount] = useState(0);
  const [totalSymbols, setTotalSymbols] = useState(0);
  const [statusMessage, setStatusMessage] = useState('Ready');
  const [results, setResults] = useState([]);
  const [trendFilter, setTrendFilter] = useState(false);
  const abortController = useRef(false);

  console.log("App Rendering", { loading, resultsCount: results.length });

  const performAnalysis = async () => {
    if (loading) { abortController.current = true; setLoading(false); return; }
    setLoading(true); setResults([]); abortController.current = false;
    setStatusMessage("Connecting to NSE...");

    let symbols = await fetchAllSymbols();

    if (symbols.length > 200) symbols = symbols.slice(0, 200);

    setTotalSymbols(symbols.length);
    setProcessedCount(0);

    const detected = [];
    const BATCH_SIZE = 2;

    for (let i = 0; i < symbols.length; i += BATCH_SIZE) {
      if (abortController.current) break;
      const batch = symbols.slice(i, i + BATCH_SIZE);
      const batchData = await Promise.all(batch.map(s => fetchStockDataNSE(s)));

      for (const res of batchData) {
        if (res) {
          const analysis = analyzeStockNSE(res.symbol, res.data, trendFilter);
          if (analysis) {
            detected.push(analysis);
            detected.sort((a, b) => Math.abs(parseFloat(b.move)) - Math.abs(parseFloat(a.move)));
            setResults([...detected]);
          }
        }
      }
      setProcessedCount(Math.min(i + BATCH_SIZE, symbols.length));
      setStatusMessage(`Scanning... ${Math.round((i / symbols.length) * 100)}%`);
      await sleep(800);
    }
    setLoading(false);
    setStatusMessage(`Done. Found ${detected.length} movers.`);
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0f172a' }} className="flex-1 bg-slate-900">
      <StatusBar style="light" />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 60, paddingBottom: 40 }}>

        <View className="items-center mb-10">
          <Text style={{ color: 'white' }} className="text-4xl font-black text-white tracking-widest italic">QUANT SCOUT</Text>
          <View className="h-1 w-24 bg-cyan-500 rounded-full mt-2" style={{ backgroundColor: '#06b6d4' }} />
          <Text style={{ color: '#64748b' }} className="text-slate-500 text-[10px] uppercase font-bold tracking-[4px] mt-4">NSE STANDALONE V1.1</Text>
        </View>

        <View className="bg-slate-800/80 p-6 rounded-[32px] border border-slate-700 shadow-2xl mb-8 overflow-hidden">
          <View className="flex-row justify-between items-center mb-8">
            <View>
              <Text className="text-white text-xl font-bold tracking-tight">Trend Check</Text>
              <Text className="text-slate-400 text-xs text-uppercase">Momentum filter</Text>
            </View>
            <TouchableOpacity
              onPress={() => setTrendFilter(!trendFilter)}
              className={`w-14 h-7 rounded-full ${trendFilter ? 'bg-cyan-500' : 'bg-slate-700'} justify-center px-1.5`}
            >
              <View className={`w-4 h-4 bg-white rounded-full ${trendFilter ? 'self-end' : 'self-start'}`} />
            </TouchableOpacity>
          </View>

          <TouchableOpacity
            className={`w-full py-5 rounded-2xl items-center active:scale-95 transition-transform ${loading ? 'bg-rose-600' : 'bg-cyan-600'}`}
            onPress={performAnalysis}
            style={{ elevation: 10 }}
          >
            <Text className="text-white text-lg font-black tracking-widest uppercase">
              {loading ? `STOP SCAN` : 'INITIATE ANALYSIS'}
            </Text>
          </TouchableOpacity>

          <View className="mt-6 flex-row items-center justify-between">
            <Text className="text-slate-500 text-[10px] font-mono uppercase">{statusMessage}</Text>
            <Text className="text-slate-500 text-[10px] font-mono">{processedCount}/{totalSymbols}</Text>
          </View>

          {loading && (
            <View className="h-1.5 bg-slate-900 mt-4 rounded-full overflow-hidden">
              <View
                className="h-full bg-cyan-400"
                style={{ width: `${(processedCount / totalSymbols) * 100}%` }}
              />
            </View>
          )}
        </View>

        {results.length > 0 && (
          <View>
            <View className="mb-6">
              <View className="flex-row justify-between items-end mb-2">
                <Text className="text-white text-2xl font-black italic tracking-tighter">MOVERS DETECTED</Text>
                <Text className="text-cyan-500 font-bold text-xs bg-cyan-500/10 px-3 py-1 rounded-full">{results.length}</Text>
              </View>
              <Text className="text-slate-500 text-[10px] font-bold uppercase tracking-[2px]">
                Analyzed {totalSymbols} stocks for momentum
              </Text>
            </View>

            {results.map((item) => (
              <View key={item.symbol} className="bg-slate-800/40 p-5 rounded-2xl mb-4 border border-slate-800 flex-row justify-between items-center shadow-sm">
                <View>
                  <Text className="text-white text-xl font-black tracking-tight">{item.symbol}</Text>
                  <Text className="text-slate-500 text-[10px] font-bold tracking-tighter">LTP: ₹{item.price}</Text>
                </View>
                <View className="items-end">
                  <Text className={`text-2xl font-black ${parseFloat(item.move) > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {parseFloat(item.move) > 0 ? '+' : ''}{item.move}%
                  </Text>
                  <Text className="text-slate-600 text-[9px] font-black uppercase tracking-widest">Momentum</Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({});
