import argparse
import json
import os
import pandas as pd
import time
from datetime import datetime, timedelta
from binance.um_futures import UMFutures  # USDT-M Futures
from typing import List, Dict, Any, Optional

def fetch_klines(
    client: UMFutures,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 500,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None
) -> List[List]:
    """
    Fetch candlestick data from Binance USDT-M Futures.
    
    Args:
        client: Binance client
        symbol: Trading pair symbol (default: BTCUSDT)
        interval: Candlestick interval (e.g., 1m, 5m, 15m, 1h, 4h, 1d)
        limit: Number of candles to fetch (max 1500)
        start_time: Optional start time in milliseconds
        end_time: Optional end time in milliseconds
        
    Returns:
        List of candlestick data
    """
    # Fetch kline data
    klines = client.klines(
        symbol=symbol,
        interval=interval,
        limit=limit,
        startTime=start_time,
        endTime=end_time
    )
    
    return klines

def process_klines(klines: List) -> List[Dict[str, Any]]:
    """
    Process raw kline data into a more usable format.
    
    Args:
        klines: Raw kline data from Binance API
        
    Returns:
        List of processed candlestick data
    """
    processed_data = []
    
    for kline in klines:
        # Extract and transform the important fields
        processed_kline = {
            "open_time": datetime.fromtimestamp(kline[0] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            "open": float(kline[1]),
            "high": float(kline[2]),
            "low": float(kline[3]),
            "close": float(kline[4]),
            "volume": float(kline[5]),
            "close_time": datetime.fromtimestamp(kline[6] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            "quote_asset_volume": float(kline[7]),
            "number_of_trades": int(kline[8]),
            "taker_buy_base_volume": float(kline[9]),
            "taker_buy_quote_volume": float(kline[10])
        }
        
        # Add derived fields that might be useful for analysis
        processed_kline.update({
            "price_range": processed_kline["high"] - processed_kline["low"],
            "price_change": processed_kline["close"] - processed_kline["open"],
            "price_change_pct": ((processed_kline["close"] - processed_kline["open"]) / processed_kline["open"]) * 100,
            "body_size": abs(processed_kline["close"] - processed_kline["open"]),
            "upper_wick": processed_kline["high"] - max(processed_kline["open"], processed_kline["close"]),
            "lower_wick": min(processed_kline["open"], processed_kline["close"]) - processed_kline["low"],
            "is_bullish": processed_kline["close"] > processed_kline["open"],
            "timestamp": int(kline[0])  # Keep original timestamp for sorting and time-series analysis
        })
        
        processed_data.append(processed_kline)
    
    return processed_data

def fetch_large_dataset(
    client: UMFutures,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    num_candles: int = 500
) -> List[List]:
    """
    Fetch a large dataset by making multiple API calls if necessary.
    
    Args:
        client: Binance client
        symbol: Trading pair symbol
        interval: Candlestick interval
        num_candles: Total number of candles to fetch
        
    Returns:
        Combined list of kline data
    """
    # Initialize empty list for all klines
    all_klines = []
    
    # Calculate the maximum number of candles per request (Binance limit)
    max_per_request = 1000
    
    # Calculate the number of requests needed
    num_requests = (num_candles + max_per_request - 1) // max_per_request
    
    # Get current time in milliseconds
    end_time = int(time.time() * 1000)
    
    # Map interval to milliseconds
    interval_ms = {
        "1m": 60 * 1000,
        "3m": 3 * 60 * 1000,
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "30m": 30 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "2h": 2 * 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "6h": 6 * 60 * 60 * 1000,
        "8h": 8 * 60 * 60 * 1000,
        "12h": 12 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
        "3d": 3 * 24 * 60 * 60 * 1000,
        "1w": 7 * 24 * 60 * 60 * 1000,
        "1M": 30 * 24 * 60 * 60 * 1000
    }
    
    for i in range(num_requests):
        # Calculate how many candles to request in this iteration
        candles_to_request = min(max_per_request, num_candles - len(all_klines))
        
        # Fetch klines
        klines = fetch_klines(
            client=client,
            symbol=symbol,
            interval=interval,
            limit=candles_to_request,
            end_time=end_time
        )
        
        # Add klines to the list
        all_klines = klines + all_klines
        
        # If we didn't get any klines, break the loop
        if not klines:
            break
        
        # Update end_time for the next request
        end_time = klines[0][0] - 1
        
        # Sleep to avoid API rate limits
        time.sleep(0.5)
        
        # If we have enough klines, break the loop
        if len(all_klines) >= num_candles:
            break
    
    # Trim to the requested number
    return all_klines[:num_candles]

def calculate_additional_metrics(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculate additional metrics that might be useful for trading.
    
    Args:
        data: Processed kline data
        
    Returns:
        Enhanced data with additional metrics
    """
    if not data:
        return []
    
    # Convert to DataFrame for easier calculations
    df = pd.DataFrame(data).sort_values('timestamp')
    
    # Calculate some basic technical indicators
    # 1. Simple Moving Averages (SMA)
    sma_periods = [7, 14, 25, 50, 200]
    for period in sma_periods:
        if len(df) >= period:
            df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
    
    # 2. Exponential Moving Averages (EMA)
    ema_periods = [9, 21]
    for period in ema_periods:
        if len(df) >= period:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    
    # 3. Relative Strength Index (RSI) - 14 period
    if len(df) >= 14:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        # Avoid division by zero
        loss = loss.replace(0, 0.00001)
        
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # 4. Bollinger Bands (20, 2)
    if len(df) >= 20:
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['stddev'] = df['close'].rolling(window=20).std()
        df['bollinger_upper'] = df['sma_20'] + (df['stddev'] * 2)
        df['bollinger_lower'] = df['sma_20'] - (df['stddev'] * 2)
        df['bollinger_width'] = (df['bollinger_upper'] - df['bollinger_lower']) / df['sma_20']
    
    # 5. Average True Range (ATR) - 14 period
    if len(df) >= 14:
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(14).mean()
    
    # 6. MACD
    if len(df) >= 26:
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # 7. Volume indicators
    df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma_20']
    
    # 8. Volatility metrics
    if len(df) >= 20:
        df['volatility_20'] = df['close'].pct_change().rolling(window=20).std() * (252 ** 0.5)  # Annualized
    
    # Sort by timestamp to ensure chronological order
    df = df.sort_values('timestamp')
    
    # Return as list of dictionaries
    return df.fillna("").to_dict('records')

def save_to_json(data: List[Dict[str, Any]], filename: str = "btc_klines.json") -> None:
    """
    Save processed data to a JSON file.
    
    Args:
        data: Processed kline data
        filename: Output filename
    """
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Data saved to {filename}")

def main():
    """Main function to run the script with command line arguments."""
    parser = argparse.ArgumentParser(description='Fetch Binance BTCUSDT Perpetual Futures candlestick data')
    
    parser.add_argument('-i', '--interval', type=str, default='1h',
                        help='Candlestick interval (e.g., 1m, 5m, 15m, 1h, 4h, 1d)')
    
    parser.add_argument('-n', '--num_candles', type=int, default=500,
                        help='Number of candles to fetch (max 1500)')
    
    parser.add_argument('-o', '--output', type=str, default='btc_klines.json',
                        help='Output JSON filename')
    
    parser.add_argument('-s', '--symbol', type=str, default='BTCUSDT',
                        help='Trading symbol (default: BTCUSDT)')
    
    parser.add_argument('-k', '--api_key', type=str, default=None,
                        help='Binance API key (optional)')
    
    parser.add_argument('-p', '--api_secret', type=str, default=None,
                        help='Binance API secret (optional)')
    
    args = parser.parse_args()
    
    # Initialize Binance USDT-M Futures client
    client = UMFutures(key=args.api_key, secret=args.api_secret)
    
    print(f"Fetching {args.num_candles} {args.interval} candles for {args.symbol}...")
    
    # Fetch data
    klines = fetch_large_dataset(
        client=client,
        symbol=args.symbol,
        interval=args.interval,
        num_candles=args.num_candles
    )
    
    # Process data
    processed_data = process_klines(klines)
    
    # Calculate additional metrics
    enhanced_data = calculate_additional_metrics(processed_data)
    
    # Save to JSON
    save_to_json(enhanced_data, args.output)
    
    print(f"Successfully processed {len(enhanced_data)} candles.")
    
    # Print sample of the data
    if enhanced_data:
        print("\nSample of processed data (first record):")
        sample_keys = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'price_change_pct', 'rsi_14', 'macd']
        sample = {k: enhanced_data[0].get(k, "N/A") for k in sample_keys if k in enhanced_data[0]}
        print(json.dumps(sample, indent=2))

if __name__ == "__main__":
    main()