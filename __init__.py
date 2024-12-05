import socketio
import pandas as pd
import asyncio
import logging
import helpers
import datetime
from time_sync import timesync
from helpers import config
from aiohttp import web


all_candles = dict()


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
        end_time = (timesync.get_synced_datetime() - datetime.timedelta(hours=4, minutes=58)).timestamp()

        # await sio.emit("loadHistoryPeriod", load_period_params)
    await sio.emit("favorite/change", target_symbols)



# Price update stream event
@sio.event
async def updateStream(sid, stream):
    global all_candles
    asset_id = stream[0][0]
    server_timestamp = stream[0][1]
    price = stream[0][2]
    
    timesync.synchronize(server_timestamp)
    target_symbols = config["TARGET_SYMBOLS"]
    for target_symbol in target_symbols:
        load_period_params = helpers.load_candles(target_symbol)
        if asset_id not in all_candles.keys():
            await sio.emit("loadHistoryPeriod", load_period_params)

    if asset_id in all_candles.keys():
        new_candles = pd.DataFrame([[server_timestamp, price]], columns=["time", "price"])
        new_candles["time"] = pd.to_datetime(new_candles["time"], unit="s")
        new_candles.set_index("time", inplace=True)
        candles = pd.concat([all_candles[asset_id], new_candles])
        all_candles[asset_id] = candles[-config["CANDLES_LIMIT"]:]

        print(asset_id)
        print(all_candles[asset_id].resample("1min").ohlc())
        

# Loading historical data
@sio.event
async def loadHistoryPeriod(sid, candles):
    global all_candles

    asset_id = candles["asset"]
    candles = pd.DataFrame.from_dict(candles["data"])
    candles["time"] = pd.to_datetime(candles["time"], unit="s")
    candles.set_index("time", inplace=True)
    candles.sort_index(inplace=True)
    candles.drop(columns="asset", inplace=True)

    all_candles[asset_id] = candles[-config["CANDLES_LIMIT"]:]
    

# Start up the main script
if __name__ == '__main__':
    # Run the server in the asyncio event loop
    try:
        asyncio.run(helpers.run_server(app))
    except KeyboardInterrupt:
        logging.info("Python script interrupted.")