"""
create a common class for gas-liquid flow rate calculation

Module: calc_gl_para
---------------------
This module provides classes and methods for gas-liquid flow rate calculations and related operations.
It includes functionality to calculate flow rates, check parameter feasibility, and prepare systems
for stable operation in chemical experiments.

Classes:
- GLcalculator_db: Handles gas-liquid flow rate calculations and system preparation.
Methods:
- add_units: Utility function to add units to experimental conditions.

Usage:
This module is designed to be used in chemical experiment setups where precise control of gas-liquid
flow rates and system stability is required.

"""
# import networkx as nx
from loguru import logger
from BV_experiments.src.general_platform import ureg

class GLcalculator_db:
    """
        A class for gas-liquid flow rate calculations and system preparation.

        Attributes:
        - setup_dict (dict): Dictionary containing setup volume information.

        Methods:
        - calc_gas_liquid_flow_rate: Calculates total, liquid, and gas flow rates.
        - calc_stable_system: Prepares the system for stable operation.
        - calc_rxn_flow: Calculates flow rates for a reaction.
        - calc_all_flow_rate: Calculates all flow rates, including dilution and makeup flows.
        - check_param_doable: Checks if the operating parameters are within feasible limits.
    """

    def __init__(
            self,
            setup_vol_dict: dict,
            gas: str,
    ):
        """
        Initializes the GLcalculator_db with setup volume information.

        Args:
        - setup_vol_dict (dict): Dictionary containing setup volume information.
        """
        self.setup_dict = setup_vol_dict
        self.gas = gas

        # set the setup volume as attributes
        for key, value in setup_vol_dict.items():
            # get the first value of the list (volume) as the attribute
            setattr(self, key, value[0])

    def calc_gas_liquid_flow_rate(self,
                                  exp_cond: dict
                                  ) -> dict:
        """
        Calculates total, liquid, and gas flow rates for the reaction.
        with the experimental condition "oxygen_equiv" or "gl_ratio"
        Args:
        - condition (dict): Experimental conditions.

        Returns:
        - dict: Flow rates including total, liquid, and gas flows.
        """

        Oxygen_volume_per_mol = 22.4  # in 1.01 bar  P1*V1 = P2*V2

        total_flow_rate = self.REACTOR / exp_cond["time"]  # ml/min

        # check the oxygen_equiv or gl_ratio
        if "oxygen_equiv" not in exp_cond and "gl_ratio" not in exp_cond:
            logger.warning(f"oxygen_equiv or gl_ratio not found in condition, use 1:1 ratio")
            exp_cond["gl_ratio"] = 1.0  # default to 1:1 ratio

        if "oxygen_equiv" in exp_cond:

            conc = exp_cond["concentration"]  # in M

            # setting flow rate of liquid and gas (in ml/min)
            if self.gas == "O2" or self.gas == "oxygen":
                # calculate the volume ratio of gas to liquid before compression
                vol_ratio_GtoL = Oxygen_volume_per_mol * conc * exp_cond["oxygen_equiv"]

            elif self.gas == "air":
                vol_ratio_GtoL = Oxygen_volume_per_mol * conc * exp_cond["oxygen_equiv"] * 5  # 1/5 of air content O2
            else:
                raise ValueError(f"Unsupported gas type: {self.gas}. Supported gases are 'O2', 'oxygen', and 'air'.")

            compressed_G_vol = vol_ratio_GtoL / exp_cond["pressure"]
            set_liquid_flow: float = total_flow_rate / (1 + compressed_G_vol)
            set_gas_flow: float = set_liquid_flow * vol_ratio_GtoL

        elif "gl_ratio" in exp_cond:
            # this ratio is the vol ratio of gas to liquid after compression
            set_liquid_flow: float = total_flow_rate / (1 + exp_cond["gl_ratio"]) * 1
            set_gas_flow: float = total_flow_rate / (1 + exp_cond["gl_ratio"]) * exp_cond[
                "gl_ratio"] * exp_cond["pressure"]

        return {"total_flow": total_flow_rate,
                "liquid_flow": set_liquid_flow,
                "gas_flow": set_gas_flow,
                }

    def calc_stable_system(self,
                           exp_cond: dict,
                           gl_flow: dict | None,
                           ) -> dict:
        """
        Prepares the system for stable operation by setting gas/liquid ratios.
        Fill the reactor with the correct gas/liquid ratio after set to the new pressure
        in order the system stablilty influence the overall slug.

        Args:
        - condition (dict): Experimental conditions.
        - gl_flow (dict | None): Gas-liquid flow rates.

        Returns:
        - dict: Prepared system parameters:{'pre_liquid_flow', 'pre_gas_flow', 'pre_run_time'}
        """
        if gl_flow is None:
            gl_flow = self.calc_gas_liquid_flow_rate(exp_cond)

        ratio_gas_to_liquid = gl_flow["gas_flow"] / gl_flow["liquid_flow"]

        max_pumpA = 2
        max_O2MFC = 5
        # the limit 4.5 ml/min pumpA; 10 ml/min O2, but separation poor
        time_g = max_O2MFC / gl_flow["gas_flow"]
        time_l = max_pumpA / gl_flow["liquid_flow"]

        # to check if run flow rate are larger than max gas/liquid limit...

        if time_g <= 1 or time_l <= 1:  # each of them is less than means setting flow rate is faster than max_pre_run
            # time required to fill the reactor (residence time) + the area before light
            fill_system = self.TUBE_MIX_GAS_TO_REACTOR / gl_flow["total_flow"] + exp_cond["time"]

            prep_sys = {"pre_liquid_flow": gl_flow["liquid_flow"],
                        "pre_gas_flow": gl_flow["gas_flow"],
                        "pre_run_time": fill_system * 1.1}
        else:
            if time_g <= time_l:  # time_g is smaller: gas_flow reach the maximum limitation....
                pre_liquid_flow = max_O2MFC / ratio_gas_to_liquid
                req_time = (self.TUBE_MIX_GAS_TO_REACTOR + self.REACTOR) / (max_O2MFC / exp_cond["pressure"]
                                                                            + pre_liquid_flow)

                prep_sys = {"pre_liquid_flow": pre_liquid_flow,
                            "pre_gas_flow": max_O2MFC,
                            "pre_run_time": req_time * 1.1}
            else:
                pre_gas_flow = max_pumpA * ratio_gas_to_liquid
                req_time = (self.TUBE_MIX_GAS_TO_REACTOR + self.REACTOR) / (pre_gas_flow / exp_cond["pressure"]
                                                                            + max_pumpA)
                prep_sys = {"pre_liquid_flow": max_pumpA,
                            "pre_gas_flow": pre_gas_flow,
                            "pre_run_time": req_time * 1.1}  # min

        if prep_sys["pre_run_time"] < 2.0:  # todo: test the minimum time (before 5.0)
            logger.debug(f"original pre_run_time {prep_sys['pre_run_time']}")
            prep_sys["pre_run_time"] = 2.0
        return prep_sys

    def calc_rxn_flow(self, condition: dict):
        """calculate the flow rate for the reaction"""
        gl_flow = self.calc_gas_liquid_flow_rate(condition)
        pre_run = self.calc_stable_system(condition, gl_flow)

        return {"total_flow": gl_flow["total_flow"],
                "liquid_flow": gl_flow["liquid_flow"],
                "gas_flow": gl_flow["gas_flow"],
                "pre_liquid_flow": pre_run["pre_liquid_flow"],
                "pre_gas_flow": pre_run["pre_gas_flow"],
                }

    def calc_all_flow_rate(self,
                           condition: dict,
                           bf_sep_rate: float = 1.0,  # in ml/min
                           hplc_ana_conc: float | None = 0.01,  # in M
                           ) -> dict:
        """
        Calculate the dilute flow rate for seperator and makeup flow rate for hplc
        """
        gl_flow = self.calc_gas_liquid_flow_rate(condition)
        pre_run = self.calc_stable_system(condition, gl_flow)

        conc = condition["concentration"]  # todo: change to use pint
        set_liquid_flow = gl_flow["liquid_flow"]

        # DILUTE_VOL = 3  # ml
        # dilute pumpM to increase the flow rate to 1 ml/min
        time_of_dilution = 13.64  # DILUTE_VOL / LOOP_VOLUME  # still 13.64 time

        if bf_sep_rate > set_liquid_flow:
            dilute_flow = bf_sep_rate - set_liquid_flow
            if dilute_flow > set_liquid_flow * time_of_dilution:  # DILUTE_VOL ~ 5 # ml
                logger.warning(
                    f"the rate of 1st pump is {dilute_flow / set_liquid_flow} times of rate of liquid. Change to {time_of_dilution:.2f} times")
                dilute_flow = set_liquid_flow * time_of_dilution
                rate_after_1st_pump = set_liquid_flow * (1 + time_of_dilution)
            else:
                rate_after_1st_pump = bf_sep_rate
        else:
            dilute_flow = 0
            rate_after_1st_pump = set_liquid_flow

        dilute_factor_1st_pump = set_liquid_flow / rate_after_1st_pump
        logger.debug(f"concentration after diluted by 1st pump: {conc * dilute_factor_1st_pump} M")

        # makeup_solvent flow rate (in ml/min)
        # ANAL_CONC = 0.010   # M

        # if the overall volume flow into the camber is larger than the seperator dilute factor will be 1
        dilute_factor_seperator = 1  # 0.3
        logger.debug(f"current dilute_factor_seperator set {dilute_factor_seperator}")
        # dilute_factor_seperator = cal_dilute_factor_sep(rate_after_1st_pump)
        conc_aft_sep = conc * dilute_factor_1st_pump * dilute_factor_seperator
        logger.debug(f"concentration after seperator: {conc_aft_sep} M")

        all_flow = {"total_flow": gl_flow["total_flow"],
                    "liquid_flow": set_liquid_flow,
                    "gas_flow": gl_flow["gas_flow"],
                    "pre_liquid_flow": pre_run["pre_liquid_flow"],
                    "pre_gas_flow": pre_run["pre_gas_flow"],
                    "dilute_flow_bf_seperator": dilute_flow,
                    "bf_sep_rate": rate_after_1st_pump,
                    }

        if hplc_ana_conc is None:
            return all_flow

        if conc_aft_sep > hplc_ana_conc:
            makeup_flow = conc_aft_sep * rate_after_1st_pump / hplc_ana_conc - rate_after_1st_pump
        else:
            logger.warning(f"concentration after diluted by 1st pump ({conc_aft_sep}) is already too diluted.")
            makeup_flow = 0

        all_flow["makeup_flow_for_hplc"] = makeup_flow
        all_flow["flow_to_hplc"] = rate_after_1st_pump + makeup_flow
        return all_flow


