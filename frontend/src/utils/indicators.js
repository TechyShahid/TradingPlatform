
// Simple Moving Average
export function calculateSMA(data, period) {
    const sma = [];
    for (let i = period - 1; i < data.length; i++) {
        const slice = data.slice(i - period + 1, i + 1);
        const sum = slice.reduce((acc, val) => acc + val.close, 0);
        sma.push({ time: data[i].time, value: sum / period });
    }
    return sma;
}

// Exponential Moving Average
export function calculateEMA(data, period) {
    const k = 2 / (period + 1);
    const ema = [];
    let previousEma = data[0].close; // Start with first close as initial EMA approximation

    // Alternative: Start SMA for first valid point at 'period' index

    for (let i = 0; i < data.length; i++) {
        const close = data[i].close;
        // EMA = Price(t) * k + EMA(y) * (1 – k)
        const value = close * k + previousEma * (1 - k);
        ema.push({ time: data[i].time, value });
        previousEma = value;
    }

    // Trim first few distinct non-stabilized points if needed, 
    // but for charting usually we just show all.
    return ema;
}

// Bollinger Bands
// Returns object with { upper: [], lower: [], middle: [] }
export function calculateBollingerBands(data, period = 20, multiplier = 2) {
    const upper = [];
    const lower = [];
    const middle = []; // This is just SMA 20

    for (let i = period - 1; i < data.length; i++) {
        const slice = data.slice(i - period + 1, i + 1);
        const sum = slice.reduce((acc, val) => acc + val.close, 0);
        const sma = sum / period;

        // Standard Deviation
        const squaredDiffs = slice.map(val => Math.pow(val.close - sma, 2));
        const avgSquaredDiff = squaredDiffs.reduce((acc, val) => acc + val, 0) / period;
        const stdDev = Math.sqrt(avgSquaredDiff);

        const time = data[i].time;
        middle.push({ time, value: sma });
        upper.push({ time, value: sma + (multiplier * stdDev) });
        lower.push({ time, value: sma - (multiplier * stdDev) });
    }

    return { upper, lower, middle };
}

// Relative Strength Index
export function calculateRSI(data, period = 14) {
    const rsi = [];
    if (data.length <= period) return rsi;

    let gain = 0;
    let loss = 0;

    // First period calculation
    for (let i = 1; i <= period; i++) {
        const change = data[i].close - data[i - 1].close;
        if (change > 0) gain += change;
        else loss -= change; // loss is positive magnitude
    }

    let avgGain = gain / period;
    let avgLoss = loss / period;

    for (let i = period + 1; i < data.length; i++) {
        const change = data[i].close - data[i - 1].close;
        const currentGain = change > 0 ? change : 0;
        const currentLoss = change < 0 ? -change : 0;

        // Wilder 's Smoothing Method
        avgGain = ((avgGain * (period - 1)) + currentGain) / period;
        avgLoss = ((avgLoss * (period - 1)) + currentLoss) / period;

        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        const value = 100 - (100 / (1 + rs));

        rsi.push({ time: data[i].time, value });
    }

    return rsi;
}
