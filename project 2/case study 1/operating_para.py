import os
import pint
from dotenv import load_dotenv, dotenv_values
from loguru import logger
from typing import Union
import asyncio
from collections import OrderedDict

from BV_experiments.calc_gl_para import GLcalculator, GLcalculator_unit, add_units
from BV_experiments.platform_error import PlatformError
from BV_experiments.Batch_analysis_uni import deliver_specific_vol

class Example2_calculator(GLcalculator):
    def __init__(
            self,
            pipeline_path: str,

    ):
        super().__init__(pipeline_path)
        env_vars = dotenv_values(dotenv_path=pipeline_path)  # import env as a OrderDict
        # tube list: pick all
        # self.tubes = OrderedDict()
        # self.tubes.update({var: float(env_vars[var]) for var in env_vars if "TUBE" in var})

        # reactor part
        self.reactor = OrderedDict()
        for var in env_vars:
            self.reactor.update({var: float(env_vars[var])})
            if "COLLECTED_VIAL" == var:
                break

        # analysis part
        self.analyzer = OrderedDict()
        for var in reversed(env_vars):
            self.analyzer.update({var: float(env_vars[var])})
            if "COLLECTED_VIAL" == var:
                break

        load_dotenv(dotenv_path=pipeline_path)
        self.TUBE_BPR_TO_PUMPM = float(os.environ.get("TUBE_BPR_TO_PUMPM"))
        self.TUBE_PUMPM_TO_VALVEC = float(os.environ.get("TUBE_PUMPM_TO_VALVEC"))
        self.TUBE_VALVEC_TO_VIAL = float(os.environ.get("TUBE_VALVEC_TO_VIAL"))  # 0.007 ml = 0.10 (m) * 70.69 (ul/m)
        self.COLLECTED_VIAL = float(os.environ.get("COLLECTED_VIAL"))  # 4.9 ml

        self.TRANSFER_SYRINGE = float(os.environ.get("TRANSFER_SYRINGE"))  # 1.0 in ml

        self.TUBE_PUMPB_TO_HPLCVALVE = float(os.environ.get("TUBE_PUMPB_TO_HPLCVALVE"))  # 0.130 ml = 0.165 (m) * 785.4 (ul/m)
        self. HPLCLOOP = float(os.environ.get("HPLCLOOP"))  # 0.001 ml

    def reaction_schedule(self,
                          condition: dict,
                          gl_flow: dict) -> dict:

        # calculate the time for pre_run_para
        pre_run_para = self.calc_stable_system(condition, gl_flow)

        # no gas consume
        start_collect_time: float = (
                self.reactor["TUBE_LOOP_TO_MIX_GAS"] / gl_flow["liquid_flow"] +
                self.TUBE_MIX_GAS_TO_REACTOR / gl_flow["total_flow"] +
                condition["time"] +
                (self.TUBE_BPR_TO_PUMPM + self.TUBE_PUMPM_TO_VALVEC +
                 self.TUBE_VALVEC_TO_VIAL) / (gl_flow["liquid_flow"] + gl_flow["gas_flow"])
        )

        # all gas consume
        consumed_all_o2: float = (
                self.TUBE_LOOP_TO_MIX_GAS / gl_flow["liquid_flow"] +
                self.TUBE_MIX_GAS_TO_REACTOR / gl_flow["total_flow"] +
                self.REACTOR / gl_flow["liquid_flow"] +
                (self.TUBE_BPR_TO_PUMPM + self.TUBE_PUMPM_TO_VALVEC +
                 self.TUBE_VALVEC_TO_VIAL) / gl_flow["liquid_flow"]
        )
        period_slowest_rate: float = (
                self.LOOP / gl_flow["liquid_flow"]
        )
        return {
            "adj_press": 15,
            "pre_run_time": pre_run_para["pre_run_time"],
            "fill_loop": self.LOOP / self.TOTAL_INFUSION_RATE,
            "residence_time": condition["time"],
            "loop_to_vial": start_collect_time,
            "consumed_all_o2": consumed_all_o2,
            "collect_time": consumed_all_o2 + period_slowest_rate - start_collect_time,
        }

    def vial_sol_info(self,
                      condition: dict,
                      gl_flow: Union[dict | None] = None,
                      schedule: dict | None = None):

        if not gl_flow or not schedule:
            logger.warning(f"without gl_flow or schedule input")
            gl_flow = self.calc_gas_liquid_flow_rate(condition)
            schedule = self.reaction_schedule(condition, gl_flow)

        total_collected_vol = schedule["collect_time"] * gl_flow["liquid_flow"]

        if total_collected_vol > self.COLLECTED_VIAL:
            raise PlatformError("total volume of collection is larger than vial")

        vial_conc = condition["concentration"] * self.LOOP / total_collected_vol
        logger.debug(f"concentration of the vial: {vial_conc} ({total_collected_vol} ml).")

        return total_collected_vol, vial_conc

    def calc_dilute_flow(self,
                         initial_conc: float,
                         final_conc: float,
                         delivered_rate: float):
        final_flow = delivered_rate * initial_conc / final_conc
        make_up_flow = final_flow - delivered_rate
        return make_up_flow, final_flow

        # # update gl_flow dictionary
        # gl_flow["makeup_flow"] = makeup_flow
        # return gl_flow

    def analysis_schedule_hplc(self,
                               delivered_rate: float,
                               make_up_flow: float
                               ):
        final_flow = delivered_rate + make_up_flow

        return self.analyzer["TUBE_TRANSFER_TO_PUMPB"] / delivered_rate + (self.analyzer[
            "TUBE_PUMPB_TO_HPLCVALVE"] + self.analyzer["HPLCLOOP"]) / final_flow

    # async def analysis_schedule(self,
    #                             sol_vol: float, sol_conc: float,
    #                             transfer_vol: float | None = None,
    #                             ) -> dict:
    #
    #     transfer_vol = self.TRANSFER_SYRINGE if not transfer_vol else transfer_vol
    #
    #     # full the IR chamber
    #     reach_IR_vol = self.TUBE_VIAL_TO_6PORTVALVE + self.TUBE_6PORTVALVE_TO_FLOWIR + self.FLOWIR
    #
    #     # with async_to_sync(sync=True):
    #     withdraw_t, infuse_t, left_vol, i = await deliver_specific_vol(
    #         reach_IR_vol + 0.1, False,
    #         withdraw_spd=self.TRANSFER_RATE, infuse_spd=self.TRANSFER_RATE,
    #         transfer_vol=self.TRANSFER_SYRINGE, execute=False, )
    #
    #     wait_to_acquir_IR = withdraw_t + infuse_t
    #
    #     # time for collecting data (minimal)
    #     total_IR_measuring = (self.MEASURING_TIME / 60) * 12  # 10 time
    #
    #     # small flow rate or stop in measuring IR == flow rate to prepare hplc sample
    #     withdraw_t, infuse_t, left_vol, i = await deliver_specific_vol(
    #         (self.TUBE_FLOWIR_TO_COLLECTOR + self.TUBE_COLLECTOR_TO_PUMPB) * 0.9, True,
    #         withdraw_spd=self.TRANSFER_RATE, infuse_spd=self.MEASURING_FLOW_RATE,
    #         transfer_vol=reach_IR_vol, execute=False)
    #
    #     start_pump = withdraw_t + infuse_t
    #
    #     switch_hplc = (
    #             (TUBE_FLOWIR_TO_COLLECTOR + TUBE_COLLECTOR_TO_PUMPB) * 0.1 / MEASURING_FLOW_RATE +
    #             (TUBE_PUMPB_TO_HPLCVALVE + HPLCLOOP) * 1.5 / (MEASURING_FLOW_RATE + makeup_flow)
    #     )
    #     if start_pump + switch_hplc > first_infuse_time:
    #         raise PlatformError("first infuse vol is not enough. second transfer is required.")
    #
    #     transfer_time = transfer_vol / TRANSFER_RATE
    #
    #     # wash
    #
    #     wash_vial_time = WASH_VIAL_VOL / WASH_FLOW
    #     return {
    #         "first_withdraw": first_withdraw_vol / TRANSFER_RATE,
    #         "reach_ir": reach_IR_vol / TRANSFER_RATE,
    #         "wait_IR_measuring": total_IR_measuring,  # or first_infuse_time
    #         "first_infuse": (transfer_vol * 0.9 - reach_IR_vol) / MEASURING_FLOW_RATE,
    #         "start_pump": start_pump,
    #         "switch_hplc": switch_hplc,
    #         "transfer": transfer_time,
    #         "wash_vial": wash_vial_time,
    #
    #     }
