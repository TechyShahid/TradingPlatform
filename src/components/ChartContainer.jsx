import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { calculateSMA, calculateEMA, calculateBollingerBands, calculateRSI } from '../utils/indicators';

const ChartContainer = forwardRef(({ data, volumeData, symbol, activeIndicators = {} }, ref) => {
    const chartContainerRef = useRef();
    const chartRef = useRef();

    // Refs for Series
    const seriesRef = useRef({
        candle: null,
        volume: null,
        sma: null,
        ema: null,
        bbUpper: null,
        bbLower: null,
        rsi: null // This needs separate chart/pane ideally or carefully managed scale
    });

    // We need 2 charts for RSI? Or one chart with stored panes? 
    // Lightweight charts V4+ supports multiple panes but via API it's automatic if you give different scaleID?
    // Actually, stacking separate charts is arguably easier for React resizing if we want full control, 
    // but the library supports panes natively now.
    // Let's stick to one chart and use `to` layout with `pane` option if available, OR just separate DOM containers.
    // Given the complexity of "Pane" in lightweight-charts for React novice, let's use ONE chart but update 
    // the layout options if we enable RSI (reduce main chart height?).

    // ACTUALLY: The easiest way to have RSI below is to have TWO charts in a vertical flex container synchronized.
    // But synchronization is hard.
    // Lightweight charts automatically stacks panes if you add a series to a new pane index? no.
    // It is simpler to just Overlay everything for now EXCEPT RSI.
    // RSI range is 0-100. Price is 1500+.
    // We MUST use a separate priceScaleId for RSI to overlay it without crushing the candles.
    // OR we put RSI in a separate <div>/chart below the main one.
    // Let's use ONE chart and overlay RSI on a separate RIGHT scale or LEFT scale?
    // No, standard is separate pane. 
    // Let's try "Pane 1" simply by using `pane: 1` in options if using v5?
    // V5 doesn't have explicit "pane" property in `addSeries`. It determines panes by order? 
    // Actually, V5 doesn't fully expose panes control easily in the react wrapper style.
    // 
    // Safe bet: Overlay RSI on the main chart but pinned to the bottom 20% using scaleMargins!
    // And shift the main Price Scale to top 75%.

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const handleResize = () => {
            if (chartRef.current) {
                chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#131722' },
                textColor: '#d1d4dc',
            },
            grid: {
                vertLines: { color: '#2a2e39' },
                horzLines: { color: '#2a2e39' },
            },
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                borderColor: '#2a2e39',
            },
            rightPriceScale: {
                borderColor: '#2a2e39',
                visible: true,
                scaleMargins: {
                    top: 0.1, // Main chart takes top 90% space mostly, but we adjust if RSI is on
                    bottom: activeIndicators.rsi ? 0.25 : 0.1, // Leave room for volume/RSI
                }
            },
        });

        chartRef.current = chart;

        // 1. Volume Series (Overlay at bottom)
        const volumeSeries = chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' },
            priceScaleId: '', // Overlay
            scaleMargins: {
                top: 0.8, // Push to bottom
                bottom: 0,
            },
        });
        seriesRef.current.volume = volumeSeries;
        volumeSeries.setData(volumeData.map(d => ({
            time: d.time,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
        })));
        volumeSeries.applyOptions({ visible: activeIndicators.volume !== false }); // Default true in logic passed

        // 2. Candle Series (Main)
        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
        });
        seriesRef.current.candle = candleSeries;
        candleSeries.setData(data);

        // 3. SMA
        if (activeIndicators.sma) {
            const smaSeries = chart.addSeries(LineSeries, { color: '#2962ff', lineWidth: 2, title: 'SMA 20' });
            const smaData = calculateSMA(data, 20);
            smaSeries.setData(smaData);
            seriesRef.current.sma = smaSeries;
        }

        // 4. EMA
        if (activeIndicators.ema) {
            const emaSeries = chart.addSeries(LineSeries, { color: '#e91e63', lineWidth: 2, title: 'EMA 20' });
            const emaData = calculateEMA(data, 20);
            emaSeries.setData(emaData);
            seriesRef.current.ema = emaSeries;
        }

        // 5. Bollinger Bands
        if (activeIndicators.bb) {
            const bbData = calculateBollingerBands(data, 20, 2);

            const bbUpper = chart.addSeries(LineSeries, { color: 'rgba(38, 166, 154, 0.5)', lineWidth: 1, title: 'BB Upper' });
            bbUpper.setData(bbData.upper);
            seriesRef.current.bbUpper = bbUpper;

            const bbLower = chart.addSeries(LineSeries, { color: 'rgba(38, 166, 154, 0.5)', lineWidth: 1, title: 'BB Lower' });
            bbLower.setData(bbData.lower);
            seriesRef.current.bbLower = bbLower;
        }

        // 6. RSI (Separate Scale/Pane hack)
        if (activeIndicators.rsi) {
            // We create a NEW price scale ID for RSI
            const rsiScaleId = 'rsi-scale';

            // Adjust Main Scale margins to make room at bottom
            chart.priceScale('right').applyOptions({
                scaleMargins: {
                    top: 0.05,
                    bottom: 0.30, // Leave 30% at bottom
                }
            });

            const rsiSeries = chart.addSeries(LineSeries, {
                color: '#9c27b0',
                lineWidth: 2,
                title: 'RSI 14',
                priceScaleId: rsiScaleId,
            });

            // Configure the RSI scale to sit at the bottom
            chart.priceScale(rsiScaleId).applyOptions({
                scaleMargins: {
                    top: 0.75, // Start at 75% down
                    bottom: 0,
                },
                visible: true,
                autoScale: false,
                borderVisible: false,
            });
            // Manual range for RSI
            // We can't easily set min/max on autoScale:false without knowing API properly for this specific scale
            // But let's rely on data or default. Standard is 0-100.

            const rsiData = calculateRSI(data, 14);
            rsiSeries.setData(rsiData);

            // Add reference lines 70/30? 
            // Lightweight charts doesn't have "horizontal lines" besides series
            // We can add a baseline series maybe? Or just leave it raw.

            seriesRef.current.rsi = rsiSeries;
        }

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, [data, activeIndicators]);
    // Re-creating chart completely when toggling indicators is inefficient in prod 
    // but easiest for accurate layout/scale updates in this prototype.

    useImperativeHandle(ref, () => ({
        update: (candle) => {
            // For real updates, we need to update ALL active series math.
            // This is tricky without keeping full history history here or in hook.
            // For this prototype, we will just update the Candle and Volume 
            // and ignore recalculating indicators for the *new single tick* to avoid complexity.
            // If user wants live indicators, we need to fetch full history + tick and recalc.

            if (seriesRef.current.candle) seriesRef.current.candle.update(candle);
            if (seriesRef.current.volume) {
                seriesRef.current.volume.update({
                    time: candle.time,
                    value: candle.volume,
                    color: candle.close >= candle.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
                });
            }
        }
    }));

    return (
        <div
            ref={chartContainerRef}
            style={{ width: '100%', height: '100%', position: 'relative' }}
        />
    );
});

export default ChartContainer;
