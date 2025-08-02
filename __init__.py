import socketio
import pandas as pd
import ta
import logging
import asyncio
import atexit
import ta.volatility
import helpers
from datetime import timedelta
from time_sync import timesync
from datetime import datetime
from helpers import config
from aiohttp import web
from strategies.key_levels import KeyLevelsTradingStrategy

all_candles = dict()
default_candles = pd.DataFrame([], columns=["time", "price"])
pending_orders = []
session = dict(
	wins=0,
	losses=0,
	initial_balance=0,
	session_start=datetime.now(),
	allow_orders=True)
orders = list()


# Initialize the strategies
strategies = [
	KeyLevelsTradingStrategy
]


# Create a client server for the proxy to connect to
sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()
sio.attach(app)


# When the proxy connects to the server to start authentication process
@sio.event
async def connected(sid, environ):
	logging.info(f"Connected client: {sid}")
	await sio.emit("auth", dict(
		isDemo=1 if config["MODE"] == "demo" else 0,
		session=config["DEMO_AUTH"] if config["MODE"] == "demo" else config["LIVE_AUTH"],
		platform=config["PLATFORM"],
		uid=config["AUTH_UID"]
	))


# Successful server authentication
@sio.event
async def successauth(sid, auth_id):
	logging.info("Authenticated to server.")
	# Register price streams for target assets
	target_symbols = config["TARGET_SYMBOLS"]
	for target_symbol in target_symbols:
		await sio.emit("changeSymbol", dict(
			asset = target_symbol,
			period = config["PERIOD"]
		))
	await sio.emit("favorite/change", target_symbols)


# Receives the current active assets
@sio.event
async def updateAssets(sid, update_assets):
	if len(config["TARGET_SYMBOLS"]) == 0:
		for asset in update_assets:
			if asset[14] == True and len(config["TARGET_SYMBOLS"]) != config["MAXIMUM_SYMBOLS"]:
				config["TARGET_SYMBOLS"].append(asset[1])
		logging.info(f"Loaded {len(config['TARGET_SYMBOLS'])} assets.")


# When balance changes when placing or closing a trade
@sio.event
async def successupdateBalance(sid, balance):
	logging.info(f"Current balance: ${balance['balance']}, Balance mode: {'Demo' if balance['isDemo'] == 1 else 'Live'}")
	config["BALANCE"] = balance["balance"]
	if session["initial_balance"] == 0:
		session["initial_balance"] = float(balance["balance"])

	
