"""
the class for the debenzylation experiment executor
"""
from pathlib import Path
from loguru import logger
import datetime
import time
import asyncio
from beanie import PydanticObjectId

from BV_experiments.src.general_platform.Analysis.anal_file_watcher import FileWatch

from BV_experiments.src.general_platform.platform_error import PlatformError

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session
from BV_experiments.src.general_platform.Executor import *

from BV_experiments.Example3_debenzylation.calculator_operating import DeBnCalculator


class DebenzylExecutor:
    """
    Debenzylation experiment executor
    """
    def __init__(self,
                 setup: object,
                 base_exp_info: object,
                 hplc_commander: Async_ClarityRemoteInterface):

        self.setup = setup
        self.base_exp_info = base_exp_info
        self.hplc_commander = hplc_commander
        self.hplc_config = self.base_exp_info.hplc_config_info

    async def run_blank(self, code: int | str):
        """
        run the blank experiment for the debenzylation experiment
        """
        await self.hplc_commander.load_method(self.hplc_config.HPLC_METHOD)
        await self.hplc_commander.set_sample_name(f"blank_{code}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
        await self.hplc_commander.run()  # delay 2 sec.....
        logger.info(
            f"blank run will finished at {(datetime.datetime.now() + datetime.timedelta(minutes=self.hplc_config.HPLC_RUNTIME)).strftime('%H:%M:%S')}")
        await asyncio.sleep((self.hplc_config.HPLC_RUNTIME - 2) * 60)
        logger.info(f"blank run finished in two minute!")

    def calc_all_parameters(self, condition: dict):
        """
        calculate all the parameters for the experiment
        Specfic for debenzylation experiment
        """
        Calctor = DeBnCalculator(setup_vol_dict=self.setup.physical_info_setup_list,
                                 gas=self.base_exp_info.gas_info.nickname,
                                 sm_info=self.base_exp_info.SM_info,
                                 is_info=self.base_exp_info.IS_info,
                                 component_1=self.base_exp_info.oxidant_info_1,
                                 component_2=self.base_exp_info.catalyst_info,
                                 component_3=self.base_exp_info.solvent_info_1,
                                 component_4=self.base_exp_info.solvent_info_2
                                 )
        condition["concentration"] = Calctor.calc_concentration(condition=condition, unit_include=False)
        # calculate the setting parameters
        logger.debug(f"theoretically concentration: {condition['concentration']}")

        # calculate the operating parameters
        volume_for_loop, inj_loop_flow_rate = Calctor.calc_inj_loop(condition, unit_include=False)

        # fixme gas input should be
        all_flows = Calctor.calc_all_flow_rate(condition,
                                               hplc_ana_conc=self.base_exp_info.hplc_config_info.HPLC_SAMPLE_CONC,
                                               )

        time_schedule = Calctor.calc_exp_schedule(condition, all_flows)
        logger.info(f"time:{time_schedule}")

        # make digraph to graph # fixme

        # calibrate the real operating parameters
        doable, setting_flows = self.cali_all_parameters(inj_loop_flow_rate, all_flows)

        return condition, volume_for_loop, inj_loop_flow_rate, all_flows, time_schedule, doable, setting_flows

    def cali_all_parameters(self, inj_loop_flow_rate, all_flows):
        # calibrate the real operating parameters
        Calibrator = HardwareCalibrator(self.setup.G,
                                        self.setup.physical_info_setup_list)

        setting_flows = Calibrator.calibrate_flow_rate(all_flows)
        # check the platform setting is doable or not
        doable = Calibrator.check_param_doable(inj_loop_flow_rate, all_flows)
        if not doable:
            raise ValueError("the platform is not able to run the experiment")
        return doable, setting_flows

    async def _run_experiment(
            self,
            mongo_id: str| PydanticObjectId,
            condition: dict,
            inj_rate: dict,
            all_flow_rate: dict,
            time_schedule: dict,
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
        analvalve_mapping = {'HPLC': '2', 'IR': '1', 'COLLECT': '3', 'NMR': '4',
                             'WASTE': '6'}  # todo: analvalve_mapping

        # Part I: preparation of system
        acq_bg, ref_bg = await standard_dad_collect_bg()
        await pre_run_exp(condition, all_flow_rate, time_schedule["pre_run_time"])
        logger.info(f"starting check the system ready..")

        # check system parameter: pressure, temp, gas-flow (total time: fill_loop_time + timeout)
        sys_state = await check_system_ready(condition, all_flow_rate['gas_flow'], 20.0)  # longer cooling time required
        if not sys_state:
            logger.error("Platform could not reach the target condition...")
            await platform_standby(self.hplc_commander,
                                   standby_hplc_method=r"D:\Data2q\BV\autostartup_analysis\autostartup_000_50ACN.MET")
            raise PlatformError("Platform could not reach the target condition...")

        await fill_loop_by_2_crosses(inj_rate, time_schedule)

        with command_session() as sess:
            # change to analytic method port
            sess.put(analValve_endpoint + "/distribution-valve/position",
                     params={"position": analvalve_mapping['HPLC']})

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
            await self.hplc_commander.send_message(f"Please be aware new hplc experiment might be sent "
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
                                                    loop_volume=self.setup.physical_info_setup_list["LOOP"][0],
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
            sess.put(analValve_endpoint + "/distribution-valve/position",
                     params={"position": analvalve_mapping['HPLC']})
            await asyncio.sleep(time_schedule['dad_to_analvalve'] * 60)

            # set the makeup flow for prepare the hplc sample
            sess.put(makeup_endpoint + "/infuse", params={"rate": f"{all_flow_rate['makeup_flow_for_hplc']} ml/min"})
            logger.info("give 3 sec delay for hplc sampling after the makeup flow is set.")
            await asyncio.sleep(time_schedule['start_hplc'] * 60 + 3)
            sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "load"})
            logger.info(
                f"Finish hplc sampling at {time.monotonic()}!")  # 0.24 sec for 0.001 ml sample / 0.25 ml/min flow rate

            # send the method.....
            await self.hplc_commander.load_method(self.base_exp_info.hplc_config_info.HPLC_METHOD)
            await self.hplc_commander.set_sample_name(f"{mongo_id}")
            await self.hplc_commander.run()  # delay 2 sec.....
            await asyncio.sleep(2)

            # inject sample by switch the hplc injection valve
            sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "inject"})
            logger.info(f"Switch the hplc injection valve and start to analysis at {time.monotonic()}!")

            # collect reaction mixture
            sess.put(makeup_endpoint + "/stop")
            sess.put(analValve_endpoint + "/distribution-valve/position",
                     params={"position": analvalve_mapping['COLLECT']})
            await asyncio.sleep(time_schedule["half_peak"] * 1.2 * 60 + 600)  # todo: only for longer information
            sess.put(analValve_endpoint + "/distribution-valve/position",
                     params={"position": analvalve_mapping['WASTE']})

        # purge the system (~ 4.5min): increasing the solvent velocity to purge the seperator
        await purge_system(time_schedule["purge_system"])
        logger.info(f"the experiment was completed!")

        # initialized all hardware
        await exp_hardware_initialize(self.base_exp_info.dad_info)
        logger.info("the hardware initialization were completed.")

        if not wait_hplc:
            logger.info("finish the experiment.")
            return True

        else:
            # give five min additional waiting time
            analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"
            filewatcher = FileWatch(folder_path=analysed_samples_folder, file_extension="txt")
            file_existed = await filewatcher.check_file_existence_timeout(
                file_name=f"{mongo_id} - DAD 2.1L- Channel 1.txt",
                timeout=(self.base_exp_info.hplc_config_info.HPLC_RUNTIME + 5) * 60,
                check_interval=3)
            return file_existed  # Path

    async def run_and_collect(
            self,
            mongo_id: str | PydanticObjectId,
            condition: dict,
            wait_hplc: bool = True,
            ) -> Path | bool:

        """    run the experiment and log the system information      """
        date = datetime.date.today().strftime("%Y%m%d")
        log_path = Path(rf"W:\BS-FlowChemistry\People\Wei-Hsin\GL_data\3_logger\{date}_{mongo_id}.log")
        i = logger.add(log_path, rotation="10 MB")

        logger.warning(f"start to run the test experiment: {mongo_id}")
        logger.info("_________________________________________________________")
        logger.info(f"condition: {condition}")

        # initialize the devices to ready
        await exp_hardware_initialize()

        # calc all operation parameters
        (condition, volume_for_loop, inj_loop_flows,
         all_flows, time_schedule, doable, setting_flows) = self.calc_all_parameters(
            condition=condition,
        )

        logger.info(f"start to adjust the system pressure for new experiment.....")
        reach_p = await adj_bpr(condition["pressure"], time_schedule["adj_press"])

        if not reach_p:
            logger.error(f"IncompleteAnalysis: The hplc file isn't found! check manually.....")
            await platform_standby(self.hplc_commander,
                                   standby_hplc_method=r"D:\Data2q\BV\autostartup_analysis\autostartup_000_50ACN.MET")
            raise PlatformError

        logger.info(f"Start to run the test experiment!!!")


        # Start background tasks without awaiting their results
        asyncio.create_task(system_log(
            date,
            mongo_id,
            time_schedule["total_operation_time"],
            folder_path=r"W:\BS-FlowChemistry\People\Wei-Hsin\GL_data\system_log\\"
        ))

        asyncio.create_task(collect_dad_given_time(
            date,
            mongo_id,
            time_schedule["total_operation_time"],
            dad_info=self.base_exp_info.dad_info,
        ))

        # Await only the task you care about
        txt_file_existed = await self._run_experiment(
            mongo_id,
            condition,
            inj_loop_flows,
            setting_flows,
            time_schedule,
            wait_hplc=wait_hplc
        )

        if not wait_hplc:
            logger.info(f"the experiment was completed and we don't wait the lc!")
            # logger finish and remove
            logger.remove(i)

        if not txt_file_existed:
            logger.error(f"hplc txt file find nowhere.... Something is wrong!!!")
            await platform_standby(self.hplc_commander,
                                   standby_hplc_method=r"D:\Data2q\BV\autostartup_analysis\autostartup_000_50ACN.MET")
            logger.info("platform standby. Wait until hardware being checked!")
            raise PlatformError

        # logger finish and remove
        logger.remove(i)
        logger.info(f"the experiment and the analysis were completed!")
        return txt_file_existed  # Path


