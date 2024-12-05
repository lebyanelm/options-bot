import socketio
import atexit
import asyncio
import subprocess
import logging
from helpers import config
from aiohttp import web

# Create a client server for the proxy to connect to
sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()
sio.attach(app)

# Global variable to store the Node.js process
node_process = None

# When the proxy connects to the server to start authentication process
@sio.event
async def connected(sid, environ):
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

async def run_server():
    """
    Starts the server and launches the Node.js script once the server is ready.
    """
    # Start the web server
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

if __name__ == '__main__':
    # Run the server in the asyncio event loop
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logging.info("Python script interrupted.")