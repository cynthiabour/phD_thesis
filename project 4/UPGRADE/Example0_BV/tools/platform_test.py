import datetime
import time
import asyncio
import requests
from loguru import logger

from pathlib import Path

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session
from BV_experiments.Example0_BV.calc_oper_para import (reagent_vol_ratio, calc_inj_loop, calc_concentration, calc_time,
                                                       calc_gas_liquid_flow_rate, calibrate_flow_rate, calibrate_syringe_rate)  # TODO: real exp
from BV_experiments.src.general_platform.Executor.Experiment.dad_parse import collect_dad_given_time
from BV_experiments.src.general_platform.Executor.Experiment.log_experiment import system_log
from BV_experiments.src.general_platform.Executor.Experiment.log_flow import flow_log
from BV_experiments.src.general_platform.platform_error import PlatformError
from BV_experiments.src.general_platform.Executor.Experiment.platform_precedure import exp_hardware_initialize
from BV_experiments.src.general_platform.Executor.Analytical.platform_remote_hplc_control import Async_ClarityRemoteInterface
from BV_experiments.src.general_platform.Executor.Experiment.platform_individual import adj_bpr, check_system_ready


async def run_fake_test(mongo_id: str, commander: Async_ClarityRemoteInterface):
    """
    to test the current setup...
    :param mongo_id:
    :param commander:
    :return:
    """
    # with command_session() as sess:
    #     sess.put("http://127.0.0.1:8000/r2/Pump_A/infuse?rate=0.1ml%2Fmin")
    #     sess.put("http://127.0.0.1:8000/O2MFC/MFC/set-flow-rate?flowrate=0.3ml%2Fmin")
    #     sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Reagent"})
    #     sess.put("http://127.0.0.1:8000/r2/ReagentValve_A/position?position=Reagent")
    #     logger.info(f"the experiment was completed at {datetime.datetime.now()}!")
    #
    #     await asyncio.sleep(600)
    #     await commander.load_method(r"D:\Data2q\BV\BV_New_method_c18_waters_16min.MET")
    #     await hplc_commander.load_method(r"D:\Data2q\BV\BV_General_method_r1met_30min_025mlmin.MET")
    #     # await commander.load_file("opendedicatedproject") # open a project for measurements
    #     await commander.set_sample_name(f"{mongo_id}")
    #     await commander.run()  # delay 2 sec.....
    #     await asyncio.sleep(2)
    #     # initialized all hardware
    #     await exp_hardware_initialize()
    #     logger.info("the hardware initialization were completed.")
    #
    #     analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"
    #     filewatcher = FileWatch(folder_path=analysed_samples_folder, file_extension="txt")
    #
    #     # wait 15 min.....(after 4 min purging system)
    #     file_existed = await filewatcher.check_file_existence_timeout(file_name=f"{mongo_id} - DAD 2.1L- Channel 2.txt",
    #                                                                   timeout=900,
    #                                                                   check_interval=3)
    #     if file_existed:
    #         result_215 = hplc_result(mongo_id, file_existed, "215nm")
    #         logger.debug(f"result at 215 nm: {result_215}")
    #         result_254 = hplc_result(mongo_id,
    #                                  Path(analysed_samples_folder) / Path(f"{mongo_id} - DAD 2.1L- Channel 1.txt"),
    #                                  "254nm")
    #         logger.debug(f"result at 254 nm: {result_254}")
    #         return {"result_254": result_254, "result_215": result_215}
    #     else:
    #         logger.error(f"The hplc file isn't found! check manually.....")
    #         return {"result_254": None, "result_215": None}
    pass