class Example2_calculator_unit(GLcalculator_unit):
    def __init__(
            self,
            pipeline_path: str = r"D:\BV\BV_experiments\Example2_methionie\pipeline.env",

    ):
        super().__init__(pipeline_path)

        env_vars = dotenv_values(dotenv_path=pipeline_path)  # import env as a OrderDict
        # tube list: pick all
        # self.tubes = OrderedDict()
        # self.tubes.update({var: float(env_vars[var]) for var in env_vars if "TUBE" in var})
        #
        # reactor part
        self.reactor = OrderedDict()
        for var in env_vars:
            self.reactor.update({var: ureg(env_vars[var])})
            if "COLLECTED_VIAL" == var:
                break

        # analysis part
        self.analyzer = OrderedDict()
        for var in reversed(env_vars):
            self.analyzer.update({var: ureg(env_vars[var])})
            if "COLLECTED_VIAL" == var:
                break

        load_dotenv(dotenv_path=pipeline_path)
        self.TUBE_BPR_TO_PUMPM = ureg(os.environ.get("TUBE_BPR_TO_PUMPM"))
        self.TUBE_PUMPM_TO_VALVEC = ureg(os.environ.get("TUBE_PUMPM_TO_VALVEC"))
        self.TUBE_VALVEC_TO_VIAL = ureg(os.environ.get("TUBE_VALVEC_TO_VIAL"))  # 0.007 ml = 0.10 (m) * 70.69 (ul/m)
        self.COLLECTED_VIAL = ureg(os.environ.get("COLLECTED_VIAL"))  # 4.9 ml

        self.TUBE_VIAL_TO_6PORTVALVE = ureg(os.environ.get("TUBE_VIAL_TO_6PORTVALVE"))  # 0.385 ml = 0.49 (m)*785.4 (ul/m)
        self.TUBE_6PORTVALVE_TO_SYRINGE = ureg(os.environ.get("TUBE_6PORTVALVE_TO_SYRINGE"))  # 0.036 ml = 0.51 (m)*70.69 (ul/m)
        self.TRANSFER_SYRINGE = ureg(os.environ.get("TRANSFER_SYRINGE"))  # 1.0 in ml
        self.TUBE_6PORTVALVE_TO_FLOWIR = ureg(os.environ.get("TUBE_6PORTVALVE_TO_FLOWIR"))  # 0.196 ml = 0.25 (m)*785.4 (ul/m)
        # self.FLOWIR = float(os.environ.get("FLOWIR"))  # = 0.01 ml = 10 μL
        self.TUBE_FLOWIR_TO_COLLECTOR = ureg(os.environ.get("TUBE_FLOWIR_TO_COLLECTOR"))  # 0.393 ml = 0.50 (m)*785.4 (ul/m)

        self.TUBE_COLLECTOR_TO_PUMPB = ureg(os.environ.get("TUBE_COLLECTOR_TO_PUMPB"))  # 0.016 ml = 0.23 (m) * 70.69 (ul/m)
        self.TUBE_PUMPB_TO_HPLCVALVE = ureg(os.environ.get("TUBE_PUMPB_TO_HPLCVALVE"))  # 0.130 ml = 0.165 (m) * 785.4 (ul/m)
        self. HPLCLOOP = ureg(os.environ.get("HPLCLOOP"))  # 0.001 ml

        # self.TRANSFER_RATE = float(os.environ.get("TRANSFER_RATE"))  # 1.5 ml/min
        # self.MEASURING_TIME = float(os.environ.get("MEASURING_TIME"))  # 15 sec
        # self.MEASURING_FLOW_RATE = float(os.environ.get("MEASURING_FLOW_RATE"))  # 0.05 ml/min
        # self.HPLC_CONC = float(os.environ.get("HPLC_CONC"))  # 0.01
        # self.WASH_FLOW = float(os.environ.get("WASH_FLOW"))  # 3.0 ml/min
        # self.WASH_VIAL_VOL = float(os.environ.get("WASH_VIAL_VOL"))  # 2.8 ml


    def reaction_schedule(self,
                          rxn_time: float | pint.Quantity,
                          pressure: float | pint.Quantity,
                          flow_rate: dict) -> dict:

        # calculate the time for pre_run_para
        pre_run_para = self.calc_stable_system(rxn_time, pressure, flow_rate)

        # no gas consume
        start_collect_time: float = (
                self.reactor["TUBE_LOOP_TO_MIX_GAS"] / flow_rate["liquid_flow"] +
                self.TUBE_MIX_GAS_TO_REACTOR / flow_rate["total_flow"] +
                rxn_time +
                (self.TUBE_BPR_TO_PUMPM + self.TUBE_PUMPM_TO_VALVEC +
                 self.TUBE_VALVEC_TO_VIAL) / (flow_rate["liquid_flow"] + flow_rate["gas_flow"])
        )

        # all gas consume
        consumed_all_o2: float = (
                self.TUBE_LOOP_TO_MIX_GAS / flow_rate["liquid_flow"] +
                self.TUBE_MIX_GAS_TO_REACTOR / flow_rate["total_flow"] +
                self.REACTOR / flow_rate["liquid_flow"] +
                (self.TUBE_BPR_TO_PUMPM + self.TUBE_PUMPM_TO_VALVEC +
                 self.TUBE_VALVEC_TO_VIAL) / flow_rate["liquid_flow"]
        )
        period_slowest_rate: float = (
                self.LOOP / flow_rate["liquid_flow"]
        )
        return {
            "adj_press": 15,
            "pre_run_time": pre_run_para["pre_run_time"],
            "fill_loop": self.LOOP / self.TOTAL_INFUSION_RATE,
            "residence_time": rxn_time,
            "loop_to_vial": start_collect_time,
            "consumed_all_o2": consumed_all_o2,
            "collect_time": consumed_all_o2 + period_slowest_rate - start_collect_time,
        }

    def vial_sol_info(self,
                      concentration: float | pint.Quantity,
                      rxn_time: float | pint.Quantity,
                      oxygen_equiv: float | pint.Quantity,
                      pressure: float | pint.Quantity,
                      gl_flow: Union[dict | None] = None,
                      schedule: dict | None = None):

        if not gl_flow or not schedule:
            logger.warning(f"without gl_flow or schedule input")
            gl_flow = self.calc_gas_liquid_flow_rate(concentration, rxn_time, oxygen_equiv, pressure)
            schedule = self.reaction_schedule(rxn_time, pressure, gl_flow)

        total_collected_vol = schedule["collect_time"] * gl_flow["liquid_flow"]

        if total_collected_vol > self.COLLECTED_VIAL:
            raise PlatformError("total volume of collection is larger than vial")

        vial_conc = concentration * self.LOOP / total_collected_vol
        logger.debug(f"concentration of the vial: {vial_conc} ({total_collected_vol} ml).")

        return total_collected_vol, vial_conc

    def calc_dilute_flow(self,
                         current_conc: pint.Quantity,
                         final_conc: pint.Quantity,
                         delivered_rate: pint.Quantity):

        final_flow = delivered_rate * current_conc / final_conc
        make_up_flow = final_flow - delivered_rate
        return make_up_flow, final_flow

        # # update gl_flow dictionary
        # gl_flow["makeup_flow"] = makeup_flow
        # return gl_flow

    def analysis_schedule_hplc(self,
                               delivered_rate: pint.Quantity,
                               make_up_flow: pint.Quantity
                               ) -> pint.Quantity:
        final_flow = delivered_rate + make_up_flow

        return self.analyzer["TUBE_6PORTVALVE_TO_PUMPB"] / delivered_rate + (self.analyzer[
            "TUBE_PUMPB_TO_HPLCVALVE"] + self.analyzer["HPLCLOOP"]) / final_flow

    # async def analysis_schedule(self,
    #                             sol_vol: float, sol_conc: float,
    #                             transfer_vol: float | None = None,
    #                             ) -> dict:
    #
    #     transfer_vol = self.TRANSFER_SYRINGE if not transfer_vol else transfer_vol
    #
    #     # full the IR chamber
    #     reach_IR_vol = self.TUBE_VIAL_TO_6PORTVALVE + self.TUBE_6PORTVALVE_TO_FLOWIR + self.FLOWIR
    #
    #     # with async_to_sync(sync=True):
    #     withdraw_t, infuse_t, left_vol, i = await deliver_specific_vol(
    #         reach_IR_vol + 0.1, False,
    #         withdraw_spd=self.TRANSFER_RATE, infuse_spd=self.TRANSFER_RATE,
    #         transfer_vol=self.TRANSFER_SYRINGE, execute=False, )
    #
    #     wait_to_acquir_IR = withdraw_t + infuse_t
    #
    #     # time for collecting data (minimal)
    #     total_IR_measuring = (self.MEASURING_TIME / 60) * 12  # 10 time
    #
    #     # small flow rate or stop in measuring IR == flow rate to prepare hplc sample
    #     withdraw_t, infuse_t, left_vol, i = await deliver_specific_vol(
    #         (self.TUBE_FLOWIR_TO_COLLECTOR + self.TUBE_COLLECTOR_TO_PUMPB) * 0.9, True,
    #         withdraw_spd=self.TRANSFER_RATE, infuse_spd=self.MEASURING_FLOW_RATE,
    #         transfer_vol=reach_IR_vol, execute=False)
    #
    #     start_pump = withdraw_t + infuse_t
    #
    #     switch_hplc = (
    #             (TUBE_FLOWIR_TO_COLLECTOR + TUBE_COLLECTOR_TO_PUMPB) * 0.1 / MEASURING_FLOW_RATE +
    #             (TUBE_PUMPB_TO_HPLCVALVE + HPLCLOOP) * 1.5 / (MEASURING_FLOW_RATE + makeup_flow)
    #     )
    #     if start_pump + switch_hplc > first_infuse_time:
    #         raise PlatformError("first infuse vol is not enough. second transfer is required.")
    #
    #     transfer_time = transfer_vol / TRANSFER_RATE
    #
    #     # wash
    #
    #     wash_vial_time = WASH_VIAL_VOL / WASH_FLOW
    #     return {
    #         "first_withdraw": first_withdraw_vol / TRANSFER_RATE,
    #         "reach_ir": reach_IR_vol / TRANSFER_RATE,
    #         "wait_IR_measuring": total_IR_measuring,  # or first_infuse_time
    #         "first_infuse": (transfer_vol * 0.9 - reach_IR_vol) / MEASURING_FLOW_RATE,
    #         "start_pump": start_pump,
    #         "switch_hplc": switch_hplc,
    #         "transfer": transfer_time,
    #         "wash_vial": wash_vial_time,
    #
    #     }

