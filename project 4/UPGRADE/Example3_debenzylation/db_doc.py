"""
Module: db_doc
---------------
This module defines the document structure for the database used in the debenzylation experiment.
All the specific information for the debenzylation experiment
(experiment conditions, chemical information, flow setup, and optimization parameter) is defined here.


Classes:
- ExpCondEquiv: Defines experiment conditions with equivalence ratios.
- ExpCondRatio: Defines experiment conditions with gas-liquid ratios.
- BaseExperiment: Base class for experiment documents, including metadata and results.
- Experiment: Specific experiment document for debenzylation experiments.
- CtrlExperiment: Control experiment document for debenzylation experiments.
- FirstDebenzylation: Contains general information and setup for the first debenzylation experiment.
- SecondDebenzylation: Contains general information and setup for the second debenzylation experiment.
- Optimize_parameters: Defines optimization parameters for the experiment.
- FlowSetCollection: Represents the flow system setup using a directed graph.
- FlowSetupDad: Represents an alternative flow system setup using a directed graph.

Usage:
This module is designed to be used in the context of chemical experiments, particularly for the debenzylation process.
It provides a structured way to define and manage experiment parameters, flow setups, and optimization configurations.


Dependencies:
- `beanie`: For MongoDB document modeling.
- `pydantic`: For data validation and settings management.
- `networkx`: For graph-based flow system representation.
- `ureg`: Custom unit registry for unit-aware calculations.
- `convert_graph_to_dict`: Utility for graph-to-dictionary conversion.
"""
from typing import Optional
from beanie import Document
from pydantic import BaseModel, Field
from datetime import datetime
import networkx as nx

from BV_experiments.src.general_platform import ureg, convert_graph_to_dict
from BV_experiments.src.general_platform.Librarian.db_models import (Category, ChemInfo, ChemicalRole,
                                                                     ExperimentState, HplcConfig,
                                                                     ChemicalPhase,
                                                                     TubeInfo, SyringeInfo)

"""
https://gryffin.readthedocs.io/en/latest/citation.html
@article{phoenics,
  title = {Phoenics: A Bayesian Optimizer for Chemistry},
  author = {Florian Häse and Loïc M. Roch and Christoph Kreisbeck and Alán Aspuru-Guzik},
  year = {2018}
  journal = {ACS Central Science},
  number = {9},
  volume = {4},
  pages = {1134--1145}
  }
"""


class ExpCondEquiv(BaseModel):
    """  experiment condition  """
    concentration: float
    gas: str
    oxygen_equiv: float
    ddq_equiv: float
    tbn_equiv: float
    acn_equiv: float
    dcm_equiv: float
    time: float
    light_intensity: float
    light_wavelength: str
    pressure: float
    temperature: float


# class HplcResults(BaseModel):
#     """
#     hplc results with uv-vis
#     """
#     result_254: Optional[dict | None]
#     result_215: Optional[dict | None]
#     result_280: Optional[dict | None]
#
#     parsed_result_254: dict = Field(default={}, description="parsed result from result_254")
#     parsed_result_215: dict = Field(default={}, description="parsed result from result_215")
#     parsed_result_280: dict = Field(default={}, description="parsed result from result_280")


class ExpCondRatio(BaseModel):
    """  experiment condition  """
    concentration: float
    gas: str
    gl_ratio: float
    ddq_equiv: float
    tbn_equiv: float
    acn_equiv: float
    dcm_equiv: float
    time: float
    light_intensity: float
    light_wavelength: str
    pressure: float
    temperature: float


class BaseExperiment(Document):
    """base experiment document for debenzylation experiment"""
    exp_code: str
    exp_state: ExperimentState = Field(default=ExperimentState.TO_RUN, description="state of experiment")

    # experiment parameters: fixme
    exp_condition: ExpCondRatio

    # optimize information
    opt_algorithm: str = Field(default="", description="optimize algorithm")
    opt_parameters: dict = Field(default_factory=dict, description="optimize parameters")

    # chem information
    exp_category: Category
    SM_info: ChemInfo
    ddq_info: ChemInfo
    catalyst_info: ChemInfo
    solvent1_info: ChemInfo
    solvent2_info: ChemInfo
    IS_info: ChemInfo
    gas_info: ChemInfo

    flow_setup: dict = Field(default_factory=dict, description="flow setup for graph (w/ tube volume as weight)")
    setup_note: dict = Field(default_factory=dict, description="flow setup details")

    dad_info: dict = Field(default_factory=dict, description="DAD method: channel information")

    # metadata
    inj_loop_flow_rate: dict = Field(default={}, description="Volumes for preparation of reaction mixture")
    inj_loop_vol: dict = Field(default={},
                               description="Volumes for preparation of reaction mixture")  # todo: use to calculate the reset volume in syringe
    flow_rate: dict = Field(default={}, description="flow Operation of reaction")
    time_schedule: dict = Field(default={}, description="overall time prediction")

    # date information
    created_at: datetime
    excuted_at: Optional[datetime] = Field(default=None)
    analysed_at: Optional[datetime] = Field(default=None)

    # experiment result
    analytical_method: str = Field(default="hplc", description="Analytical method")
    analysis_info: dict = Field(default_factory=dict, description="Analysis method")
    performance_result: Optional[dict] = Field(default={}, description="Analysis results")
    note: Optional[dict] = Field(default_factory=dict)


# fixme: new experiment need to manual change it
class Experiment(BaseExperiment):
    class Settings:
        name = "debenzylation_2bn_glucoside"

        @classmethod
        def set_collection_name(cls, collection_name: str):
            cls.name = collection_name


