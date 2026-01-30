
/**
 * Resamples Daily candle data into Weekly or Monthly resolutions.
 * @param {Array} data - Array of Daily candles {time, open, high, low, close, volume} (time in seconds)
 * @param {String} type - '1W' or '1M'
 */
export function resampleDaily(data, type) {
    if (!data || data.length === 0) return [];
    if (type === '1D') return data;

    const resampled = [];
    let currentCandle = null;
    let currentPeriodKey = null; // String key to identify period (e.g. "2025-W10" or "2025-01")

    data.forEach(candle => {
        const date = new Date(candle.time * 1000);
        let periodKey;

        if (type === '1W') {
            // ISO Week number strategy or simple Monday start
            // Simple: Reset on Monday (Day 1). 
            // Or just use ISO string prefix if we want crude weeks.
            // Let's use a "Week Start Date" approach.
            const day = date.getDay(); // 0=Sun, 1=Mon...
            const diff = date.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
            // This sets to Monday
            const monday = new Date(date);
            monday.setDate(diff);
            monday.setHours(0, 0, 0, 0);
            periodKey = monday.getTime();
        } else if (type === '1M') {
            // Period is Month
            periodKey = `${date.getFullYear()}-${date.getMonth()}`;
        } else {
            return;
        }

        if (currentCandle && periodKey !== currentPeriodKey) {
            resampled.push(currentCandle);
            currentCandle = null;
        }

        if (!currentCandle) {
            currentPeriodKey = periodKey;

            // For time, usually we use the START of period
            let candleTime = candle.time;
            if (type === '1M') {
                const d = new Date(candle.time * 1000);
                d.setDate(1); // 1st of month
                candleTime = d.getTime() / 1000;
            } else if (type === '1W') {
                // periodKey is the Monday timestamp
                candleTime = periodKey / 1000;
            }

            currentCandle = {
                time: candleTime,
                open: candle.open,
                high: candle.high,
                low: candle.low,
                close: candle.close,
                volume: candle.volume || 0
            };
        } else {
            currentCandle.high = Math.max(currentCandle.high, candle.high);
            currentCandle.low = Math.min(currentCandle.low, candle.low);
            currentCandle.close = candle.close;
            currentCandle.volume += (candle.volume || 0);
        }
    });

    if (currentCandle) {
        resampled.push(currentCandle);
    }

    return resampled;
}
