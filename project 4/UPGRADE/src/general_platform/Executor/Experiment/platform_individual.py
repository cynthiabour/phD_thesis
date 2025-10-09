import datetime
import time
import asyncio
import pint
from loguru import logger

from requests import HTTPError
from pathlib import Path

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session

from BV_experiments.src.general_platform.Analysis.anal_file_watcher import FileWatch
# from BV_experiments.src.general_platform.Analysis.anal_hplc_chromatogram import HPLC_METHOD

# from BV_experiments.Example0_BV.calc_oper_para import (calc_inj_loop, calc_concentration, calc_time,
#                                                        calibrate_flow_rate, calibrate_syringe_rate)  # TODO: real exp

from BV_experiments.src.general_platform.Executor.Experiment.dad_parse import collect_dad_given_time
from BV_experiments.src.general_platform.Executor.Experiment.dad_track import dad_tracing_half_height
from BV_experiments.src.general_platform.Executor.Experiment.log_experiment import system_log
from BV_experiments.src.general_platform.Executor.Experiment.log_flow import flow_log
from BV_experiments.src.general_platform.Executor.Experiment.platform_precedure import exp_hardware_initialize, platform_standby

# from BV_experiments.src.general_platform.Coordinator.main_anal import processing_hplc_file
from BV_experiments.src.general_platform.platform_error import PlatformError
from BV_experiments.src.general_platform.Executor.Analytical.platform_remote_hplc_control import (
    Async_ClarityRemoteInterface)



def parse_vapourtec_light_info(condition: dict) -> int | None:
    logger.info(f"____ parse photo-reactor infomation to intensity ____")

    # check the condition have key ["light_wavelength", "light_intensity"]
    if not all(key in condition for key in ["light_wavelength", "light_intensity"]):
        logger.warning(
            f"there is no light information in condition, please check if there are the photo-reactor information")
        if "wavelength" in condition:
            condition["light_wavelength"] = condition["wavelength"]
        if "light" in condition:
            condition["light_intensity"] = condition["light"]

    # power of vapoutec photo reactor
    vapourtec_photo_reactor_map = {"525nm": 13, "440nm": 24, "420nm": 53}  # 420nm is UV150

    try:
        wavelength = condition['light_wavelength']
        # return the input intensity in percentage
        return round(float(condition['light_intensity'] / vapourtec_photo_reactor_map[wavelength]) * 100)
    except KeyError:
        logger.error(f"there is no wavelength parameter in condition, "
                     f"please provide the photo-reactor information")
        return None

def parse_vapourtec_cooling(condition: dict) -> str:
    """
    Parse the condition to the heating/cooling parameter for vapourtec photo-reactor
    false: cooling, true: heating
    """

    if "light_wavelength" in condition:
        temp_100_map = {"525nm": 34, "440nm": 42, "420nm": 53}  # 420nm idk
        heating = "false" if condition['temperature'] < temp_100_map[condition["light_wavelength"]] else "true"
        return heating
    else:
        logger.error(f"there is no wavelength parameter in condition, "
                     f"please provide the photo-reactor information")
        # raise KeyError(f"check the condition: {condition}")
        return "true"

