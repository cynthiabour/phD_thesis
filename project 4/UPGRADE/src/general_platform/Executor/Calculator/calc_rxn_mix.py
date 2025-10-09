"""
This module provides a class for preparing reaction mixtures in chemical experiments.
It includes functionality to calculate reagent volumes, assign reagents to syringes, and compute reaction mixture properties.

Classes:
- CalcRxnMix: Handles the preparation of reaction mixtures,
including volume calculations, syringe assignments, and loop preparation schedules.


Dependencies:
- `networkx`: For graph-based flow system representation.
- `loguru`: For logging.
- `ureg`: Custom unit registry for unit-aware calculations.
- `ChemInfo`, `SyringeInfo`, `ChemicalPhase`: Data models for chemical and syringe information.
"""

import networkx as nx
from loguru import logger

from BV_experiments.src.general_platform import ureg
from BV_experiments.src.general_platform.Librarian.db_models import ChemInfo, SyringeInfo, ChemicalPhase


class CalcRxnMix:
    """
        a class Handles the preparation of reaction mixtures
        Key Methods:
        - find_syringes_before_loop: Identifies syringes reachable before the loop in the flow graph.
        - plt_graph: Visualizes the directed graph representing the flow system.
        - get_syringe_info: Extracts syringe information from the flow graph.
        - calc_all_reagent_vol_ratio: Calculates the volume of all reagents based on their composition and reaction conditions.
        - calc_syr_vol_ratios: Assigns reagents to syringes and calculates their volumes.
        - calc_concentration: Computes the final concentration of the reaction mixture.
        - calc_inj_loop: Calculates the injection loop volumes and rates for reagents.
        - calc_loop_prep_schedule: Generates a schedule for preparing the reaction loop.

        Usage:
        This module is designed to be used in chemical experiment setups where precise preparation of reaction mixtures is required. It supports:
        - Volume and rate calculations for reagents.
        - Syringe assignment based on flow graph properties.
        - Loop preparation scheduling for automated systems.
    """
    def __init__(self,
                 graph: nx.DiGraph,
                 sm_info: ChemInfo,
                 is_info: ChemInfo,
                 component_1: ChemInfo,
                 filling_time: float | ureg.Quantity = 1.0,
                 **kwargs
                 ):
        # initialize the setup information (directed graph)
        self.graph = graph
        # Find all nodes that have a path to "Loop"
        self.nodes_before_loop = nx.ancestors(graph, "Loop")
        # subgraph = graph.subgraph(predecessors)

        # Extract the syringe information
        # self.syringe_dict = {key: value for key, value in setup_dict.items() if isinstance(value, SyringeInfo)}
        self.syringe_dict = self.find_syringes_before_loop()

        # Extract loop information
        self.LOOP: ureg.Quantity = self.graph.nodes["Loop"]["weight"] * ureg.ml

        # Extract the time information
        self.filling_time: float = filling_time

        # Initialize the reagent information
        self.sm_info: ChemInfo = sm_info
        self.is_info: ChemInfo = is_info
        self.component_1: ChemInfo = component_1
        # Dynamically set component_2 to component_4
        for i in range(2, 5):
            setattr(self, f'component_{i}', kwargs.get(f'component_{i}', None))

        self.composition = None
        self._parse_liquid_composition()

    def find_syringes_before_loop(self) -> dict[str, SyringeInfo]:
        """Find all syringes that are reachable before the loop."""

        # Get all nodes that are reachable before "Loop"
        predecessors: set = self.nodes_before_loop

        return {
            node: self.graph.nodes[node]["properties"]
            for node in predecessors
            if node.startswith("Syr")  # Filter only syringes
        }

    def plt_graph(self, graph):
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 6))
        nx.draw(graph, with_labels=True, node_size=2000, node_color="lightblue")
        plt.show()
        # pos = nx.spring_layout(self.graph)
        # nx.draw(self.graph, pos, with_labels=True)
        # plt.show()

    def get_syringe_info(self) -> dict[str, SyringeInfo]:
        """Extract only SyringeInfo from the given dictionary."""
        return self.syringe_dict

    @staticmethod
    def _liquid_component_attr(component: ChemInfo) -> dict[str, str]:
        if component.phase == ChemicalPhase.LIQUID:
            if component.density is None:
                return {
                    "concentration": component.concentration,
                    "dissolve_solvent": component.dissolve_solvent,
                }
            return {
                "density": component.density,
                "MW": component.MW,
            }

    def _parse_liquid_composition(self) -> dict[str: ureg.Quantity]:
        """Extract and process reagent composition details from ChemInfo objects."""
        # Extract the reagent composition
        composition = {
            value.nickname: self._liquid_component_attr(value)
            for attr, value in self.__dict__.items()
            if isinstance(value, ChemInfo)
        }

        # composition = {}
        # for attr, value in self.__dict__.items():
        #     if isinstance(value, ChemInfo):
        #         composition[value.nickname] = self._liquid_component_attr(value)

        # Convert units for relevant keys
        unit_mappings = {
            "density": (ureg.g / ureg.mL),
            "concentration": (ureg.mol / ureg.L),
            "MW": (ureg.g / ureg.mol),
        }

        # Convert the reagent information
        for reagent, attributes in composition.items():
            for key, unit in unit_mappings.items():
                if key in attributes:
                    if isinstance(attributes[key], float):
                        r_attr = attributes[key] * unit
                    else:
                        r_attr = ureg.parse_expression(attributes[key])
                    attributes[key] = r_attr

        logger.debug(composition)
        self.composition: dict[str: ureg.Quantity] = composition
        return composition

    def filter_loop_condition(self, condition: dict) -> dict[str, float]:
        """Filter the condition dictionary to only include reagent equivalents."""
        # the return with include the reagent equivalent (in equiv) (include gas)
        return {key: value for key, value in condition.items() if key.endswith("_equiv")}

    def _specific_equiv_to_vol(self, nickname: str, nickname_equiv: float) -> ureg.Quantity:
        """Calculate specific volume of a reagent based on its composition and equivalent."""

        # Calculate the volume of the reagent based on its composition
        if "density" in self.composition[nickname]:
            # Neat reagents
            vol = (nickname_equiv * ureg.mole *
                   self.composition[nickname]["MW"] / self.composition[nickname]["density"])
        elif "concentration" in self.composition[nickname]:
            # Solution reagents
            vol = (nickname_equiv * ureg.mole /
                   self.composition[nickname]["concentration"])
        else:
            raise ValueError(f"Composition data for '{nickname}' is missing density or concentration.")

        return vol.to("ml")

    def calc_all_reagent_vol_ratio(self, condition: dict) -> dict[str, ureg.Quantity]:
        """Calculate the volume of all reagents based on their composition and reaction conditions."""

        # Extract the reagent composition
        composition = self.composition
        # Extract all reagent equivalent from the condition (include gas)
        equiv_dict = {key: value for key, value in condition.items() if key.endswith("_equiv")}

        # Check if the reagent equivalent is in the condition
        if not equiv_dict:
            raise ValueError("No reagent equivalent found in condition.")

        # add SM to equiv_dict
        equiv_dict["sm_equiv"] = 1
        equiv_dict["is_equiv"] = 1

        vols = {}
        # Calculate the volume of each reagent based on its composition
        for key, value in composition.items():
            if "IS" in key:
                # skip IS
                continue
            if "SM" in key:
                # only calculate the volume of SM
                key = "SM"  # fixme: nickname should be unique "SM-1"
            if f"{key.lower()}_equiv" in equiv_dict:
                vol = self._specific_equiv_to_vol(key, equiv_dict[f"{key.lower()}_equiv"])
                vols[key] = vol

        return vols  # return the volume of all reagents (skip IS)

    def calc_syr_vol_ratios(self, condition: dict) -> dict[str, ureg.Quantity]:
        """assign the reagent to the syringe based on the syringe info."""

        # Compute volume ratios for all reagents
        volume_ratio: dict[str, ureg.Quantity] = self.calc_all_reagent_vol_ratio(condition)

        # Extract the reagent nickname from the syringe details
        syringe_dict: dict[str, SyringeInfo] = self.syringe_dict

        syr_vols = {}

        for syringe, details in syringe_dict.items():
            # Extract the reagent nickname from the syringe details

            nickname = details.contents
            if "SM" in nickname:
                nickname = "SM"

            if nickname in volume_ratio:
                syr_vols[syringe] = {
                    "nickname": nickname,
                    "vol": volume_ratio[nickname]
                }

        return syr_vols

    # fixme
    def calc_concentration(self,
                           condition: dict,
                           unit_include: bool = False) -> ureg.Quantity | float:
        """Calculate the final concentration of the reaction mixture."""
        init_conc = ureg.parse_expression(self.sm_info.concentration)
        vol_ratio = self.calc_all_reagent_vol_ratio(condition)
        syr_vol_ratio = self.calc_syr_vol_ratios(condition)

        # find the one nickname is contain SM
        sm_vol = next(item['vol'] for item in syr_vol_ratio.values() if 'SM' in item['nickname'])
        # Extract the vol values and sum them
        total_vol = sum(item['vol'] for item in syr_vol_ratio.values())
        if unit_include:
            return (init_conc * sm_vol / total_vol).to('mol/L')

        return (init_conc * sm_vol / total_vol).to('mol/L').magnitude  # final concentration in M

    # fixme
    def calc_inj_loop(self,
                      condition: dict,
                      unit_include: bool = False) -> tuple:
        """Calculate the volume of the reagents and the rate of the reagents."""

        # get the total volume of the reagents
        total_volume = self.LOOP.to("ml")

        # Calculate the volume ratio of the reagents through the syringe
        volume_ratio = self.calc_syr_vol_ratios(condition)
        total_vol_ratio = sum(volume_ratio.values())

        # Calculate the volume of all reagents
        vol_ratio = self.calc_all_reagent_vol_ratio(condition)

        # Calculate the rate of all reagents
        rate_ratio = {key: value / self.filling_time for key, value in vol_ratio.items()}
        # Calculate the total infusion rate
        total_infusion_rate = sum(rate_ratio.values())

        return vol_ratio, rate_ratio

    def calc_loop_prep_schedule(self,
                                condition: dict,
                                unit_include: bool = False) -> dict:
        """Calculate the loop preparation schedule."""

        inj_vol, inj_rate = self.calc_inj_loop(condition, unit_include=False)
        total_infusion_rate = sum(inj_rate.values())

        # fixme:
        return {"3_mix": (self.CROSS + self.TUBE_CROSS_TO_CROSS) / (
                inj_rate['SYRINGE3'] + inj_rate['SYRINGE4'] + inj_rate['SYRINGE6']) * 1.2,
                "5_mix": (self.CROSS + self.TUBE_MIXER_TO_LOOP) / total_infusion_rate,
                "delay_filling": 0.025 / total_infusion_rate,
                "fill_loop": self.LOOP / total_infusion_rate * 1.0,
                }

