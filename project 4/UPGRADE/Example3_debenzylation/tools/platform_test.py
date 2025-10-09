from pathlib import Path
from loguru import logger
import datetime
import time
import asyncio

from BV_experiments.src.general_platform import ureg
from BV_experiments.src.general_platform.Analysis.anal_file_watcher import FileWatch

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session

from BV_experiments.src.general_platform.Executor.Calculator.hardware_calibrate import HardwareCalibrator

from BV_experiments.src.general_platform.platform_error import PlatformError
from BV_experiments.src.general_platform.Executor.Analytical.platform_remote_hplc_control import Async_ClarityRemoteInterface

from BV_experiments.src.general_platform.Executor.Experiment.platform_individual import adj_bpr, pre_run_exp, check_system_ready, fill_loop_by_2_crosses, purge_system

from BV_experiments.src.general_platform.Executor.Experiment.platform_precedure import exp_hardware_initialize, platform_standby
from BV_experiments.src.general_platform.Executor.Experiment.dad_track import standard_dad_collect_bg, dad_tracing_half_height
from BV_experiments.src.general_platform.Executor.Experiment.dad_parse import collect_dad_given_time
from BV_experiments.src.general_platform.Executor.Experiment.log_experiment import system_log

from BV_experiments.Example3_debenzylation.db_doc import (FirstDebenzylation, SecondDebenzylation,
                                                          FlowSetCollection, FlowSetupDad)
from BV_experiments.Example3_debenzylation.calculator_operating import CalculatorOperating