def all_calcultion():
    condition = {'concentration': 0.3, 'oxygen_equiv': 1.2,
                 'time': 1.0, 'wavelength': "440nm",
                 'light': 24, 'pressure': 2.5, 'temperature': 52,
                 }
    condition_unit = add_units(condition)
    # env_path = r"D:\BV\BV_experiments\Example2_methionie\pipeline.env"
    env_path = r"D:\BV\BV_experiments\Example2_methionie\pipeline_02.env"
    calculator = Example2_calculator(env_path, )

    rates = calculator.calc_gas_liquid_flow_rate(condition)
    print(rates)
    sys = calculator.calc_stable_system(condition, gl_flow=rates)
    print(sys)
    rxn_schedule = calculator.reaction_schedule(condition, gl_flow=rates)
    print(rxn_schedule)

    # vial_vol, vial_conc = calculator.vial_sol_info(condition)
    col_vol, col_conc = calculator.vial_sol_info(condition)
    logger.info(f"total volume: {col_vol}")
    logger.info(f"total concentration: {col_conc}")

    # dilute flow
    syr_delivered_rate = 0.2
    rates["syr_delivered_rate"] = syr_delivered_rate
    make_up_flow, final_flow = calculator.calc_dilute_flow(col_conc,
                                                           final_conc=0.01,
                                                           delivered_rate=syr_delivered_rate)
    logger.info(f"make-up flow for hplc: {make_up_flow} ml/min (final flow: {final_flow} ml/min).")
    rates["make_up_flow"] = make_up_flow

    ana_time = calculator.analysis_schedule_hplc(syr_delivered_rate, make_up_flow)
    print(ana_time)

if __name__ == "__main__":
    all_calcultion()
