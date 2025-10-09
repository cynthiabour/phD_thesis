import datetime
import time
import asyncio
from collections import deque
import statistics
from loguru import logger

from pathlib import Path

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session
from BV_experiments.src.general_platform.Analysis.anal_file_watcher import FileWatch
from BV_experiments.Example0_BV.calc_oper_para import (total_infusion_rate,
                                                       calc_inj_loop, calc_concentration, calc_time,
                                                       calc_gas_liquid_flow_rate, calc_stable_system,
                                                       calibrate_flow_rate, calibrate_syringe_rate)
from BV_experiments.src.general_platform.Executor.Experiment.dad_parse import background_collect, collect_dad_given_time
from BV_experiments.src.general_platform.Executor.Experiment.log_experiment import system_log
from BV_experiments.Example0_BV.main_anal import processing_hplc_file
from BV_experiments.src.general_platform.platform_error import PlatformError
from BV_experiments.src.general_platform.Executor.Experiment.platform_precedure import exp_hardware_initialize, platform_standby, startup_hplc
from BV_experiments.src.general_platform.Executor.Analytical.platform_remote_hplc_control import Async_ClarityRemoteInterface
from BV_experiments.src.general_platform.Analysis.anal_hplc_chromatogram import HPLC_METHOD
from BV_experiments.src.general_platform.Executor.Experiment.log_flow import flow_log
from BV_experiments.src.general_platform.Executor.Experiment.platform_individual import adj_bpr, check_system_ready

