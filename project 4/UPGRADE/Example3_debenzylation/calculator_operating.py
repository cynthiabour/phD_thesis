import pint
from loguru import logger

from BV_experiments.src.general_platform import ureg
from BV_experiments.src.general_platform.Executor.Calculator.calc_gl_para import GLcalculator_db
from BV_experiments.src.general_platform.Librarian.db_models import ChemInfo


class DeBnCalculator(GLcalculator_db):

    def __init__(self,
                 setup_vol_dict: dict,
                 sm_info: ChemInfo,
                 is_info: ChemInfo,
                 component_1: ChemInfo,
                 gas: str,
                 **kwargs
                 ):
        super().__init__(setup_vol_dict, gas)

        self.sm_info = sm_info
        self.is_info = is_info
        self.component_1 = component_1
        # Dynamically set component_2 to component_4
        for i in range(2, 5):
            setattr(self, f'component_{i}', kwargs.get(f'component_{i}', None))

        # for vial collection
        self.TUBE_PUMPM_TO_VALVEC = 0.05  # ml/min
        self.TUBE_VALVEC_TO_VIAL = 0.007
        self.COLLECTED_VIAL = 4.9  # ml

    def component_attr(self, component: ChemInfo) -> dict:

        if component.density is None:
            return {
                "concentration": component.concentration,
                "dissolve_solvent": component.dissolve_solvent,
            }
        return {
            "density": component.density,
            "MW": component.MW}

    def syringe_vol_ratio(self, condition: dict) -> dict:
        """Calculate the reagent volume ratio on given reaction conditions.."""

        # check the reagent information
        composition = {}
        for attr, value in self.__dict__.items():
            if isinstance(value, ChemInfo):
                # fixme : need to check the component name (nickname)
                composition[value.nickname] = self.component_attr(value)

        for key, value in composition.items():
            for value_key, value_value in value.items():
                if value_key == 'density':
                    value[value_key] = value_value * ureg.g / ureg.mL if isinstance(
                        value_value, float) else ureg.parse_expression(value_value)
                elif value_key == 'concentration':
                    value[value_key] = value_value * ureg.mol / ureg.L if isinstance(
                        value_value, float) else ureg.parse_expression(value_value)
                elif value_key == 'MW':
                    value[value_key] = value_value * ureg.g / ureg.mol if isinstance(
                        value_value, float) else ureg.parse_expression(value_value)
        logger.debug(composition)

        # check the syringe information
        syringe_info = {key: value for key, value in self.setup_dict.items() if key.startswith("SYRINGE")}
        # logger.debug(syringe_info)

        # fixme: find a better way to calculate the reagent volume ratio
        # todo: smart way to calculate the reaction condition....

        volume_ratio = {
            "SYRINGE0": {"nickname": "TBN",
                         "vol": condition["tbn_equiv"] * ureg.mole / composition["TBN"]["concentration"]},
            "SYRINGE5": {"nickname": "SM+IS", "vol": 1 * ureg.mole / composition["SM"]["concentration"]},
            "SYRINGE3": {"nickname": "ACN",
                         "vol": condition["acn_equiv"] * ureg.mole * composition["ACN"]["MW"] / composition["ACN"][
                             "density"]},
            "SYRINGE4": {"nickname": "DDQ",
                         "vol": condition["ddq_equiv"] * ureg.mole / composition["DDQ"]["concentration"]},
            "SYRINGE6": {"nickname": "DCM",
                         "vol": condition["dcm_equiv"] * ureg.mole * composition["DCM"]["MW"] / composition["DCM"][
                             "density"]},
        }
        # change the volume to ml
        for key, value in volume_ratio.items():
            value["vol"] = value["vol"].to('ml')

        return volume_ratio

    def calc_inj_loop(self,
                      condition: dict,
                      filling_time: pint.Quantity = 1.0 * ureg.min,
                      unit_include: bool = False) -> tuple[dict, dict]:

        """Calculate the loop filling."""
        # Get the loop filling parameters
        syr_vol_ratio = self.syringe_vol_ratio(condition)

        # Calculate the required volume to fill the loop [0.5 mL]
        vol_of_all = {
            key: value["vol"] * self.setup_dict["LOOP"][0] * ureg.ml / sum(
                item['vol'] for item in syr_vol_ratio.values()) for key, value in syr_vol_ratio.items()}

        rate_of_all = {key: value / filling_time for key, value in vol_of_all.items()}

        if unit_include:
            return vol_of_all, rate_of_all

        # dict[str:pint.Quantity]  --> dict[str:float]
        vol_of_all_float = {key: value.to('ml').magnitude for key, value in vol_of_all.items()}
        rate_of_all_float = {key: value.to('ml/min').magnitude for key, value in rate_of_all.items()}

        return vol_of_all_float, rate_of_all_float

    def calc_concentration(self,
                           condition: dict,
                           unit_include: bool = False) -> pint.Quantity | float:
        """Calculate the final concentration."""
        init_conc = ureg.parse_expression(self.sm_info.concentration)
        syr_vol_ratio = self.syringe_vol_ratio(condition)

        # find the one nickname is contain SM
        sm_vol = next(item['vol'] for item in syr_vol_ratio.values() if 'SM' in item['nickname'])
        # Extract the vol values and sum them
        total_vol = sum(item['vol'] for item in syr_vol_ratio.values())
        if unit_include:
            return (init_conc * sm_vol / total_vol).to('mol/L')

        return (init_conc * sm_vol / total_vol).to('mol/L').magnitude  # final concentration in M

    def calc_equivalent_solvent(self, condition: dict) -> tuple[float, float]:
        """Calculate the equivalent solvent."""
        # check condition dictionary have equiv_acn and equiv_dcm
        # fixme: need to check the condition dictionary
        equiv_acn = condition.get('acn_equiv', 0)

    def calc_vol_eq11(self, condition: dict) -> dict:
        # calualte the gas and liquid flow rate to 1:1
        logger.warning(f"The volume ratio of gas and liquid is 1:1, ignore the oxygen_equiv")

        total_flow_rate = self.REACTOR / condition["time"]  # ml/min
        half_flow = total_flow_rate / 2

        # liquid flow rate
        set_liquid_flow: float = half_flow
        # gas flow rate
        set_gas_flow: float = half_flow * condition["pressure"]
        return {
            "total_flow": total_flow_rate,
            "liquid_flow": set_liquid_flow,
            "gas_flow": set_gas_flow,
        }

    def calc_air_liquid_flow_rate(self,
                                  condition: dict
                                  ) -> dict:
        """
        Calculation all flow used in the reaction....
        #condition: dict
        Returns: dict:{total flow, liquid flow, gas flow}
        """

        Oxygen_volume_per_mol = 22.4  # in 1.01 bar  P1*V1 = P2*V2

        total_flow_rate = self.REACTOR / condition["time"]  # ml/min
        # parameters
        conc = condition["concentration"]  # in M
        vol_ratio_GtoL = Oxygen_volume_per_mol * conc * condition["oxygen_equiv"] * 5
        compressed_G_vol = vol_ratio_GtoL / condition["pressure"]

        # setting flow rate of liquid and gas (in ml/min)
        set_liquid_flow: float = total_flow_rate / (1 + compressed_G_vol)
        set_gas_flow: float = set_liquid_flow * vol_ratio_GtoL
        return {"total_flow": total_flow_rate,
                "liquid_flow": set_liquid_flow,
                "gas_flow": set_gas_flow,
                }

    def calc_loop_prep_schedule(self,
                                condition: dict,
                                filling_time: pint.Quantity = 1.0 * ureg.min,
                                unit_include: bool = False) -> dict:
        """Calculate the loop preparation schedule."""

        inj_vol, inj_rate = self.calc_inj_loop(condition,
                                               filling_time=filling_time,
                                               unit_include=False)
        total_infusion_rate = sum(inj_rate.values())
        wash_rate = total_infusion_rate*5
        # fixme:  G to check which syr is connect first
        # wash the fitting and tube (wash_5_mix did not make sense but it works)
        return {"wash_3_mix": (self.CROSS + self.TUBE_CROSS_TO_CROSS) / 3 / (wash_rate / 5),
                "wash_5_mix": self.CROSS / 2 / (wash_rate / 5),
                "3_mix": (self.CROSS + self.TUBE_CROSS_TO_CROSS) / (
                        inj_rate['SYRINGE3'] + inj_rate['SYRINGE4'] + inj_rate['SYRINGE6']) * 1.2,
                "5_mix": (self.CROSS + self.TUBE_MIXER_TO_LOOP) / total_infusion_rate,
                "delay_filling": 0.2 / total_infusion_rate,
                "fill_loop": self.LOOP / total_infusion_rate * 1.0,
                }

    def calc_exp_schedule(self,
                          condition: dict,
                          flow_rate: dict,
                          loop_fill_time: pint.Quantity = 1.0 * ureg.min,
                          unit_included: bool = False) -> dict:
        """
        Calculate the experiment schedule.
        """
        # calculat the pre-run time
        prep_sys_para = self.calc_stable_system(condition,
                                                flow_rate)
        # calculate the injection loop
        loop_schedule = self.calc_loop_prep_schedule(condition,
                                                     filling_time=loop_fill_time,
                                                     unit_include=False)

        # trial and error for the purging time required..........
        before_sensor_time: float = (
                self.TUBE_LOOP_TO_MIX_GAS / flow_rate["liquid_flow"] +
                (self.TUBE_MIX_GAS_TO_REACTOR + self.TUBE_REACTOR_TO_BPR
                 + self.TEE) / flow_rate["total_flow"] +
                condition["time"] +
                self.TUBE_BPR_TO_PUMPB / (
                        flow_rate["liquid_flow"] + flow_rate[
                    "gas_flow"]) +  # some gas will be consumed...expand the time
                self.TUBE_PUMPB_TO_SEPARATOR / (flow_rate["bf_sep_rate"] + flow_rate["gas_flow"]) +
                (self.SEPARATOR + self.AF2400X + self.TUBE_AF2400X_TO_DAD) / flow_rate["bf_sep_rate"]
        )

        consumed_all_o2: float = (
                self.TUBE_LOOP_TO_MIX_GAS / flow_rate["liquid_flow"] +
                (self.TUBE_MIX_GAS_TO_REACTOR + self.TUBE_REACTOR_TO_BPR
                 + self.TEE) / flow_rate["total_flow"] +
                self.REACTOR / flow_rate["liquid_flow"] +
                self.TUBE_BPR_TO_PUMPB / flow_rate["liquid_flow"] +  # all gas
                self.TUBE_PUMPB_TO_SEPARATOR / flow_rate["bf_sep_rate"] +
                (self.SEPARATOR + self.AF2400X + self.TUBE_AF2400X_TO_DAD) / flow_rate["bf_sep_rate"]
        )

        dilute_vol = self.LOOP * flow_rate["bf_sep_rate"] / flow_rate["liquid_flow"]  # in a range of
        logger.debug(f"theoretical total volume after seperator: {dilute_vol}")

        # sampling by 1 ul HPLC loop : dilute 2.00 ml of HPLC sampling...once the reaction mixture stable

        total_available_time = self.LOOP / flow_rate["liquid_flow"]
        logger.debug(f"theoretical available sampling time: {total_available_time}")
        logger.debug(f"total volume of HPLC sample solution will be {total_available_time * flow_rate['flow_to_hplc']}")

        """
        # adj_press: adjust
        fill_loop / pushing_mixture: for tubing
        loop_to_sensor: the theoretical maximum time to reach DAD....
        delay_to_valveC: after the front of the peak detected by DAD, the time to reach the collection valve

        wait_til_dilute: the leading reaction mixture go to the waste
        dilution: DILUTE_VOL (5 ml) for hplc sampling -> using for pumpB 

        start_hplc: collect the middle of the diluted soln (~2.5 mL) 
        purge_tube_to_hplc: switch valveC to waste, wash both side and pumpB purge the tube......
        purge whole system: 5 time volume of the system volume (~4 ml) w/ consistent flow rate...
        """

        time_schedule = {"adj_press": 15,
                         "pre_run_time": prep_sys_para["pre_run_time"],
                         # "pushing_mixture": TUBE_MIXER_TO_LOOP / total_infusion_rate * 0.5,
                         "loop_to_sensor": before_sensor_time,
                         "half_peak": dilute_vol / 2 / flow_rate['bf_sep_rate'],  # before_sensor_time / 2
                         "consumed_all_o2": consumed_all_o2,
                         "dad_to_analvalve": self.TUBE_DAD_TO_ANALVALVE / flow_rate["bf_sep_rate"],
                         "start_hplc": (self.TUBE_ANALVALVE_TO_PUMPM / flow_rate['bf_sep_rate'] +
                                        (self.TUBE_PUMPM_TO_HPLCVAVLE + self.HPLCLOOP) / flow_rate["flow_to_hplc"]),
                         "purge_system": 5 * (
                                 self.LOOP + self.TUBE_LOOP_TO_MIX_GAS + self.TUBE_MIX_GAS_TO_REACTOR + self.REACTOR +
                                 self.TUBE_REACTOR_TO_BPR + self.BPR + self.TUBE_BPR_TO_PUMPB +
                                 self.TUBE_PUMPB_TO_SEPARATOR + self.SEPARATOR + self.AF2400X +
                                 self.TUBE_AF2400X_TO_DAD + self.DAD + self.TUBE_DAD_TO_ANALVALVE +
                                 self.TUBE_ANALVALVE_TO_PUMPM + self.TUBE_PUMPM_TO_HPLCVAVLE) / 2.5,
                         }
        time_schedule.update(loop_schedule)

        # record total operation time: the maximum time.....
        time_schedule["total_operation_time"] = (time_schedule["pre_run_time"]
                                                 + time_schedule["3_mix"] + time_schedule["5_mix"] + time_schedule[
                                                     "delay_filling"]
                                                 + time_schedule["fill_loop"]
                                                 + time_schedule["consumed_all_o2"]
                                                 + time_schedule["half_peak"] * 2
                                                 + time_schedule["dad_to_analvalve"]
                                                 + time_schedule["start_hplc"]
                                                 + time_schedule["purge_system"]
                                                 )
        time_schedule["shortest_before_lc"] = (time_schedule["pre_run_time"]
                                               + time_schedule["3_mix"] + time_schedule["5_mix"] + time_schedule[
                                                   "delay_filling"]
                                               + time_schedule["fill_loop"]
                                               + time_schedule["loop_to_sensor"]
                                               + time_schedule["dad_to_analvalve"]
                                               + time_schedule["start_hplc"]
                                               )
        return time_schedule

    def collector_schedule(self,
                           condition: dict,
                           flow_rate: dict,
                           loop_fill_time: pint.Quantity = 1.0 * ureg.min,
                           unit_included: bool = False) -> dict:
        """Calculate the collector schedule for vial collection."""
        # calculat the pre-run time
        prep_sys_para = self.calc_stable_system(condition,
                                                flow_rate)
        # calculate the injection loop
        loop_schedule = self.calc_loop_prep_schedule(condition,
                                                     filling_time=loop_fill_time,
                                                     unit_include=False)

        # trial and error for the purging time required..........
        # no_O2_consumption
        t_0: float = (
                self.TUBE_LOOP_TO_MIX_GAS / flow_rate["liquid_flow"] +
                (self.TUBE_MIX_GAS_TO_REACTOR + self.TUBE_REACTOR_TO_BPR +
                 self.TEE + self.REACTOR) / flow_rate["total_flow"] +
                (self.TUBE_BPR_TO_PUMPB + self.TEE +
                 self.TUBE_PUMPB_TO_COLLECTVALVE + self.TUBE_COLLECTVALVE_TO_COLLECTVIAL) / (
                        flow_rate["liquid_flow"] + flow_rate["gas_flow"])
        )

        # consumed_all_o2
        t_all: float = (
                self.TUBE_LOOP_TO_MIX_GAS / flow_rate["liquid_flow"] +
                (self.TUBE_MIX_GAS_TO_REACTOR + self.TEE) / flow_rate["total_flow"] +
                (self.REACTOR + self.TUBE_REACTOR_TO_BPR +
                 self.TUBE_BPR_TO_PUMPB + self.TEE +
                 self.TUBE_PUMPB_TO_COLLECTVALVE + self.TUBE_COLLECTVALVE_TO_COLLECTVIAL) / flow_rate["liquid_flow"]
        )

        long_residence_time = self.LOOP / flow_rate["liquid_flow"]
        short_residence_time = self.LOOP / (flow_rate["liquid_flow"] + flow_rate["gas_flow"])

        if long_residence_time * flow_rate['liquid_flow'] > self.COLLECTED_VIAL:
            logger.warning(
                f"the total available time is not enough to collect all vials: {long_residence_time * flow_rate['liquid_flow']}")
        else:
            logger.debug(f"theoretical total volume after seperator: {long_residence_time * flow_rate['liquid_flow']}")

        # collect all
        start_collect_time = t_0
        end_collect_time = t_all + long_residence_time

        # collect middle
        start_collect_time_mid = t_all
        end_collect_time_mid = t_0 + short_residence_time

        time_schedule = {"adj_press": 15,
                         "pre_run_time": prep_sys_para["pre_run_time"],
                         "loop_to_sensor": t_0,
                         "consumed_all_o2": t_all,
                         "collect_all_time": end_collect_time - start_collect_time,
                         "collect_middle_time": end_collect_time_mid - start_collect_time_mid,
                         }

        time_schedule.update(loop_schedule)

        # record total operation time: the maximum time.....
        time_schedule["total_operation_time"] = (time_schedule["pre_run_time"]
                                                 + time_schedule["3_mix"] + time_schedule["5_mix"] + time_schedule[
                                                     "delay_filling"]
                                                 + time_schedule["fill_loop"]
                                                 + time_schedule["consumed_all_o2"]
                                                 + time_schedule["collect_all_time"]
                                                 )
        return time_schedule

    def collector_dilute_conc(self, condition: dict, flow_rate: dict, schedule: dict, unit_include: bool = False
                              ) -> pint.Quantity | float:
        """Calculate the collector dilute concentration."""
        if "collect_all_time" not in schedule:
            raise KeyError("schedule must contain collect_all_time")

        # calculate the hplc analysis time
        # fixme: add 2 min
        total_vol = (schedule["collect_all_time"] + 2) * flow_rate["liquid_flow"]
        concentration: pint.Quantity = self.calc_concentration(condition, unit_include=True)

        collector_conc: pint.Quantity = concentration * self.LOOP / total_vol
        logger.debug(f"collector_conc: {collector_conc}")
        if unit_include:
            return collector_conc.to('mol/L')
        return collector_conc.to('mol/L').magnitude  # in M

    def calc_hplc_dilute_flow(self,
                              condition: dict,
                              flow_rate: dict,
                              schedule: dict,
                              hplc_ana_conc: float = 0.01,
                              highest_total_speed: float = 1.0,
                              ) -> dict[str, float]:
        """calulate the hplc dilute flow rate and transfer rate for hplc analysis"""

        if "collect_all_time" not in schedule:
            raise KeyError("schedule must contain collect_all_time")
        if "liquid_flow" not in flow_rate:
            raise KeyError("flow_rate must contain liquid_flow")
        # calculate the collector dilute concentration
        collector_conc = self.collector_dilute_conc(condition, flow_rate, schedule, unit_include=True)

        # calculate the hplc analysis flow rate
        hplc_conc = hplc_ana_conc * ureg.mol / ureg.L

        dilute_ratio = collector_conc / hplc_conc
        dilute_ratio = dilute_ratio.to('dimensionless').magnitude
        logger.debug(f"dilute_ratio: {dilute_ratio}")

        if dilute_ratio <= 1:
            logger.warning("the collector concentration is lower than the hplc analysis concentration")
            transfer_rate = highest_total_speed  # * ureg.mL / ureg.min
            dilute_flow = 0.0
        elif dilute_ratio > 11:
            logger.debug("the pump cannot dilute to hplc analysis concentration")
            total_rate = highest_total_speed  # * ureg.mL / ureg.min
            transfer_rate = total_rate / dilute_ratio
            dilute_flow = transfer_rate * (dilute_ratio - 1)
        else:
            transfer_rate = highest_total_speed / 10  # * ureg.mL / ureg.min
            dilute_flow = transfer_rate * (dilute_ratio - 1)

        return {"withdraw_rate": 5.0,
                'transfer_rate': transfer_rate,
                'makeup_flow': dilute_flow,
                'total_hplc_rate': dilute_flow + transfer_rate,
                }

    def calc_hplc_schedule(self,
                           collector_vol: float,
                           anal_flow: dict,
                           ) -> dict:

        """Calculate the hplc schedule for analysis."""
        waste_vol = (collector_vol * 0.15 + self.NEEDLE_UNIT
                     + self.TUBE_NEEDLE_TO_TRANSFERVALVE + self.TRANSFERVALVE)
        analysis_vol = collector_vol * 0.85
        logger.debug(f"waste volume: {waste_vol} ml; analysis volume: {analysis_vol} ml")

        # bumper
        if waste_vol + analysis_vol > self.TRANSFERSYRINGE:
            raise ValueError("the waste volume and analysis volume is larger than the transfer syringe volume")

        analysis_schedule: dict = {
            "withdraw_all": {
                "time": (waste_vol + analysis_vol) / anal_flow["withdraw_rate"],
                "vol": waste_vol + analysis_vol,
                "xfer_flow": anal_flow["withdraw_rate"]},
            "to_waste": {
                "time": waste_vol / anal_flow["transfer_rate"],
                "vol": waste_vol,
                "xfer_flow": anal_flow["withdraw_rate"]},

            "to_dilute": {
                "time": self.TUBE_TRANSFERVALVE_TO_PUMPM / anal_flow["transfer_rate"],
                "vol": self.TUBE_TRANSFERVALVE_TO_PUMPM,
                "xfer_flow": anal_flow["transfer_rate"]},

            "to_hplc": {
                "time": (self.TUBE_PUMPM_TO_HPLCVAVLE + self.HPLCLOOP) / anal_flow["total_hplc_rate"] * 1.2,
                "vol": ((self.TUBE_PUMPM_TO_HPLCVAVLE
                        + self.HPLCLOOP) / anal_flow["total_hplc_rate"] * 1.2) * anal_flow["transfer_rate"],
                "xfer_flow": anal_flow["transfer_rate"]},
        }

        remained_vol = analysis_vol - analysis_schedule["to_dilute"]["vol"] - analysis_schedule["to_hplc"]["vol"]
        logger.debug(f"remained volume: {remained_vol} ml")
        if remained_vol < 0:
            raise ValueError("the analysis volume is larger than the volume for analysis")

        # analysis_schedule["remove_remained"] = remained_vol / dilute_flow["withdraw_rate"]
        analysis_schedule["total_operation"] = {
            "time": sum(value["time"] for value in analysis_schedule.values())}
        return analysis_schedule

