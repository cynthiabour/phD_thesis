"""
To record the whole experiment to csv file for future diagnosis

system log: log the r2, MFC, etc.

"""
import time
import asyncio
import pandas as pd
import requests
from requests import HTTPError
import datetime
import pint
from loguru import logger

async def system_log(date: datetime,
                     mongo_id: str,
                     total_time: float | pint.Quantity,
                     folder_path: str = r"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\system_log\\"
                     ) -> dict:
    if isinstance(total_time, float):
        logger.warning("the total time will be converted to minutes")
    if isinstance(total_time, pint.Quantity):
        total_time = total_time.to("min").magnitude

    end_time = time.monotonic() + total_time * 60

    read_r2_sys = requests.get("http://127.0.0.1:8000/r2/GSensor2/monitor-system")

    if read_r2_sys.status_code == 500:
        default_data = {
            "RunState_code": "0",
            "allValve": "00000",
            "pumpA_P": 10,
            "pumpB_P": 10,
            "sysP (mbar)": 10,
            "Temp": 10,
            "o2_flow": 0.0,
            "epc": 0.0,
            "air_flow": 0.0,
            "pumpM_P": 0.0,
            "pumpAdd_P": 0.0,
            "analvalve": 0,
            "lcvalve": 0
        }
        log = pd.DataFrame(default_data, index=[time.monotonic()])
    else:
        record = read_r2_sys.json()
        read_temp = requests.get("http://127.0.0.1:8000/r2/reactor-3/temperature")
        read_o2 = requests.get("http://127.0.0.1:8000/O2MFC/MFC/get-flow-rate")
        read_epc = requests.get("http://127.0.0.1:8000/pressEPC/EPC/get-pressure")
        read_air = requests.get("http://127.0.0.1:8000/pressMFC/MFC/get-flow-rate")
        read_pumpM = requests.get("http://127.0.0.1:8000/Knauer-pumpM/pressure/read-pressure?units=bar")
        read_pumpAdd = requests.get("http://127.0.0.1:8000/Knauer-pumpA/pressure/read-pressure?units=bar")
        read_analvalve = requests.get("http://127.0.0.1:8000/AnalValve/distribution-valve/position")
        read_lcvalve = requests.get("http://127.0.0.1:8000/HPLCvalve/injection-valve/position")

        record["Temp"] = read_temp.json()
        record["o2_flow"] = read_o2.json()
        record["epc"] = read_epc.json()
        record["air_flow"] = read_air.json()
        record["pumpM_P"] = read_pumpM.json() * 1000
        record["pumpAdd_P"] = read_pumpAdd.json() * 1000
        record["analvalve"] = read_analvalve.json()
        if read_lcvalve.json() == "load":
            record["lcvalve"] = 0
        elif read_lcvalve.json() == "inject":
            record["lcvalve"] = 1
        else:
            record["lcvalve"] = 2
        log = pd.DataFrame(record, index=[time.monotonic()])
        await asyncio.sleep(1.0)  # previous, 5.0

    while time.monotonic() < end_time:
        try:
            read_sys = requests.get("http://127.0.0.1:8000/r2/GSensor2/monitor-system")
            read_sys.raise_for_status()
            n_record = read_sys.json()
            read_temp = requests.get("http://127.0.0.1:8000/r2/reactor-3/temperature")
            read_o2 = requests.get("http://127.0.0.1:8000/O2MFC/MFC/get-flow-rate")
            read_epc = requests.get("http://127.0.0.1:8000/pressEPC/EPC/get-pressure")
            read_air = requests.get("http://127.0.0.1:8000/pressMFC/MFC/get-flow-rate")
            read_pumpM = requests.get("http://127.0.0.1:8000/Knauer-pumpM/pressure/read-pressure?units=bar")
            read_pumpAdd = requests.get("http://127.0.0.1:8000/Knauer-pumpA/pressure/read-pressure?units=bar")
            read_analvalve = requests.get("http://127.0.0.1:8000/AnalValve/distribution-valve/position")
            read_lcvalve = requests.get("http://127.0.0.1:8000/HPLCvalve/injection-valve/position")

            n_record["Temp"] = read_temp.json()
            n_record["o2_flow"] = read_o2.json()
            n_record["epc"] = read_epc.json()
            n_record["air_flow"] = read_air.json()
            n_record["pumpM_P"] = read_pumpM.json() * 1000
            n_record["pumpAdd_P"] = read_pumpAdd.json() * 1000
            n_record["analvalve"] = read_analvalve.json()

            if read_lcvalve.json() == "load":
                n_record["lcvalve"] = 0
            elif read_lcvalve.json() == "inject":
                n_record["lcvalve"] = 1
            else:
                n_record["lcvalve"] = 2
            log = pd.concat([log, pd.DataFrame(n_record, index=[time.monotonic()])])
            await asyncio.sleep(1.0)  # previous, 5.0
        except HTTPError:
            # retry after 1 second
            await asyncio.sleep(1.0)
            continue
        finally:
            # show latest 10 rows
            # print(log.tail(10))
            # in case failing, save everytime for now....
            log.to_csv(f'{folder_path}{date}_log_{mongo_id}.csv', header=True)

    logger.info("finish the log of system")
    # save to mongodb
    return log.to_dict()

if __name__ == "__main__":
    mongo_id = "test"
    total_time = 25  # total time of experiments
    date = datetime.date.today().strftime("%Y%m%d")
    asyncio.run(system_log(date,
                           mongo_id,
                           1,
                           folder_path=r"W:\BS-FlowChemistry\People\Wei-Hsin\GL_data\system_log\\"))


