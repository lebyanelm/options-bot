# Imports
import logging
import json
import asyncio
import atexit
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


# Configure the helper module
config = load_config()
logging_level = logging.DEBUG if config["VERBOSITY"] == "debug" else logging.INFO
logging.basicConfig(format='Bot - %(asctime)s - %(levelname)s - %(message)s',
                    level=logging_level)