async def run_blank(code: int | str,
                    hplc_commander: Async_ClarityRemoteInterface
                    ):
    HPLCConfig = FirstDebenzylation.hplc_config_info
    await hplc_commander.load_method(HPLCConfig.HPLC_METHOD)
    await hplc_commander.set_sample_name(f"blank_{code}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
    await hplc_commander.run()  # delay 2 sec.....
    logger.info(
        f"blank run will finished at {(datetime.datetime.now()+ datetime.timedelta(minutes=HPLCConfig.HPLC_RUNTIME)).strftime('%H:%M:%S')}")
    await asyncio.sleep((HPLCConfig.HPLC_RUNTIME-2) * 60 + 2)
    logger.info(f"blank run finished!")

async def run_exp_w_collector(
        mongo_id: str,
        condition: dict,
        inj_rate: dict,
        all_flow_rate: dict,
        time_schedule: dict,
) -> bool:
    """
    run the collector to collect the reaction mixture
    :return:
    """
    # Part I: preparation of system
    await pre_run_exp(condition, all_flow_rate, time_schedule["pre_run_time"])
    logger.info(f"starting check the system ready..")

    # check system parameter: pressure, temp, gas-flow (total time: fill_loop_time + timeout)
    sys_state = await check_system_ready(condition, all_flow_rate['gas_flow'], 20.0)  # longer cooling time required
    if not sys_state:
        logger.error("Platform could not reach the target condition...")
        await exp_hardware_initialize()
        raise PlatformError("Platform could not reach the target condition...")

    await fill_loop_by_2_crosses(inj_rate, time_schedule)

    with command_session() as sess:
        # switch the InjValveA to inject the reaction mixture into the system, RUN the experiment
        switching_time = time.monotonic()
        sess.put(r2_endpoint + "/InjectionValve_A/position", params={"position": "inject"})
        logger.info(f"switch the injectionValve A to inject at {switching_time}! Starting reaction....")

        # to inform the user the time of the reaction slug will come out
        start_time = datetime.datetime.now()
        fast_time = datetime.timedelta(
            minutes=time_schedule["loop_to_sensor"])
        slow_time = datetime.timedelta(
            minutes=(time_schedule["loop_to_sensor"] + time_schedule["collect_all_time"] + 2))
        logger.info(f"reaction slug come out between {(start_time + fast_time).strftime('%Y-%m-%d %H:%M:%S')} "
                    f"and {(start_time + slow_time).strftime('%Y-%m-%d %H:%M:%S')} (collect 2 more mins).")

        # wait time to change the collectValve
        await asyncio.sleep(time_schedule["loop_to_sensor"] * 60)

        # change the valve to collection mode (Reagent)
        sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Reagent"})

        # wait time to collect the reaction mixture
        await asyncio.sleep(time_schedule["collect_all_time"] * 60 + 120)  # fixme: add 2 min

        # change the valve to waste mode
        sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Solvent"})
        logger.info(f"the experiment was completed!")
        await exp_hardware_initialize()
        logger.info(f"the hardware initialization was completed!")
    return True

async def wait_til_pump_stop(timeout: int = 60) -> bool:
    """check if the ml600 pump is still running"""
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:

        with command_session() as sess:
            pump_status = sess.get(trnasfer_endpoint + "/pump/is-pumping").json()
            if pump_status:
                logger.info("the pump is still running")
            else:
                logger.info("the pump is stopped")
                return True
        await asyncio.sleep(1)
    logger.error(f"the pump is still running after the timeout {timeout} sec")


async def wash_vial(remained_volume: float | None = None):
    """
    wash the vial with solvent
    """

    with command_session() as sess:

        if remained_volume is None:
            # stop the pump
            sess.put(trnasfer_endpoint + "/pump/stop")
            cur_volume = sess.get(trnasfer_endpoint + "/pump/get_position").json()
            remained_volume = ureg(cur_volume).to("ml").magnitude  # ml

            sess.put(trnasfer_endpoint + "/pump/infuse", params={"rate": f"{5.0} ml/min", "volume": f"{remained_volume} ml"})
            await wait_til_pump_stop(timeout=remained_volume / 5.0 * 60 + 2)

        logger.info("start to wash the vial")
        # pump 2.5 ml of solvent to wash the vial
        sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Reagent"})
        sess.put(dilute_endpoint + "/infuse", params={"rate": f"{5.0} ml/min"})
        await asyncio.sleep(30)
        sess.put(dilute_endpoint + "/stop")

        # transfer the solvent to the waste
        sess.put(trnasfer_endpoint + "/valve/position", params={"position": "syr-left"})   # collector
        sess.put(trnasfer_endpoint + "/pump/withdraw", params={"rate": f"{5.0} ml/min", "volume": f"{2.5} ml"})
        await wait_til_pump_stop(timeout=32)
        sess.put(trnasfer_endpoint + "/valve/position", params={"position": "syr-front"})  # waste
        sess.put(trnasfer_endpoint + "/pump/infuse", params={"rate": f"{5.0} ml/min", "volume": f"{2.5} ml"})

        # transfer the solvent to the waste (2nd time)
        sess.put(dilute_endpoint + "/infuse", params={"rate": f"{5.0} ml/min"})
        await asyncio.sleep(30)
        sess.put(dilute_endpoint + "/stop")
        # transfer the solvent to the waste
        await wait_til_pump_stop(timeout=5)
        sess.put(trnasfer_endpoint + "/valve/position", params={"position": "syr-left"})   # collector
        sess.put(trnasfer_endpoint + "/pump/withdraw", params={"rate": f"{5.0} ml/min", "volume": f"{2.5} ml"})
        await wait_til_pump_stop(timeout=32)
        sess.put(trnasfer_endpoint + "/valve/position", params={"position": "syr-front"})  # waste
        sess.put(trnasfer_endpoint + "/pump/infuse", params={"rate": f"{5.0} ml/min", "volume": f"{2.5} ml"})

        # transfer the solvent to the waste (3rd time)
        sess.put(dilute_endpoint + "/infuse", params={"rate": f"{5.0} ml/min"})
        await asyncio.sleep(30)
        sess.put(dilute_endpoint + "/stop")
        # transfer the solvent to the waste
        await wait_til_pump_stop(timeout=5)
        sess.put(trnasfer_endpoint + "/valve/position", params={"position": "syr-left"})  # collector
        sess.put(trnasfer_endpoint + "/pump/withdraw", params={"rate": f"{5.0} ml/min", "volume": f"{2.5} ml"})
        await wait_til_pump_stop(timeout=32)
        sess.put(trnasfer_endpoint + "/valve/position", params={"position": "syr-right"})  # analysis
        sess.put(trnasfer_endpoint + "/pump/infuse", params={"rate": f"{5.0} ml/min", "volume": f"{2.5} ml"})
        await wait_til_pump_stop(timeout=32)

        return True


async def analyze_experiment(
        mongo_id: str,
        anal_flow: dict,
        anal_schedule: dict,
        hplc_commander: Async_ClarityRemoteInterface,
) -> bool:

    """
    run the hplc analysis
    :param mongo_id: experiment name or mongodb_id
    :param condition: condition including concentration
    :param hplc_commander: hplc commander to send cammand to hplc computer
    :return: True if all process is finished.
    """

    logger.info("____ start analysis process ____")
    transfer_mapping = {"collector": "syr-left", "waste": "syr-front", "analysis": "syr-right"}

    # Part II: prepare the hplc sample
    with command_session() as sess:
        # switch transfer valve to the correct collect
        sess.put(trnasfer_endpoint + "/valve/position", params={"position": transfer_mapping['collector']})
        sess.put(trnasfer_endpoint + "/pump/withdraw", params={"rate": f"{anal_schedule['withdraw_all']['xfer_flow']} ml/min",
                                                               "volume": f"{anal_schedule['withdraw_all']['vol']} ml"})

        # wait time to collect the reaction mixture
        await asyncio.sleep(anal_schedule["withdraw_all"]["time"] * 60)
        await wait_til_pump_stop(5)

        # switch the transfer valve to the waste
        sess.put(trnasfer_endpoint + "/valve/position", params={"position": transfer_mapping['waste']})
        # transfer the reaction mixture to the waste
        sess.put(trnasfer_endpoint + "/pump/infuse", params={"rate": f"{anal_schedule['to_waste']['xfer_flow']} ml/min",
                                                             "volume": f"{anal_schedule['to_waste']['vol']} ml"})
        await asyncio.sleep(anal_schedule["to_waste"]["time"] * 60)
        await wait_til_pump_stop(5)

        # switch the transfer valve to the analysis
        sess.put(trnasfer_endpoint + "/valve/position", params={"position": transfer_mapping['analysis']})
        # transfer the reaction mixture to the analysis
        sess.put(trnasfer_endpoint + "/pump/infuse",
                 params={"rate": f"{anal_schedule['to_hplc']['xfer_flow']} ml/min",
                         })

        await asyncio.sleep(anal_schedule["to_dilute"]["time"] * 60)

        # set the makeup flow for prepare the hplc sample
        sess.put(makeup_endpoint + "/infuse", params={"rate": f"{anal_flow['makeup_flow']} ml/min"})
        logger.info("give 3 sec delay for hplc sampling after the makeup flow is set.")
        await asyncio.sleep(3)
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "load"})
        logger.info(f"Finish hplc sampling at {time.monotonic()}!")

        HPLCConfig = FirstDebenzylation.hplc_config_info
        await hplc_commander.load_method(HPLCConfig.HPLC_METHOD)
        await hplc_commander.set_sample_name(f"{mongo_id}")
        await hplc_commander.run()  # delay 2 sec.....
        await asyncio.sleep(2)
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "inject"})
        sess.put(makeup_endpoint + "/stop")

    logger.info(
        f"the experiment was completed! The sample will be analyzed at {HPLCConfig.HPLC_RUNTIME} min.")
    return True