async def adj_bpr(target_press: float,
                  timeout: float = 20,
                  acceptable_error: float = 0.02) -> bool:
    logger.info(f"____ adjust pressure ____")

    # the bpr is measured difference of two se
    set_pressure = target_press - 1.0

    # calculate the acceptable range of the system pressure [0.98 * target_press, 1.02 * target_press]
    limit = [(1 - acceptable_error) * set_pressure, (1 + acceptable_error) * set_pressure]

    start_adjP_time = time.monotonic()
    with command_session() as sess:
        sess.put(pressEPC_endpoint + "/EPC/set-pressure", params={"pressure": f"{set_pressure} bar"})

        sess.put(pressMFC_endpoint + "/MFC/set-flow-rate", params={"flowrate": f"10 ml/min"})

    end_adjP_time = start_adjP_time + timeout * 60
    check = 0

    while time.monotonic() < end_adjP_time:
        # consecutive 20 measurements show the similar results: 1 sec/ data point
        try:
            read_signal = sess.get(pressEPC_endpoint + "/EPC/get-pressure")
            read_signal.raise_for_status()
        except HTTPError:
            # retry after 1 second
            logger.warning("fail to acquire")
            await asyncio.sleep(1.0)
            continue

        p_signal = float(read_signal.text)
        if limit[0] <= p_signal <= limit[1]:
            logger.debug("reach the target pressure!")
            check += 1
            await asyncio.sleep(1.0)
        else:
            print(
                f"Sleeping and waiting for the pressure to be ready... "
                f"Reside waiting time {end_adjP_time - time.monotonic():.0f} s")
            await asyncio.sleep(2.0)

        # after the pressure is stable for 20 sec, adjust the gas flow rate to reduce the amount of gas usage
        if check == 20:
            logger.info(f"reach the stable pressure (consecutive 20 sec) at {time.monotonic()}")

            # flow rate is based on the target pressure (based on the test results)
            if set_pressure >= 4.0:
                sess.put(pressMFC_endpoint + "/MFC/set-flow-rate", params={"flowrate": f"2.0 ml/min"})
            elif set_pressure >= 2.0:
                sess.put(pressMFC_endpoint + "/MFC/set-flow-rate", params={"flowrate": f"1.5 ml/min"})
            else:
                sess.put(pressMFC_endpoint + "/MFC/set-flow-rate", params={"flowrate": f"1.0 ml/min"})
            return True

    logger.error(f"Timeout: the bpr could not reach stable target pressure in {timeout} min...")
    return False


async def fill_loop_by_2_crosses(syr_flow: dict[str, float | pint.Quantity],
                                 time_schedule: dict) -> bool:
    # check all input correct
    # check the time schedule
    if not all(key in time_schedule for key in ["wash_3_mix", "wash_5_mix", "3_mix", "5_mix", "delay_filling", "fill_loop"]):
        raise KeyError(f"the time schedule is not complete: {time_schedule}")

    # check syringe flow rate
    if not all(key in syr_flow for key in ["SYRINGE0", "SYRINGE5", "SYRINGE3", "SYRINGE4", "SYRINGE6"]):
        raise KeyError(f"the syringe key is incorrect: {syr_flow}")

    # check the syringe flow rate is type of pint.Quantity
    if all(isinstance(value, pint.Quantity) for value in syr_flow.values()):
        # change the syringe flow rate to float
        logger.warning(f"the syringe flow rate is pint.Quantity, change to float")
        syr_flow_f = {key: value.to("ml/min").magnitude for key, value in syr_flow.items()}
    else:
        logger.warning(f"the syringe flow rate is float. Assume the unit is ml/min")
        syr_flow_f = syr_flow
    total_infusion_rate = sum([value for value in syr_flow_f.values()])  # ml/min
    logger.info(f"total infusion rate: {total_infusion_rate} ml/min & time of filling: {time_schedule['fill_loop']} min")

    # todo: get the connection information from G
    # FlowSetupDad.G.edges
    # ('Syr0', 'cross_5mix'), ('Syr3', 'cross_3mix'), ('Syr4', 'cross_3mix'), ('Syr5', 'cross_5mix'), ('Syr6', 'cross_3mix')
    logger.info(f"____ loop preparation ____")
    with command_session() as sess:
        # purge the system
        sess.put(syr3_endpoint + "/pump/infuse",
                 params={"rate": f"{total_infusion_rate / 5} ml/min", })  # "volume": f" ml"
        sess.put(syr4_endpoint + "/pump/infuse",
                 params={"rate": f"{total_infusion_rate / 5} ml/min", })  # "volume": f" ml"
        sess.put(syr6_endpoint + "/pump/infuse",
                 params={"rate": f"{total_infusion_rate / 5} ml/min", })  # "volume": f" ml"
        await asyncio.sleep(time_schedule["wash_3_mix"] * 60)

        sess.put(syr0_endpoint + "/pump/infuse",
                 params={"rate": f"{total_infusion_rate / 5} ml/min"})
        sess.put(syr5_endpoint + "/pump/infuse",
                 params={"rate": f"{total_infusion_rate / 5} ml/min"}, )
        await asyncio.sleep(time_schedule["wash_5_mix"] * 60)

        # prepare the reaction mixture
        logger.debug("start to prepare the reaction mixture")
        sess.put(syr3_endpoint + "/pump/infuse", params={"rate": f"{syr_flow_f['SYRINGE3']} ml/min"})
        sess.put(syr4_endpoint + "/pump/infuse", params={"rate": f"{syr_flow_f['SYRINGE4']} ml/min"})
        sess.put(syr6_endpoint + "/pump/infuse", params={"rate": f"{syr_flow_f['SYRINGE6']} ml/min"})
        await asyncio.sleep(time_schedule["3_mix"] * 60)

        logger.debug("reach 2nd cross")

        sess.put(syr0_endpoint + "/pump/infuse", params={"rate": f"{syr_flow_f['SYRINGE0']} ml/min"})
        sess.put(syr5_endpoint + "/pump/infuse", params={"rate": f"{syr_flow_f['SYRINGE5']} ml/min"}, )

        await asyncio.sleep(time_schedule["5_mix"] * 60)

        logger.debug("reach to loop!")
        await asyncio.sleep(time_schedule["delay_filling"] * 60 + 1)  # Fixme 3 more seconds for the delay?? (double) change to 1 sec

        logger.info(f"START loop filling! at {time.monotonic()}")
        start_time = time.monotonic()
        end_time = start_time + time_schedule["fill_loop"] * 60

        # await asyncio.sleep(FILLING_TIME * 1.0 * 60)  # time of filling
        while time.monotonic() < end_time:
            logger.debug(f"{end_time - time.monotonic()} sec left.")
            await asyncio.sleep(1)

        logger.info(f"END loop filling! at {time.monotonic()}")
        # push rxn mixture in the tube into the loop to reduce the usage of
        sess.put(syr3_endpoint + "/pump/stop")
        sess.put(syr4_endpoint + "/pump/stop")
        sess.put(syr6_endpoint + "/pump/stop")
        sess.put(syr5_endpoint + "/pump/stop")
        sess.put(syr0_endpoint + "/pump/stop")
        logger.debug(f"finish filling the loop! stop all pump")

    return True


