import random
import time
from collections import deque
import matplotlib.pyplot as plt
import numpy as np
import requests

MINUTES = 2
# initial data (60 *2 data points)
pressure_history = deque([0.1]*60*MINUTES,maxlen=60*MINUTES)
x = list(range(120))

ax = plt.plot(x, pressure_history)


def update_plot():
    plt.clf()
    plt.plot(x, pressure_history)
    plt.draw()
    plt.pause(0.001)


while True:
    time.sleep(0.5)
    measuring_time = time.monotonic()
    # read_v = requests.get("http://127.0.0.1:8000/bubble-sensor-measure/bubble-sensor/read-voltage")
    # read_sys_p = requests.get("http://127.0.0.1:8000/r2/PressureSensor/read-pressure?units=mbar")

    print(f"{measuring_time}: {read_sys_p.text}")
    pressure_history.append(float(read_sys_p.text))
    update_plot()





