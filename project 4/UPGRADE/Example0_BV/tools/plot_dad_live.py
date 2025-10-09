import time
from collections import deque
import datetime

import matplotlib.pyplot as plt
import pandas as pd
import requests
import asyncio
import statistics

from loguru import logger

from BV_experiments.src.general_platform.Executor.Experiment.dad_parse import background_collect

MINUTES = 2
# initial data (60 *2 data points)
signal_history = deque([0.1] * 60 * MINUTES, maxlen=60 * MINUTES)
ref_history = deque([0.1] * 60 * MINUTES, maxlen=60 * MINUTES)
cal_history = deque([0.1] * 60 * MINUTES, maxlen=60 * MINUTES)
med_history = deque([0.1] * 60 * MINUTES, maxlen=60 * MINUTES)
aux_history = deque([0.1] * 60 * MINUTES, maxlen=60 * MINUTES)
x = list(range(120))

ax = plt.plot(x, signal_history)
plt.plot(x, cal_history)

acq_data_deque = deque([0.0] * 20, maxlen=20)
cal_data_deque = deque([0.0] * 20, maxlen=20)


def update_plot():
    plt.clf()
    plt.plot(x, signal_history, color="blue", label="500nm", )
    plt.plot(x, ref_history, color="magenta", label="700nm", )
    plt.plot(x, cal_history, color="green", label="cal")
    plt.plot(x, med_history, color="black", label="med")
    plt.plot(x, aux_history, color="cyan", label="aux")
    plt.draw()
    plt.pause(0.001)

