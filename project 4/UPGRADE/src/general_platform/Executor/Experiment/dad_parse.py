import time
from collections import deque
import datetime
import math

import pandas as pd
import requests
import asyncio
import statistics

from loguru import logger
from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor.Experiment.platform_precedure import dad_initialize

# fixme: class
# create deque to store the data
acq_data_deque = deque([0.0] * 20, maxlen=20)
sup_data_deque = deque([0.0] * 20, maxlen=20)


async def wait_to_stable_wo_ref(
        s: requests.sessions.Session,
        channel: int,
        interval: float = 1.0,
        period: float = 10,
        timeout: float = 20,
        fluctuation: float = 0.2) -> deque[float]:
    """
    subset of collecting background

    :param s:
    :param channel:
    :param interval: time interval to aquire data point in seconds
    :param period: to get stable signal in certain period in seconds
    :param timeout: in mins
    :param fluctuation:
    :return: signal_deque or False to present timeout
    """
    # calc the data points required
    d_num = math.ceil(period / interval)

    # check signal stable by ten collection
    signal_deque = deque([0.0] * d_num, maxlen=d_num)
    signal_diff = deque([0.0] * d_num, maxlen=d_num)

    start_time = time.monotonic()
    waiting_period = timeout * 60
    end_time = start_time + waiting_period

    for n in range(d_num):
        # renew the deque by real intensity of the signal
        signal = s.get(dad_endpoint + f"/channel{channel}/acquire-signal")
        n_signal = signal.json()
        signal_deque.append(n_signal)

        # get new diff
        n_diff = n_signal - signal_deque[-4]  # deque[-2] is last measure point
        signal_diff.append(n_diff)

        await asyncio.sleep(interval)

    logger.debug(f"signal deque: {signal_deque}")
    logger.debug(f"signal difference: {signal_diff}")

    # wait to stable
    while time.monotonic() < end_time:
        signal = s.get(dad_endpoint + f"/channel{channel}/acquire-signal")
        n_signal = signal.json()
        signal_deque.append(n_signal)
        # get new diff
        n_diff = n_signal - signal_deque[-4]
        signal_diff.append(n_diff)
        logger.debug(f"new signal: {n_signal}, signal_diff: {n_diff}")

        stability_list = [True if abs(x) < fluctuation else False for x in signal_diff]

        if all(stability_list):
            logger.info(f"the signal of channel{channel} is stable!!")
            return signal_deque

        await asyncio.sleep(interval)

    # always return the last deque even it is not stable
    logger.warning(f"the dad cannot be get the stable signal......check manually....")
    return signal_deque


async def background_collect(
        s: requests.sessions.Session,
        channel: int,
        interval: float = 0.8,
        period: float = 10,
        timeout: float = 10) -> float | bool:
    """ collect background to replace to autozero function """

    # check signal stable by ten collection
    signal_deque = await wait_to_stable_wo_ref(s, channel, interval=interval, period=period, timeout=timeout)
    return statistics.mean(signal_deque)


async def get_dad_signals(s: requests.sessions.Session,
                          wl_info,
                          acq_bg, ref_bg, aux_bg, aux2_bg) -> pd.DataFrame:
    """ get the dad all channel signals and process the signals"""
    # get signal
    acq_signal = s.get("http://127.0.0.1:8000/dad/channel1/acquire-signal")
    ref_signal = s.get("http://127.0.0.1:8000/dad/channel2/acquire-signal")
    aux_signal = s.get("http://127.0.0.1:8000/dad/channel3/acquire-signal")
    aux2_signal = s.get("http://127.0.0.1:8000/dad/channel4/acquire-signal")

    # background correction
    acq_data = acq_signal.json() - acq_bg
    ref_data = ref_signal.json() - ref_bg
    aux_data = aux_signal.json() - aux_bg
    aux2_data = aux2_signal.json() - aux2_bg

    # calibrate the signal
    cal_ref = 0.0012 * ref_data ** 2 + 0.9893 * ref_data  # new for 75 ms
    # cal_ref = 0.0012 * ref_data ** 2 + 0.9893 * ref_data + 3.522  # for 75 ms
    # cal_ref = 0.0006 * ref_signal.json() ** 2 +0.9313 * ref_signal.json() + 23.778    # for 20 ms
    sup_data = acq_data - cal_ref

    # add the data to deque
    acq_data_deque.append(acq_data)
    sup_data_deque.append(sup_data)

    acq_median = statistics.median(acq_data_deque)
    sup_median = statistics.median(sup_data_deque)

    logger.debug(f"real signal: {acq_signal.json()} (cal:{acq_data} (median: {acq_median})); "
                 f"real ref: {ref_signal.json()} (cal: {ref_data}; "
                 f"auxiliary sg: {aux_signal.json()} (cal: {aux_data}); "
                 f"suppressed sg: {sup_data} (median: {sup_median})"
                 )
    spectra = pd.DataFrame([acq_signal.json(), acq_data, acq_median,
                            ref_signal.json(), ref_data,
                            sup_data, sup_median,
                            aux_signal.json(), aux_data,
                            aux2_signal.json(), aux2_data],
                           index=[f"{wl_info['channel_1']}nm", f"{wl_info['channel_1']}cal",
                                  f"{wl_info['channel_1']}(med)",
                                  f"{wl_info['channel_2']}nm", f"{wl_info['channel_2']}cal",
                                  "suppressed", "sup(med)",
                                  f"{wl_info['channel_3']}nm", f"{wl_info['channel_3']}cal",
                                  f"{wl_info['channel_4']}nm", f"{wl_info['channel_4']}cal"],
                           columns=[time.monotonic()]
                           ).T
    return spectra