async def old_run_experiment(
        mongo_id: str,
        condition: dict,
        inj_rate: dict,
        flow_rate: dict,
        time_schedule: dict,
        commander: Async_ClarityRemoteInterface) -> Path | bool:
    """
    run the experiment
    :param mongo_id: experiment name or mongodb_id
    :param condition: condition including concentration
    :param inj_rate:
    :param flow_rate:
    :param time_schedule:
    :param commander: hplc commander to send cammand to hplc computer
    :return: True if all process is finished.
    """
    # cal pre-run condition
    prep_sys_para = calc_stable_system(condition, flow_rate)
    logger.info(f"prepared system: {prep_sys_para}")

    # Part I: run the reaction
    with command_session() as sess:
        sess.put(r2_endpoint + "/Power/power-on")

        # pre-run reaction condition.... to fill the reactor with same ratio of gas/liquid volume
        sess.put(O2MFC_endpoint + "/MFC/set-flow-rate",
                 params={"flowrate": f"{prep_sys_para['pre_gas_flow']} ml/min"})
        sess.put(r2_endpoint + "/Pump_A/infuse",
                 params={"rate": f"{prep_sys_para['pre_liquid_flow']} ml/min"})

        intensity = round(float(condition['light']) * 100 / 13)
        sess.put(r2_endpoint + "/reactor-3/temperature", params={"temperature": f"{condition['temperature']}°C"})
        sess.put(r2_endpoint + "/PhotoReactor/intensity", params={"percent": f"{intensity}"})

        # pre-run and prepare the reaction mixture in the same time...
        # await asyncio.sleep((prep_sys_para['pre_run_time'] -
        #                      time_schedule["fill_loop"] - time_schedule["pushing_mixture"]) * 60)

        # pre-run the system (minimum 2 min)
        await asyncio.sleep(prep_sys_para['pre_run_time'] * 60)
        sess.put(O2MFC_endpoint + "/MFC/set-flow-rate", params={"flowrate": f"{flow_rate['gas_flow']} ml/min"})
        sess.put(r2_endpoint + "/Pump_A/infuse", params={"rate": f"{flow_rate['liquid_flow']} ml/min"})

        # loop preparation
        from BV_experiments.Example0_BV.calc_oper_para import CROSS, TUBE_CROSS_TO_CROSS
        t_0_1 = (CROSS + TUBE_CROSS_TO_CROSS) / 3 / (total_infusion_rate / 5)
        t_0_2 = CROSS / 2 / (total_infusion_rate / 5)

        # purge the system
        sess.put(solvent_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min"})
        sess.put(activator_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min"})
        sess.put(quencher_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min"})
        await asyncio.sleep(t_0_1 * 60)
        sess.put(eosinY_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min"})
        sess.put(SMIS_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate/5} ml/min"}, )
        await asyncio.sleep(t_0_2 * 60)

        # Start to prepare the reaction mixture: FILLING_TIME
        logger.debug("start to prepare the reaction mixture")
        sess.put(solvent_endpoint + "/pump/infuse", params={"rate": f"{inj_rate['Solvent']} ml/min"})
        sess.put(activator_endpoint + "/pump/infuse", params={"rate": f"{inj_rate['Activator']} ml/min"})
        sess.put(quencher_endpoint + "/pump/infuse", params={"rate": f"{inj_rate['Quencher']} ml/min"})
        await asyncio.sleep(time_schedule['3_mix'] * 60)

        logger.info("reach the 2nd cross")
        sess.put(eosinY_endpoint + "/pump/infuse", params={"rate": f"{inj_rate['Dye']} ml/min"})
        sess.put(SMIS_endpoint + "/pump/infuse", params={"rate": f"{inj_rate['SMIS']} ml/min"}, )

        await asyncio.sleep(time_schedule['5_mix'] * 60)
        logger.info("start infusing to loop!")

        await asyncio.sleep(time_schedule['delay_filling'] * 60)

        logger.info("start filling loop")
        await asyncio.sleep(time_schedule["fill_loop"] * 60)  # time of filling

        sess.put(SMIS_endpoint + "/pump/stop")
        sess.put(eosinY_endpoint + "/pump/stop")
        sess.put(activator_endpoint + "/pump/stop")
        sess.put(quencher_endpoint + "/pump/stop")
        sess.put(solvent_endpoint + "/pump/stop")

        # logger.info(f"finish filling the loop! stop all pump")
        logger.info(f"starting check the system ready..")

        # check system parameter: pressure, temp, gas-flow (total time: fill_loop_time + timeout)
        sys_state = await check_system_ready(condition, flow_rate['gas_flow'], 2.0)

        if not sys_state:
            logger.error("Platform could not reach the target condition...")
            await platform_standby(commander)
            raise PlatformError("Platform could not reach the target condition...")

        # switch the InjValveA to inject the reaction mixture into the system, RUN the experiment
        switching_time = time.monotonic()
        sess.put(r2_endpoint + "/InjectionValve_A/position", params={"position": "inject"})
        logger.info(f"switch the injectionValve A to inject at {switching_time}! Starting reaction....")

        # purge the tube for mixing
        from BV_experiments.Example0_BV.calc_oper_para import CROSS, TUBE_CROSS_TO_CROSS, TUBE_MIXER_TO_LOOP

        purge_volume_ml = (TUBE_MIXER_TO_LOOP + CROSS * 2 + TUBE_CROSS_TO_CROSS) * 2
        sess.put(solvent_endpoint + "/pump/infuse", params={
            "rate": f"{total_infusion_rate * 4} ml/min",
            "volume": f"{purge_volume_ml} ml"})
        logger.info(f"purge the mixer and tube with {purge_volume_ml} ml solvent.")

        # Wait 1 residence time TODO: might need to shorten the time
        await asyncio.sleep(condition["time"] * 60 - 20)

        # collect background
        sess.put(pumpM_endpoint + "/pump/infuse", params={"rate": "2.0 ml/min"})
        await asyncio.sleep(20.0)
        # set the wavelength and bandwidth (again)
        # sess.put(dad_endpoint + "/channel1/set-wavelength", params={"wavelength": "480"})
        # sess.put(dad_endpoint + "/channel1/set-bandwidth", params={"bandwidth": "8"})
        # sess.put(dad_endpoint + "/channel2/set-wavelength", params={"wavelength": "700"})
        # sess.put(dad_endpoint + "/channel2/set-bandwidth", params={"bandwidth": "8"})
        # sess.put(dad_endpoint + "/channel1/set-integration-time", params={"int_time": "75"})
        # await asyncio.sleep(2.0)

        # collect the background in 20 sec
        acq_bg, ref_bg = await asyncio.gather(
            background_collect(sess, channel=1, interval=0.8, period=20, timeout=5),
            background_collect(sess, 2, 0.8, 20, 5)  # previously 2 -> 10
        )

        logger.debug(f"480 nm background:{acq_bg}; 700 nm background:{ref_bg}")
        sess.put(pumpM_endpoint + "/pump/infuse", params={"rate": f"{flow_rate['dilute_flow']} ml/min"})
        logger.info("Starting collect DAD data! Waiting for the reaction mixture came out.....")

    # waiting 1.0 times of the calculated time required....
    waiting_time = (time_schedule["loop_to_sensor"]) * 0.9 * 60  # the fast....
    end_waiting_time = switching_time + waiting_time

    # tracking_time = (time_schedule["consumed_all_o2"] + time_schedule["half_peak"]) * 1.0 * 60
    tracking_time = (time_schedule["consumed_all_o2"] * 1.1 + time_schedule["half_peak"] * 2) * 60  #todo, should not need 2 time
    end_tracking_time = switching_time + tracking_time
    detected = 0

    # threshold = dad_threshold(condition["concentration"], flow_rate)
    cal_data_deque = deque([0.0] * 20, maxlen=20)  # 30 sec
    cal_med_deque = deque([0.0] * 20, maxlen=20)  # 30 sec
    cal_diff_deque = deque([0.0] * 10, maxlen=10)  # 15 sec

    while time.monotonic() < end_waiting_time:  # only for record the data...
        acq_signal = sess.get(dad_endpoint + "/channel1/acquire-signal")
        ref_signal = sess.get(dad_endpoint + "/channel2/acquire-signal")
        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        cal_data = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data  # new for 75 ms

        cal_data_deque.append(cal_data)
        cal_med = statistics.median(cal_data_deque)
        cal_med_deque.append(cal_med)  # median of 20 data point

        logger.info(f"calibrated signal: {cal_data} (median: {cal_med})")
        await asyncio.sleep(1.3)

    logger.info(f"have been waited {time_schedule['loop_to_sensor']} min")

    # start pumpB
    sess.put(r2_endpoint + "/Pump_B/infuse", params={"rate": f"{flow_rate['makeup_flow']} ml/min"})
    logger.debug(f"start pumping pumpB")

    while time.monotonic() < end_tracking_time:  # start to track the data...
        acq_signal = sess.get(dad_endpoint + "/channel1/acquire-signal")
        ref_signal = sess.get(dad_endpoint + "/channel2/acquire-signal")
        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        cal_data = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data  # new for 75 ms

        cal_data_deque.append(cal_data)
        cal_med = statistics.median(cal_data_deque)
        cal_med_deque.append(cal_med)  # median of 20 data point

        logger.debug(
            f"signal: {acq_signal.json()}(cal: {acq_data}); "
            f"ref: {ref_signal.json()}(cal: {ref_data}); "
            f"calibrate: {cal_data} (median: {cal_med})")
        logger.info(f"calibrated signal: {cal_data} (median: {cal_med})")

        # TODO: better threshold
        if cal_med > 5:
            detected += 1
            logger.info("color change!")

        if detected == 25:
            logger.info(f"consecutive 25 data points show color at 480 nm/ 700 nm")
            break
        logger.debug(
                     f"Sleeping and waiting for the reaction to arrive for {time.monotonic() - end_waiting_time :.0f} s."
                     f"We need another {end_tracking_time - time.monotonic():.0f} s")
        await asyncio.sleep(1.3)

    # once the signal (cal) was greater than 60 for 20 sec...
    # start to check the peak apex...
    while time.monotonic() < end_tracking_time:
        # renew the deque by real intensity of the signal
        acq_signal = sess.get(dad_endpoint + "/channel1/acquire-signal")
        ref_signal = sess.get(dad_endpoint + "/channel2/acquire-signal")
        acq_data = acq_signal.json() - acq_bg
        ref_data = ref_signal.json() - ref_bg
        cal_data = acq_data - 0.0012 * ref_data ** 2 - 0.9893 * ref_data  # new for 75 ms

        cal_data_deque.append(cal_data)
        cal_med = statistics.median(cal_data_deque)
        cal_med_deque.append(cal_med)  # median of 20 data point

        # get difference btw 4 time of interval (5 sec)
        cal_diff = cal_med - cal_med_deque[-4]  # deque[-2] is last measure point
        cal_diff_deque.append(cal_diff)
        logger.info(f"calibrated signal: {cal_data} (median: {cal_med}, signal_diff: {cal_diff})")

        # check the signal is increase (by cal_diff) for a while (15 sec)
        ramp_list = [True if x > 0.001 else False for x in cal_diff_deque]

        # check consecutive signal is decrease and break
        if all(ramp_list):
            logger.info(f"the signal is still increasing!!")
        else:
            # ramp_list_2 = [True if x < 0.001 else False for x in cal_diff_deque]
            # ramp_list contains False
            if not ramp_list[-1]:
                # final number in the deque is False
                logger.info(f"the signal might reach the apex!")
                # ramp_list[:] = [not elem for elem in ramp_list]
                flip_ramp_list = [not elem for elem in ramp_list]
                if all(flip_ramp_list):
                    logger.info(f"the signal reach the apex")
                    break
            else:
                # not the final number in the deque is False
                logger.info(f"wrong alarm...")

        await asyncio.sleep(1.3)

    # Part II: prepare the hplc sample
    with command_session() as sess:
        logger.info(f"starting to prepare the hplc sample.")

        # await asyncio.sleep(time_schedule['start_hplc'] * 60)
        await asyncio.sleep(time_schedule['start_hplc'] * 60 + 5) # TODO: deley 10 more sec // default 3
        logger.info(f"Finish hplc sampling!")

        # send the method.....
        await commander.load_method(HPLC_METHOD)
        await commander.set_sample_name(f"{mongo_id}")
        await commander.run()  # delay 2 sec.....
        await asyncio.sleep(2)

        # inject sample by switch the hplc injection valve
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "inject"})
        logger.info(f"Switch the hplc injection valve and start to analysis")

        # await asyncio.sleep(5)  # 0.24 sec for 0.001 ml sample / 0.25 ml/min flow rate
        # sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "load"})
        logger.info(f"complete injecting the hplc sample and start the analysis")
        await asyncio.sleep(time_schedule["half_peak"] * 60)  # todo: only for longer information

        # Purge system ~9 min: increasing the solvent velocity to purge the seperator
        sess.put(r2_endpoint + "/PhotoReactor/power-off")  # set to 0%
        sess.put(r2_endpoint + "/reactor-3/temperature", params={"temperature": f"29°C"})

        logger.info(f"Start to purge system....")
        sess.put(O2MFC_endpoint + "/MFC/set-flow-rate", params={"flowrate": "0.5 ml/min"})
        sess.put(r2_endpoint + "/Pump_A/infuse", params={"rate": "0.5 ml/min"})
        sess.put(pumpM_endpoint + "/pump/infuse", params={"rate": "2.0 ml/min"})
        await asyncio.sleep(time_schedule["purge_system"] * 0.3 * 60)
        sess.put(r2_endpoint + "/Pump_B/infuse", params={"rate": "0.2 ml/min"})
        sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Solvent"})
        await asyncio.sleep(time_schedule["purge_system"] * 0.7 * 60)

    logger.info(f"the experiment was completed!")
    # initialized all hardware
    await exp_hardware_initialize()
    logger.info("the hardware initialization were completed.")
    # TODO: return True
    # wait 31 min.....(after 9 min purging system)
    analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"
    filewatcher = FileWatch(folder_path=analysed_samples_folder, file_extension="txt")
    file_existed = await filewatcher.check_file_existence_timeout(file_name=f"{mongo_id} - DAD 2.1L- Channel 2.txt",
                                                                  timeout=1860,  # 31 min
                                                                  check_interval=3)
    return file_existed

async def old_overall_run(mongo_id: str,
                      condition: dict,
                      hplc_commander: Async_ClarityRemoteInterface) -> dict | bool:
    """
    all parameters for running experiment and hplc analysis and processing are included in this function.
    """
    date = datetime.date.today().strftime("%Y%m%d")
    # log_path = Path(rf"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\logger\{date}_{mongo_id}.log")
    # log_path = Path(rf"D:\BV\BV_experiments\log\{date}_{mongo_id}.log")
    # i = logger.add(log_path, rotation="10 MB")
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
            old_run_experiment(
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

        analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"
        if txt_file_existed:
            attempts = 0
            # PermissionError [Errno 13] Permission denied will happened. try 3 time
            # @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(10), reraise=True)
            while attempts < 3:
                try:
                    hplc_results = processing_hplc_file(mongo_id, txt_file_existed, condition, "tmob")
                    return hplc_results
                except PermissionError as e:
                    attempts += 1
                    logger.error(f"{e}")
                    await asyncio.sleep(10)
        else:
            logger.error(f"IncompleteAnalysis: The hplc file isn't found! check manually.....")
            # raise IncompleteAnalysis
            return False

    else:
        logger.error(f"the pressure could not reach the required conditions.... Something is wrong!!!")
        await platform_standby(hplc_commander)
        logger.info("platform standby. Wait until hardware being checked!")
        raise PlatformError


async def old_main():
    i = logger.add(f"/BV_experiments/log/myapp.log", rotation="10 MB")
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':

        # hplc commander
        hplc_commander = Async_ClarityRemoteInterface(remote=True, host='192.168.10.11', port=10015,
                                                      instrument_number=1)
        await startup_hplc(hplc_commander)
        mongo_id = "640506b73fedbeb2be0c13a20_fake_test_0.1ML_7"
        exp_condition = {'dye_equiv': 0.05, 'activator_equiv': 0.50, 'quencher_equiv': 5.0, 'oxygen_equiv': 1.2,
                         'solvent_equiv': 0, 'time': 50, 'light': 8, 'pressure': 6.0, 'temperature': 30,}
        raw_hplc_results = await old_overall_run(mongo_id, exp_condition, hplc_commander)
        logger.info(f"{mongo_id}: {raw_hplc_results}")

        await hplc_commander.load_method(r"D:\Data2q\BV\autostartup_analysis\autostartup_000_BV_c18_shortened.MET")
        logger.info(f"finish all test!")

    elif socket.gethostname() == 'BSPC-8WSHWS2':
        logger.error(f"automatic platform is not on this computer.")
        pass

    logger.remove(i)

if __name__ == "__main__":
    asyncio.run(old_main())