async def run_experiment(
        mongo_id: str,
        condition: dict,
        inj_rate: dict,
        all_flow_rate: dict,
        time_schedule: dict,
        commander: Async_ClarityRemoteInterface,
        wait_hplc: bool,
) -> Path | bool:
    """
    run the experiment
    :param mongo_id: experiment name or mongodb_id
    :param condition: condition including concentration
    :param inj_rate: injection rate for the loop. unit: ml/min
    :param flow_rate: flow rate for the system. unit: ml/min
    :param time_schedule: time schedule for the experiment. unit: min
    :param commander: hplc commander to send cammand to hplc computer
    :param wait_hplc: wait til hplc finished or not
    :return: True if all process is finished.
    """
    analvalve_mapping = {'HPLC': '2', 'IR': '1', 'COLLECT': '3', 'NMR': '4', 'WASTE': '6'}  # todo: analvalve_mapping

    # Part I: preparation of system
    acq_bg, ref_bg = await standard_dad_collect_bg()

    # pre-run the system # fixme the reaction time was used
    await pre_run_exp(condition, all_flow_rate, time_schedule["pre_run_time"])
    logger.info(f"starting check the system ready..")

    # check system parameter: pressure, temp, gas-flow (total time: fill_loop_time + timeout)
    sys_state = await check_system_ready(condition, all_flow_rate['gas_flow'], 20.0)  # longer cooling time required
    if not sys_state:
        logger.error("Platform could not reach the target condition...")
        await platform_standby(commander,
                               standby_hplc_method=r"D:\Data2q\BV\autostartup_analysis\autostartup_000_50ACN.MET")
        raise PlatformError("Platform could not reach the target condition...")

    # if use pre-mixed syringe, de it
    await fill_loop_by_2_crosses(inj_rate, time_schedule)

    with command_session() as sess:
        # change to analytic method port
        sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping['HPLC']})

        # switch the InjValveA to inject the reaction mixture into the system, RUN the experiment
        switching_time = time.monotonic()
        sess.put(r2_endpoint + "/InjectionValve_A/position", params={"position": "inject"})
        logger.info(f"switch the injectionValve A to inject at {switching_time}! Starting reaction....")

        # to inform the user the time of the reaction slug will come out
        start_time = datetime.datetime.now()
        fast_time = datetime.timedelta(
            minutes=time_schedule["loop_to_sensor"] * 0.9 - 1)
        slow_time = datetime.timedelta(
            minutes=(time_schedule["consumed_all_o2"] + time_schedule["half_peak"]) * 1.0 + 2)
        logger.info(f"reaction slug come out between {(start_time + fast_time).strftime('%Y-%m-%d %H:%M:%S')} "
                    f"and {(start_time + slow_time).strftime('%Y-%m-%d %H:%M:%S')}.")
        await commander.send_message(f"Please be aware new hplc experiment might be sent "
                                     f"btw {(start_time + fast_time).strftime('%Y-%m-%d %H:%M:%S')} "
                                     f"and {(start_time + slow_time).strftime('%Y-%m-%d %H:%M:%S')}.")
        # Wait 1 residence time TODO: might need to shorten the time
        logger.warning(f"wait for the reaction mixture to come out {condition['time'] - 2} min. "
                       f"(in theory, {time_schedule['loop_to_sensor'] - 2} min.)")
        if condition["time"] > 2:
            await asyncio.sleep(condition["time"] * 60 - 120)  # 2 min for background collection

    # todo: check all three channels (1,3,4) for the peak
    peak_result = await dad_tracing_half_height(switching_time,
                                                all_flow_rate,
                                                time_schedule,
                                                loop_volume=FlowSetupDad.physical_info_setup_list["LOOP"][0],
                                                acq_bg=acq_bg, ref_bg=ref_bg,
                                                acq_channel=1, ref_channel=2)

    if not peak_result:
        logger.error("fail tracing the peak")
        # await platform_standby(commander,
        #                        standby_hplc_method=r"D:\Data2q\BV\autostartup_analysis\autostartup_000_50ACN.MET")
        # raise PlatformError
    else:
        logger.info(f"succeed tracing the peak")

    # Part II: prepare the hplc sample
    with command_session() as sess:
        # switch the AnalysisValve to the correct analysis position
        sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping['HPLC']})
        await asyncio.sleep(time_schedule['dad_to_analvalve'] * 60)

        # set the makeup flow for prepare the hplc sample
        sess.put(makeup_endpoint + "/infuse", params={"rate": f"{all_flow_rate['makeup_flow_for_hplc']} ml/min"})
        logger.info("give 3 sec delay for hplc sampling after the makeup flow is set.")
        await asyncio.sleep(time_schedule['start_hplc'] * 60 + 3)
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "load"})
        logger.info(f"Finish hplc sampling at {time.monotonic()}!")  # 0.24 sec for 0.001 ml sample / 0.25 ml/min flow rate

        # send the method.....
        await commander.load_method(FirstDebenzylation.hplc_config_info.HPLC_METHOD)
        await commander.set_sample_name(f"{mongo_id}")
        await commander.run()  # delay 2 sec.....
        await asyncio.sleep(2)

        # inject sample by switch the hplc injection valve
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "inject"})
        logger.info(f"Switch the hplc injection valve and start to analysis at {time.monotonic()}!")

        # collect reaction mixture
        sess.put(makeup_endpoint + "/stop")
        sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping['COLLECT']})
        await asyncio.sleep(time_schedule["half_peak"] * 1.2 * 60 + 600)  # todo: only for longer information
        sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping['WASTE']})

    # purge the system (~ 4.5min): increasing the solvent velocity to purge the seperator
    await purge_system(time_schedule["purge_system"])
    logger.info(f"the experiment was completed!")

    # initialized all hardware
    await exp_hardware_initialize(FirstDebenzylation.dad_info)
    logger.info("the hardware initialization were completed.")

    if not wait_hplc:
        logger.info("finish the experiment.")
        return True

    else:
        # wait 3 min.....(after 9 min purging system)
        analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"
        filewatcher = FileWatch(folder_path=analysed_samples_folder, file_extension="txt")
        file_existed = await filewatcher.check_file_existence_timeout(file_name=f"{mongo_id} - DAD 2.1L- Channel 1.txt",
                                                                      timeout=2500,  # 35 min
                                                                      check_interval=3)
        return file_existed