async def collect_dad_given_time(date: datetime,
                                 mongo_id: str,
                                 duration: float,
                                 dad_info: dict):
    """collect the dad data in given time"""
    # todo: add G to check which pump is running
    # logger.info("start pump M")
    logger.info("start pump B")
    s = requests.Session()
    s.put("http://127.0.0.1:8000/r2/Pump_B/infuse?rate=2.0%20ml%2Fmin")
    await asyncio.sleep(2.0)
    # initialize the dad
    await dad_initialize(dad_info)
    await asyncio.sleep(2.0)

    # set the signal to zero: 1 mins too short
    acq_bg, ref_bg, aux_bg, aux2_bg = await asyncio.gather(background_collect(s, 1, 0.8, 10, 5),
                                                           background_collect(s, 2, 0.8, 10, 5),
                                                           background_collect(s, 3, 0.8, 10, 5),
                                                           background_collect(s, 4, 0.8, 10, 5))
    # acq_bg, ref_bg, aux_bg, aux2_bg = 0, 0, 0, 0
    wl_info = dad_info["wavelength"]

    logger.debug(f"{wl_info['channel_1']} nm bg:{acq_bg}; {wl_info['channel_2']} nm bg:{ref_bg};"
                 f"{wl_info['channel_3']} nm bg: {aux_bg}; {wl_info['channel_4']} nm bg: {aux2_bg}")

    s.put("http://127.0.0.1:8000/r2/Pump_B/stop")
    logger.info("stop pump B after bg collection")

    # time to acquire data (every 1.3 sec)
    start_time = time.monotonic()
    end_time = start_time + duration * 60

    spectra = await get_dad_signals(s, wl_info, acq_bg, ref_bg, aux_bg, aux2_bg)
    await asyncio.sleep(1.3)

    while time.monotonic() < end_time:
        n_spectrum = await get_dad_signals(s, wl_info, acq_bg, ref_bg, aux_bg, aux2_bg)
        spectra = pd.concat([spectra, n_spectrum])
        # fixme: input the save folder
        spectra.to_csv(rf'W:\BS-FlowChemistry\People\Wei-Hsin\GL_data\dad_spectra\{date}_spectra_{mongo_id}.csv',
                       header=True
                       )
        await asyncio.sleep(1.3)

    logger.info("finish dad data collection request!")


# def old_data_parse(file_name: str):
#     from BV_experiments.tools.plot_exp import find_files_with_text, check_find_files
#     from pathlib import Path
#     mongo_id = "control_test_028"
#     dad_log_folder = Path(r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\dad_spectra")
#     d_matching_files = find_files_with_text(dad_log_folder, mongo_id)
#     d_log = check_find_files(d_matching_files)
#
#     dad_np = pd.read_csv(d_log).to_numpy()


if __name__ == "__main__":
    # logger.add(f"dad.log", rotation="10 MB")
    date = datetime.date.today().strftime("%Y%m%d")
    dad_info = {"wavelength": {"channel_1": "350", "channel_2": "700", "channel_3": "254", "channel_4": "280"},
                "bandwidth": "8",
                "integration_time": "75"}
    asyncio.run(collect_dad_given_time(date,
                                       "test_001",
                                       1.0,
                                       dad_info=dad_info))

    # file_path = Path(r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\dad_spectra\20230731_control_test_028_test.csv")
    # data = pd.read_csv(file_path, hesader=0, index_col=0)