def calc_all_parameters(condition: dict,
                        setup: object,
                        base_exp_info: object,
                        ):
    """
    calculate all the parameters for the experiment
    Specfic for debenzylation experiment
    """
    Calctor = DeBnCalculator(setup_vol_dict=setup.physical_info_setup_list,
                             sm_info=base_exp_info.SM_info,
                             is_info=base_exp_info.IS_info,
                             gas=base_exp_info.gas_info.nickname,
                             component_1=base_exp_info.oxidant_info_1,
                             component_2=base_exp_info.catalyst_info,
                             component_3=base_exp_info.solvent_info_1,
                             component_4=base_exp_info.solvent_info_2
                             )
    condition["concentration"] = Calctor.calc_concentration(condition=condition, unit_include=False)
    # calculate the setting parameters
    logger.debug(f"theoretically concentration: {condition['concentration']}")

    # calculate the operating parameters
    volume_for_loop, inj_loop_flow_rate = Calctor.calc_inj_loop(condition, unit_include=False)
    # fixme gas input should be

    all_flows = Calctor.calc_all_flow_rate(condition,
                                           hplc_ana_conc=base_exp_info.hplc_config_info.HPLC_SAMPLE_CONC,
                                           )

    time_schedule = Calctor.calc_exp_schedule(condition, all_flows)
    logger.info(f"time:{time_schedule}")
    # make digraph to graph # fixme

    # calibrate the real operating parameters
    Calibrator = HardwareCalibrator(setup.G, setup.physical_info_setup_list)
    setting_flows = Calibrator.calibrate_flow_rate(all_flows)
    # check the platform setting is doable or not
    doable = Calibrator.check_param_doable(inj_loop_flow_rate, all_flows)
    if not doable:
        raise ValueError("the platform is not able to run the experiment")

    return condition, volume_for_loop, inj_loop_flow_rate, all_flows, time_schedule, doable, setting_flows


if __name__ == "__main__":
    from BV_experiments.Example3_debenzylation.db_doc import SecondDebenzylation, FlowSetupDad


    hplc_commander = Async_ClarityRemoteInterface(remote=True,
                                                  host='192.168.10.11',
                                                  port=10015,
                                                  instrument_number=1)

    executor = DebenzylExecutor(FlowSetupDad, SecondDebenzylation, hplc_commander)

    condition = {'tbn_equiv': 1, 'acn_equiv': 0, 'ddq_equiv': 0.5, 'dcm_equiv': 806,
                 'gas': 'oxygen', 'gl_ratio': 1,
                 'temperature': 28, 'time': 2, 'light_wavelength': '440nm',
                 'light_intensity': 24, 'pressure': 3}

    calc_all_parameters(condition, FlowSetupDad, SecondDebenzylation)
    condition, volume_for_loop, inj_loop_flow_rate, all_flows, time_schedule, doable, setting_flows = executor.calc_all_parameters(condition)
    executor.cali_all_parameters(inj_loop_flow_rate, all_flows)