async def overall_run_collect(mongo_id: str,
                              condition: dict,
                              hplc_commander: Async_ClarityRemoteInterface | None = None,
                              ) -> dict | bool:
    """
    all parameters for running experiment and hplc analysis and processing are included in this function.
    """
    date = datetime.date.today().strftime("%Y%m%d")
    log_path = Path(rf"W:\BS-FlowChemistry\People\Wei-Hsin\GL_data\3_logger\{date}_{mongo_id}.log")
    i = logger.add(log_path, rotation="10 MB")
    logger.warning(f"start to run the test experiment: {mongo_id}")
    logger.info("_________________________________________________________")
    logger.info(f"condition: {condition}")
    logger.info(f"0. the experiment was conducted with air.")
    logger.warning(f"2. bypass the analysisValve and with pumpM pumping")

    await exp_hardware_initialize()

    # calc concentration
    Calctor = CalculatorOperating(setup_vol_dict=FlowSetCollection.physical_info_setup_list,
                                  sm_info=SecondDebenzylation.SM_info,
                                  is_info=SecondDebenzylation.IS_info,
                                  component_1=SecondDebenzylation.oxidant_info_1,
                                  component_2=SecondDebenzylation.catalyst_info,
                                  component_3=SecondDebenzylation.solvent_info_1,
                                  component_4=SecondDebenzylation.solvent_info_2
                                  )
    condition["concentration"] = Calctor.calc_concentration(condition)
    logger.debug(f"theoretically concentration: {condition['concentration']}")

    # calculate the operating parameters
    volume_for_loop, inj_loop_flow_rate = Calctor.calc_inj_loop(condition, unit_include=False)
    gl_flows = Calctor.calc_air_liquid_flow_rate(condition)
    prep_sys_para = Calctor.calc_stable_system(condition, gl_flows)
    gl_flows["pre_liquid_flow"] = prep_sys_para["pre_liquid_flow"]
    gl_flows["pre_gas_flow"] = prep_sys_para["pre_gas_flow"]

    time_schedule = Calctor.collector_schedule(condition, gl_flows)
    logger.info(f"time:{time_schedule}")

    # calibrate the real operating parameters
    # Calibrator = HardwareCalibrator(Flow_setup.G, Flow_setup.physical_info_setup)
    # fixme: the flow rate input should be more general
    # setting_gas_liquid_flow = Calibrator.calibrate_flow_rate(all_flows)
    # Calibrator.check_param_doable(inj_loop_flow_rate, all_flows)

    # Experiment section
    logger.info(f"start to adjust the system pressure for new experiment.....")
    reach_p = await adj_bpr(condition["pressure"], time_schedule["adj_press"])

    if not reach_p:
        logger.error(f"IncompleteAnalysis: The hplc file isn't found! check manually.....")
        await exp_hardware_initialize()
        raise PlatformError

    bg_log = asyncio.create_task(
        system_log(
            date,
            mongo_id,
            time_schedule["total_operation_time"],
            folder_path=r"W:\BS-FlowChemistry\People\Wei-Hsin\GL_data\system_log\\")
    )

    logger.info(f"Start to run the test experiment!!!")
    await run_exp_w_collector(mongo_id, condition, inj_loop_flow_rate, gl_flows, time_schedule,)

    # calculate the hplc analysis flow rate
    hplc_dilute_flow = Calctor.calc_hplc_dilute_flow(condition=condition,
                                                     flow_rate=gl_flows,
                                                     schedule=time_schedule,
                                                     hplc_ana_conc=SecondDebenzylation.hplc_config_info.HPLC_SAMPLE_CONC
                                                     )
    logger.info(f"hplc dilute flow: {hplc_dilute_flow}")
    # calculate the hplc schedule for analysis # fixme: add 2 min collection time
    hplc_schedule = Calctor.calc_hplc_schedule(
        collector_vol=(time_schedule["collect_all_time"] + 2) * gl_flows["liquid_flow"],
        anal_flow=hplc_dilute_flow)
    logger.info(f"hplc schedule: {hplc_schedule}")

    if not bg_log.done():
        logger.debug("Experiment section finished. The system log is still running")
        # bg_log.cancel()
        # logger.info("the system log was cancelled.")

    if hplc_commander is None:
        logger.info("the hplc commander is None. skip the hplc analysis.")
        return True

    await analyze_experiment(mongo_id, hplc_dilute_flow, hplc_schedule, hplc_commander)

    # initialize the system
    await exp_hardware_initialize()
    logger.info("the hardware initialization was completed!")

    return True