# fixme: new experiment need to manual change it
class CtrlExperiment(BaseExperiment):
    class Settings:
        name = "ctrl_2bn_glucoside"


# class FirstDebenzylation:
#     """  save general information of the experiment """
#
#     exp_description = Category(
#         name="debenzylation_flow",
#         description="Preforming debenzylation with DDQ/TBN catalytic cycle with 440nm in flow"
#     )
#
#     # SM_info = ChemInfo(
#     #     nickname="SM",  # fixme: nickname should be unique "SM-1"
#     #     name="4-methylphenyl 2,3-di-O-benzoyl-4-O-benzyl-6-O-(9-fluorenylmethoxycarbonyl)-1-thio-ß-D-glucopyranoside",
#     #     formula="C49H42O9S",
#     #     smile="CC(C=C1)=CC=C1S[C@H]2[C@H](OC(C3=CC=CC=C3)=O)[C@@H](OC(C4=CC=CC=C4)=O)[C@H](OCC5=CC=CC=C5)[C@@H](COC(OCC6C(C=CC=C7)=C7C8=C6C=CC=C8)=O)O2",
#     #     CAS_nume="",
#     #     MW=str(806.93 * ureg.g / ureg.mol),
#     #     phase=ChemicalPhase.LIQUID,
#     #     chemical_role=ChemicalRole.STARTING_MATERIAL,
#     #     batch="aga_commercial",  # inventory code or synthesis batch
#     #     concentration=str(0.05 * ureg.mol / ureg.L),
#     #     dissolve_solvent="dcm"
#     # )
#     SM_info = ChemInfo(
#         nickname="SM",  # fixme: nickname should be unique "SM-2"
#         name="4-Methylphenyl 2,3-di-O-benzoyl-4-O-benzyl-6-O-(9-fluorenylmethoxycarbonyl)-1-thio-ß-D-glucopyranoside",
#         formula="C44H40O9S",
#         smile="CCS[C@H]1[C@H](OCC2=CC=CC=C2)[C@@H](OC(C3=CC=CC=C3)=O)[C@H](OC(OCC4C(C=CC=C5)=C5C6=C4C=CC=C6)=O)[C@@H](COC(C7=CC=CC=C7)=O)O1",
#         CAS_nume="Glc-2176",
#         MW=str(744.86 * ureg.g / ureg.mol),
#         phase=ChemicalPhase.LIQUID,
#         chemical_role=ChemicalRole.STARTING_MATERIAL,
#         batch="aga_commercial",  # inventory code or synthesis batch
#         concentration=str(0.05 * ureg.mol / ureg.L),
#         dissolve_solvent="dcm"
#     )
#     IS_info = ChemInfo(
#         nickname="IS", # fixme: nickname should be unique "IS-2"
#         name="1,3,5-trimethoxybenzol",
#         formula="C9H12O3",
#         smile="COC1=CC(OC)=CC(OC)=C1",
#         CAS_nume="621-23-8",
#         MW=str(168.19 * ureg.g / ureg.mol),
#         phase=ChemicalPhase.LIQUID,
#         density=str(1.09 * ureg.g / ureg.mL),  # {MW in g/mol, density in g/mL}
#         batch="inventory-4491",  # inventory code
#         chemical_role=ChemicalRole.INTERNAL_STANDARD,
#         dissolve_solvent="dcm",
#     )
#
#     # IS_info = ChemInfo(
#     #     nickname="IS_mei222",
#     #     name="4-methylphenyl 2,3,4,6-trtra-O-acetyl-1-thio-ß-D-glucopyranoside",
#     #     formula="C21H26O9S",
#     #     smile="CC(C=C1)=CC=C1S[C@H]2[C@H](OC(C)=O)[C@@H](OC(C)=O)[C@H](OC(C)=O)[C@@H](COC(C)=O)O2",
#     #     CAS_nume="",
#     #     MW=str(454.5 * ureg.g / ureg.mol),
#     #     phase=ChemicalPhase.LIQUID,
#     #     chemical_role=ChemicalRole.INTERNAL_STANDARD,
#     #     batch="mei_222_batch",  # inventory code or synthesis batch
#     #     concentration=str(0.025 * ureg.mol / ureg.L),
#     #     dissolve_solvent="dcm"
#     # )
#
#     oxidant_info_1 = ChemInfo(
#         nickname="DDQ",
#         name="2,3-dichloro-5,6-dicyano-1,4-benzoquinonee",
#         formula="C8Cl2N2O2",
#         smile="C(#N)C1=C(C(=O)C(=C(C1=O)Cl)Cl)C#N",
#         CAS_nume="84-58-2",
#         MW=str(227.00 * ureg.g / ureg.mol),
#         phase=ChemicalPhase.LIQUID,
#         chemical_role=ChemicalRole.INTERNAL_STANDARD,
#         batch="1440",  # inventory code or synthesis batch
#         concentration=str(0.05 * ureg.mol / ureg.L),
#         dissolve_solvent="acn"
#     )
#
#     catalyst_info = ChemInfo(
#         nickname="TBN",
#         name="tert-butyl nitrite",
#         formula="C4H9NO2",
#         smile="CC(C)(C)ON=O",
#         CAS_nume="540-80-7",
#         MW=str(103.12 * ureg.g / ureg.mol),
#         phase=ChemicalPhase.LIQUID,
#         chemical_role=ChemicalRole.CATALYST,
#         batch="5665",  # inventory code or synthesis batch
#         density=str(0.919 * 0.9 * ureg.g / ureg.mL),  # FIXME: measure density {in mg/uL} * purity
#     )
#
#     solvent_info_1 = ChemInfo(
#         nickname="DCM",
#         name="dichloromethane",
#         formula="CH2Cl2",
#         smile="ClCCl",
#         CAS_nume="75-09-2",
#         MW=str(84.93 * ureg.g / ureg.mol),
#         phase=ChemicalPhase.LIQUID,
#         chemical_role=ChemicalRole.SOLVENT,
#         density=str(1.3266 * ureg.g / ureg.mL),  # {MW in g/mol, density in g/mL}
#         batch="lager"  # inventory code
#     )
#
#     solvent_info_2 = ChemInfo(
#         nickname="ACN",
#         name="acetonitrile",
#         formula="CH3CN",
#         smile="CC#N",
#         CAS_nume="75-05-8",
#         MW=str(41.05 * ureg.g / ureg.mol),
#         phase=ChemicalPhase.LIQUID,
#         chemical_role=ChemicalRole.SOLVENT,
#         density=str(0.786 * ureg.g / ureg.mL),  # {MW in g/mol, density in g/mL}
#         batch="analytical_grade"  # inventory code
#     )
#
#     # gas_info = ChemInfo(
#     #     nickname="O2",
#     #     name="oxygen",
#     #     formula="O2",
#     #     smile="O=O",
#     #     CAS_nume="7782-44-7",
#     #     MW=str(32.00 * ureg.g / ureg.mol),
#     #     phase=ChemicalPhase.GAS,
#     #     chemical_role=ChemicalRole.REAGENT,
#     #     density=str(1.429 * ureg.g / ureg.L),  # (STP, 0°C and 1 atm)
#     # )
#
#     gas_info = ChemInfo(
#         nickname="air",
#         name="air",
#         formula="N2O2",
#         smile="NA",
#         CAS_nume="NA",
#         phase=ChemicalPhase.GAS,
#         MW=str(28.96 * ureg.g / ureg.mol),
#         chemical_role=ChemicalRole.ADDITIVE,
#         density=str(1.204 * ureg.g / ureg.L),  # {MW in g/mol, density in g/mL}
#     )
#
#     dad_info = {"wavelength": {"channel_1": "254", "channel_2": "700", "channel_3": "350", "channel_4": "280"},
#                 "bandwidth": "8",
#                 "integration_time": "75"}
#
#     hplc_config_info = HplcConfig(
#         HPLC_SAMPLE_CONC=0.001,
#         HPLC_COLUMN="YMC Meteoric Core C18 100*2.1 mmID, S-2.7 um 8nm",
#
#         HPLC_FLOW_RATE="0.25 ml/min",
#         HPLC_ELUENT={"EluentA": "100% water + 0.1% TFA", "EluentB": "100% ACN + 0.1% TFA"},
#
#         # HPLC_METHOD = r"D:\Data2q\BV\sugar_E_method_15min_50ACN.met"  # 12 min
#         # HPLC_METHOD=r"D:\Data2q\BV\sugar_E_method_17min_50ACN.met",  # 15 min
#         # HPLC_METHOD=r"D:\Data2q\BV\sugar_E_method_22min_50ACN.met",  # 22 min
#         HPLC_METHOD=r"D:\Data2q\BV\sugar_E_method_20min_50ACN_xiaoyu.met",  # 20 min
#         HPLC_RUNTIME=20,
#         # HPLC_GRADIENT = {"time (min.)": "EluentA (%)", 0: 50, 0.5: 50, 3.0: 5, 6.5: 5, 7.0: 50, 10.0: 50}
#         # the preesure always have ~3 min delay
#         # HPLC_GRADIENT={"time (min.)": "EluentA (%)", 0: 50, 0.5: 50, 5.0: 5, 9.5: 5, 10.5: 50, 13.5: 50},
#         # HPLC_GRADIENT={"time (min.)": "EluentA (%)", 0: 50, 0.5: 50, 5.0: 5, 9.5: 5, 10.5: 50, 13.5: 50},
#         HPLC_GRADIENT={"time (min.)": "EluentA (%)", 0: 50, 0.5: 50, 15.0: 5, 18.0: 5, 18.5: 50},
#         # HPLC_GRADIENT={"time (min.)": "EluentA (%)", 0: 50, 0.5: 50, 18.0: 5, 20.0: 50},
#         ACQUISITION={"wavelength": {"channel_1": "254",
#                                     "channel_2": "215",
#                                     "channel_3": "280",
#                                     "channel_4": ""},
#                      "bandwidth": "8",
#                      "sampling_frequency": "10 Hz",
#                      "time_constant": "0.1 s",
#                      "integration_time": "100 ms",
#                      "detector": "DAD"},
#
#         ASCII_FILE_FORMAT={"delimiter": "\t", "header": 17,
#                            "footer": 0, "skiprows": 0, "skipfooter": 0,
#                            "y_axis": "Absorbance [mAu]", "x_axis": "time (min.)",
#                            },
#         ROI=[2.0, 12],
#         # todo: check current method
#         PEAK_RT={"is": 3.81, "product": 6.90, "side-product": 8.28, "sm": 8.64},
#         PEAK_RT_2={"ddp": 1.21, "unknown": 1.55},
#
#         ACCEPTED_SHIFT=0.22,  # TODO: too large....
#
#         BACKGROUND_FILES={
#             # "channel_1": r"20241002151302_blank - DAD 2.1L- Channel 1.txt",
#             # "channel_2": r"20241002151302_blank - DAD 2.1L- Channel 2.txt",
#             # "channel_3": r"20241002151302_blank - DAD 2.1L- Channel 3.txt",
#             "channel_1": r"whhsu180_ctrl_32_no_prepared_loop - DAD 2.1L- Channel 1.txt",
#             "channel_2": r"whhsu180_ctrl_32_no_prepared_loop - DAD 2.1L- Channel 2.txt",
#             "channel_3": r"whhsu180_ctrl_32_no_prepared_loop - DAD 2.1L- Channel 3.txt",
#
#         },
#         START_RAMP={
#             "time": 0.5,
#             "path": r"D:\Data2q\BV\autostartup_analysis",
#             "method_list": ("autostartup_005_50ACN.MET",
#                             "autostartup_010_50ACN.MET",
#                             "autostartup_015_50ACN.MET",
#                             "autostartup_020_50ACN.MET",
#                             "autostartup_025_50ACN.MET",
#                             )
#         }
#     )


