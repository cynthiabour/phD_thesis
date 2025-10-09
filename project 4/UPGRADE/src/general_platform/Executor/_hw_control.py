import contextlib

import requests
from loguru import logger

HOST = "127.0.0.1"
PORT = 8000

api_base = f"http://{HOST}:{PORT}"

# syring
syr0_endpoint = f"{api_base}/syr0"  # high concentration mixture; EY
syr3_endpoint = f"{api_base}/syr3"  # solvent
syr4_endpoint = f"{api_base}/syr4"  # activator
syr5_endpoint = f"{api_base}/syr5"  # quencher
syr6_endpoint = f"{api_base}/syr6"  # smis
ml600_endpoint = f"{api_base}/ML600"

dad_endpoint = f"{api_base}/dad"
bubble_sensor_measure_endpoint = f"{api_base}/bubble-sensor-measure"
bubble_sensor_power_endpoint = f"{api_base}/bubble-sensor-power"

O2MFC_endpoint = f"{api_base}/O2MFC"
pressMFC_endpoint = f"{api_base}/pressMFC"
pressEPC_endpoint = f"{api_base}/pressEPC"
r2_endpoint = f"{api_base}/r2"
pumpM_endpoint = f"{api_base}/Knauer-pumpM"
pumpAdd_endpoint = f"{api_base}/Knauer-pumpA"

sixportvalve_endpoint = f"{api_base}/6PortValve"
HPLCvalve_endpoint = f"{api_base}/HPLCvalve"
collector_endpoint = f"{api_base}/16Collector"
analValve_endpoint = f"{api_base}/AnalValve"
trnasfer_endpoint = f"{api_base}/ML600"

# analytic devices
nmr_endpoint = f"{api_base}/nmr"
flowir_endpoint = f"{api_base}/flowir"
# hplc_endpoint = f"{api_base}/hplc"
# ms_endpoint = f"{api_base}/ms"

# fixme: add the dilute and makeup pump
# reaction_endpoint = r2_endpoint + "/Pump_A"
reaction_endpoint = r2_endpoint + "/Pump_B"
dilute_endpoint = pumpAdd_endpoint + "/pump"
makeup_endpoint = pumpM_endpoint + "/pump"

__all__ = [
    "syr0_endpoint",
    "syr3_endpoint",
    "syr4_endpoint",
    "syr5_endpoint",
    "syr6_endpoint",
    "ml600_endpoint",
    "bubble_sensor_measure_endpoint",
    "bubble_sensor_power_endpoint",
    "O2MFC_endpoint",
    "pressMFC_endpoint",
    "pressEPC_endpoint",
    "r2_endpoint",
    "HPLCvalve_endpoint",
    "dad_endpoint",
    "analValve_endpoint",
    "pumpM_endpoint",
    "pumpAdd_endpoint",
    "collector_endpoint",
    "sixportvalve_endpoint",
    "flowir_endpoint",
    "dilute_endpoint",
    "makeup_endpoint",
    "reaction_endpoint",
    "trnasfer_endpoint",
    # "hplc_endpoint",
]


def check_for_errors(resp, *args, **kwargs):
    resp.raise_for_status()


def log_responses(resp, *args, **kwargs):
    logger.debug(f"Reply: {resp.text} on {resp.url}")


@contextlib.contextmanager  #decorator: add __enter__ and __exit__
def command_session():
    with requests.Session() as session:
        session.hooks["response"] = [log_responses, check_for_errors]
        yield session
