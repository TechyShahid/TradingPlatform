
/**
 * Resamples 1-minute candle data into larger resolutions
 * @param {Array} data - Array of 1-minute candles {time, open, high, low, close, volume}
 * @param {Number} minutes - Target duration in minutes (e.g., 5, 15, 60)
 */
export function resampleData(data, minutes) {
    if (!data || data.length === 0) return [];
    if (minutes === 1) return data; // No resampling needed

    const resampled = [];
    let currentCandle = null;
    let periodStartTime = null; // timestamp of the current bucket start

    // Target duration in seconds
    const durationSeconds = minutes * 60;

    data.forEach(candle => {
        // Calculate the bucket start time
        // E.g. for 5m: 10:03 -> 10:00. 10:06 -> 10:05.
        // candle.time is seconds.
        // We should align to the grid.
        const timestamp = candle.time;
        const bucketStart = Math.floor(timestamp / durationSeconds) * durationSeconds;

        if (currentCandle && bucketStart !== periodStartTime) {
            // New period, push the old one
            resampled.push(currentCandle);
            currentCandle = null;
        }

        if (!currentCandle) {
            periodStartTime = bucketStart;
            currentCandle = {
                time: bucketStart,
                open: candle.open,
                high: candle.high,
                low: candle.low,
                close: candle.close,
                volume: candle.volume || 0
            };
        } else {
            // Update current candle
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
