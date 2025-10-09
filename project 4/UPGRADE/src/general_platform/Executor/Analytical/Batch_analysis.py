"""
Universial delivery method for the platform.....
( only increase the analysis + clean the vial)

"""
import datetime

from BV_experiments.src.general_platform.Executor.Analytical.platform_remote_hplc_control import Async_ClarityRemoteInterface
from BV_experiments.src.general_platform.Executor.Analytical.Batch_analysis_uni import *
from BV_experiments.src.general_platform.Executor.Analytical.Batch_analysis_thread import *


class BatchAnalysis:
    """to control batch_analysis"""

    def __init__(self,
                 deliver_method: str,
                 analysis_method: dict,
                 collection: list | None = None,
                 *args,
                 **kwargs
                 ):
        """

        :param deliver_method:
        :param analysis_method:
        :param collection:
        :param args:
        :param kwargs: please give dictionary of analysis method.... for example
        {
        "hplc-uv":
            {
            "remote":
            "HPLC_FLOW_RATE" : "0.25 ml/min"
            "HPLC_ELUENT" = {"EluentA": "100% water + 0.1% TFA", "EluentB": "100% ACN + 0.1% TFA"}
            "HPLC_DAD" = 215
            "HPLC_METHOD" = r"D:\Data2q\BV\methionine_method_10min.MET"
            "HPLC_RUNTIME" = 11
            "HPLC_GRADIENT" = {"time (min.)": "EluentA (%)", 0: 99, 2: 99, 5: 5, 6.5: 5, 7: 99, 10: 99}
            "ROI" = [0.5, 2.5]
            "PEAK_RT" = {"sm": 0.96, "sulfoxide": 1.85}

            ACCEPTED_SHIFT = 0.22  # TODO: too large....
            }
        }
        """

        self.collect = collection


        # analysis methods
        available_methods = ["flowir", "nmr", "hplc-uv"]
        self.ana_meta = analysis_method

        if "flowir" in analysis_method.keys():
            logger.info(f"establish ir connection. check ir is connect....")
            # todo: establish c
        if "nmr" in analysis_method.keys():
            logger.info(f"establish nmr. check nmr")
            # todo:
        if "hplc-uv" in analysis_method.keys():
            # todo: process the hplc file
            if remote:
                self.commander = Async_ClarityRemoteInterface()

    async def batch_analysis(self,
                             date: datetime,
                             mongo_id: str,
                             condition: dict,
                             flow_rate: dict,
                             schedule: dict,
                             commander: Async_ClarityRemoteInterface,
                             wait_hplc: bool
                             ):

            # prime the syringe
            withdraw_t, infuse_t, left_vol, i = await deliver_specific_vol(TUBE_VIAL_TO_6PORTVAVLE * 1.3,
                                                                           last_full_withdraw=False,
                                                                           withdraw_p="vial",
                                                                           infuse_p="waste",
                                                                           withdraw_spd=TRANSFER_RATE,
                                                                           infuse_spd=TRANSFER_RATE,
                                                                           transfer_vol=TRANSFER_SYRINGE,
                                                                           execute=True,
                                                                           wait_to_finish_infuse=True)

            logger.info(f"start to deliver the reaction mixture to IR")
            reach_IR_vol = TUBE_6PORTVALVE_TO_FLOWIR + FLOWIR
            # transfer the (vol + 0.1 ml) to full the IR chamber
            withdraw_t, infuse_t, left_vol, i = await deliver_specific_vol(reach_IR_vol + 0.1,
                                                                           last_full_withdraw=False,
                                                                           withdraw_p="vial",
                                                                           infuse_p="analysis",
                                                                           withdraw_spd=TRANSFER_RATE,
                                                                           infuse_spd=TRANSFER_RATE,
                                                                           transfer_vol=TRANSFER_SYRINGE,
                                                                           execute=True,
                                                                           wait_to_finish_infuse=True)



            # collect_ir_data and prepared hplc sample in the same time.
            reach_hplc_vol = TUBE_FLOWIR_TO_COLLECTOR + TUBE_COLLECTOR_TO_PUMPB + (TUBE_PUMPB_TO_HPLCVAVLE
                                                                                   + HPLCLOOP) * MEASURING_FLOW_RATE / (
                                     flow_rate["makeup_flow"] + MEASURING_FLOW_RATE)

            use_hplc, ir_yield = await asyncio.gather(
                prepare_hplc_sample(mongo_id, flow_rate, commander, False, reach_hplc_vol * 1.3),
                collect_ir_data(date, mongo_id, ir_bg, reach_hplc_vol / MEASURING_FLOW_RATE))
            rest_vol = coll_vol - TUBE_VIAL_TO_6PORTVAVLE * 1.3 - (reach_IR_vol + 0.1) - reach_hplc_vol * 1.3

            await collect_rm(rest_vol)
            await wash_system(0, execute=True)
            await exp_hardware_init()

    async def collect_rm(self,
                         rest_vol,
                         coll_p: str):
        """ position 16 was to waste """

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

    async def prepare_hplc_sample(self,
                                  mongo_id: str,
                                  flow_rate: dict,
                                  wait_hplc: bool,
                                  used_prepared_lc_vol: float | None = None) -> float:

        logger.info(" ____ prepare lc sample ____")

        with command_session() as sess:
            # prepare hplc sample
            sess.put(collector_endpoint + "/distribution-valve/position", params={"position": "1"})
            sess.put(r2_endpoint + "/Pump_B/infuse", params={"rate": f"{flow_rate['makeup_flow']} ml/min"})

            reach_hplc_vol = TUBE_FLOWIR_TO_COLLECTOR + TUBE_COLLECTOR_TO_PUMPB + (TUBE_PUMPB_TO_HPLCVAVLE
                                                                                   + HPLCLOOP) * MEASURING_FLOW_RATE / (
                                     flow_rate["makeup_flow"] + MEASURING_FLOW_RATE)

            if not used_prepared_lc_vol:
                used_prepared_lc_vol = reach_hplc_vol * 1.3

            t_withdraw_t, t_infuse_t, left_vol, infuse_t = await deliver_specific_vol(used_prepared_lc_vol,
                                                                                      last_full_withdraw=False,
                                                                                      withdraw_p="vial",
                                                                                      infuse_p="analysis",
                                                                                      withdraw_spd=TRANSFER_RATE,
                                                                                      infuse_spd=MEASURING_FLOW_RATE,
                                                                                      transfer_vol=TRANSFER_SYRINGE,
                                                                                      execute=True,
                                                                                      wait_to_finish_infuse=False)

            transfer_end_time = time.monotonic() + infuse_t * 60

            # fixme: only if
            await asyncio.sleep(reach_hplc_vol * 1.1 % TRANSFER_SYRINGE / MEASURING_FLOW_RATE - 5)
            sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "load"})

            # send the method.....
            await self.commander.load_method(HPLC_METHOD)
            await self.commander.set_sample_name(f"{mongo_id}")
            await self.commander.run()  # delay 2 sec.....
            await asyncio.sleep(2)

            # inject sample by switch the hplc injection valve
            # 0.24 sec for 0.001 ml sample / 0.25 ml/min flow rate
            sess.put(HPLCvalve_endpoint + "/injection-valve/position", params={"position": "inject"})
            logger.info(f"Switch the hplc injection valve and start to analysis")

            # sess.put(syr3_endpoint + "/pump/infuse",
            #          params={"rate": f" {MEASURING_FLOW_RATE} ml/min", "volume": f"{left_vol} ml"})  # deliver full syringe

            if not wait_hplc:
                while time.monotonic() < transfer_end_time:
                    await asyncio.sleep(1)
                return reach_hplc_vol * 1.3

        logger.info("wait the hplc analysis finish")
        await asyncio.sleep(HPLC_RUNTIME * 60)
        return reach_hplc_vol * 1.3

async def main():
    analysis_method = {"hplc-uv":
                           dict(remote=True, HPLC_FLOW_RATE="0.25 ml/min",
                                HPLC_ELUENT={"EluentA": "100% water + 0.1% TFA", "EluentB": "100% ACN + 0.1% TFA"},
                                HPLC_DAD=215, HPLC_METHOD=r"D:\Data2q\BV\methionine_method_10min.MET", HPLC_RUNTIME=11,
                                HPLC_GRADIENT={"time (min.)": "EluentA (%)", 0: 99, 2: 99, 5: 5, 6.5: 5, 7: 99, 10: 99},
                                ROI=[0.5, 2.5], PEAK_RT={"sm": 0.96, "sulfoxide": 1.85}, ACCEPTED_SHIFT=0.22)}

    w, i, rest_vol = await deliver_specific_vol(0.591 + 0.1, last_full_withdraw=True, execute=False)
    print(rest_vol)

if __name__ == "__main__":
    asyncio.run(main())