async def check_system_ready(condition: dict,
                             gas_flow_rate: float,
                             timeout: float = 5,
                             warning_active: bool = False  # todo:
                             ) -> bool:
    logger.info(f"____ checking the system ____")
    logger.info(f"____ check pressure, temperature, O2 flow ____")

    # calculate the acceptable range of the system
    limit_p = [0.99 * (condition["pressure"]-1), 1.01 * (condition["pressure"]-1)]
    limit_gas_flow = [0.98 * gas_flow_rate,
                      1.02 * gas_flow_rate]  # at low flow rate (e.g. 0.1 ml/min), fluctuation is slightly bigger. increase the range from 0.99-1.01 to 0.98-1.02
    limit_t = [condition["temperature"] - 2, condition["temperature"] + 2]

    change = 0
    start_time = time.monotonic()
    end_time = start_time + timeout * 60

    # todo: make warning everytime
    def log_warning(message: str, value, limit: list):
        logger.warning(f"{message}: {value} (acceptable range: {limit[0]} - {limit[1]})")

    with command_session() as sess:
        while time.monotonic() < end_time:
            # check pressure (by EPC & R2)
            p_epc = sess.get(pressEPC_endpoint + "/EPC/get-pressure").json()
            p_r2 = sess.get(
                r2_endpoint + "/PressureSensor/read-pressure?units=mbar").json() / 1000  # currently units is set

            # check oxygen flow rate (MFC)
            O2 = sess.get(O2MFC_endpoint + "/MFC/get-flow-rate").json()

            # # check temp (R2)
            current_t = sess.get(r2_endpoint + "/reactor-3/temperature")
            try:
                t = current_t.json()
            except Exception as e:
                print(f"{e}:{current_t}")
                t = -1000000
                pass

            if limit_p[0] <= p_epc <= limit_p[1] and \
                    limit_gas_flow[0] <= O2 <= limit_gas_flow[1] and \
                    limit_t[0] <= t <= limit_t[1]:
                logger.info(f'the system is ready')
                return True

            # adjust temperature if necessary
            # todo: most of the time, the temperature is the key to pass the checking
            if change < 6:
                if t < limit_t[0]:
                    logger.warning(f"temperature is too low: {t} (lowest acceptable temp. {limit_t[0]}")
                    # fixme: the heating on or off need more smart way to decide
                    # heating = "true"
                    # sess.put(r2_endpoint + "/reactor-3/temperature",
                    #          params={"temperature": f"{condition['temperature']}°C",
                    #                  "heating": heating})
                    # change += 1
                    # logger.info(f"current the heating is {heating}")

                elif t > limit_t[1]:
                    logger.warning(f"temperature is too high: {t} (highest acceptable temp. {limit_t[1]}")
                    heating = "false"
                    sess.put(r2_endpoint + "/reactor-3/temperature",
                             params={"temperature": f"{condition['temperature']}°C",
                                     "heating": heating})
                    change += 1
                    logger.info(f"current the heating is {heating}")

                await asyncio.sleep(1)
                continue

            # # change back to initial setup
            # heating = "false" if condition['temperature'] < 34 else "true"
            # sess.put(r2_endpoint + "/reactor-3/temperature", params={"temperature": f"{condition['temperature']}°C",
            #                                                          "heating": heating})
            if t < limit_t[0]:
                logger.warning(f"temperature is still too low: {t}. (lowest acceptable temp. {limit_t[0]})"
                               f"Physically incapability might be the reason.")
            elif t > limit_t[1]:
                logger.warning(f"temperature is too high: {t} (highest acceptable temp. {limit_t[1]})"
                               f"Physically incapability might be the reason.")

            if p_r2 < limit_p[0] + 1:
                logger.warning(f"pressure of r2 is too low: {p_r2} (lowest acceptable pressure {limit_p[0] + 1}")
            elif p_r2 > limit_p[1] + 1:
                logger.warning(f"pressure of r2 is too high: {p_r2} (highest acceptable pressure {limit_p[1] + 1}")

            if p_epc < limit_p[0]:
                logger.warning(f"pressure of epc is too low: {p_epc} (lowest acceptable pressure {limit_p[0]}")
            elif p_epc > limit_p[1]:
                logger.warning(f"pressure of epc is too high: {p_epc} (highest acceptable pressure {limit_p[1]}")

            if O2 < limit_gas_flow[0]:
                logger.warning(f"oxygen flow rate is too low: {O2} (lowest acceptable flow rate  {limit_gas_flow[0]}")
            elif O2 > limit_gas_flow[1]:
                logger.warning(
                    f"oxygen flow rate is too high: {O2} (highest acceptable flow rate {limit_gas_flow[1]}")

        logger.error(f"Timeout: the system could not reach stable target condition in {timeout} min...")

        if p_epc < limit_p[0]:
            logger.error(f"pressure of epc is too low: {p_epc} (lowest acceptable pressure {limit_p[0]}")
        elif p_epc > limit_p[1]:
            logger.error(f"pressure of epc is too high: {p_epc} (highest acceptable pressure {limit_p[1]}")

        if p_r2 < limit_p[0] + 1:
            logger.warning(f"pressure of r2 is too low: {p_r2} (lowest acceptable pressure {limit_p[0] + 1}")
        elif p_r2 > limit_p[1] + 1:
            logger.warning(f"pressure of r2 is too high: {p_r2} (highest acceptable pressure {limit_p[1] + 1}")

        if O2 < limit_gas_flow[0]:
            logger.error(f"oxygen flow rate is too low: {O2} (lowest acceptable flow rate  {limit_gas_flow[0]}")
        elif O2 > limit_gas_flow[1]:
            logger.error(f"oxygen flow rate is too high: {O2} (highest acceptable flow rate {limit_gas_flow[1]}")

        if t < limit_t[0]:
            logger.error(f"temperature is too low: {t} (lowest acceptable temp. {limit_t[0]}")
            logger.warning(f"Physically incapability might be the reason. Check manually")

        elif t > limit_t[1]:
            logger.error(f"temperature is too high: {t} (highest acceptable temp. {limit_t[1]}")
            logger.warning(f"Physically incapability might be the reason. Check manually")

        return False