# Price update stream event
order_placed = False
@sio.event
async def updateStream(_, stream):
	global all_candles
	global order_placed
	global orders
	global pending_orders

	now_time = datetime.now()
	# Only process data if orders are still allowed
	if now_time - session["session_start"] >= timedelta(hours=24):
		session["session_start"] = now_time
		session["allow_orders"] = True
	if not session["allow_orders"]:
		print("Orders not allowed.")
		return
	
	asset_id = stream[0][0]
	server_timestamp = stream[0][1]
	price = stream[0][2]
	timesync.synchronize(server_timestamp)
	
	# Update the prices with the new candle
	if asset_id in all_candles.keys():
		new_candles = pd.DataFrame([[server_timestamp, price]], columns=["time", "price"])
		new_candles["time"] = pd.to_datetime(new_candles["time"], unit="s")
		new_candles.set_index("time", inplace=True)
		all_candles[asset_id] = pd.concat([all_candles[asset_id], new_candles])
		logging.debug(f"Data length for {asset_id}: {len(all_candles[asset_id])}")
		all_candles[asset_id] = all_candles[asset_id].iloc[-config["CANDLES_LIMIT"]:]

	# Ensure to always clean the order counter.
	for order in orders:
		order_time = pd.to_datetime(order["closeTime"])
		if now_time > order_time:
			orders.remove(order)
			logging.debug(f"Order ({order['id']}) expired, and has been removed.")
		
	# Calculate the multi analysis data points
	if all_candles.get(asset_id) is None:
		logging.debug(f"Asset has no data feed ({asset_id}).")
		return
	else:
		# Make sure theres enough data to make a pivot calculation
		if len(all_candles.get(asset_id)) < config["CANDLES_LIMIT"]:
			logging.debug("Not enough data.")
			return
	ohlc_data = all_candles[asset_id].resample("30s").ohlc().xs('price', axis=1, level=0)
	pivot_point, touch_count, _ = helpers.calculate_pivot_point(ohlc_data)
	last_price = ohlc_data.iloc[-1]
	order_type = None
	
	if touch_count < 3:
		if pivot_point > last_price["close"]:
			order_type = 0
		elif pivot_point < last_price["close"]:
			order_type = 1
	elif touch_count > 2:
		if pivot_point > last_price["close"]:
			order_type = 1
		elif pivot_point < last_price["close"]:
			order_type = 0
			
	for pending_order in pending_orders:
		if pending_order.get("symbol") == asset_id or pending_order.get("asset") == asset_id:
			# Check if this pending order has been too long since it was created (i.e. morethan 4 hours.)
			current_time = datetime.now()
			order_time = pd.to_datetime(pending_order["dateCreated"])
			order_time_delta = (current_time - order_time)

			if order_time_delta > pd.Timedelta(minutes=1):
				# Cancel the pending order
				if pending_order.get("ticket"):
					await sio.emit("cancelPendingOrder", dict(ticket = pending_order["ticket"]))
				pending_orders.remove(pending_order)
			else:
				logging.debug("Pending order still active.")
				return
			break

	if len(orders):
		return

	# Calculate the timeframe / expiry based on the volatily of the asset
	timeframe = round(helpers.average_time_above_pivot(ohlc_data, pivot_point, order_type))
	risk_perc = config["BALANCE_AT_RISK"]
	balance_risk = config["BALANCE"] - session["initial_balance"] if config["BALANCE"] > session["initial_balance"] else config["BALANCE"] * risk_perc
	logging.debug(f"Place pending order at amount: {balance_risk}")

	new_pending_order = dict(
		amount = balance_risk,
		asset = asset_id,
		command = order_type,
		minPayout = round(config["MIN_PAYOUT"] * 100),
		openTime = 0,
		openPrice = pivot_point,
		openType = 1,
		timeframe = 60 * timeframe
	)
	logging.debug(f"Pending order has been requested: {new_pending_order}")
	await sio.emit("openPendingOrder", new_pending_order)
	new_pending_order["dateCreated"] = str(datetime.now())
	pending_orders.append(new_pending_order)


# When script starts find out how the current order progress incase script restart due to a disconnection
@sio.event
async def updateClosedDeals(sid, closed_orders):
	for closed_order in closed_orders:
		# Focus on orders made in the current day session
		now_date = datetime.now()
		order_date = pd.to_datetime(closed_order["closeTime"])
		if now_date - order_date < pd.Timedelta(hours=24):
			# Determine the current accuracy ratio
			if closed_order["profit"] > 0:
				session["wins"] += 1
			else:
				session["losses"] += 1

	if session["wins"] + session["losses"] > 0:
		logging.info(f"Current accuracy ratio: {round(session['wins']/(session['wins']+session['losses'])*100, 2)}%")



# Get an updated list of still opened orders to avoid placing pending orders on active asset
@sio.event
async def updateOpenedDeals(sid, opened_deals):
	global orders
	orders = opened_deals


@sio.event
async def successopenPendingOrder(sid, new_order):
	global pending_orders
	new_order = new_order.get("data")
	if new_order:
		for index, _ in enumerate(pending_orders):
			if pending_orders[index].get("asset") == new_order["symbol"]:
				pending_orders[index] = new_order