async def overall_run(mongo_id: str,
                      condition: dict,
                      hplc_commander: Async_ClarityRemoteInterface) -> dict | bool:
    """
    all parameters for running experiment and hplc analysis and processing are included in this function.
    """
    date = datetime.date.today().strftime("%Y%m%d")
    log_path = Path(rf"W:\BS-FlowChemistry\People\Wei-Hsin\GL_data\3_logger\{date}_{mongo_id}.log")
    i = logger.add(log_path, rotation="10 MB")
    logger.warning(f"start to run the test experiment: {mongo_id}")
    logger.info("_________________________________________________________")
    logger.info(f"condition: {condition}")
    logger.info(f"0. the experiment was conducted with pure oxygen.")
    logger.warning(f"2. bypass the analysisValve and with pumpM pumping")

    await exp_hardware_initialize(SecondDebenzylation.dad_info)  # initialize the devices to ready

    # calc concentration
    Calctor = CalculatorOperating(setup_vol_dict=FlowSetupDad.physical_info_setup_list,
                                  sm_info=SecondDebenzylation.SM_info,
                                  is_info=SecondDebenzylation.IS_info,
                                  component_1=SecondDebenzylation.oxidant_info_1,
                                  component_2=SecondDebenzylation.catalyst_info,
                                  component_3=SecondDebenzylation.solvent_info_1,
                                  component_4=SecondDebenzylation.solvent_info_2
                                  )
    condition["concentration"] = Calctor.calc_concentration(condition)
    logger.debug(f"theoretically concentration: {condition['concentration']}")

    # calculate the operating parameters
    volume_for_loop, inj_loop_flow_rate = Calctor.calc_inj_loop(condition, unit_include=False)
    # if use eq11, gas not be defined as "air" or "O2"
    all_flows = Calctor.calc_all_flow_rate(condition,
                                           hplc_ana_conc=SecondDebenzylation.hplc_config_info.HPLC_SAMPLE_CONC,
                                           gas="")
    time_schedule = Calctor.calc_exp_schedule(condition, all_flows)
    logger.info(f"time:{time_schedule}")

    # calibrate the real operating parameters
    # Calibrator = HardwareCalibrator(FlowSetupDad.G, FlowSetupDad.physical_info_setup_list)
    # setting_gas_liquid_flow = Calibrator.calibrate_flow_rate(all_flows)
    # Calibrator.check_param_doable(inj_loop_flow_rate, all_flows)

    logger.info(f"start to adjust the system pressure for new experiment.....")
    reach_p = await adj_bpr(condition["pressure"], time_schedule["adj_press"])

    if not reach_p:
        logger.error(f"IncompleteAnalysis: The hplc file isn't found! check manually.....")
        await platform_standby(hplc_commander,
                               standby_hplc_method=r"D:\Data2q\BV\autostartup_analysis\autostartup_000_50ACN.MET")
        raise PlatformError

    logger.info(f"Start to run the test experiment!!!")

    txt_file_existed, _, _ = await asyncio.gather(
        run_experiment(
            mongo_id,
            condition,
            inj_loop_flow_rate,
            all_flows,
            time_schedule,
            hplc_commander,
            wait_hplc=True
        ),
        system_log(
            date,
            mongo_id,
            time_schedule["total_operation_time"],
            folder_path=r"W:\BS-FlowChemistry\People\Wei-Hsin\GL_data\system_log\\"),
        collect_dad_given_time(
            date,
            mongo_id,
            time_schedule["total_operation_time"],
            dad_info=FirstDebenzylation.dad_info,
        ),
    )

    if not txt_file_existed:
        logger.error(f"hplc txt file find nowhere.... Something is wrong!!!")
        await platform_standby(hplc_commander,
                               standby_hplc_method=r"D:\Data2q\BV\autostartup_analysis\autostartup_000_50ACN.MET")
        logger.info("platform standby. Wait until hardware being checked!")
        raise PlatformError

    return True