# async def loop_by_2_crosses_by_condition(condition: dict):
#     # original operation method
#     logger.info(f"____ loop preparation ____")
#     # Calculate the volume ratio of the reagents
#     vol_ratio = reagent_vol_ratio(condition)
#     # Calculate the required volume to fill the loop [0.1 mL]
#
#     from BV_experiments.Example0_BV.calc_oper_para import LOOP_VOLUME, FILLING_TIME, total_infusion_rate
#     # calculate the volume of each reagent and the rate of each reagent
#     vol_of_all = {key: value * LOOP_VOLUME / sum(vol_ratio.values()) for key, value in vol_ratio.items()}
#     rate_of_all = {key: value / FILLING_TIME for key, value in vol_of_all.items()}
#
#     # calculate the time required for each step
#     from calc_oper_para import CROSS, TUBE_CROSS_TO_CROSS, TUBE_MIXER_TO_LOOP  # 4 ul, 5 ul, 7 ul
#
#     # t_0 = [0.15, 0.10]
#     t_0_1 = (CROSS + TUBE_CROSS_TO_CROSS) / 3 / (total_infusion_rate / 5)
#     t_0_2 = CROSS / 2 / (total_infusion_rate / 5)
#
#     # prepare the mixture in first cross and tube to the 2nd cross
#     t_1 = (CROSS + TUBE_CROSS_TO_CROSS) / (
#             rate_of_all['Solvent'] + rate_of_all['Activator'] + rate_of_all['Quencher']) * 1.2
#     # prepare the mixture in the 2nd cross and tube to the loop
#     t_2 = (CROSS + TUBE_MIXER_TO_LOOP) / total_infusion_rate
#     t_3 = 0.025 / total_infusion_rate  # default waste, 0.025 ml
#     # filling time calculation
#     t_4 = FILLING_TIME * 1.0  # 1.0 :0.1 ml
#
#     # start the loop preparation
#     with command_session() as sess:
#         # purge the system
#         sess.put(solvent_endpoint + "/pump/infuse",
#                  params={"rate": f"{total_infusion_rate / 5} ml/min", })  # "volume": f" ml"
#         sess.put(activator_endpoint + "/pump/infuse",
#                  params={"rate": f"{total_infusion_rate / 5} ml/min", })  # "volume": f" ml"
#         sess.put(quencher_endpoint + "/pump/infuse",
#                  params={"rate": f"{total_infusion_rate / 5} ml/min", })  # "volume": f" ml"
#         await asyncio.sleep(t_0_1 * 60)
#         sess.put(eosinY_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate / 5} ml/min"})
#         sess.put(SMIS_endpoint + "/pump/infuse", params={"rate": f"{total_infusion_rate / 5} ml/min"}, )
#         await asyncio.sleep(t_0_2 * 60)
#
#         # prepare the reaction mixture
#         logger.debug("start to prepare the reaction mixture")
#         sess.put(solvent_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Solvent']} ml/min"})
#         sess.put(activator_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Activator']} ml/min"})
#         sess.put(quencher_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Quencher']} ml/min"})
#         await asyncio.sleep(t_1 * 60)
#
#         logger.debug("reach 2nd cross")
#
#         sess.put(eosinY_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['Dye']} ml/min"})
#         sess.put(SMIS_endpoint + "/pump/infuse", params={"rate": f"{rate_of_all['SMIS']} ml/min"}, )
#
#         await asyncio.sleep(t_2 * 60)
#         logger.info("start infusing to loop!")
#
#         await asyncio.sleep(t_3 * 60 + 3)
#
#         logger.info(f"START loop filling! at {time.monotonic()}")
#         start_time = time.monotonic()
#         end_time = start_time + t_4 * 60
#
#         # await asyncio.sleep(FILLING_TIME * 1.0 * 60)  # time of filling
#         while time.monotonic() < end_time:
#             logger.debug(f"{end_time - time.monotonic()} sec left.")
#             await asyncio.sleep(1)
#
#         logger.info(f"END loop filling! at {time.monotonic()}")
#         # push rxn mixture in the tube into the loop to reduce the usage of
#         sess.put(SMIS_endpoint + "/pump/stop")
#         sess.put(eosinY_endpoint + "/pump/stop")
#         sess.put(activator_endpoint + "/pump/stop")
#         sess.put(quencher_endpoint + "/pump/stop")
#         sess.put(solvent_endpoint + "/pump/stop")
#         logger.debug(f"finish filling the loop! stop all pump")
#
#         return True


if __name__ == "__main__":
    from BV_experiments.Example3_debenzylation.db_doc import FirstDebenzylation, FlowSetupDad

    # max acn_equiv = 1500 (10 mM) after dilution
    concentration = 0.02 * ureg.mol / ureg.L

    # calculate dcm_equiv by acn_equiv

    condition = {"tbn_equiv": 2, "acn_equiv": 0, "ddq_equiv": 0.5, "dcm_equiv": 2000,
                 "oxygen_equiv": 2.2, "temperature": 28, "time": 5,
                 'light_wavelength': "440nm", "light_intensity": 100, "pressure": 5}

    calculator = CalcRxnMix(graph=FlowSetupDad.G,
                            sm_info=FirstDebenzylation.SM_info,
                            is_info=FirstDebenzylation.IS_info,
                            component_1=FirstDebenzylation.oxidant_info_1,
                            component_2=FirstDebenzylation.catalyst_info,
                            component_3=FirstDebenzylation.solvent_info_1,
                            component_4=FirstDebenzylation.solvent_info_2
                            )

    print(calculator.get_syringe_info())
    print(calculator.calc_all_reagent_vol_ratio(condition))
    print(calculator.calc_syr_vol_ratios(condition))
