# Imports
import logging
from config import config
import subprocess
import os
from pymongo import MongoClient
from config import config


# Logger
logging.basicConfig(format='Bot - %(asctime)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG if config["VERBOSITY"] == "debug" else logging.INFO)


# Connects to a MongoDB cloud database to store data and track orders
def connect_database():
    try:
        client = MongoClient(host=config["MONGODB"])
        client.admin.command("ping")
        return client.get_database(config["APP_NAME"])
    except ConnectionError as error:
            logging.error(error)
    
    
# Starts up a proxy server for connecting to the broker server
def start_proxy_server():
    env = os.environ.copy()
    proxy_server_process = subprocess.Popen(["node", "server.js"], stdout=subprocess.PIPE)
    return proxy_server_process