@sio.event
async def erroropenPendingOrder(sid, new_order):
	global pending_orders
	# Attempt to remove any unconfirmed orders.
	for pending_order in pending_orders:
		if pending_order.get("dateCreated") is None:
			pending_orders.remove(pending_order)


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
	if len(all_candles[asset_id]) <= config["CANDLES_LIMIT"]:
		last_index = all_candles[asset_id].iloc[0].name.timestamp()
		load_period_params = helpers.load_candles(asset_id, last_index)
		await sio.emit("loadHistoryPeriod", load_period_params)
		logging.info(f"{asset_id} currently has {len(all_candles[asset_id])} candles.")
	else:
		logging.info(f"{asset_id} has completed loading.")


@sio.event
async def updateHistoryNew(sid, history):
	global all_candles
	asset_id = history["asset"]
	candles = pd.DataFrame(history["history"], columns=["time", "price"])
	candles["time"] = pd.to_datetime(candles["time"], unit="s")
	candles.set_index("time", inplace=True)
	candles.sort_index(inplace=True)
	if len(candles):
		last_index = candles.iloc[0].name.timestamp()
		load_period_params = helpers.load_candles(asset_id, last_index)
		all_candles[asset_id] = candles
		# Initialize a placeholder to hold price data for the particular asset.
		await sio.emit("loadHistoryPeriod", load_period_params)
	

@sio.event
async def successopenOrder(_, order):
	global orders
	global pending_orders
	orders.append(order)
	roi = (config["BALANCE"] - session["initial_balance"]) / session["initial_balance"]
	logging.info(f'ROI (Return on investment): {roi}')
	print(session["initial_balance"], config["BALANCE"])

	for pending_order in pending_orders:
		await sio.emit("cancelPendingOrder", dict(ticket = pending_order["ticket"]))
	pending_orders = []
		
	
@sio.event
async def successcloseOrder(_, orders_):
	global orders
	for closed_order in orders_["deals"]:
		for placed_order in orders:
			if placed_order["id"] == closed_order["id"]:
				orders.remove(placed_order)
				logging.debug(f"Order ({closed_order['id']}) closed.")
				break
		if closed_order["profit"] > 0:
			session["wins"] += 1
		else:
			session["losses"] += 1

		roi = (config["BALANCE"] - session["initial_balance"]) / session["initial_balance"]
		logging.info(f'Accuracy score: {session["wins"]/(session["wins"] + session["losses"])}')
		logging.info(f'ROI (Return on investment): {roi}')
		
		# If losses are incured or profit target has been reached stop trading
		if roi in (-0.1, 0.2):
			if roi < -0.1:
				session["allow_orders"] = False
			if roi > 0.2:
				session["allow_orders"] = False
			now_time = datetime.now()
			tommorrow_time = datetime(year=now_time.year,
						month=now_time.month, day=now_time.day+1,
						hour=now_time.hour, minute=now_time.minute)
			logging.info(f"Orders have been stopped for: {tommorrow_time - now_time}")


@sio.event
async def successupdatePending(sid, _pending_orders):
	global pending_orders
	pending_orders = _pending_orders
	logging.info(f"Total pending orders: {len(pending_orders)}")
	for pending_order in pending_orders:
		# Check if this pending order has been too long since it was created (i.e. morethan 4 hours.)
		if pending_order.get("dateCreated"):
			current_time = datetime.now()
			order_time = pd.to_datetime(pending_order["dateCreated"])
			if (current_time - order_time) > pd.Timedelta(minutes=1):
				# Cancel the pending order
				await sio.emit("cancelPendingOrder", dict(ticket = pending_order["ticket"]))
				pending_orders.remove(pending_order)
				logging.info(f"Remaining total pending orders (pruned): {len(pending_orders)}")


"""
When the script reaches its end of life (EOF), attempt a clean up process.
Such as canceling any existing pending orders to prevent accidental losses.
"""
atexit.register(helpers.cleanup_routine, pending_orders, sio)


# Start up the main script
if __name__ == '__main__':
	# Run the server in the asyncio event loop
	try:
		asyncio.run(helpers.run_server(app))
	except KeyboardInterrupt:
		logging.info("Python script interrupted.")
