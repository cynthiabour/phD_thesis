"""
to test the phenylHexone possibility
experiment


"""
import asyncio
import datetime
from pathlib import Path
from gryffin import Gryffin
from loguru import logger
import time

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session
from BV_experiments.anal_hplc_chromatogram import HPLC_METHOD
from BV_experiments.calc_oper_para import calc_gas_liquid_flow_rate, calibrate_flow_rate, calc_stable_system, calc_time
from BV_experiments.src.general_platform.Executor.Experiment.dad_parse import collect_dad_given_time
from BV_experiments.log_experiment import system_log
from BV_experiments.src.general_platform.Executor.Experiment.log_flow import flow_log
from BV_experiments.src.general_platform.platform_error import PlatformError
from BV_experiments.platform_individual import adj_bpr, pre_run_exp, check_system_ready, purge_system, \
    dad_tracing_half_height
# Flowchem devices

from BV_experiments.platform_precedure import exp_hardware_initialize
from BV_experiments.src.general_platform.Executor.Analytical.platform_remote_hplc_control import Async_ClarityRemoteInterface


# flowchem_devices = get_all_flowchem_devices()
#
# # pressure
# press_control = flowchem_devices['pressEPC']['EPC']
# press_helper = flowchem_devices['pressMFC']['MFC']
#
# # fill the loop
# loop_pump = flowchem_devices["syr5"]["pump"]
# loop_valve = flowchem_devices['r2']['InjectionValve_A']
#
# # reation setup
# deliver_gas = flowchem_devices['O2MFC']['MFC']
# deliver_liquid = flowchem_devices["r2"]['Pump_A']
# reactor_temp = flowchem_devices["r2"]["reactor-3"]
# reactor_photo = flowchem_devices["r2"]['PhotoReactor']
#
# # collect reaction mixture
# wash_liquid = flowchem_devices['Knauer-pumpM']['pump']
#
# # transfer reaction mixture
# transfer_liquid = flowchem_devices["ML600"]["left_pump"]
# transfer_valve = flowchem_devices["ML600"]['left_valve']
# # transfer_liquid = flowchem_devices["syr3"]["pump"]
# # transfer_valve = flowchem_devices['6PortValve']['distribution-valve']
#
# # analysis
# dilute_liquid = flowchem_devices["r2"]['Pump_B']
# hplc_valve = flowchem_devices['HPLCvalve']['injection-valve']
#
# # collection
# collect_valve = flowchem_devices["r2"]['CollectionValve']
#
# # power
# r2_power = flowchem_devices['r2']['Power']
# bubble_power = flowchem_devices['bubble-sensor-power']['5V']
#
# # sensor
# # todo: create list for sensors/logging
# general_exp_sensor = flowchem_devices['r2']['GSensor2']
# pumpM_pressure = flowchem_devices['Knauer-pumpM']['pressure']
# bubble = flowchem_devices['bubble-sensor-measure']['bubble-sensor']


async def run_experiment(
        mongo_id: str,
        condition: dict,
        inj_rate: dict,
        flow_rate: dict,
        time_schedule: dict,
        commander: Async_ClarityRemoteInterface,
        wait_hplc: bool,
        coll_p: str) -> Path | bool:
    """
    run the experiment
    :param coll_p: collect 1 min hplc sample.
    :param mongo_id: experiment name or mongodb_id
    :param condition: condition including concentration
    :param inj_rate:
    :param flow_rate:
    :param time_schedule:
    :param commander: hplc commander to send cammand to hplc computer
    :param wait_hplc: wait til hplc finished or not
    :return: True if all process is finished.
    """
    await pre_run_exp(condition, flow_rate)
    logger.info(f"starting check the system ready..")

    # check system parameter: pressure, temp, gas-flow (total time: fill_loop_time + timeout)
    sys_state = await check_system_ready(condition, flow_rate['gas_flow'], 20.0)  # longer cooling time required
    if not sys_state:
        logger.error("Platform could not reach the target condition...")
        await exp_hardware_initialize()
        raise PlatformError("Platform could not reach the target condition...")

    # filling the loop (~ 1 min)
    with command_session() as sess:
        sess.put(solvent_endpoint + "/pump/infuse",
                 params={"rate": f"1 ml/min", "volume": "0.38 ml"})
        await asyncio.sleep(0.4 * 60)

        # switch the InjValveA to inject the reaction mixture into the system, RUN the experiment
        switching_time = time.monotonic()
        sess.put(r2_endpoint + "/InjectionValve_A/position", params={"position": "inject"})
        logger.info(f"switch the injectionValve A to inject at {switching_time}! Starting reaction....")

        # Wait 1 residence time TODO: might need to shorten the time
        await asyncio.sleep(condition["time"] * 60 - 20)

    # peak_result = await dad_tracing_apex(switching_time, flow_rate, time_schedule)
    peak_result = await dad_tracing_half_height(switching_time, flow_rate, time_schedule)

    if not peak_result:
        logger.error("fail tracing the peak")
        raise PlatformError

    logger.debug(f"succeed tracing the peak")

    # Part II: prepare the hplc sample
    with command_session() as sess:
        # todo: collect reaction mixture
        sess.put(collector_endpoint + "/distribution-valve/position", params={"position": coll_p})
        await asyncio.sleep(time_schedule['start_hplc'] * 60)
        # await asyncio.sleep(time_schedule['start_hplc'] * 60 + 5) # TODO: deley 10 more sec // default 3
        logger.info(f"Finish hplc sampling at {time.monotonic()}!")

        # send the method.....
        await commander.load_method(HPLC_METHOD)
        await commander.set_sample_name(f"{mongo_id}")
        await commander.run()  # delay 2 sec.....
        await asyncio.sleep(2)

        # inject sample by switch the hplc injection valve
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "inject"})
        logger.info(f"Switch the hplc injection valve and start to analysis")

        await asyncio.sleep(1)  # 0.24 sec for 0.001 ml sample / 0.25 ml/min flow rate
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "load"})
        logger.info(f"complete injecting the hplc sample and start the analysis")

        #todo: collect solution 1 min
        await asyncio.sleep(60)
        sess.put(collector_endpoint + "/distribution-valve/position", params={"position": "16"})

        await asyncio.sleep(time_schedule["half_peak"] * 1.2 * 60 + 540)  # todo: only for longer information

    # purge the system (~ 4.5min): increasing the solvent velocity to purge the seperator
    await purge_system(time_schedule["purge_system"])
    logger.info(f"the experiment was completed!")

    # initialized all hardware
    await exp_hardware_initialize()
    logger.info("the hardware initialization were completed.")

    if not wait_hplc:
        logger.info("finish the experiment without waiting hplc finish.")
        return True

    logger.error(f"wait_hplc parapmeter should be set to False. current is {wait_hplc}")
    # wait 35 min.....(after 9 min purging system)
    # analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"
    # filewatcher = FileWatch(folder_path=analysed_samples_folder, file_extension="txt")
    # file_existed = await filewatcher.check_file_existence_timeout(file_name=f"{mongo_id} - DAD 2.1L- Channel 2.txt",
    #                                                               timeout=2500,  # 35 min
    #                                                               check_interval=3)
    # return file_existed