# def processing_hplc_file(mongo_id: str,
#                          file_existed: Path,
#                          condition: dict,
#                          analysed_samples_folder: str = r"W:\BS-FlowChemistry\data\exported_chromatograms"
#                          ) -> dict:
#     # parse the txt file at 215 nm
#
#     raw_result_215 = hplc_txt_to_peaks(mongo_id, file_existed, "215", cc_is)
#     logger.debug(f"raw result at 215 nm: {raw_result_215}")
#
#     parse_result_215 = parse_raw_exp_result(condition, raw_result_215, "215", cc_is) if raw_result_215 else False
#     logger.debug(f"parsed result at 215 nm: {parse_result_215}")
#
#     # parse the txt file at 254 nm
#     raw_result_254 = hplc_txt_to_peaks(mongo_id,
#                                        Path(analysed_samples_folder) / Path(f"{mongo_id} - DAD 2.1L- Channel 1.txt"),
#                                        "254", cc_is)
#     logger.debug(f"result at 254 nm: {raw_result_254}")
#
#     parse_result_254 = parse_raw_exp_result(condition, raw_result_254, "254", cc_is) if raw_result_254 else False
#     logger.debug(f"parsed result at 254 nm: {parse_result_254}")
#
#     assigned_info = {"PEAK_RT": PEAK_RT, "PEAK_RT_2": PEAK_RT_2, "ACCEPTED_SHIFT": ACCEPTED_SHIFT}
#     hplc_method_info = {"eluent": HPLC_ELUENT, "gradient": HPLC_GRADIENT, "flow_rate": HPLC_FLOW_RATE}
#
#     return {"result_254": raw_result_254, "result_215": raw_result_215,
#             "parsed_result_254": parse_result_254, "parsed_result_215": parse_result_215,
#             "hplc_method": HPLC_METHOD,
#             "method_info": hplc_method_info,
#             "assigned_PEAKs": assigned_info,
#             }

