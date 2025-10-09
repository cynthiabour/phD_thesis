from collections import deque
import asyncio
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from loguru import logger
from pathlib import Path

MINUTES = 2
# initial data (60 *2 data points)
signal_history = deque([0.1] * 60 * MINUTES, maxlen=60 * MINUTES)
x = list(range(120))

ax = plt.plot(x, signal_history)
# plt.plot(x, cal_history)

# def wait_color_change():
#     """
#     Wait until the reaction mixture w/ EosinY is stable.
#
#     the intensity of gas should btw 0-0.3 voltage
#     methanol: 0.3 mm ID, 1/16" OD, 2.62-2.64 voltage (light); 2.6-2.75 voltage (without light)
#     reaction mixture: depand on the concentration ( 25 mM directly dilute by inline methanol: 2.45 voltage)
#
#     """
#
#     logger.info("Waiting for the reaction mixture came out.")
#     detected = 0
#     # consecutive 10 measurements show the similar results: 5 sec/ data point
#     while True:
#         with command_session() as sess:
#             time.sleep(0.5)
#             r = sess.get(bubble_sensor_measure_endpoint + "/bubble-sensor/read-voltage")
#         if 1.0 <= float(r.text) <= 2.47:
#             logger.info("color change!")
#             detected += 1
#         else:
#             # logger.info("fake alarm!!")
#             detected = 0
#         if detected == 10:
#             break

def update_plot():
    plt.clf()
    plt.plot(x, signal_history, color="blue", label="bubble", )
    plt.draw()
    plt.pause(0.001)

async def flow_log(date: datetime, mongo_id: str, total_time: float,
                   folder_path: str = r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\flow_log"):
    """collect the flow information in given time by bubble sensor
    solvent: 2.5 V; air: 0 V
    """
    folder_path = Path(folder_path)

    s = requests.Session()
    # turn on the power of the sensor and power supply
    s.put("http://127.0.0.1:8000/bubble-sensor-power/5V/power-on")
    s.put("http://127.0.0.1:8000/bubble-sensor-measure/bubble-sensor/power-on")

    # time to acquire data
    start_time = time.monotonic()
    measure_period = total_time * 60
    end_time = start_time + measure_period

    # ask the signal in voltage
    v = requests.get("http://127.0.0.1:8000/bubble-sensor-measure/bubble-sensor/read-voltage")
    # logger.debug(f"{v.json()} voltage")
    spectra = pd.DataFrame([v.json()],
                           index=["Voltage"],
                           columns=[time.monotonic()]
                           ).T
    # signal_history.append(v.json())
    await asyncio.sleep(0.01)

    while time.monotonic() < end_time:
        v = requests.get("http://127.0.0.1:8000/bubble-sensor-measure/bubble-sensor/read-voltage")
        # logger.debug(f"{v.json()} voltage")
        spectra = pd.concat(
            [spectra,
             pd.DataFrame([v.json()],
                          index=["Voltage"],
                          columns=[time.monotonic()]
                          ).T
             ]
        )
        # signal_history.append(v.json())
        await asyncio.sleep(0.01)

        # update_plot()
        file_path = folder_path / Path(f"{date}_bubble_sensor_{mongo_id}.csv")
        spectra.to_csv(file_path,
                       header=True
                       )

    plt.close()
    # turn on the power of the sensor and power supply
    s.put("http://127.0.0.1:8000/bubble-sensor-power/5V/power-off")
    s.put("http://127.0.0.1:8000/bubble-sensor-measure/bubble-sensor/power-off")
    logger.info("finish the data acquisition and turn off the bubble sensor!")

async def main():
    # logger.add(f"dad.log", rotation="10 MB")
    # s=requests.Session()
    # s.put("http://127.0.0.1:8000/bubble-sensor-power/5V/power-off")
    # s.put("http://127.0.0.1:8000/bubble-sensor-measure/bubble-sensor/power-off")

    saving_folder_name = r'W:\BS-FlowChemistry\People\Wei-Hsin\GL_data\flow_log'
    date = datetime.date.today().strftime("%Y%m%d")
    name = 'control_27'
    await flow_log(date, name, 120, saving_folder_name)


if __name__ == "__main__":
    asyncio.run(main())