async def monitor_dad_given_time(date: datetime, mongo_id: str, t: float, pump_flow: dict = None):
    """collect the dad data in given time"""
    logger.info("start pump M")
    s = requests.Session()
    s.put("http://127.0.0.1:8000/Knauer-pumpM/pump/infuse?rate=2.0%20ml%2Fmin")

    await asyncio.sleep(20.0)

    # set the wavelength at ch1
    s.put("http://127.0.0.1:8000/dad/channel1/set-wavelength?wavelength=350")
    # set the bandwidth  at ch1
    s.put("http://127.0.0.1:8000/dad/channel1/set-bandwidth?bandwidth=8")
    # set the wavelength at ch2
    s.put("http://127.0.0.1:8000/dad/channel2/set-wavelength?wavelength=700")
    # set the bandwidth  at ch2
    s.put("http://127.0.0.1:8000/dad/channel2/set-bandwidth?bandwidth=8")
    # set the wavelength at ch3
    s.put("http://127.0.0.1:8000/dad/channel3/set-wavelength?wavelength=400")
    # set the bandwidth  at ch3
    s.put("http://127.0.0.1:8000/dad/channel3/set-bandwidth?bandwidth=8")
    # set the wavelength at ch3
    s.put("http://127.0.0.1:8000/dad/channel4/set-wavelength?wavelength=480")
    # set the bandwidth  at ch3
    s.put("http://127.0.0.1:8000/dad/channel4/set-bandwidth?bandwidth=8")
    # set integration time
    s.put("http://127.0.0.1:8000/dad/channel1/set-integration-time?int_time=75")
    await asyncio.sleep(2.0)

    # set the signal to zero: 1 mins too short
    acq_bg, ref_bg, aux_bg, aux2_bg = await asyncio.gather(background_collect(s, 1, 0.8, 10, 5),
                                                           background_collect(s, 2, 0.8, 10, 5),
                                                           background_collect(s, 3, 0.8, 10, 5),
                                                           background_collect(s, 4, 0.8, 10, 5))
    logger.debug(f"350 nm bg:{acq_bg}; 700 nm bg:{ref_bg};500nm bg: {aux_bg}; 480 nm bg: {aux2_bg}")

    s.put("http://127.0.0.1:8000/Knauer-pumpM/pump/stop")
    # s.put("http://127.0.0.1:8000/Knauer-pumpM/pump/infuse?rate=0.0%20ml%2Fmin")
    logger.info("stop pump M")
    logger.info("start pump methanol and O2 gas")

    s.put(f"http://127.0.0.1:8000/r2/Pump_A/infuse?rate={pump_flow['liquid_flow']}ml%2Fmin")
    s.put(f"http://127.0.0.1:8000/O2MFC/MFC/set-flow-rate?flowrate={pump_flow['gas_flow']}ml%2Fmin")
    # s.put("http://127.0.0.1:8000/Knauer-pumpM/pump/infuse?rate=0.02%20ml%2Fmin")

    # time to acquire data
    start_time = time.monotonic()
    measure_period = t * 60
    end_time = start_time + measure_period

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
    cal_ref = 0.0012 * ref_data ** 2 + 0.9893 * ref_data  # new for 75 ms
    # cal_ref = 0.0012 * ref_data ** 2 + 0.9893 * ref_data + 3.522  # new for 75 ms
    # cal_ref = 0.0006 * ref_signal.json() ** 2 +0.9313 * ref_signal.json() + 23.778    # for 20 ms
    cal_data = acq_data - cal_ref

    acq_data_deque.append(acq_data)
    cal_data_deque.append(cal_data)

    acq_median = statistics.median(acq_data_deque)
    cal_median = statistics.median(cal_data_deque)

    logger.debug(f"signal: {acq_signal.json()} (cal:{acq_data} (median: {acq_median})); "
                 f"ref: {ref_signal.json()} (cal: {ref_data}; "
                 f"auxiliary: {aux_signal.json()} (cal: {aux_data});"
                 f"calibrate: {cal_data} (median: {cal_median})")
    spectra = pd.DataFrame([acq_signal.json(), ref_signal.json(),
                            acq_data, ref_data, acq_median,
                            cal_data, cal_median,
                            aux_signal.json(), aux_data,
                            aux2_signal.json(), aux2_data],
                           index=["480nm", "700nm",
                                  "480cal", "700cal", "480(med)",
                                  "cal", "cal(med)",
                                  "500nm", "500cal",
                                  "460nm", "460cal"],
                           columns=[time.monotonic()]
                           ).T

    await asyncio.sleep(1.3)

    while time.monotonic() < end_time:
        acq_signal = s.get("http://127.0.0.1:8000/dad/channel1/acquire-signal")
        ref_signal = s.get("http://127.0.0.1:8000/dad/channel2/acquire-signal")
        aux_signal = s.get("http://127.0.0.1:8000/dad/channel3/acquire-signal")
        aux2_signal = s.get("http://127.0.0.1:8000/dad/channel4/acquire-signal")

        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        aux_data = aux_signal.json() - aux_bg
        aux2_data = aux2_signal.json() - aux2_bg

        cal_ref = 0.0012 * ref_data ** 2 + 0.9893 * ref_data  # new for 75 ms
        # cal_ref = 0.0012 * ref_data ** 2 + 0.9893 * ref_data + 3.522  # new for 75 ms
        # cal_ref = 0.0006 * ref_signal.json() ** 2 +0.9313 * ref_signal.json() + 23.778  # for 20 ms
        cal_data = acq_data - cal_ref

        acq_data_deque.append(acq_data)
        cal_data_deque.append(cal_data)

        acq_median = statistics.median(acq_data_deque)
        cal_median = statistics.median(cal_data_deque)
        logger.debug(
            f"real signal: {acq_signal.json()} (cal:{acq_data} (median: {acq_median})); "
            f"real ref: {ref_signal.json()} (cal: {ref_data}; "
            f"auxiliary sg: {aux_signal.json()} (cal: {aux_data});"
            f"calibrate: {cal_data} (median: {cal_median})")
        # spectra = pd.concat([spectra, pd.Series(acq_signal.json(), index=[time.monotonic()])])
        spectra = pd.concat(
            [spectra,
             pd.DataFrame([acq_signal.json(), ref_signal.json(),
                           acq_data, ref_data, acq_median,
                           cal_data, cal_median,
                           aux_signal.json(), aux_data,
                           aux2_signal.json(), aux2_data],
                          index=["480nm", "700nm",
                                 "480cal", "700cal", "480(med)",
                                 "cal", "cal(med)",
                                 "500nm", "500cal",
                                 "460nm", "460cal"],
                          columns=[time.monotonic()],
                          ).T
             ]
        )
        signal_history.append(acq_data)
        ref_history.append(ref_data)
        cal_history.append(cal_data)
        med_history.append(cal_median)
        aux_history.append(aux2_data)
        await asyncio.sleep(1.3)

        update_plot()
        spectra.to_csv(rf'W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\dad_spectra\{date}_spectra_{mongo_id}.csv',
                       header=True
                       )

    plt.close()
    logger.info("finish the dad data request for the plot!")

    s.put("http://127.0.0.1:8000/r2/Pump_A/stop")
    s.put("http://127.0.0.1:8000/O2MFC/MFC/stop")
    s.put("http://127.0.0.1:8000/Knauer-pumpM/pump/stop")

    logger.info("finish dad data collection request! Stop pumpA and O2 MFC")