class SecondDebenzylation:
    """  save general information of the experiment """

    exp_description = Category(
        name="debenzylation_flow",
        description="Preforming debenzylation with DDQ/TBN catalytic cycle with 440nm in flow"
    )

    SM_info = ChemInfo(
        nickname="SM",  # fixme: nickname should be unique "SM-2"
        name="4-Methylphenyl 2,3-di-O-benzoyl-4-O-benzyl-6-O-(9-fluorenylmethoxycarbonyl)-1-thio-ß-D-glucopyranoside",
        formula="C44H40O9S",
        smile="CCS[C@H]1[C@H](OCC2=CC=CC=C2)[C@@H](OC(C3=CC=CC=C3)=O)[C@H](OC(OCC4C(C=CC=C5)=C5C6=C4C=CC=C6)=O)[C@@H](COC(C7=CC=CC=C7)=O)O1",
        CAS_nume="Glc-2176",
        MW=str(744.86 * ureg.g / ureg.mol),
        phase=ChemicalPhase.LIQUID,
        chemical_role=ChemicalRole.STARTING_MATERIAL,
        batch="aga_commercial",  # inventory code or synthesis batch
        concentration=str(0.05 * ureg.mol / ureg.L),
        dissolve_solvent="dcm"
    )

    IS_info = ChemInfo(
        nickname="IS",  # fixme: test something else
        name="1,3,5-trimethoxybenzol",
        formula="C9H12O3",
        smile="COC1=CC(OC)=CC(OC)=C1",
        CAS_nume="621-23-8",
        MW=str(168.19 * ureg.g / ureg.mol),
        phase=ChemicalPhase.LIQUID,
        density=str(1.09 * ureg.g / ureg.mL),  # {MW in g/mol, density in g/mL}
        batch="inventory-4491",  # inventory code
        chemical_role=ChemicalRole.INTERNAL_STANDARD,
        dissolve_solvent="dcm",
    )

    oxidant_info_1 = ChemInfo(
        nickname="DDQ",
        name="2,3-dichloro-5,6-dicyano-1,4-benzoquinonee",
        formula="C8Cl2N2O2",
        smile="C(#N)C1=C(C(=O)C(=C(C1=O)Cl)Cl)C#N",
        CAS_nume="84-58-2",
        MW=str(227.00 * ureg.g / ureg.mol),
        phase=ChemicalPhase.LIQUID,
        chemical_role=ChemicalRole.INTERNAL_STANDARD,
        batch="1440",  # inventory code or synthesis batch
        concentration=str(0.05 * ureg.mol / ureg.L),
        dissolve_solvent="acn"
    )

    catalyst_info = ChemInfo(
        nickname="TBN",
        name="tert-butyl nitrite",
        formula="C4H9NO2",
        smile="CC(C)(C)ON=O",
        CAS_nume="540-80-7",
        MW=str(103.12 * ureg.g / ureg.mol),
        phase=ChemicalPhase.LIQUID,
        chemical_role=ChemicalRole.CATALYST,
        batch="5665",  # inventory code or synthesis batch
        # density=str(0.867 * ureg.g / ureg.mL),
        # purity=str(0.9),
        concentration=str(0.075669 * ureg.mol / ureg.L),  # Fixme: dilution 100X (100uL 90%pure TBN + 9.9ml DCM)
    )

    solvent_info_1 = ChemInfo(
        nickname="DCM",
        name="dichloromethane",
        formula="CH2Cl2",
        smile="ClCCl",
        CAS_nume="75-09-2",
        MW=str(84.93 * ureg.g / ureg.mol),
        phase=ChemicalPhase.LIQUID,
        chemical_role=ChemicalRole.SOLVENT,
        density=str(1.3266 * ureg.g / ureg.mL),  # {MW in g/mol, density in g/mL}
        batch="lager"  # inventory code
    )

    solvent_info_2 = ChemInfo(
        nickname="ACN",
        name="acetonitrile",
        formula="CH3CN",
        smile="CC#N",
        CAS_nume="75-05-8",
        MW=str(41.05 * ureg.g / ureg.mol),
        phase=ChemicalPhase.LIQUID,
        chemical_role=ChemicalRole.SOLVENT,
        density=str(0.786 * ureg.g / ureg.mL),  # {MW in g/mol, density in g/mL}
        batch="analytical_grade"  # inventory code
    )

    gas_info = ChemInfo(
        nickname="air",
        name="air",
        formula="N2O2",
        smile="NA",
        CAS_nume="NA",
        phase=ChemicalPhase.GAS,
        MW=str(28.96 * ureg.g / ureg.mol),
        chemical_role=ChemicalRole.ADDITIVE,
        density=str(1.204 * ureg.g / ureg.L),  # {MW in g/mol, density in g/mL}
    )

    # pureO2_info = ChemInfo(
    #     nickname="O2",
    #     name="oxygen",
    #     formula="O2",
    #     smile="O=O",
    #     phase=ChemicalPhase.GAS,
    #     chemical_role=ChemicalRole.REAGENT,
    # )

    dad_info = {"wavelength": {"channel_1": "254", "channel_2": "700", "channel_3": "350", "channel_4": "280"},
                "bandwidth": "8",
                "integration_time": "75"}

    hplc_config_info = HplcConfig(
        HPLC_SAMPLE_CONC=0.001,
        HPLC_COLUMN="YMC Meteoric Core C18 100*2.1 mmID, S-2.7 um 8nm",

        HPLC_FLOW_RATE="0.25 ml/min",
        HPLC_ELUENT={"EluentA": "100% water + 0.1% TFA", "EluentB": "100% ACN + 0.1% TFA"},

        # HPLC_METHOD = r"D:\Data2q\BV\sugar_E_method_15min_50ACN.met"  # 12 min
        # HPLC_METHOD=r"D:\Data2q\BV\sugar_E_method_17min_50ACN.met",  # 15 min
        HPLC_METHOD=r"D:\Data2q\BV\sugar_E_method_20min_50ACN_xiaoyu.met",  # 20 min
        # HPLC_METHOD=r"D:\Data2q\BV\sugar_E_method_22min_50ACN.met",  # 22 min
        HPLC_RUNTIME=20,
        # HPLC_GRADIENT = {"time (min.)": "EluentA (%)", 0: 50, 0.5: 50, 3.0: 5, 6.5: 5, 7.0: 50, 10.0: 50}
        # HPLC_GRADIENT={"time (min.)": "EluentA (%)", 0: 50, 0.5: 50, 5.0: 5, 9.5: 5, 10.5: 50, 13.5: 50},
        HPLC_GRADIENT={"time (min.)": "EluentA (%)", 0: 50, 0.5: 50, 15.0: 5, 18.0: 5, 18.5: 50},
        ACQUISITION={"wavelength": {"channel_1": "254",
                                    "channel_2": "215",
                                    "channel_3": "280",
                                    "channel_4": ""},
                     "bandwidth": "8",
                     "sampling_frequency": "10 Hz",
                     "time_constant": "0.1 s",
                     "integration_time": "100 ms",
                     "detector": "DAD"},

        ASCII_FILE_FORMAT={"delimiter": "\t", "header": 17,
                           "footer": 0, "skiprows": 0, "skipfooter": 0,
                           "y_axis": "Absorbance [mAu]", "x_axis": "time (min.)",
                           },
        ROI=[2.0, 12],
        # todo: check
        PEAK_RT={"is": 3.81, "product": 6.90, "side-product": 8.28, "sm": 8.64},
        PEAK_RT_2={"ddp": 1.21, "unknown": 1.55},

        ACCEPTED_SHIFT=0.22,  # TODO: too large....
        CALIBRATION={
            "cc_is": "is",
            "channel_1_initial_conc": 1.0,  # area_of_sm / area_of_is
            "channel_2_initial_conc": 1.0,
            "channel_3_initial_conc": 1.0,
            "channel_1": {"product": (1, 0), "side-product": (1, 0), "sm": (1, 0)},  # tuple(a, b) = a * x + b
            "channel_2": {"product": (1, 0), "side-product": (1, 0), "sm": (1, 0)},
            "channel_3": {"product": (1, 0), "side-product": (1, 0), "sm": (1, 0)},
        },

        BACKGROUND_FILES={
            # "channel_1": r"20241002151302_blank - DAD 2.1L- Channel 1.txt",  # 15 min (real 12 min)
            # "channel_2": r"20241002151302_blank - DAD 2.1L- Channel 2.txt",
            # "channel_3": r"20241002151302_blank - DAD 2.1L- Channel 3.txt",
            "channel_1": r"whhsu180_ctrl_32_no_prepared_loop - DAD 2.1L- Channel 1.txt",  # 17 min (real 15 min)
            "channel_2": r"whhsu180_ctrl_32_no_prepared_loop - DAD 2.1L- Channel 2.txt",
            "channel_3": r"whhsu180_ctrl_32_no_prepared_loop - DAD 2.1L- Channel 3.txt",
        },
        START_RAMP={
            "time": 0.5,
            "path": r"D:\Data2q\BV\autostartup_analysis",
            "method_list": ("autostartup_005_50ACN.MET",
                            "autostartup_010_50ACN.MET",
                            "autostartup_015_50ACN.MET",
                            "autostartup_020_50ACN.MET",
                            "autostartup_025_50ACN.MET",
                            )
        }
    )