# class CalcGLFlow: # fixme
#     """
#     a class for gas-liquid flow rate calculations and system preparation.
#
#     Key Methods:
#     - find_devices_before_reactor: Identifies devices reachable before the reactor in the flow graph.
#     - plt_graph: Visualizes the directed graph representing the flow system.
#     - get_device_info: Extracts device information from the flow graph.
#     - calc_gas_liquid_flow_rate: Calculates total, liquid, and gas flow rates based on experimental conditions.
#     - calc_stable_system: Prepares the system for stable operation by setting gas-liquid ratios.
#     - calc_all_flow_parameters: Calculates all flow parameters, including dilution and makeup flows.
#
#     Usage:
#     This module is designed to be used in chemical experiment setups where precise control of gas-liquid flow rates and system stability is required. It supports:
#     - Flow rate calculations for gas and liquid phases.
#     - Device assignment based on flow graph properties.
#     - System preparation for stable operation.
#     """
#     def __init__(self,
#                  graph: nx.DiGraph,
#                  reactor_volume: float | ureg.Quantity,
#                  max_gas_flow: float | ureg.Quantity = 5.0,
#                  max_liquid_flow: float | ureg.Quantity = 2.0,
#                  **kwargs
#                  ):
#         # Initialize the setup information (directed graph)
#         self.graph = graph
#         # Find all nodes that have a path to "Reactor"
#         self.nodes_before_reactor = nx.ancestors(graph, "Reactor")
#
#         # Extract the device information
#         self.device_dict = self.find_devices_before_reactor()
#
#         # Reactor volume
#         self.REACTOR: ureg.Quantity = reactor_volume * ureg.ml
#
#         # Maximum flow rates
#         self.max_gas_flow: ureg.Quantity = max_gas_flow * ureg("ml/min")
#         self.max_liquid_flow: ureg.Quantity = max_liquid_flow * ureg("ml/min")
#
#     def find_devices_before_reactor(self) -> dict[str, DeviceInfo]:
#         """Find all devices that are reachable before the reactor."""
#         predecessors: set = self.nodes_before_reactor
#         return {
#             node: self.graph.nodes[node]["properties"]
#             for node in predecessors
#             if node.startswith("Device")  # Filter only devices
#         }
#
#     def plt_graph(self, graph):
#         import matplotlib.pyplot as plt
#         plt.figure(figsize=(10, 6))
#         nx.draw(graph, with_labels=True, node_size=2000, node_color="lightblue")
#         plt.show()
#
#     def get_device_info(self) -> dict[str, DeviceInfo]:
#         """Extract only DeviceInfo from the given dictionary."""
#         return self.device_dict
#
#     def calc_gas_liquid_flow_rate(self, condition: dict) -> dict[str, ureg.Quantity]:
#         """Calculate total, liquid, and gas flow rates based on experimental conditions."""
#         total_flow_rate = self.REACTOR / condition["time"]  # ml/min
#
#         if "oxygen_equiv" in condition:
#             gas_flow = total_flow_rate * condition["oxygen_equiv"] / (1 + condition["oxygen_equiv"])
#             liquid_flow = total_flow_rate - gas_flow
#         elif "gl_ratio" in condition:
#             gas_flow = total_flow_rate / (1 + 1 / condition["gl_ratio"])
#             liquid_flow = total_flow_rate - gas_flow
#         else:
#             raise ValueError("Condition must include either 'oxygen_equiv' or 'gl_ratio'.")
#
#         return {
#             "total_flow": total_flow_rate.to("ml/min"),
#             "liquid_flow": liquid_flow.to("ml/min"),
#             "gas_flow": gas_flow.to("ml/min")
#         }
#
#     def calc_stable_system(self, condition: dict, gl_flow: dict | None = None) -> dict[str, ureg.Quantity]:
#         """Prepare the system for stable operation by setting gas-liquid ratios."""
#         if gl_flow is None:
#             gl_flow = self.calc_gas_liquid_flow_rate(condition)
#
#         gas_to_liquid_ratio = gl_flow["gas_flow"] / gl_flow["liquid_flow"]
#
#         time_g = self.max_gas_flow / gl_flow["gas_flow"]
#         time_l = self.max_liquid_flow / gl_flow["liquid_flow"]
#
#         if time_g <= 1 or time_l <= 1:
#             pre_run_time = self.REACTOR / gl_flow["total_flow"]
#         else:
#             pre_run_time = max(time_g, time_l)
#
#         return {
#             "pre_liquid_flow": gl_flow["liquid_flow"],
#             "pre_gas_flow": gl_flow["gas_flow"],
#             "pre_run_time": max(pre_run_time, 2.0)  # Minimum pre-run time of 2 minutes
#         }
#
#     def calc_all_flow_parameters(self, condition: dict, bf_sep_rate: float = 1.0, hplc_ana_conc: float | None = 0.01) -> dict[str, ureg.Quantity]:
#         """Calculate all flow parameters, including dilution and makeup flows."""
#         gl_flow = self.calc_gas_liquid_flow_rate(condition)
#         pre_run = self.calc_stable_system(condition, gl_flow)
#
#         dilute_flow = max(0, bf_sep_rate - gl_flow["liquid_flow"])
#         makeup_flow = max(0, (hplc_ana_conc * dilute_flow) / gl_flow["liquid_flow"] - dilute_flow)
#
#         return {
#             "total_flow": gl_flow["total_flow"],
#             "liquid_flow": gl_flow["liquid_flow"],
#             "gas_flow": gl_flow["gas_flow"],
#             "pre_liquid_flow": pre_run["pre_liquid_flow"],
#             "pre_gas_flow": pre_run["pre_gas_flow"],
#             "dilute_flow": dilute_flow * ureg("ml/min"),
#             "makeup_flow": makeup_flow * ureg("ml/min")
#         }