async def pre_run_exp(condition: dict,
                      flow_rate: dict,
                      pre_run_time: float) -> None:

    # check input correct
    # check the flow rate contain the key
    if not all(key in flow_rate for key in ["pre_gas_flow", "pre_liquid_flow"]):
        raise KeyError(f"the flow rate key is incorrect: {flow_rate}")
        # todo: cal pre-run condition
        # prep_sys_para = calc_stable_system(condition, flow_rate)
    # check the type of flow rate
    if all(isinstance(value, pint.Quantity) for value in flow_rate.values()):
        # change the flow rate to float
        logger.warning(f"the flow rate is pint.Quantity, change to float")
        flow_rate = {key: value.to("ml/min").magnitude for key, value in flow_rate.items()}
    logger.info(f"____ pre-run ____")
    # Part 0: prepare the system
    with command_session() as sess:

        # switch on the light & control the temperature
        intensity_pct = parse_vapourtec_light_info(condition)
        sess.put(r2_endpoint + "/PhotoReactor/intensity", params={"percent": f"{intensity_pct}"})

        heating= parse_vapourtec_cooling(condition)
        sess.put(r2_endpoint + "/reactor-3/temperature",
                 params={"temperature": f"{condition['temperature']}°C", "heating": heating}) #fixme:???

        logger.info(f"pre-run the system for {pre_run_time} min")
        sess.put(r2_endpoint + "/Power/power-on")
        # pre-run reaction condition.... to fill the reactor with same ratio of gas/liquid volume
        sess.put(O2MFC_endpoint + "/MFC/set-flow-rate",
                 params={"flowrate": f"{flow_rate['pre_gas_flow']} ml/min"})
        sess.put(reaction_endpoint + "/infuse", params={"rate": f"{flow_rate['pre_liquid_flow']} ml/min"})
        await asyncio.sleep(pre_run_time * 60)

        # # fixme: run the real condition
        sess.put(O2MFC_endpoint + "/MFC/set-flow-rate", params={"flowrate": f"{flow_rate['gas_flow']} ml/min"})
        sess.put(reaction_endpoint + "/infuse", params={"rate": f"{flow_rate['liquid_flow']} ml/min"})
        logger.info(f"run one residence time to make the system more stable")
        await asyncio.sleep(condition["time"] * 60)  # fixme: not running pre-run time but the reaction time


