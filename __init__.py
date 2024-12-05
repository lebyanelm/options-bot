import socketio
import pandas as pd
import asyncio
import logging
import helpers
import datetime
from time_sync import timesync
from helpers import config
from aiohttp import web


# Create a client server for the proxy to connect to
sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()
sio.attach(app)


# When the proxy connects to the server to start authentication process
@sio.event
async def connected(sid, environ):
    logging.debug(f"Connected client: {sid}")
    await sio.emit("auth", dict(
        isDemo=1 if config["MODE"] == "demo" else 0,
        session=config["DEMO_AUTH"] if config["MODE"] == "demo" else config["LIVE_AUTH"],
        platform=config["PLATFORM"],
        uid=config["AUTH_UID"]
    ))


# Successful server authentication
@sio.event
async def successauth(sid, auth):
    # Register price streams for target assets
    target_symbols = config["TARGET_SYMBOLS"]
    for target_symbol in target_symbols:
        await sio.emit("changeSymbol", dict(
            asset = target_symbol,
            period = config["PERIOD"]
        ))

        # Load asset latest historical data
        load_period_params = helpers.load_candles(target_symbol)
        print(load_period_params)

    await sio.emit("favorite/change", target_symbols)



# Price update stream event
@sio.event
async def updateStream(sid, stream):
    server_timestamp = stream[0][1]
    timestamp = timesync.get_synced_time()


@sio.event
async def loadHistoryPeriod(sid, candles):
    candles = pd.DataFrame.from_dict(candles["data"])
    print(candles)
    

# Start up the main script
if __name__ == '__main__':
    # Run the server in the asyncio event loop
    try:
        asyncio.run(helpers.run_server(app))
    except KeyboardInterrupt:
        logging.info("Python script interrupted.")