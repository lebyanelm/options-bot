import numpy as np
import pandas as pd

class KeyLevelsTradingStrategy:
    def __init__(self, timeframes, volatility_threshold=0.02):
        """
        Initialize bot with multiple timeframes and a volatility filter.
        :param timeframes: Dictionary with timeframe labels as keys and OHLC data as values.
        :param volatility_threshold: ATR-based filter to avoid volatile markets.
        """
        self.timeframes = dict(m1=timeframes["m1"], m5=timeframes["m5"], m15=timeframes["m15"])
        self.volatility_threshold = volatility_threshold
        self.support_levels = []
        self.resistance_levels = []
        self.recalculate_levels()
        # print(f"Support level: {self.support_levels[-1]}, Resistance: {self.resistance_levels[-1]}")

    def recalculate_levels(self):
        """
        Dynamically recalculate support and resistance levels based on multi-timeframe analysis.
        """
        levels = []
        for timeframe, ohlc in self.timeframes.items():
            # swing_highs = ohlc['high'].rolling(window=10).max()
            # swing_lows = ohlc['low'].rolling(window=10).min()
            # levels.extend(swing_highs.dropna().values)
            # levels.extend(swing_lows.dropna().values)
            # def most_recurring_pivot_point(ohlc_data, bin_size=0.5):
            """
            Calculates the most recurring pivot point based on OHLC data.
            
            Parameters:
            - ohlc_data: DataFrame with columns ['High', 'Low', 'Close']
            - bin_size: Rounding interval for grouping similar pivot points (default = 0.5)
            
            Returns:
            - The most recurring pivot point (float)
            """
            # Step 1: Compute Pivot Points
            ohlc["pivot"] = (ohlc["high"] + ohlc["low"] + ohlc["close"]) / 3

            # Step 2: Round Pivot Points to the nearest bin_size to group similar levels
            ohlc["pivot_rounded"] = np.round(ohlc["pivot"] / 0.5) * 0.5

            # Step 3: Find the most frequent pivot level
            pivot_counts = ohlc["pivot_rounded"].value_counts()
            most_frequent_pivot = pivot_counts.idxmax()  # Highest occurring pivot level

            # Step 4: Calculate the average pivot within this frequent range
            recurring_pivots = ohlc[ohlc["pivot_rounded"] == most_frequent_pivot]["pivot"]
            most_recurring_pivot = recurring_pivots.mean()

            print("Pivot point: ", most_recurring_pivot)

        self.support_levels = sorted(set(level for level in levels if level < ohlc.iloc[-1]['close']))
        self.resistance_levels = sorted(set(level for level in levels if level > ohlc.iloc[-1]['close']))

    def is_near_key_level(self, price, levels, threshold=0.002):
        """
        Check if price is near a key level within a given threshold.
        """
        return any(abs(price - level) <= threshold for level in levels)
    
    def calculate_atr(self, ohlc, period=14):
        """
        Calculate the Average True Range (ATR) for volatility filtering.
        """
        ohlc['tr'] = np.maximum(ohlc['high'] - ohlc['low'],
                                 np.abs(ohlc['high'] - ohlc['close'].shift(1)),
                                 np.abs(ohlc['low'] - ohlc['close'].shift(1)))
        return ohlc['tr'].rolling(window=period).mean().iloc[-1]

    def signal_trade(self, ohlc):
        """
        Determine whether to enter a CALL, PUT, or NO TRADE.
        :param ohlc: Pandas DataFrame with 'open', 'high', 'low', 'close'.
        :return: 'CALL', 'PUT', or 'NOT'
        """
        self.recalculate_levels()
        last_candle = ohlc.iloc[-1]
        prev_candle = ohlc.iloc[-2]

        close_price = last_candle['close']
        open_price = last_candle['open']
        high_price = last_candle['high']
        low_price = last_candle['low']
        
        atr = self.calculate_atr(ohlc)
        if atr > self.volatility_threshold:
            return "NOT"  # Avoid trading in high volatility

        near_support = self.is_near_key_level(close_price, self.support_levels)
        near_resistance = self.is_near_key_level(close_price, self.resistance_levels)

        if near_support and low_price < prev_candle['low'] and close_price > open_price:
            return "CALL"
        if near_resistance and high_price > prev_candle['high'] and close_price < open_price:
            return "PUT"

        return "NOT"