def plot_old_dad():
    raw = pd.read_csv(
        r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\dad_spectra\20230424_spectra_640506b73fedbeb2be0c13a20_fake_test_0.1ML_modify.csv")
    # raw.plot(x="time", y="cal(med)")
    ax = raw.plot(x="time (min)", y="480nm", alpha=0.5, color="blue", figsize=(10, 2.5), label="480nm")
    raw.plot(x="time (min)", y="700nm", alpha=0.5, color="orange", label="700nm", ax=ax)
    raw.plot(x="time (min)", y="cal", alpha=0.5, label="cal", ax=ax)
    raw.plot(x="time (min)", y="cal(med)", color="black", label="cal(med)", ax=ax)
    # plt.show()
    plt.savefig('W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\dad_spectra\o20_fake_test_0.1ML_1_modify_size_10_2.5.svg')



async def main():
    logger.add(f"TinT_bf_bpr.log", rotation="10 MB")
    date = datetime.date.today().strftime("%Y%m%d")
    # name = 'test_tubeintube_before_bpr_3bar_2.2equiv_6min_0.09L_1.17G'
    from BV_experiments.src.general_platform.Executor.Experiment.platform_individual import adj_bpr

    condition = {'dye_equiv': 0.001, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.2,
                 'solvent_equiv': 1.0, 'time': 5, 'light': 0, 'pressure': 6.0, 'temperature': 34,
                 }
    from BV_experiments.Example0_BV.calc_oper_para import calc_concentration, calc_gas_liquid_flow_rate
    condition["concentration"] = calc_concentration(condition)
    logger.info(f"condition:{condition}")
    set_gas_liquid_flow = calc_gas_liquid_flow_rate(condition)
    logger.info(f"pump:{set_gas_liquid_flow}")

    await adj_bpr(6.0)
    name = f'test_tubeintube_before_bpr_{condition["pressure"]}bar_{condition["oxygen_equiv"]}equiv_{condition["time"]}min'
    await monitor_dad_given_time(date, name, 20, set_gas_liquid_flow)

    condition = {'dye_equiv': 0.001, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.2,
                 'solvent_equiv': 1.0, 'time': 15, 'light': 13, 'pressure': 4.0, 'temperature': 34,
                 }
    from BV_experiments.Example0_BV.calc_oper_para import calc_concentration, calc_gas_liquid_flow_rate
    condition["concentration"] = calc_concentration(condition)
    logger.info(f"condition:{condition}")
    set_gas_liquid_flow = calc_gas_liquid_flow_rate(condition)
    logger.info(f"pump:{set_gas_liquid_flow}")

    await adj_bpr(4.0)
    name = f'test_tubeintube_before_bpr_{condition["pressure"]}bar_{condition["oxygen_equiv"]}equiv_{condition["time"]}min'
    await monitor_dad_given_time(date, name, 20, set_gas_liquid_flow)

    condition = {'dye_equiv': 0.001, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.2,
                 'solvent_equiv': 1.0, 'time': 15, 'light': 13, 'pressure': 2.0, 'temperature': 34,
                 }
    from BV_experiments.Example0_BV.calc_oper_para import calc_concentration, calc_gas_liquid_flow_rate
    condition["concentration"] = calc_concentration(condition)
    logger.info(f"condition:{condition}")
    set_gas_liquid_flow = calc_gas_liquid_flow_rate(condition)
    logger.info(f"pump:{set_gas_liquid_flow}")

    await adj_bpr(2.0)
    name = f'test_tubeintube_before_bpr_{condition["pressure"]}bar_{condition["oxygen_equiv"]}equiv_{condition["time"]}min'
    await monitor_dad_given_time(date, name, 20, set_gas_liquid_flow)

    from BV_experiments.src.general_platform.Executor.Experiment.platform_precedure import platform_shutdown
    from BV_experiments.src.general_platform.Executor.Analytical.platform_remote_hplc_control import Async_ClarityRemoteInterface

    hplc_commander = Async_ClarityRemoteInterface(remote=True, host='192.168.10.11', port=10015,
                                                  instrument_number=1)
    await platform_shutdown(hplc_commander)
    # plot_old_dad()

if __name__ == "__main__":
    asyncio.run(main())
