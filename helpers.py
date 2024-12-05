# Imports
import logging
import json
import asyncio
import os
from pymongo import MongoClient


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
async def run_node_script(script_path):
    global node_process
    try:
        # Start the Node.js process
        node_process = await asyncio.create_subprocess_exec(
            'node', script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        logging.info("Node.js script started.")

        # Read output asynchronously (optional)
        async for line in node_process.stdout:
            logging.info(line.decode().strip())

        # Wait for the process to finish
        await node_process.wait()
        logging.info("Node.js script finished.")
    except Exception as e:
        logging.error(f"Error running Node.js script: {e}")
    finally:
        # Ensure process is terminated if still running
        if node_process and node_process.returncode is None:
            node_process.terminate()
            await node_process.wait()
            logging.info("Node.js script terminated.")


# Configure the helper module
config = load_config()
logging.basicConfig(format='Bot - %(asctime)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG if config["VERBOSITY"] == "debug" else logging.INFO)