class Optimize_parameters:
    algorithm_package = "BO-gryffin"

    # load config
    config = {
        "parameters": [
            # {"name": "concentration", "type": "continuous", "low": 0.010, "high": 1.22},
            {"name": "ddq_equiv", "type": "continuous", "low": 0.005, "high": 0.10},
            {"name": "tbn_equiv", "type": "continuous", "low": 0.05, "high": 0.50},
            # {"name": "oxygen_equiv", "type": "continuous", "low": 1.5, "high": 2.2},
            # {"name": "g_to_l_ratio", "type": "continuous", "low": 1, "high": 5},
            # {"name": "dcm_equiv", "type": "continuous", "low": 1.0, "high": 20.0},
            # {"name": "acn_equiv", "type": "continuous", "low": 1.0, "high": 20.0},
            {"name": "time", "type": "continuous", "low": 1.0, "high": 10.0},
            # {"name": "light", "type": "continuous", "low": 12, "high": 24},
            # {"name": "pressure", "type": "continuous", "low": 3.0, "high": 6.0},
            {"name": "temperature", "type": "continuous", "low": 0, "high": 70},
        ],
        "objectives": [
            # {"name": "Productivity_1", "goal": "max"},
            {"name": "Yield_1", "goal": "max"},
            # {"name": "time", "goal": "min"},
            # {"name": "concentration", "goal": "max"},
        ],
    }


