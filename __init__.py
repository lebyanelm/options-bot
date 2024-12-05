import socketio
import pandas as pd
import asyncio
import logging
import helpers
import random
from time_sync import timesync
from helpers import config
from aiohttp import web


all_candles = dict()
session_balance = 0


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
async def successauth(sid, auth_id):
    # Register price streams for target assets
    target_symbols = config["TARGET_SYMBOLS"]
    for target_symbol in target_symbols:
        await sio.emit("changeSymbol", dict(
            asset = target_symbol,
            period = config["PERIOD"]
        ))
    await sio.emit("favorite/change", target_symbols)


# When balance changes when placing or closing a trade
@sio.event
async def successupdateBalance(sid, balance):
    config["BALANCE"] = balance["balance"] 


# Price update stream event
order_placed = False
@sio.event
async def updateStream(_, stream):
    global all_candles
    global order_placed
    asset_id = stream[0][0]
    server_timestamp = stream[0][1]
    price = stream[0][2]
    timesync.synchronize(server_timestamp)
    if asset_id in all_candles.keys():
        new_candles = pd.DataFrame([[server_timestamp, price]], columns=["time", "price"])
        new_candles["time"] = pd.to_datetime(new_candles["time"], unit="s")
        new_candles.set_index("time", inplace=True)
        candles = pd.concat([all_candles[asset_id], new_candles])
        # Always limit the candles to a certain limit for memory purposes
        all_candles[asset_id] = candles[-config["CANDLES_LIMIT"]:]

    trade_types = ["call", "put"]
    random_index = random.randint(0, len(trade_types)-1)
    
    order_params = helpers.get_order_params(asset_id, trade_types[random_index])
    if order_placed == False:
        await sio.emit("openOrder", order_params)
        order_placed = True
        

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
    all_candles[asset_id] = pd.concat([candles, all_candles[asset_id]])
    all_candles[asset_id].sort_index(inplace=True)


@sio.event
async def updateHistoryNew(sid, history):
    global all_candles
    asset_id = history["asset"]
    candles = pd.DataFrame(history["history"], columns=["time", "price"])
    candles["time"] = pd.to_datetime(candles["time"], unit="s")
    candles.set_index("time", inplace=True)
    candles.sort_index(inplace=True)
    last_index = candles.iloc[0].name.timestamp()
    load_period_params = helpers.load_candles(asset_id, last_index)
    if asset_id not in all_candles.keys():
        await sio.emit("loadHistoryPeriod", load_period_params)
    all_candles[asset_id] = candles[-config["CANDLES_LIMIT"]:]
    

@sio.event
async def failopenOrder(_, error):
    print(error)
    

# Start up the main script
if __name__ == '__main__':
    # Run the server in the asyncio event loop
    try:
        asyncio.run(helpers.run_server(app))
    except KeyboardInterrupt:
        logging.info("Python script interrupted.")