async def run_experiment_without_prepared_mixture(
        mongo_id: str,
        condition: dict,
        inj_rate: dict,
        flow_rate: dict,
        time_schedule: dict,
        commander: Async_ClarityRemoteInterface) -> Path | bool:
    """

    """
    from BV_experiments.src.general_platform.Executor.Experiment.platform_individual import pre_run_exp, dad_tracing_half_height, purge_system

    await pre_run_exp(condition, flow_rate)
    logger.info(f"starting check the system ready..")

    # check system parameter: pressure, temp, gas-flow (total time: fill_loop_time + timeout)
    sys_state = await check_system_ready(condition, flow_rate['gas_flow'], 20.0)
    if not sys_state:
        logger.error("Platform could not reach the target condition...")
        await exp_hardware_initialize()
        raise PlatformError("Platform could not reach the target condition...")

    # filling the loop
    # await loop_by_2_crosses(condition)

    with command_session() as sess:
        # switch the InjValveA to inject the reaction mixture into the system, RUN the experiment
        switching_time = time.monotonic()
        sess.put(r2_endpoint + "/InjectionValve_A/position", params={"position": "inject"})
        logger.info(f"switch the injectionValve A to inject at {switching_time}! Starting reaction....")

        # Wait 1 residence time TODO: might need to shorten the time
        await asyncio.sleep(condition["time"] * 60 - 20)

    # peak_result = await dad_tracing_apex(switching_time, flow_rate, time_schedule)
    peak_result = await dad_tracing_half_height(switching_time, flow_rate, time_schedule)

    if not peak_result:
        logger.debug("fail tracing the peak")

    logger.debug(f"succeed tracing the peak")

    # Part II: prepare the hplc sample
    with command_session() as sess:
        await asyncio.sleep(time_schedule['start_hplc'] * 60)
        # await asyncio.sleep(time_schedule['start_hplc'] * 60 + 5) # TODO: deley 10 more sec // default 3
        logger.info(f"Finish hplc sampling at {time.monotonic()}!")

        # send the method.....
        # await commander.load_method(HPLC_METHOD)
        # await commander.set_sample_name(f"{mongo_id}")
        # await commander.run()  # delay 2 sec.....
        # await asyncio.sleep(2)

        # inject sample by switch the hplc injection valve
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "inject"})
        logger.info(f"Switch the hplc injection valve and start to analysis")

        await asyncio.sleep(1)  # 0.24 sec for 0.001 ml sample / 0.25 ml/min flow rate
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "load"})
        logger.info(f"complete injecting the hplc sample and start the analysis")
        await asyncio.sleep(time_schedule["half_peak"] * 1.2 * 60 + 600)  # todo: only for longer information

    # purge the system (~ 4.5min): increasing the solvent velocity to purge the seperator
    await purge_system(time_schedule["purge_system"])
    logger.info(f"the experiment was completed!")

    # initialized all hardware
    await exp_hardware_initialize()
    logger.info("the hardware initialization were completed.")

    return True