class FlowSetCollection:
    # Create a directed graph
    G = nx.Graph()
    # Add nodes with weights
    G.add_node("PumpA", weight=0)
    G.add_node("Syr0", weight=0)
    G.add_node("Syr3", weight=0)
    G.add_node("Syr4", weight=0)
    G.add_node("Syr5", weight=0)
    G.add_node("Syr6", weight=0)
    G.add_node("cross_3mix", weight=0.004)
    G.add_node("cross_5mix", weight=0.004)
    G.add_node("Loop", weight=0.5)
    G.add_node('tee_gl', weight=0.0029)
    G.add_node("Reactor", weight=2.886)
    G.add_node("Bpr", weight=0)
    G.add_node("PumpB", weight=0)
    G.add_node('tee_dilu01', weight=0.0029)
    G.add_node("CollectValve", weight=0)  # new
    G.add_node("CollectVial", weight=5.0)  # new
    G.add_node("TransferValve", weight=0)  # new
    G.add_node("TransferSyringe", weight=5.0)  # new
    # G.add_node('Separator', weight=0.5 + 0.788)
    # G.add_node("Dad", weight=0)
    G.add_node("AnalValve", weight=0)
    G.add_node("PumpM", weight=0)
    G.add_node('tee_dilu02', weight=0.0029)
    G.add_node("HplcLoop", weight=0.001)

    # Add an edge with a weight
    G.add_edge("Syr3", "cross_3mix", weight=0)
    G.add_edge("Syr4", "cross_3mix", weight=0)
    G.add_edge("Syr6", "cross_3mix", weight=0)
    G.add_edge("cross_3mix", "cross_5mix", weight=0.007)
    G.add_edge("Syr0", "cross_5mix", weight=0.007)
    G.add_edge("Syr5", "cross_5mix", weight=0.007)
    G.add_edge("cross_5mix", "Loop", weight=0.005)
    G.add_edge("PumpA", "Loop", weight=0)
    G.add_edge("Loop", "tee_gl", weight=0.005)
    G.add_edge("tee_gl", "Reactor", weight=0.079)
    G.add_edge("Reactor", "Bpr", weight=0.110)
    G.add_edge("Bpr", "tee_dilu01", weight=0.008)
    G.add_edge("PumpB", "tee_dilu01", weight=0)
    G.add_edge("tee_dilu01", "CollectValve", weight=0.071)  # new
    G.add_edge("CollectValve", "CollectVial", weight=0.007)  # new
    G.add_edge("CollectVial", "TransferValve", weight=0.09)  # new
    G.add_edge("TransferValve", "TransferSyringe", weight=0)  # new
    G.add_edge("TransferValve", "tee_dilu02", weight=0.385)  # new # fixme: need to change to small diameter
    # G.add_edge("tee_dilu01", "Separator", weight=0.014)
    # G.add_edge("Separator", "Dad", weight=0.007 + 0.016)
    # G.add_edge("Dad", "AnalValve", weight=0.011 + 0.017)
    G.add_edge("AnalValve", "tee_dilu02", weight=0.011)
    G.add_edge("PumpM", "tee_dilu02", weight=0)
    G.add_edge("tee_dilu02", "HplcLoop", weight=0.130)

    # fixme:
    physical_info_setup_list: dict = {
        # "SYRINGE0": [0.25, "TBN", "Hamilton", "2.304 mm ID"],
        "SYRINGE0": [1.0, "TBN", "Hamilton", "4.608 mm ID"],
        "SYRINGE5": [2.5, "SM+IS", "Hamilton", "7.28 mm ID"],
        "SYRINGE3": [10.0, "ACN", "Hamilton", "14.57 mm ID"],
        "SYRINGE4": [2.5, "DDQ", "Hamilton", "7.28 mm ID"],
        "SYRINGE6": [10.0, "DCM", "Hamilton", "14.57 mm ID"],
        "LOOP": [2, "NA", "0.8 mm ID"],
        "CROSS": [0.004],
        "TUBE_CROSS_TO_CROSS": [0.007, "0.10 m", "0.3 mm ID"],
        "TUBE_MIXER_TO_LOOP": [0.005, "0.07 m", "0.3 mm ID"],
        "TUBE_LOOP_TO_MIX_GAS": [0.007, "0.10 m", "0.3 mm ID"],
        "TEE": [0.0029, "P-632"],
        "TUBE_MIX_GAS_TO_REACTOR": [0.079, "0.10 m", "1.0 mm ID"],
        "REACTOR": [1.1, "NA", "1.0 mm ID", "total 3.075 ml - (0.10+0.14)*785.4 (ul/m)"],  # 2.886
        "TUBE_REACTOR_TO_BPR": [0.110, "0.14 m", "1.0 mm ID"],
        "BPR": [0.0],
        "TUBE_BPR_TO_PUMPB": [0.008, "0.10 m", "0.3 mm ID"],
        # "TUBE_PUMPB_TO_SEPARATOR": [0.275, "0.35 m", "1.0 mm ID"],
        # "SEPARATOR": [0.5],
        # "AF2400X": [0.788, "1.52 m", "0.032 inch ID"],
        # "TUBE_AF2400X_TO_DAD": [0.007, "0.10 m", "0.3 mm ID"],
        # "DAD": [0.0],
        # "TUBE_DAD_TO_ANALVALVE": [0.006, "0.08 m", "0.3 mm ID"],
        "TUBE_PUMPB_TO_COLLECTVALVE": [0.071, "1.00 m", "0.3 mm ID"],  # new
        "TUBE_COLLECTVALVE_TO_COLLECTVIAL": [0.007, "0.10 m", "0.3 mm ID"],  # new
        "COLLECTOR": [5.0],  # new
        "NEEDLE_UNIT": [0.055, "0.07 m", "1.0 mm ID"],  # new
        "TUBE_NEEDLE_TO_TRANSFERVALVE": [0.035, "0.50 m", "0.3 mm ID"],  # new
        "TRANSFERVALVE": [0.0],  # new
        "TRANSFERSYRINGE": [5.0],  # new
        "TUBE_TRANSFERVALVE_TO_PUMPM": [0.024, "0.35 m", "0.3 mm ID"],  # new: fixme?
        "TUBE_ANALVALVE_TO_PUMPM": [0, "0.16 m", "0.3 mm ID", "2"],
        "TUBE_PUMPM_TO_HPLCVAVLE": [0.130, "0.165 m", "1.0 mm ID"],
        "HPLCLOOP": [0.001],
        "TUBE_ANALVALVE_TO_IR": [float("Inf"), "", "", "1"],
        "TUBE_ANALVALVE_TO_COLLECT": [float("Inf"), "", "", "3"],
        "TUBE_ANALVALVE_TO_NMR": [float("Inf"), "", "", "4"],
        "TUBE_ANALVALVE_TO_WASTE": [float("Inf"), "", "", "6"],
    }


