# Imports
import dotenv
import os

dotenv.load_dotenv(override=True)


config = dict(
    # Runtime
    APP_NAME = os.environ.get("APP_NAME"),
    MODE = os.environ.get("MODE"),
    PLATFORM = os.environ.get("PLATFORM"),
    VERBOSITY = os.environ.get("VERBOSITY"),

    # Server connection
    LIVE_SERVER = os.environ.get("LIVE_SERVER"),
    DEMO_SERVER = os.environ.get("DEMO_SERVER"),
    ORIGIN = os.environ.get("ORIGIN"),
    AUTH_TIMEOUT = os.environ.get("AUTH_TIMEOUT"),
    PROXY_SERVER = os.environ.get("PROXY_SERVER"),
    PROXY_SERVER_PORT = os.environ.get("PROXY_SERVER_PORT"),

    # Server authentication
    LIVE_AUTH = os.environ.get("LIVE_AUTH"),
    DEMO_AUTH = os.environ.get("DEMO_AUTH"),
    AUTH_UID = os.environ.get("AUTH_UID"),

    # Database
    MONGODB = os.environ.get("MONGODB"),

    # Strategy
    TARGET_SYMBOLS = os.environ.get("TARGET_SYMBOLS"),
    PERIOD = os.environ.get("PERIOD")
)

# Format the config value types
if config["AUTH_TIMEOUT"]:
    config["AUTH_TIMEOUT"] = int(config["AUTH_TIMEOUT"])
if config["PLATFORM"]:
    config["PLATFORM"] = int(config["PLATFORM"])
if config["PERIOD"]:
    config["PERIOD"] = int(config["PERIOD"])
if config["AUTH_UID"]:
    config["AUTH_UID"] = int(config["AUTH_UID"])
if config["TARGET_SYMBOLS"]:
    config["TARGET_SYMBOLS"] = config["TARGET_SYMBOLS"].split(",")
if config["PROXY_SERVER_PORT"]:
    config["PROXY_SERVER_PORT"] = int(config["PROXY_SERVER_PORT"])