async def loop_by_2_crosses(condition: dict):
    logger.info("_________________________________________________________")

    # calc concentration
    condition["concentration"] = calc_concentration(condition)
    logger.debug(f"theoretically concentration: {condition['concentration']}")

    vol_ratio = reagent_vol_ratio(condition)
    # Calculate the required volume to fill the loop [0.1 mL]

    LOOP_VOLUME = 0.1  # ml
    FILLING_TIME = 0.5  # mins
    total_infusion_rate = LOOP_VOLUME / FILLING_TIME

    vol_of_all = {key: value * LOOP_VOLUME / sum(vol_ratio.values()) for key, value in vol_ratio.items()}
    rate_of_all = {key: value / FILLING_TIME for key, value in vol_of_all.items()}
    logger.debug(f"volume: {vol_of_all}")
    logger.debug(f"rate: {rate_of_all}")
    # find_lowest_
    CROSS = 0.004
    TUBE_CROSS_TO_CROSS = 0.005  # in ml = 0.07 (m)*70.69 (ul/m)
    TUBE_MIXER_TO_LOOP = 0.007  # delay from mixer to loop # in ml = 0.10 (m)*70.69 (ul/m)

    t_0 = [0.15, 0.10]
    t_0_1 = (CROSS + TUBE_CROSS_TO_CROSS) / 3 / (total_infusion_rate/5)
    t_0_2 = CROSS / 2 / (total_infusion_rate/5)

    t_1 = (CROSS + TUBE_CROSS_TO_CROSS) / (
                rate_of_all['Solvent'] + rate_of_all['Activator'] + rate_of_all['Quencher']) * 1.2
    t_2 = (CROSS + TUBE_MIXER_TO_LOOP) / total_infusion_rate  # * 1.2
    t_3 = FILLING_TIME * 0.250  # 0.025 ml
    t_4 = FILLING_TIME * 0.5  # 1.0 :0.1 ml

    sess = requests.Session()
    # purge the system
    sess.put(solvent_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min",})  #"volume": f" ml"
    sess.put(activator_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min",})  #"volume": f" ml"
    sess.put(quencher_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min",})  #"volume": f" ml"
    await asyncio.sleep(t_0_1 * 60)
    sess.put(eosinY_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min"})
    sess.put(SMIS_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min"}, )
    await asyncio.sleep(t_0_2 * 60)

    # prepare the reaction mixture
    logger.debug("start to prepare the reaction mixture")
    sess.put(solvent_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Solvent']} ml/min"})
    sess.put(activator_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Activator']} ml/min"})
    sess.put(quencher_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Quencher']} ml/min"})
    await asyncio.sleep(t_1 * 60)

    logger.debug("reach 2nd cross")

    sess.put(eosinY_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Dye']} ml/min"})
    sess.put(SMIS_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['SMIS']} ml/min"}, )

    await asyncio.sleep(t_2 * 60)
    logger.info("start infusing to loop!")

    await asyncio.sleep(t_3 * 60)

    for x in range(3):
        print(3 - x)
        await asyncio.sleep(1)

    logger.info("START!")
    start_time = time.monotonic()
    end_time = start_time + t_4 * 60

    # await asyncio.sleep(FILLING_TIME * 1.0 * 60)  # time of filling
    while time.monotonic() < end_time:
        print(f"{end_time - time.monotonic()} sec left.")
        await asyncio.sleep(1)

    logger.info("END!")

    # await asyncio.sleep(FILLING_TIME * 0.25 * 60)
    # push rxn mixture in the tube into the loop to reduce the usage of
    sess.put(SMIS_endpoint + "/pump/stop")
    sess.put(eosinY_endpoint + "/pump/stop")
    sess.put(activator_endpoint + "/pump/stop")
    sess.put(quencher_endpoint + "/pump/stop")
    sess.put(solvent_endpoint + "/pump/stop")

    logger.debug(f"finish filling the loop! stop all pump")

    purge_volume_ml = (TUBE_MIXER_TO_LOOP + CROSS * 2 + TUBE_CROSS_TO_CROSS) * 2
    sess.put(solvent_endpoint + "/pump/infuse", params={
        "rate": f"{total_infusion_rate * 4} ml/min",
        "volume": f"{purge_volume_ml} ml"})
    #
    # logger.info(f"purge the mixer and tube with {purge_volume_ml} ml solvent.")
    # logger.info("finished")


async def loop_by_manifolds(condition: dict):
    logger.info("_________________________________________________________")

    # calc concentration
    condition["concentration"] = calc_concentration(condition)
    logger.debug(f"theoretically concentration: {condition['concentration']}")

    # calculate the operating parameters
    # volume_for_loop, inj_loop_flow_rate = calc_inj_loop(condition)
    # gas_liquid_flow = calc_gas_liquid_flow_rate(condition)
    # time_schedule = calc_time(condition, gas_liquid_flow)

    vol_ratio = reagent_vol_ratio(condition)
    # Calculate the required volume to fill the loop [0.1 mL]

    LOOP_VOLUME = 0.1  # ml
    FILLING_TIME = 1  # mins
    total_infusion_rate = LOOP_VOLUME / FILLING_TIME

    vol_of_all = {key: value * LOOP_VOLUME / sum(vol_ratio.values()) for key, value in vol_ratio.items()}
    rate_of_all = {key: value / FILLING_TIME for key, value in vol_of_all.items()}

    MANIFOLDS_SWEPT_VOLUME = 0.139
    TUBE_MIXER_TO_LOOP = 0.007  # delay from mixer to loop

    sess = requests.Session()
    # Start to fill the loop: FILLING_TIME
    sess.put(solvent_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Solvent']} ml/min"})
    sess.put(eosinY_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Dye']} ml/min"})
    sess.put(activator_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Activator']} ml/min"})
    sess.put(quencher_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Quencher']} ml/min"})
    sess.put(SMIS_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['SMIS']} ml/min"}, )

    await asyncio.sleep(MANIFOLDS_SWEPT_VOLUME / total_infusion_rate * 60)
    await asyncio.sleep(TUBE_MIXER_TO_LOOP / total_infusion_rate * 60)

    logger.info("start infusing to loop!")
    await asyncio.sleep(FILLING_TIME * 0.25 * 60)
    for x in range(3):
        print(x)
        await asyncio.sleep(1)

    logger.info("START!")
    start_time = time.monotonic()
    end_time = start_time + FILLING_TIME * 1.0 * 60
    # await asyncio.sleep(FILLING_TIME * 1.0 * 60)  # time of filling
    while time.monotonic() < end_time:
        print(f"{end_time - time.monotonic()} sec left.")
        await asyncio.sleep(1)

    logger.info("END!")

    # await asyncio.sleep(FILLING_TIME * 0.25 * 60)
    # push rxn mixture in the tube into the loop to reduce the usage of
    sess.put(SMIS_endpoint + "/pump/stop")

    # logger.debug(
    #     f"replace the starting material with solvent: total volume of SM used:"
    #     f" {rate_of_all['SMIS'] * rate_of_all['pushing_mixture']} ml")
    # sess.put(solvent_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['SMIS'] + rate_of_all['Solvent']} ml/min"})
    # await asyncio.sleep(TUBE_MIXER_TO_LOOP / total_infusion_rate * 0.5 * 60)

    sess.put(eosinY_endpoint + "/pump/stop")
    sess.put(activator_endpoint + "/pump/stop")
    sess.put(quencher_endpoint + "/pump/stop")
    sess.put(solvent_endpoint + "/pump/stop")

    logger.debug(f"finish filling the loop! stop all pump")

    purge_volume_ml = (TUBE_MIXER_TO_LOOP + MANIFOLDS_SWEPT_VOLUME) * 2
    sess.put(solvent_endpoint + "/pump/infuse", params={
        "rate": f"{total_infusion_rate * 2} ml/min",
        "volume": f"{purge_volume_ml} ml"})
    logger.info(f"purge the mixer and tube with {purge_volume_ml} ml solvent.")
    logger.info("finished")


async def overall_run_w_log(mongo_id: str,
                            condition: dict,
                            hplc_commander: Async_ClarityRemoteInterface
                            ) -> dict | bool:
    """
    all parameters for running experiment and hplc analysis and processing are included in this function.
    """
    date = datetime.date.today().strftime("%Y%m%d")
    log_path = Path(rf"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\logger\{date}_{mongo_id}.log")
    i = logger.add(log_path, rotation="10 MB")

    logger.info("_________________________________________________________")
    logger.info(f"condition of {mongo_id}: {condition}")

    # calc concentration
    condition["concentration"] = calc_concentration(condition)
    logger.debug(f"theoretically concentration: {condition['concentration']}")

    # calculate the operating parameters
    volume_for_loop, inj_loop_flow_rate = calc_inj_loop(condition)
    gas_liquid_flow = calc_gas_liquid_flow_rate(condition)
    time_schedule = calc_time(condition, inj_loop_flow_rate, gas_liquid_flow)

    # calibrate the real operating parameters
    setting_syringe_rate = calibrate_syringe_rate(inj_loop_flow_rate)
    setting_gas_liquid_flow = calibrate_flow_rate(gas_liquid_flow)

    logger.info(f"time:{time_schedule}")

    logger.info(f"start to adjust the system pressure for new experiment.....")
    reach_p = await adj_bpr(condition["pressure"], time_schedule["adj_press"])

    if reach_p:
        logger.info(f"Start to run the test experiment!!!")
        txt_file_existed, _, _, _ = await asyncio.gather(
            run_experiment_without_prepared_mixture(
                mongo_id,
                condition,
                setting_syringe_rate,
                setting_gas_liquid_flow,
                time_schedule,
                hplc_commander
            ),
            system_log(date, mongo_id, time_schedule["total_operation_time"]),
            collect_dad_given_time(date, mongo_id, time_schedule["total_operation_time"]),
            flow_log(date, mongo_id, time_schedule["total_operation_time"])
        )
        logger.info("experiment finished.")

        # analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"
        # if txt_file_existed:
        #     attempts = 0
        #     # PermissionError [Errno 13] Permission denied will happened. try 3 time
        #     # @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(10), reraise=True)
        #     while attempts < 3:
        #         try:
        #             hplc_results = processing_hplc_file(mongo_id,
        #                                                 txt_file_existed,
        #                                                 condition,"tmob",
        #                                                 analysed_samples_folder)
        #             logger.remove(i)
        #             return hplc_results
        #         except Exception as e:
        #             attempts += 1
        #             logger.error(f"{e}")
        #             await asyncio.sleep(10)
        # else:
        #     logger.error(f"IncompleteAnalysis: The hplc file isn't found! check manually.....")
        #     # raise IncompleteAnalysis
        #     logger.remove(i)
        #     return False

    else:
        logger.error(f"the pressure could not reach the required conditions.... Something is wrong!!!")
        await exp_hardware_initialize()
        logger.info("platform standby. Wait until hardware being checked!")
        logger.remove(i)
        raise PlatformError


async def main():
    # i = logger.add(f"D:\BV\BV_experiments\log\myapp.log", rotation="10 MB")
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':
        # hplc commander
        hplc_commander = Async_ClarityRemoteInterface(remote=True, host='192.168.10.11', port=10015,
                                                      instrument_number=1)
        # await startup_hplc(hplc_commander)

        # await hplc_commander.load_method(HPLC_METHOD)
        # await hplc_commander.set_sample_name(f"blank_dilution_test_9_20230713")
        # await hplc_commander.run()  # delay 2 sec.....
        # await asyncio.sleep(600)

        # mongo_id = "whhsu136_010_condition_dv3_0.22loop_1_13_time"
        mongo_id = "sol20_4.5min_dv_0.22loop_1.5maxpM"

        # exp_condition = {'dye_equiv': 0.001, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.0,
        #                  'solvent_equiv': 200, 'time': 5, 'light': 0, 'pressure': 4.0, 'temperature': 28,
        #                  }
        exp_condition = {'dye_equiv': 0.01, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.2,
                           'solvent_equiv': 20.0, 'time': 4.5, 'light': 0, 'pressure': 4.0, 'temperature': 28,
                           }

        # control_condition = {'exp_code': f"WHH-136-old_002",
        #                      'dye_equiv': 0.08620196580886841, 'activator_equiv': 0.013944430276751518,
        #                      'quencher_equiv': 7.827028274536133, 'oxygen_equiv': 2.1007368564605713,
        #                      'solvent_equiv': 115.25133514404297, 'time': 5,
        #                      'light': 9.500490188598633, 'pressure': 4.167105197906494,
        #                      'temperature': 32.520042419433594,
        #                      }

        # exp_condition = {
        #     'exp_code': f"WHH-136-010",
        #     'dye_equiv': 0.017158085480332375, 'activator_equiv': 0.05112427473068237,
        #     'quencher_equiv': 9.386429786682129,
        #     'oxygen_equiv': 2.079172134399414, 'solvent_equiv': 10.309477806091309, 'time': 23.64241600036621,
        #     'light': 0, 'pressure': 3.272460699081421, 'temperature': 28,
        # }
        # exp_condition = {
        #     'exp_code': f"WHH-136-010",
        #     'dye_equiv': 0.017158085480332375, 'activator_equiv': 0.05112427473068237,
        #     'quencher_equiv': 9.386429786682129,
        #     'oxygen_equiv': 2.079172134399414, 'solvent_equiv': 10.309477806091309, 'time': 23.64241600036621,
        #     'light': 0, 'pressure': 3.272460699081421, 'temperature': 28,
        # }

        raw_hplc_results = await overall_run_w_log(mongo_id, exp_condition, hplc_commander)
        # logger.info(f"{mongo_id}: {raw_hplc_results}")
        #
        # # await hplc_commander.load_method(r"D:\Data2q\BV\autostartup_analysis\autostartup_000_BV_c18_shortened.MET")
        # await platform_shutdown(hplc_commander)
        # logger.info(f"finish all test!")

    elif socket.gethostname() == 'BSPC-8WSHWS2':
        logger.error(f"automatic platform is not on this computer.")
        pass

    # logger.remove(i)

if __name__ == "__main__":
    asyncio.run(main())