async def main():
    i = logger.add(rf"D:\BV\BV_experiments\log\suger_test.log")
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':

        hplc_commander = Async_ClarityRemoteInterface(remote=True, host='192.168.10.11', port=10015,
                                                      instrument_number=1)
        # # first run to initialize the hplc flow rate
        # await hplc_commander.slow_flowrate_ramp(r"D:\Data2q\BV\autostartup_analysis",
        #                                         method_list=("autostartup_005_50ACN.MET",
        #                                                      "autostartup_010_50ACN.MET",
        #                                                      "autostartup_015_50ACN.MET",
        #                                                      "autostartup_020_50ACN.MET",
        #                                                      "autostartup_025_50ACN.MET",
        #                                                      )
        #                                         )
        # logger.info(f"run blank test!")
        # await run_blank("1st_blank", hplc_commander)

        await exp_hardware_initialize(SecondDebenzylation.dad_info)  # initialize the devices to ready
        mongo_id = "yxy00B1_ctrl_156"
        ctrl_condition =  {'tbn_equiv': 100, 'acn_equiv': 0, 'ddq_equiv': 0.5, 'dcm_equiv': 806,
                            # 'oxygen_equiv': 5,
                            'temperature': 28, 'time': 5, 'light_wavelength': '440nm',
                            'light_intensity': 100, 'pressure': 3}

        # raw_hplc_results = await overall_run_collect(mongo_id, ctrl_condition, hplc_commander)
        raw_hplc_results = await overall_run(mongo_id, ctrl_condition, hplc_commander)
        logger.info(f"{mongo_id}: {raw_hplc_results}")

        last_run = False
        if last_run:
            logger.info(f"finish all test!")
            # await platform_standby(hplc_commander,
            #                        standby_hplc_method=r"D:\Data2q\BV\autostartup_analysis\autostartup_000_50ACN.MET")
            # logger.info(f"platform is standby now.")

            STOP_METHOD = r"D:\Data2q\BV\autostartup_analysis\autostartup_000_50ACN.MET"
            await hplc_commander.load_method(STOP_METHOD)
            logger.info(f"stop hplc. Please manually turn off the hplc system!")

    elif socket.gethostname() == 'BSPC-8WSHWS2':
        logger.error(f"automatic platform is not on this computer.")
        pass

    logger.remove(i)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

