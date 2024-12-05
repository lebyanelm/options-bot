import datetime
import time


class TimeSynchronizer:
    def __init__(self):
        self.timezone_offset = datetime.timedelta(hours=2)

    def get_synced_time(self):
        synced_time = time.time() - self.timezone_offset.total_seconds()
        return synced_time
    
    def get_synced_datetime(self):
        synced_time = self.get_synced_time()
        rounded_time_seconds = round(synced_time)
        synced_datetime_utc = datetime.datetime.fromtimestamp(rounded_time_seconds)
        return synced_datetime_utc
timesync = TimeSynchronizer()