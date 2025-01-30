# Imports
import logging
import json
import asyncio
import socketio
import atexit
import random
import time
import datetime
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
            elif node_process.poll() is not None:
                break
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


def cleanup_routine():
    global node_process
    if node_process is not None:
        try:
            if node_process is not None:  # Check if Node.js process is still running
                node_process.terminate()
                logging.info("Node.js script terminated.")
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
    logging.info("Running cleanup routine.")
atexit.register(cleanup_routine)


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
    
    
async def add_price_alert(sio: socketio.AsyncServer, asset_id: str, price: float):
    await sio.emit("price-alert/add", dict(price=price, assetId=asset_id))
    

def get_order_params(asset_id: str, order_type: str) -> dict:
    request_id = get_random_request_id()
    timezone_offset = datetime.timedelta(hours=2)
    expiry_offset = datetime.timedelta(minutes=config["EXPIRY"])
    now = datetime.datetime.now()
    close_at = (now + timezone_offset) + expiry_offset
    return dict(
        asset = asset_id,
        requestId = request_id,
        optionType = 100,
        isDemo = 1 if config["MODE"] == "demo" else 0,
        action = order_type,
        amount = config["BALANCE"] * config["BALANCE_AT_RISK"],
        closeAt = close_at.timestamp()
    )

    
def get_random_request_id():
    rand = str(random.randint(10, 99))
    cu = time.time()
    t = str(cu + (2 * 60 * 60))
    return int(float(t + rand))
    

config = load_config()
logging_level = logging.DEBUG if config["VERBOSITY"] == "debug" else logging.INFO
if config["VERBOSITY"] == "":
    logging_level = logging.ERROR
logging.basicConfig(format='Bot - %(asctime)s - %(levelname)s - %(message)s',
                    level=logging_level)