# A = 0.15 ^2 * 3.14159 = 0.0707 mm^2
# B = 0.5 ^2 * 3.14159 = 0.7854 mm^2

class FlowSetupDad:
    """Flow system setup using a directed graph to represent fluid movement."""
    # Use Directed Graph (DiGraph) instead of an undirected graph
    G = nx.DiGraph()

    # Add nodes with volume weights
    G.add_node("Syringe0", weight=1.0,
               properties=SyringeInfo(volume=1.0, contents="TBN", brand="Hamilton", diameter="4.608 mm ID"))
    G.add_node("Syringe3", weight=10.0,
               properties=SyringeInfo(volume=10.0, contents="ACN", brand="Hamilton", diameter="14.57 mm ID"))
    G.add_node("Syringe4", weight=0,
               properties=SyringeInfo(volume=2.5, contents="DDQ", brand="Hamilton", diameter="7.28 mm ID"))
    G.add_node("Syringe5", weight=0,
               properties=SyringeInfo(volume=2.5, contents="SM+IS", brand="Hamilton", diameter="7.28 mm ID"))
    G.add_node("Syringe6", weight=10.0,
               properties=SyringeInfo(volume=10.0, contents="DCM", brand="Hamilton", diameter="14.57 mm ID"))
    G.add_node("cross_3mix", weight=0.004, properties=TubeInfo(volume=0.004, length="", diameter="", notes=""))
    G.add_node("cross_5mix", weight=0.004, properties=TubeInfo(volume=0.004, length="", diameter="", notes=""))
    G.add_node("Loop", weight=1.5, properties=TubeInfo(volume=1.5, length="NA", diameter="0.8 mm ID"))

    G.add_node("PumpB", weight=0)
    G.add_node('tee_gl', weight=0.0029, properties=TubeInfo(volume=0.0029, length="", diameter="", notes="P-632"))
    G.add_node("Reactor", weight=1.1,
               properties=TubeInfo(volume=1.1, length="3.67 m", diameter="1.0 mm ID",
                                   notes="total 3.075 ml - (0.10+0.14)*785.4 (ul/m)"))  # 2.886
    G.add_node("Bpr", weight=0, properties=TubeInfo(volume=0, length="", diameter="", notes=""))
    G.add_node("PumpA", weight=0)
    G.add_node('tee_dilu01', weight=0.0029, properties=TubeInfo(volume=0.0029, length="", diameter="", notes="P-632"))
    G.add_node('Separator', weight=0.5 + 0.788,
               properties=TubeInfo(volume=0.5 + 0.788, length="1.52 m", diameter="0.032 inch ID",
                                   notes="SEPARATOR+AF2400X"), )
    G.add_node("Dad", weight=0.0024,
               properties=TubeInfo(volume=0.0024, length="", diameter="", notes=""))
    G.add_node("AnalValve", weight=0)
    G.add_node("PumpM", weight=0)
    G.add_node('tee_dilu02', weight=0.0029, properties=TubeInfo(volume=0.0029, length="", diameter="", notes="P-632"))
    G.add_node("HplcLoop", weight=0.001, properties=TubeInfo(volume=0.001, length="", diameter="", notes=""))

    # Add an edge with a weight
    G.add_edge("Syringe3", "cross_3mix", weight=0)
    G.add_edge("Syringe4", "cross_3mix", weight=0)
    G.add_edge("Syringe6", "cross_3mix", weight=0)
    G.add_edge("cross_3mix", "cross_5mix", weight=0.007,
               properties=TubeInfo(volume=0.007, length="0.10 m", diameter="0.3 mm ID"), )

    G.add_edge("Syringe0", "cross_5mix", weight=0)
    G.add_edge("Syringe5", "cross_5mix", weight=0)
    G.add_edge("cross_5mix", "Loop", weight=0.005,
               properties=TubeInfo(volume=0.005, length="0.07 m", diameter="0.3 mm ID"), )

    G.add_edge("PumpA", "Loop", weight=0)
    G.add_edge("Loop", "tee_gl", weight=0.005)
    G.add_edge("tee_gl", "Reactor", weight=0.079,
               properties=TubeInfo(volume=0.079, length="0.10 m", diameter="1.0 mm ID"))
    G.add_edge("Reactor", "Bpr", weight=0.110,
               properties=TubeInfo(volume=0.110, length="0.14 m", diameter="1.0 mm ID"))

    G.add_edge("Bpr", "tee_dilu01", weight=0.008,
               properties=TubeInfo(volume=0.008, length="0.10 m", diameter="0.3 mm ID"))
    G.add_edge("PumpB", "tee_dilu01", weight=0)
    G.add_edge("tee_dilu01", "Separator", weight=0.275,
               properties=TubeInfo(volume=0.275, length="0.35 m", diameter="1.0 mm ID"))
    G.add_edge("Separator", "Dad", weight=0.007,
               properties=TubeInfo(volume=0.007, length="0.10 m", diameter="0.3 mm ID"))
    G.add_edge("Dad", "AnalValve",
               weight=0.006,
               properties=TubeInfo(volume=0.006, length="0.08 m", diameter="0.3 mm ID",
                                   notes="fixme: tube length needs checking"))
    G.add_edge("AnalValve", "tee_dilu02", weight=0.0, )
    G.add_edge("PumpM", "tee_dilu02", weight=0,
               properties=TubeInfo(volume=0, length="0.16 m", diameter="0.3 mm ID", notes="2"))
    G.add_edge("tee_dilu02", "HplcLoop", weight=0.130,
               properties=TubeInfo(volume=0.130, length="0.165 m", diameter="1.0 mm ID", notes=""))

    physical_info_setup_list: dict = {
        # "SYRINGE0": [0.25, "TBN", "Hamilton", "2.304 mm ID"],
        "SYRINGE0": [1.0, "TBN", "Hamilton", "4.608 mm ID"],
        "SYRINGE5": [2.5, "SM+IS", "Hamilton", "7.28 mm ID"],
        "SYRINGE3": [10.0, "ACN", "Hamilton", "14.57 mm ID"],
        "SYRINGE4": [2.5, "DDQ", "Hamilton", "7.28 mm ID"],
        "SYRINGE6": [10.0, "DCM", "Hamilton", "14.57 mm ID"],
        "LOOP": [2, "NA", "0.8 mm ID"],
        "CROSS": [0.004],
        "TUBE_CROSS_TO_CROSS": [0.007, "0.10 m", "0.3 mm ID"],
        "TUBE_MIXER_TO_LOOP": [0.005, "0.07 m", "0.3 mm ID"],
        "TUBE_LOOP_TO_MIX_GAS": [0.007, "0.10 m", "0.3 mm ID"],
        "TEE": [0.0029, "P-632"],
        "TUBE_MIX_GAS_TO_REACTOR": [0.079, "0.10 m", "1.0 mm ID"],
        "REACTOR": [1.1, "3.67 m", "1.0 mm ID", "total 3.075 ml - (0.10+0.14)*785.4 (ul/m)"],  # 2.886
        "TUBE_REACTOR_TO_BPR": [0.110, "0.14 m", "1.0 mm ID"],
        "BPR": [0.0],
        "TUBE_BPR_TO_PUMPB": [0.008, "0.10 m", "0.3 mm ID"],
        "TUBE_PUMPB_TO_SEPARATOR": [0.275, "0.35 m", "1.0 mm ID"],
        "SEPARATOR": [0.5],
        "AF2400X": [0.788, "1.52 m", "0.032 inch ID"],
        "TUBE_AF2400X_TO_DAD": [0.007, "0.10 m", "0.3 mm ID"],
        "DAD": [0.0],
        "TUBE_DAD_TO_ANALVALVE": [0.006, "0.08 m", "0.3 mm ID"],  # fixme: 8.9 cm was cut, the tube need to be check
        "TUBE_ANALVALVE_TO_PUMPM": [0, "0.16 m", "0.3 mm ID", "2"],
        "TUBE_PUMPM_TO_HPLCVAVLE": [0.130, "0.165 m", "1.0 mm ID"],
        "HPLCLOOP": [0.001],
        "TUBE_ANALVALVE_TO_IR": [float("Inf"), "", "", "1"],
        "TUBE_ANALVALVE_TO_COLLECT": [float("Inf"), "", "", "3"],
        # fixme: need to update the tube length
        "TUBE_ANALVALVE_TO_NMR": [float("Inf"), "", "", "4"],
        "TUBE_ANALVALVE_TO_WASTE": [float("Inf"), "", "", "6"],
    }