async def purge_system(purge_system_time: float = 4.5):
    """purge the system after sampling and collect data"""
    logger.info(f"____ purge system ____")
    with command_session() as sess:
        # turn off the power of the reactor
        sess.put(r2_endpoint + "/PhotoReactor/power-off")  # set to 0%
        sess.put(r2_endpoint + "/reactor-3/temperature", params={"temperature": f"29°C",
                                                                 "heating": "true"})

        # wash the system with solvent
        sess.put(O2MFC_endpoint + "/MFC/set-flow-rate", params={"flowrate": "0.5 ml/min"})
        sess.put(reaction_endpoint + "/infuse", params={"rate": "0.5 ml/min"})

        sess.put(dilute_endpoint + "/infuse", params={"rate": "2.0 ml/min"})

        await asyncio.sleep(purge_system_time * 0.3 * 60)
        sess.put(makeup_endpoint + "/infuse", params={"rate": "0.2 ml/min"})

        # sess.put(r2_endpoint + "/CollectionValve/position", params={"position": "Solvent"})
        await asyncio.sleep(purge_system_time * 0.7 * 60)


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
    :param inj_rate: {'SYRINGE0': 0.007150720164012728, 'SYRINGE5': 0.09559026130810268, 'SYRINGE3': 0.34946388787383326, 'SYRINGE4': 0.04779513065405134, 'SYRINGE6': 0.0}
    :param all_flow_rate: {'total_flow': 0.5772, 'liquid_flow': 0.4927867409080387, 'gas_flow': 0.253239777275884, 'pre_liquid_flow': 2, 'pre_gas_flow': 1.02778648958472, 'dilute_flow_bf_seperator': 0.5072132590919614, 'bf_sep_rate': 1.0, 'makeup_flow_for_hplc': 8.421122666513543, 'flow_to_hplc': 9.421122666513543}
    :param time_schedule: {'adj_press': 15, 'pre_run_time': 2.0, '3_mix': 0.03322769121495339, '5_mix': 0.018000000000000002, 'delay_filling': 0.05, 'fill_loop': 1.0, 'loop_to_sensor': 6.679566536152186, 'half_peak': 0.5073188445357415, 'consumed_all_o2': 7.544394954459828, 'dad_to_analvalve': 0.028, 'start_hplc': 0.024904924565479512, 'purge_system': 10.167999999999997, 'total_operation_time': 21.881165259311743, 'shortest_before_lc': 9.833699151932619}
    :param commander: hplc commander to send cammand to hplc computer
    :param wait_hplc: wait til hplc finished or not
    :return:
    """
    analvalve_mapping = {'HPLC': '2', 'IR': '1', 'COLLECT': '3', 'NMR': '4', 'WASTE': '6'}  # todo: analvalve_mapping

    await pre_run_exp(condition, all_flow_rate, time_schedule["pre_run_time"])
    logger.info(f"starting check the system ready..")

    # check system parameter: pressure, temp, gas-flow (total time: fill_loop_time + timeout)
    sys_state = await check_system_ready(condition, all_flow_rate['gas_flow'], 20.0)
    if not sys_state:
        logger.error("Platform could not reach the target condition...")
        # fixme
        await platform_standby(commander,
                               standby_hplc_method="")
        raise PlatformError("Platform could not reach the target condition...")

    await fill_loop_by_2_crosses(inj_rate, time_schedule)

    # Part I: run the reaction
    with command_session() as sess:

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
        await asyncio.sleep(condition["time"] * 60 - 20)

    peak_result = await dad_tracing_half_height(switching_time, all_flow_rate, time_schedule)

    if not peak_result:
        logger.error("fail tracing the peak")
        # await platform_standby(commander,
        #                        standby_hplc_method=r"")
        # raise PlatformError
    else:
        logger.info(f"succeed tracing the peak")

    # Part II: prepare the hplc sample
    with command_session() as sess:
        # switch the AnalysisValve to the correct analysis position
        sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping['HPLC']})
        await asyncio.sleep(time_schedule['dad_to_analvalve'] * 60)

        sess.put(makeup_endpoint + "/infuse", params={"rate": f"{all_flow_rate['makeup_flow_for_hplc']} ml/min"})

        await asyncio.sleep(time_schedule['start_hplc'] * 60)
        # await asyncio.sleep(time_schedule['start_hplc'] * 60 + 5) # TODO: deley 10 more sec // default 3
        logger.info(f"Finish hplc sampling at {time.monotonic()}!")
        # logger.error(f"collecting the reaction mixture for hplc analysis....")

        # send the method.....
        # fixme
        await commander.load_method(r"")
        await commander.set_sample_name(f"{mongo_id}")
        await commander.run()  # delay 2 sec.....
        await asyncio.sleep(2)

        # inject sample by switch the hplc injection valve
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "inject"})
        logger.info(f"Switch the hplc injection valve and start to analysis")

        await asyncio.sleep(1)  # 0.24 sec for 0.001 ml sample / 0.25 ml/min flow rate
        sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "load"})
        logger.info(f"complete injecting the hplc sample and start the analysis")

        # collect reaction mixture
        sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping['COLLECT']})
        await asyncio.sleep(time_schedule["half_peak"] * 1.2 * 60 + 600)  # todo: only for longer information
        sess.put(analValve_endpoint + "/distribution-valve/position", params={"position": analvalve_mapping['WASTE']})

    # purge the system (~ 4.5min): increasing the solvent velocity to purge the seperator
    await purge_system(time_schedule["purge_system"])
    logger.info(f"the experiment was completed!")

    # initialized all hardware: fixme
    await exp_hardware_initialize()
    logger.info("the hardware initialization were completed.")

    if not wait_hplc:
        logger.info("finish the experiment.")
        return True

    else:
        # wait 35 min.....(after 9 min purging system)
        analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"
        filewatcher = FileWatch(folder_path=analysed_samples_folder, file_extension="txt")
        file_existed = await filewatcher.check_file_existence_timeout(file_name=f"{mongo_id} - DAD 2.1L- Channel 2.txt",
                                                                      timeout=2500,  # 35 min
                                                                      check_interval=3)
        return file_existed

# fixme: more general???
async def overall_run(mongo_id: str,
                      condition: dict,
                      hplc_commander: Async_ClarityRemoteInterface) -> dict | bool:
    """
    all parameters for running experiment and hplc analysis and processing are included in this function.
    """
    date = datetime.date.today().strftime("%Y%m%d")
    log_path = Path(rf"W:\BS-FlowChemistry\People\Wei-Hsin\BV_data\logger\{date}_{mongo_id}.log")
    # log_path = Path(rf"D:\BV\BV_experiments\log\{date}_{mongo_id}.log")
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

    if not reach_p:
        logger.error(f"IncompleteAnalysis: The hplc file isn't found! check manually.....")
        await platform_standby(hplc_commander)
        raise PlatformError

    logger.info(f"Start to run the test experiment!!!")
    txt_file_existed, _, _, _ = await asyncio.gather(
        run_experiment(
            mongo_id,
            condition,
            setting_syringe_rate,
            setting_gas_liquid_flow,
            time_schedule,
            hplc_commander,
            wait_hplc=True
        ),
        system_log(date, mongo_id, time_schedule["total_operation_time"]),
        collect_dad_given_time(date, mongo_id, time_schedule["total_operation_time"]),
        flow_log(date, mongo_id, time_schedule["total_operation_time"])
    )

    if not txt_file_existed:
        logger.error(f"hplc txt file find nowhere.... Something is wrong!!!")
        await platform_standby(hplc_commander)
        logger.info("platform standby. Wait until hardware being checked!")
        raise PlatformError

    return processing_hplc_file(mongo_id, txt_file_existed, condition, cc_is="tmob")


async def main():
    # i = logger.add(f"D:\BV\BV_experiments\log\myapp.log", rotation="10 MB")
    import socket
    if socket.gethostname() == 'BSMC-YMEF002121':
        # # only run to prepare the soln
        # control_condition = {'dye_equiv': 0.01, 'activator_equiv': 0.050, 'quencher_equiv': 2, 'oxygen_equiv': 2.2,
        #                     'solvent_equiv': 500.0, 'time': 10, 'light': 13, 'pressure': 4.0, 'temperature': 34, }
        # control_condition["concentration"] = calc_concentration(control_condition)
        # volume_for_loop, loop_flow_rate = calc_inj_loop(control_condition)
        # # loop filing
        # await loop_by_2_crosses(control_condition)
        pass
        # hplc_commander = Async_ClarityRemoteInterface(remote=True, host='192.168.10.11', port=10015,
        #                                               instrument_number=1)
        # # overall run
        # mongo_id = "dad_halfH_0.01EY_2.2O2_sol20_4.5min_4bar_pumpM_1.0_Xlight_0.38loop_2"
        # exp_condition = {'dye_equiv': 0.01, 'activator_equiv': 0.050, 'quencher_equiv': 20, 'oxygen_equiv': 2.2,
        #                  'solvent_equiv': 20.0, 'time': 4.5, 'light': 0, 'pressure': 4.0, 'temperature': 34, }
        # raw_hplc_results = await overall_run(mongo_id, exp_condition, hplc_commander)
        # logger.info(f"{mongo_id}: {raw_hplc_results}")

        # raw_hplc_results = await overall_run_w_log(mongo_id, exp_condition, hplc_commander)
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