def add_units(condition: dict) -> dict:
    condition_unit = dict()

    condition_unit.update({key: value for key, value in condition.items() if "equiv" in key})
    condition_unit.update(
        {"concentration": condition["concentration"] * ureg("mol/l")} if "concentration" in condition else {})
    condition_unit.update({"time": condition["time"] * ureg("min")} if "time" in condition else {})
    condition_unit.update({"wavelength": ureg(condition["wavelength"])} if "wavelength" in condition else {})
    condition_unit.update({"light": condition["light"] * ureg("W")} if "light" in condition else {})
    condition_unit.update({"pressure": condition["pressure"] * ureg("bar")} if "pressure" in condition else {})
    condition_unit.update({"temperature": condition["temperature"] * ureg.degC} if "temperature" in condition else {})

    return condition_unit


if __name__ == "__main__":
    exp_id = "test"
    old_condition = {'concentration': 0.3, 'oxygen_equiv': 2, 'time': 5,
                     'wavelength': "440nm", 'light': 24, 'pressure': 3, 'temperature': 52, }
    new_condition = {'concentration': 0.3, 'time': 5,
                     'wavelength': "440nm", 'light': 24, 'pressure': 3, 'temperature': 52, }

    from BV_experiments.Example3_debenzylation.db_doc import FlowSetupDad
    from BV_experiments.Example3_debenzylation.db_doc import SecondDebenzylation

    calculator = GLcalculator_db(FlowSetupDad.physical_info_setup_list,
                                 SecondDebenzylation.gas_info.nickname)
    flow = calculator.calc_gas_liquid_flow_rate(old_condition)
    print(flow)
    # print(calculator.check_param_doable(flow))
    sys = calculator.calc_stable_system(old_condition, flow)
    print(sys)
