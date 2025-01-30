import pandas as pd
import numpy as np
import logging
import traceback
from strategies.base_strategy import Strategy
import plotly.graph_objects as go
import pandas as pd
import dash
from dash import dcc, html, Output, Input
from helpers import config
from threading import Thread
import asyncio

# graphing purposes
# import matplotlib
# matplotlib.use('TkAgg')
# import matplotlib.pyplot as plt
# import mplfinance as mpf
# from matplotlib.patches import Rectangle


app = dash.Dash(__name__)
app.layout = html.Div([
    html.H1("Support and resistance strategy"),
    dcc.Graph(id='realtime-candlestick-chart'),
    dcc.Interval(id='update-interval', interval=1000),  # Update every 1 second
])

resampled_data = pd.DataFrame()



sr_bounds = 0.0001
rolling_window = 20

past_support_level = None
past_resistance_level = None

def process_data(data: pd.DataFrame):
    global resampled_data
    global support_level
    global resistance_level
    global support_breakout
    global resistance_breakout
    global past_support_level
    global past_resistance_level

    resampled_data = data.copy().resample(f"{config['PERIOD']/60} min").ohlc()["price"]
    resampled_data["Support"] = resampled_data["low"].rolling(window=rolling_window).min()
    resampled_data["Resistance"] = resampled_data["high"].rolling(window=rolling_window).max()
    resampled_data.dropna(inplace=True)
    
    # Calculate the breakout levels
    support_level = resampled_data["Support"].iloc[-1]
    resistance_level = resampled_data["Resistance"].iloc[-1]
    support_breakout = support_level - support_level * sr_bounds
    resistance_breakout = resistance_level + resistance_level * sr_bounds
    resampled_data.rename({"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True, axis=1)
    
    if past_support_level != support_breakout:
        past_support_level = support_breakout
        return 0
    elif past_support_level == None:
        past_support_level = support_breakout

    if past_resistance_level != resistance_breakout:
        past_resistance_level = resistance_breakout    
        return 1
    elif past_resistance_level == None:
        past_resistance_level = resistance_breakout 
    
    # rename colunms
        
@app.callback(
    Output('realtime-candlestick-chart', 'figure'),
    [Input('update-interval', 'n_intervals')]
)
def update_chart(n):
    global past_support_level
    global past_resistance_level
    global resampled_data
    global support_level
    global resistance_level
    global support_breakout
    global resistance_breakout
    
    """Generate the chart with the latest data."""
    if resampled_data.empty:
        return go.Figure()  # Return empty figure if no data yet   
        
    support_x0 = resampled_data[resampled_data["Support"] == support_level].iloc[0].name
    support_x1 = resampled_data[resampled_data["Support"] == support_level].iloc[-1].name

    resistance_x0 = resampled_data[resampled_data["Resistance"] == resistance_level].iloc[0].name
    resistance_x1 = resampled_data[resampled_data["Resistance"] == resistance_level].iloc[-1].name

    graph_data = resampled_data.iloc[-20:]
    fig = go.Figure(data=[
        go.Candlestick(
            x=graph_data.index,
            open=graph_data['Open'],
            high=graph_data['High'],
            low=graph_data['Low'],
            close=graph_data['Close']
        )
    ])
    fig.update_layout(
        title="Real-Time Candlestick Chart",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=True
    )
    
    fig.add_shape(
        type="line",
        y0=support_breakout,
        y1=support_breakout,
        x0=support_x0,
        x1=support_x1,
    )

    fig.add_shape(
        type="line",
        y0=resistance_breakout,
        y1=resistance_breakout,
        x0=resistance_x0,
        x1=resistance_x1,
    )
    
    return fig


def run_dash_app():
    """Runs Dash app in a separate thread."""
    app.run(debug=False, use_reloader=False, dev_tools_silence_routes_logging=True)

# Start the Dash app in a separate thread
dash_thread = Thread(target=run_dash_app)
dash_thread.daemon = True
dash_thread.start()