async def one_exp(exp_n, condition, hplc_commander):
    # start logging
    date = datetime.date.today().strftime("%Y%m%d")
    log_path = Path(rf"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\logger\{date}_whhsu-147-{exp_n:03}.log")
    i = logger.add(log_path)
    logger.info("_________________________________________________________")
    logger.info("blue light was used for the final test...")  # todo

    logger.info(f"condition of whhsu-147-{exp_n:03}: {condition}")


    # calculate all parameters from the condition
    inj_loop_flow_rate = {'Solvent': 1, "SMIS": 0, "Quencher": 0, "Activator": 0, "Dye": 0}
    logger.info("prepared 0.1M reaction mixture in syringe 'Solvent'.")

    gas_liquid_flow = calc_gas_liquid_flow_rate(condition)
    logger.info(f"gas_liquid_flow: {gas_liquid_flow}")

    prep_sys_para = calc_stable_system(condition, gas_liquid_flow)
    # {'pre_liquid_flow': 1.1160714285714286, 'pre_gas_flow': 5, 'pre_run_time': 5.0}

    schedule = calc_time(condition, inj_loop_flow_rate, gas_liquid_flow)
    logger.info(f"schedule: {schedule}")

    # calibrate the real operating parameters
    set_gas_liquid_flow = calibrate_flow_rate(gas_liquid_flow)
    logger.info(f"set_flow: {set_gas_liquid_flow}")

    # run experiment!
    await exp_hardware_initialize()
    logger.info(f"start to adjust the system pressure for new experiment.....")
    reach_p = await adj_bpr(condition["pressure"], 15)

    if not reach_p:
        logger.error(f"the pressure could not reach the required conditions.... Something is wrong!!!")
        logger.remove(i)
        raise PlatformError

    logger.info(f"run the experiment!!! total predicting running time: {schedule['total_operation_time']}")

    tasks = [run_experiment(
        f"whhsu-147-{exp_n:03}",
        condition,
        inj_loop_flow_rate,
        set_gas_liquid_flow,
        schedule,
        hplc_commander,
        wait_hplc=False,
        coll_p=str(exp_n)
    ),
        system_log(date, f"whhsu-147-{exp_n:03}", schedule["total_operation_time"]),
        collect_dad_given_time(date, f"whhsu-147-{exp_n:03}", schedule["total_operation_time"]),
        flow_log(date, f"whhsu-147-{exp_n:03}", schedule["total_operation_time"])
    ]

    # Use asyncio.as_completed to gather results as they complete
    for coro in asyncio.as_completed(tasks):
        result = await coro
        logger.info(f"Function completed: {result}")
        break  # Stop the loop after the first function completes

    await asyncio.sleep(600)  # 10 min
    logger.debug(f"start to analysis the experiment, finish the logging")
    # close logger
    logger.remove(i)

