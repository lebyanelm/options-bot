# Imports
import logging
import json
import asyncio
import socketio
import atexit
import random
import time
import datetime
import numpy as np
from time_sync import timesync
from pymongo import MongoClient
from aiohttp import web


def connect_database():
    try:
        client = MongoClient(host=config["MONGODB"])
        client.admin.command("ping")
        return client.get_database(config["APP_NAME"])
    except ConnectionError as error:
            logging.error(error)


def load_config():
    config = dict()
    try:
        with open("config.json", 'r') as config_file:
            config = json.load(config_file)
    except Exception as error:
        logging.error(error)

    config = append_session_config(config)    
    return config

    
def append_session_config(_config: dict) -> dict:
    _config["SESSION_PROFIT"] = 0
    _config["SESSION_ORDERS"] = 0
    _config["SESSION_ACCURACY"] = 0
    _config["SESSION_RISK"] = 0
    return _config

    
node_process = None
async def start_node_script(script_path):
    """
    Asynchronously starts the Node.js script.
    """
    global node_process
    try:
        node_process = await asyncio.create_subprocess_exec(
            'node', script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        logging.info("Node.js script started.")

        while True:
            line = await node_process.stdout.readline()
            if line:
                # logging.info(f"Node.js: {line.decode().strip()}")
                pass
    except Exception as e:
        logging.error(f"Error running Node.js script: {e}")
    finally:
        if node_process and node_process.returncode is None:
            node_process.terminate()
            logging.info("Node.js script terminated.")


async def run_server(app):
    """
    Starts the server and launches the Node.js script once the server is ready.
    """
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='localhost', port=config["PROXY_SERVER_PORT"])
    await site.start()

    logging.info("Server started and ready to accept connections.")

    asyncio.create_task(start_node_script(config["PROXY_SCRIPT"]))

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logging.info("Server shutting down.")
        await runner.cleanup()


def cleanup_routine(pending_orders, socketio_server):
    global node_process
    if node_process is not None:
        try:
            if node_process is not None:  # Check if Node.js process is still running
                node_process.terminate()
                logging.info("Node.js script terminated.")
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
    logging.info("Running cleanup routine.")

    # Cancel any pending orders left
    # for pending_order in pending_orders:
    #     socketio_server.emit("cancelPendingOrder", dict(ticket = pending_order["ticket"]))
    #     pending_orders.remove(pending_order)
    # logging.info("Pending orders cleared before exit.")


def load_candles(asset_id: str, _time = None) -> dict:
    index = get_random_request_id()
    period = config["PERIOD"]
    if _time is None:
        time_sync = timesync.get_synced_time()
        time_red = last_time(time_sync, period)
    else:
        time_red = _time
    offset = get_period_offset(period)
    return dict(
        asset = asset_id,
        index = index,
        offset = offset,
        period = period,
        time = time_red
    )   


def last_time(timestamp, period):
    timestamp_redondeado = (timestamp // period) * period
    return timestamp_redondeado
    
    
def get_period_offset(period):
    if (period == 5): return 1_000;
    if (period == 10): return 2_000;
    if (period == 15): return 3_000;
    if (period == 30): return 6_000;
    if (period == 60): return 9_000;
    if (period == 120): return 18_000;
    if (period == 180): return 27_000;
    if (period == 300): return 45_000;
    if (period == 600): return 90_000;
    if (period == 900): return 135_000;
    if (period == 1_800): return 270_000;
    if (period == 3_600): return 540_000;
    if (period == 14_400): return 2_160_000;
    if (period == 86_4000): return 12_960_000;
    return 0;
    
    

import numpy as np

def average_time_above_pivot(ohlc_data, pivot_point, direction=0):
    """
    Determines the average number of candles price stays above (for calls) or below (for puts) 
    the pivot point before breaking.

    :param ohlc_data: List of dictionaries with OHLCV data (each representing a candle).
                      Example format: [{"open": 1.2, "high": 1.3, "low": 1.1, "close": 1.25}, ...]
    :param pivot_point: The calculated pivot level.
    :param direction: "call" for time above pivot, "put" for time below pivot.
    :return: Average time (in number of candles) price remains above/below the pivot.
    """
    durations = []
    current_duration = 0
    in_position = False  # Tracks whether price is currently above/below the pivot
    
    for _, candle in ohlc_data.iterrows():
        price_above = candle['close'] > pivot_point
        price_below = candle['close'] < pivot_point

        if direction == 0:
            if price_above:
                current_duration += 1
                in_position = True
            elif in_position:  # Break below pivot point
                durations.append(current_duration)
                current_duration = 0
                in_position = False

        elif direction == 1:
            if price_below:
                current_duration += 1
                in_position = True
            elif in_position:  # Break above pivot point
                durations.append(current_duration)
                current_duration = 0
                in_position = False

    # Append last duration if still in position
    if in_position and current_duration > 0:
        durations.append(current_duration)

    return np.mean(durations) if durations else 0  # Return 0 if no durations recorded

    
def get_random_request_id():
    rand = str(random.randint(10, 99))
    cu = time.time()
    t = str(cu + (2 * 60 * 60))
    return int(float(t + rand))
    
    
    
def calculate_pivot_point(ohlc, bin_size=0.5, touch_tolerance=0.2):
    """
    Determines the most recurring pivot point and counts how many times it has been touched.
    
    Parameters:
    - ohlc: DataFrame with columns ['high', 'low', 'close']
    - bin_size: Rounding interval for grouping similar pivot points (default = 0.5)
    - touch_tolerance: Allowed price deviation to consider a pivot "touched" (default = 0.2)
    
    Returns:
    - most_frequent_pivot (float): The most recurring pivot level.
    - touch_count (int): Number of times the pivot has been touched.
    - breakout_probability (float): Estimated probability of a breakout.
    """
    # Compute Pivot Points
    ohlc["pivot"] = (ohlc["high"] + ohlc["low"] + ohlc["close"]) / 3

    # Round Pivot Points to the nearest bin_size to group similar levels
    ohlc["pivot_rounded"] = np.round(ohlc["pivot"] / bin_size) * bin_size

    # Find the most frequent pivot level
    pivot_counts = ohlc["pivot_rounded"].value_counts()
    most_frequent_pivot = pivot_counts.idxmax()  # Highest occurring pivot level

    # Calculate the average pivot within this frequent range
    recurring_pivots = ohlc[ohlc["pivot_rounded"] == most_frequent_pivot]["pivot"]
    most_recurring_pivot = recurring_pivots.mean()

    # Count how many times the pivot level was touched
    touch_count = ((ohlc["low"] <= most_recurring_pivot + touch_tolerance) & 
                   (ohlc["high"] >= most_recurring_pivot - touch_tolerance)).sum()

    # Determine breakout probability based on touch frequency
    if touch_count <= 2:
        breakout_probability = 60 + np.random.randint(0, 11)  # 60-70% chance
    elif 3 <= touch_count <= 4:
        breakout_probability = 40 + np.random.randint(0, 21)  # 40-60% chance
    else:
        breakout_probability = 20 + np.random.randint(0, 21)  # 20-40% chance

    return most_recurring_pivot, touch_count, breakout_probability

        
config = load_config()
logging_level = logging.DEBUG if config["VERBOSITY"] == "debug" else logging.INFO
if config["VERBOSITY"] == "":
    logging_level = logging.ERROR
logging.basicConfig(format='Bot - %(asctime)s - %(levelname)s - %(message)s',
                    level=logging_level)