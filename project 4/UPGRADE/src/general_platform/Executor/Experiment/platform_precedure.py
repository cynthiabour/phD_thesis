"""
the platform general start and pulse, shotdown methods
"""
import asyncio

from BV_experiments.src.general_platform.Executor.Analytical.platform_remote_hplc_control import Async_ClarityRemoteInterface
from BV_experiments.src.general_platform.Executor._hw_control import *
from loguru import logger
from datetime import time, datetime

from BV_experiments.src.general_platform.Executor._hw_control import command_session

async def dad_initialize(dad_info: dict | None = None):
    """ initialize the dad"""
    if dad_info is None:
        wavelength_info = {"channel-1": "350", "channel_2": "700", "channel_3": "254", "channel_4": "280"}
        bandwidth = "8"
        int_time = "75"
    else:
        wavelength_info = dad_info["wavelength"]
        bandwidth = dad_info["bandwidth"] if "bandwidth" in dad_info.keys() else "8"
        int_time = dad_info["integration_time"] if "integration_time" in dad_info.keys() else "8"

    logger.info(f"initialize the dad")  # after any experiment
    with command_session() as sess:
        # check the d2 lamp should already on before experiment....
        for channel, wavelength in wavelength_info.items():
            sess.put(dad_endpoint + f"/channel{channel[-1]}/set-wavelength", params={"wavelength": wavelength})
            sess.put(dad_endpoint + f"/channel{channel[-1]}/set-bandwidth", params={"bandwidth": bandwidth})
            sess.put(dad_endpoint + f"/channel{channel[-1]}/set-integration-time", params={"int_time": int_time})
    logger.debug(f"finish dad initialize!")


async def exp_hardware_initialize(dad_info: dict | None = None):
    """ initialize the platform and prepared for the next experiment"""
    logger.info(f"initialize the hardware")  # after any experiment

    if dad_info is not None:
        # TODO: check the d2 lamp should already on before experiment....
        await dad_initialize(dad_info=dad_info)
    else:
        logger.warning(f"no dad_info provided, check the dad status manually!")

    with command_session() as sess:
        # R2
        sess.put(r2_endpoint + "/Pump_A/stop")  # set 0.0 ml/min
        sess.put(r2_endpoint + "/Pump_B/stop")  # set 0.0 ml/min
        sess.put(r2_endpoint + "/InjectionValve_A/position", params={"position": "load"})
        sess.put(r2_endpoint + "/InjectionValve_B/position", params={"position": "load"})
        sess.put(r2_endpoint + "/ReagentValve_A/position", params={"position": "Solvent"})
        sess.put(r2_endpoint + "/ReagentValve_B/position", params={"position": "Reagent"})
        sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Solvent"})

        sess.put(r2_endpoint + "/PhotoReactor/power-off")  # set to 0%
        sess.put(r2_endpoint + "/reactor-3/temperature", params={"temperature": f"22°C", "heating": "true", })  # current rt ~27.5
        sess.put(r2_endpoint + "/Power/power-on")

        # o2 MFC
        sess.put(O2MFC_endpoint + "/MFC/stop")  # set 0.0 ml/min

        # HPLC valve
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "inject"})

        # AnalValve
        # todo: check the mapping of the valve (by physical setup)
        analvalve_mapping = {'HPLC': '2', 'IR': '1', 'COLLECT': '3', 'NMR': '4', 'WASTE': '6'}  # todo: analvalve_mapping
        sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping["COLLECT"]})

        # HPLC pump
        sess.put(pumpM_endpoint + "/pump/stop")
        sess.put(pumpAdd_endpoint + "/pump/stop")

        # TODO: Reply: {"detail":"Not Found"} on http://127.0.0.1:8000/syr0/pump/stop
        # syringe pumps
        sess.put(syr0_endpoint + "/pump/stop")
        sess.put(syr3_endpoint + "/pump/stop")
        sess.put(syr4_endpoint + "/pump/stop")
        sess.put(syr5_endpoint + "/pump/stop")
        sess.put(syr6_endpoint + "/pump/stop")

        # sess.put(bubble_sensor_power_endpoint + "/5V/power-off")
        # sess.put(bubble_sensor_measure_endpoint + "/bubble-sensor/power-off")

    logger.info(f"finish hardware initialize!")

async def wash_collector():
    TUBE_COLLECTOR_01 = 0.016 + 0.130  # in ml = 0.23 (m)*70.69 (ul/m) + 0.165 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_02 = 0.251  # in ml = 0.32 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_03 = 0.157  # in ml = 0.20 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_04 = 0.165  # in ml = 0.21 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_05 = 0.157  # in ml = 0.20 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_06 = 0.353  # in ml = 0.45 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_07 = 0.204  # in ml = 0.26 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_08 = 0.157  # in ml = 0.20 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_09 = 0.141  # in ml = 0.18 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_10 = 0.126  # in ml = 0.16 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_11 = 0.196  # in ml = 0.25 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_12 = 0.165  # in ml = 0.21 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_13 = 0.173  # in ml = 0.22 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_14 = 0.393  # in ml = 0.50 (m)*785.4 (ul/m)
    TUBE_COLLECTOR_15 = 0.432  # in ml = 0.55 (m)*785.4 (ul/m)