if __name__ == "__main__":
    from BV_experiments.Example3_debenzylation.db_doc import SecondDebenzylation, FlowSetupDad

    # max acn_equiv = 1500 (10 mM) after dilution
    concentration = 0.02 * ureg.mol / ureg.L

    # calculate dcm_equiv by acn_equiv
    condition = {'tbn_equiv': 1, 'acn_equiv': 0, 'ddq_equiv': 0.5, 'dcm_equiv': 806,
                 'gas': 'oxygen', 'gl_ratio': 1,
                 'temperature': 28, 'time': 2, 'light_wavelength': '440nm',
                 'light_intensity': 24, 'pressure': 3}

    calculator = DeBnCalculator(setup_vol_dict=FlowSetupDad.physical_info_setup_list,
                                gas="oxygen",
                                sm_info=SecondDebenzylation.SM_info,
                                is_info=SecondDebenzylation.IS_info,
                                component_1=SecondDebenzylation.oxidant_info_1,
                                component_2=SecondDebenzylation.catalyst_info,
                                component_3=SecondDebenzylation.solvent_info_1,
                                component_4=SecondDebenzylation.solvent_info_2,
                                )

    condition["concentration"] = calculator.calc_concentration(condition=condition, unit_include=False)
    # calculate the setting parameters
    logger.debug(f"theoretically concentration: {condition['concentration']}")

    # calculate the operating parameters
    syr_vol, syr_rate = calculator.calc_inj_loop(condition=condition,
                                                 filling_time=1.0 * ureg.min,
                                                 unit_include=True)
    for key, value in syr_vol.items():
        logger.info(f"{key}: {value.to('ml').magnitude} ml")

    syr_vol, syr_rate = calculator.calc_inj_loop(condition=condition,
                                                 filling_time=1.0 * ureg.min,
                                                 unit_include=False)
    logger.info(syr_rate)

    all_flows = calculator.calc_all_flow_rate(condition,
                                              hplc_ana_conc=SecondDebenzylation.hplc_config_info.HPLC_SAMPLE_CONC,
                                              )
    logger.info(f"all flow rate: {all_flows}")

    time_schedule = calculator.calc_exp_schedule(condition, all_flows)
    logger.info(f"time:{time_schedule}")

