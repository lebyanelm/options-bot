import socketio
import atexit
import asyncio
import logging
import helpers
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
    print("Auth", auth)


# Start up the main script
if __name__ == '__main__':
    # Run the server in the asyncio event loop
    try:
        asyncio.run(helpers.run_server(app))
    except KeyboardInterrupt:
        logging.info("Python script interrupted.")