async def startup_hplc(hplc_commander: Async_ClarityRemoteInterface,
                       hplc_exp_method: str,
                       open_clarity_method: str = r"D:\Data2q\BV\autostartup_analysis\autostartup_000_BV_c18_shortened.MET",
                       ramp_methods: tuple = ("autostartup_005_BV_c18_shortened.MET",
                                              "autostartup_010_BV_c18_shortened.MET",
                                              "autostartup_015_BV_c18_shortened.MET",
                                              "autostartup_020_BV_c18_shortened.MET",
                                              "autostartup_025_BV_c18_shortened.MET",
                                              )):

    # await hplc_commander.exit()
    # await hplc_commander.switch_lamp_on(address="192.168.10.102", port=10001) #address and port hardcoded
    #TODO: currently, please switch the lamp manually

    await hplc_commander.open_clarity_chrom("admin",
                                            config_file=r"C:\ClarityChrom\Cfg\automated_exp.cfg",
                                            start_method=open_clarity_method, )

    await hplc_commander.slow_flowrate_ramp(r"D:\Data2q\BV\autostartup_analysis",
                                            method_list=ramp_methods)

    await hplc_commander.load_method(hplc_exp_method)
    logger.info(f"finish the hplc startup. load the method for analysis (flow rate 0.25 ml/min).")


async def prime_syringe_and_lines(dry_reactor=False):
    """
    prime the syring and tubing btw the mixer
    :param dry_reactor:
    :return: bool
    """
    CHECK_VALVE = 0.187  # CV3000+CV3001 = 96 ul + 91 ul
    TUBE_SMIS = 0.0106  # in ml = 0.10 (m)*70.69 (ul/m)
    TUBE_QUENCHER = 0.016 + CHECK_VALVE  # in ml = 0.22 (m)*70.69 (ul/m)
    TUBE_DYE = 0.011  # in ml = 0.22 (m)*70.69 (ul/m)
    TUBE_SOLVENT = 0.283 + CHECK_VALVE  # in ml = (0.26 + 0.10) (m)*785.4 (ul/m)
    TUBE_ACTIVATOR = 0.015 + CHECK_VALVE  # in ml = (0.10 + 0.11) (m)*70.69 (ul/m)

    with command_session() as sess:
        # TODO: program of prime....

        pass

async def platform_standby(hplc_commander: Async_ClarityRemoteInterface,
                           dad_info: dict | None = None,
                           off_duty_time: datetime.time = time(21, 0),
                           standby_hplc_method: str = r"D:\Data2q\BV\autostartup_analysis\autostartup_000_BV_c18_shortened.MET"):
    """ standby the platform due to errors"""
    current_time = datetime.now().time()
    # off_duty_time = time(20, 00)

    await exp_hardware_initialize(dad_info)
    with command_session() as sess:
        # MFC
        sess.put(pressEPC_endpoint + "/EPC/stop")
        sess.put(pressMFC_endpoint + "/MFC/stop")  # set 0.0 ml/min

        # DAD
        sess.put(dad_endpoint + "/d2/power-off") if current_time > off_duty_time else None

        # R2
        sess.put(r2_endpoint + "/Power/power-off")

    # HPLC
    await hplc_commander.load_method(standby_hplc_method) if current_time > off_duty_time else None

    logger.info("system + hplc standby... wait for further operation....")

async def platform_shutdown(hplc_commander: Async_ClarityRemoteInterface,
                            dad_info: dict | None = None):

    """ shutdown the platform"""
    await platform_standby(hplc_commander, dad_info)
    with command_session() as sess:
        # todo: HPLC_end method_preserve the column under ACN + 0.1% TFA
        # await hplc_commander.load_method(r"D:\Data2q\BV\End_method_025mlmin.MET")
        # await hplc_commander.run()
        # await asyncio.sleep(1200)

        # DAD
        sess.put(dad_endpoint + "/d2/power-off")

        # HPLC
        await hplc_commander.load_method(r"D:\Data2q\BV\autostartup_analysis\autostartup_000_BV_c18_shortened.MET")
        # Todo: turn of the lamp manually

        # TODO: check method did not shut all programme off
        # await hplc_commander.exit()
        # await hplc_commander.switch_lamp_off(address="192.168.10.102", port=10001)  # TODO: address and port hardcoded

    logger.info(f"finish hardware shutdown!")

async def main():
    commander = Async_ClarityRemoteInterface(remote=True, host='192.168.10.11', port=10015, instrument_number=1)
    from BV_experiments.Example3_debenzylation.db_doc import FirstDebenzylation, FlowSetupDad
    # await platform_standby(commander, dad_info=FirstDebenzylation.dad_info)
    await platform_shutdown(commander, dad_info=FirstDebenzylation.dad_info)
    # await exp_hardware_initialize(dad_info=FirstDebenzylation.dad_info)

    analvalve_mapping = {
        key.split("_TO_")[1]: value[-1]
        for key, value in FlowSetupDad.physical_info_setup_list.items()
        if key.startswith("TUBE_ANALVALVE") and isinstance(value[-1], str)
    }


if __name__ == "__main__":
    # asyncio.run(exp_hardware_initialize())
    asyncio.run(main())