def run_griffy():

    config = {"parameters": [
        # {"name": "oxygen_equiv", "type": "continuous", "low": 1.0, "high": 4.0}, # 2.0
        {"name": "time", "type": "continuous", "low": 10, "high": 50},
        # {"name": "pressure", "type": "continuous", "low": 0.0, "high": 6.0},  # 5.0
        {"name": "temperature", "type": "continuous", "low": 0, "high": 70},
    ], "objectives": [
        {"name": "Yield", "goal": "max"},
    ], "general": {"num_cpus": "3"}}
    # Initialize gryffin
    gryffin = Gryffin(config_dict=config)

    observations = []
    # run BS
    for iter_t in range(10):
        logger.info(f"{datetime.datetime.now()}// start {iter_t+1} round")
        # query gryffin for new params
        # query gryffin for new conditions_to_test, 1 exploration 1 exploitation (i.e. lambda 1 and -1)
        conditions_to_test = gryffin.recommend(
            observations=observations, num_batches=1, sampling_strategies=[-1, 1]
        )  # output two dic in a list
        logger.info(f'suggest 2 new_exp_conditions: {conditions_to_test}')

async def collect_rm(coll_vol: float,
                     coll_p: str):
    """
    collect some sample after hplc preparation in case the sampling failing.... :(
    position 1 : beaker
    position 16: waste
    """

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

    logger.info("____ collect rest reaction mixture ____")
    with command_session() as sess:
        sess.put(collector_endpoint + "/distribution-valve/position", params={"position": coll_p})
        withdraw_t, infuse_t, left_vol, i = await deliver_specific_vol(rest_vol,
                                                                       last_full_withdraw=False,
                                                                       withdraw_p="vial",
                                                                       infuse_p="analysis",
                                                                       withdraw_spd=TRANSFER_RATE,
                                                                       infuse_spd=TRANSFER_RATE,
                                                                       transfer_vol=TRANSFER_SYRINGE,
                                                                       execute=True,
                                                                       wait_to_finish_infuse=True)
        # get tube_info
        tube = "TUBE_COLLECTOR_" + coll_p
        TUBE_COLLECTOR_TO_ = float(os.environ.get(tube))
        push_vol = TUBE_6PORTVALVE_TO_FLOWIR + FLOWIR + TUBE_FLOWIR_TO_COLLECTOR + TUBE_COLLECTOR_TO_
        await clean_vial(rinse_speed=2.0, rinse_vol=push_vol * 1.2, infuse_p="analysis", execute=True)

async def main():
    hplc_commander = Async_ClarityRemoteInterface(remote=True, host='192.168.10.11', port=10015, instrument_number=1)

    # conditions = build.space_filling_lhs(
    #     {"time": [20, 50],
    #      "temperature": [0, 70],
    #      "pressure": [2.0, 5.0]},
    #     num_samples=5
    # )

    # conditions = build.box_behnken(
    #     {"time": [20, 30, 50],
    #      "temperature": [0, 52, 70],
    #      "pressure": [2.0, 5.0]},
    # )

    inital_test_condition = [
        {'dye_equiv': 0.001, 'activator_equiv': 0.2, 'quencher_equiv': 2,
         'solvent_equiv': 226.08, 'concentration': 0.1, 'oxygen_equiv': 2.0,
         'time': 30, 'light': 13, 'pressure': 5.0, 'temperature': 70},
        {'dye_equiv': 0.001, 'activator_equiv': 0.2, 'quencher_equiv': 2,
         'solvent_equiv': 226.08, 'concentration': 0.1, 'oxygen_equiv': 2.0,
         'time': 50, 'light': 13, 'pressure': 5.0, 'temperature': 0},
        {'dye_equiv': 0.001, 'activator_equiv': 0.2, 'quencher_equiv': 2,
         'solvent_equiv': 226.08, 'concentration': 0.1, 'oxygen_equiv': 2.0,
         'time': 50, 'light': 13, 'pressure': 5.0, 'temperature': 43},
        {'dye_equiv': 0.001, 'activator_equiv': 0.2, 'quencher_equiv': 2,
         'solvent_equiv': 226.08, 'concentration': 0.1, 'oxygen_equiv': 2.0,
         'time': 30, 'light': 13, 'pressure': 5.0, 'temperature': 43},
        {'dye_equiv': 0.001, 'activator_equiv': 0.2, 'quencher_equiv': 2,
         'solvent_equiv': 226.08, 'concentration': 0.1, 'oxygen_equiv': 2.0,
         'time': 10, 'light': 13, 'pressure': 5.0, 'temperature': 43},
    ]

    exp_n = 6
    condition = {'dye_equiv': 0.001, 'activator_equiv': 0.2, 'quencher_equiv': 2,
                 'solvent_equiv': 226.08, 'concentration': 0.1, 'oxygen_equiv': 2.0,
                 'time': 90, 'light': 50, 'pressure': 5.0, 'temperature': 43}
    await one_exp(exp_n, condition, hplc_commander)

    # for condition in inital_test_condition:
    #     exp_n += 1
    #     await one_exp(exp_n, condition, hplc_commander)

if __name__ == "__main__":
    # asyncio.run(main())
    asyncio.run(exp_hardware_initialize())
