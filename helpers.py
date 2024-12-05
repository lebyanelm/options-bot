# Imports
import logging
import json
import asyncio
import atexit
import random
import time
import datetime
from time_sync import timesync
from pymongo import MongoClient
from aiohttp import web


# Connects to a MongoDB cloud database to store data and track orders
def connect_database():
    try:
        client = MongoClient(host=config["MONGODB"])
        client.admin.command("ping")
        return client.get_database(config["APP_NAME"])
    except ConnectionError as error:
            logging.error(error)


# Read a JSON configuration file with setting values
def load_config():
    config = dict()
    try:
        with open("config.json", 'r') as config_file:
            config = json.load(config_file)
    except Exception as error:
        print(error)
    return config

    
# Starts up a proxy server for connecting to the broker server
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

        # Optionally, read Node.js script output
        while True:
            line = await node_process.stdout.readline()
            if line:
                logging.info(f"Node.js: {line.decode().strip()}")
            elif node_process.poll() is not None:
                break
    except Exception as e:
        logging.error(f"Error running Node.js script: {e}")
    finally:
        if node_process and node_process.returncode is None:
            node_process.terminate()
            logging.info("Node.js script terminated.")


# Asyncronously run the server
async def run_server(app):
    """
    Starts the server and launches the Node.js script once the server is ready.
    """
    # Start the web server
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='localhost', port=config["PROXY_SERVER_PORT"])
    await site.start()

    logging.info("Server started and ready to accept connections.")

    # Start the Node.js script after the server is ready
    asyncio.create_task(start_node_script(config["PROXY_SCRIPT"]))

    # Keep the server running
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logging.info("Server shutting down.")
        await runner.cleanup()


# Register an exit clean-up routine to close opened threads
def cleanup_routine():
    global node_process
    if node_process is not None:
        try:
            if node_process.poll() is None:  # Check if Node.js process is still running
                node_process.terminate()
                logging.info("Node.js script terminated.")
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
    logging.info("Running cleanup routine.")
atexit.register(cleanup_routine)


# Get latest historical data
def load_candles(asset_id: str) -> dict:
    rand = str(random.randint(10, 99))
    cu = int(time.time())
    t = str(cu + (2 * 60 * 60))
    index = int(t + rand)
    end_time = (timesync.get_synced_datetime() - datetime.timedelta(hours=2, minutes=58)).timestamp()
    period = config["PERIOD"]
    return dict(
        asset = asset_id,
        index = index,
        offset = get_period_offset(period),
        period = period,
        time = int(end_time)
    )
    
    
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
    

# Configure the helper module
config = load_config()
logging_level = logging.DEBUG if config["VERBOSITY"] == "debug" else logging.INFO
if config["VERBOSITY"] == "":
    logging_level = logging.ERROR
logging.basicConfig(format='Bot - %(asctime)s - %(levelname)s - %(message)s',
                    level=logging_level)