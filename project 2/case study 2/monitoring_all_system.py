"""
This script is used to monitor the status of all the devices in the system.

"""
from loguru import logger
import time
from datetime import datetime
from requests import HTTPError

import pandas as pd

# Flowchem devices
from flowchem.client.client import get_all_flowchem_devices
from BV_experiments.platform_error import PlatformError


flowchem_devices = get_all_flowchem_devices()

try:
    r2_power = flowchem_devices['r2']['Power']
    r2_general_sensor = flowchem_devices['r2']['GSensor2']

    # r2_pressure_sensor = flowchem_devices['r2']['PressureSensor']
    # r2_pump_sensorA = flowchem_devices['r2']['PumpSensor_A']
    # r2_pump_sensorB = flowchem_devices['r2']['PumpSensor_B']
    r2_reactor1 = flowchem_devices["r2"]["reactor-1"]
    r2_reactor3 = flowchem_devices["r2"]["reactor-3"]
    r2_pumpA = flowchem_devices["r2"]["Pump_A"]
    r2_pumpB = flowchem_devices["r2"]["Pump_B"]
    # r2_reagent_valveA = flowchem_devices["r2"]["ReagentValve_A"]
    # r2_reagent_valveB = flowchem_devices["r2"]["ReagentValve_B"]
    # r2_injection_valveA = flowchem_devices["r2"]["InjectionValve_A"]
    # r2_injection_valveB = flowchem_devices["r2"]["InjectionValve_B"]
    # r2_collection_valve = flowchem_devices["r2"]["CollectionValve"]

    syr0_pump = flowchem_devices["syr0"]['pump']  # hydrazine
    syr3_pump = flowchem_devices["syr3"]['pump']  # hydrazine
    syr4_pump = flowchem_devices["syr4"]['pump']  # hydrazine
    syr5_pump = flowchem_devices["syr5"]['pump']  # sugar pump
    six_port_valve = flowchem_devices["6PortValve"]["distribution-valve"]


except KeyError as e:
    raise PlatformError(f"Device {e} not found in the system")

def get_default_status() -> dict:
    """Return a dictionary of default status values."""
    return {
        "RunState_code": "0",
        "allValve": "00000",
        "pumpA_P": 10,
        "pumpB_P": 10,
        "sysP (mbar)": 10,
        "temp_R1": 10,
        "temp_R3": 10,
        "pumpA_status": 0,
        "pumpB_status": 0,
        "syr0_status": 0,
        "syr3_status": 0,
        "syr4_status": 0,
        "syr5_status": 0,
        "six_port_valve_status": 0
    }

def get_device_status() -> dict:
    """Return the status of a device."""
    try:
        system_status = r2_general_sensor.get("monitor-system").json()
        system_status['temp_R1'] = r2_reactor1.get("temperature").json()
        system_status['temp_R3'] = r2_reactor3.get("temperature").json()
        system_status['pumpA_status'] = r2_pumpA.get("is-pumping").json() * 1
        system_status['pumpB_status'] = r2_pumpB.get("is-pumping").json() * 1
        system_status['syr0_status'] = syr0_pump.get("is-pumping").json() * 1
        system_status['syr3_status'] = syr3_pump.get("is-pumping").json() * 1
        system_status['syr4_status'] = syr4_pump.get("is-pumping").json() * 1
        system_status['syr5_status'] = syr5_pump.get("is-pumping").json() * 1
        system_status['six_port_valve_status'] = six_port_valve.get("position").json()
        return system_status
    except HTTPError as e:
        logger.error(f"Could not get the status of the device. Error: {e}")
        raise(e)


def system_log(date: datetime, exp_name: str, timeout: float = 10 * 60):

    """Monitor the status of all devices in the system"""
    end_time = time.monotonic() + timeout * 60

    try:
        record = get_device_status()
        log = pd.DataFrame(record, index=[time.monotonic()])
        time.sleep(1.0)  # previous, 5.0

    except HTTPError as e:
        logger.error(f"Could not get the status of the device. Error: {e}")
        default_data = get_default_status()
        log = pd.DataFrame(default_data, index=[time.monotonic()])

    while time.monotonic() < end_time:
        try:
            n_record = get_device_status()
            log = pd.concat([log, pd.DataFrame(n_record, index=[time.monotonic()])])
            time.sleep(1.0)  # previous, 5.0
        except HTTPError:
            time.sleep(1.0)
            continue
        finally:
            log.to_csv(rf'W:\BS-FlowChemistry\People\Wei-Hsin\202405_sugar\logger\{date}_log_{exp_name}.csv', header=True)

    logger.info("finish the log of system")


if __name__ == "__main__":
    datestamp = datetime.now().strftime("%Y%m%d-%H%M")

    system_log(datestamp,
               "lev_deprotection_whole_real_run"
               )