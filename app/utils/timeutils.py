from datetime import datetime

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
