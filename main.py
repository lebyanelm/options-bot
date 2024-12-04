import socketio
from aiohttp import web
from config import config

sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()
sio.attach(app)

@sio.event
async def connected(sid, environ):
    await sio.emit("auth", dict(
        isDemo=1 if config["MODE"] == "demo" else 0,
        session=config["DEMO_AUTH"] if config["MODE"] == "demo" else config["LIVE_AUTH"],
        platform=config["PLATFORM"],
        uid=config["AUTH_UID"]
    ))
    
    
# Successful authentication
@sio.on("successauth")
async def successauth(sid, auth):
    print("Auth", auth)
    

# Run the application
if __name__ == '__main__':
    web.run_app(app, host='localhost', port=config["PROXY_SERVER_PORT"])