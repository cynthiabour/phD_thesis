from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import BaseModel, Field

from BV_experiments.src.general_platform.Librarian.db_models import Category, ChemInfo, ChemicalRole, ExperimentState


class Experiment_condition(BaseModel):
    """  experiment condition  """
    concentration: float
    dye_equiv: float
    activator_equiv: float
    quencher_equiv: float
    oxygen_equiv: float
    solvent_equiv: float
    time: float
    light: float
    pressure: float
    temperature: float

# class HPLC_results(BaseModel):
#     """
#     hplc results
#     """
#     result_254: Optional[dict | None]
#     result_215: Optional[dict | None]
#     parsed_result_254: dict = Field(default={}, description="parsed result from result_254")
#     parsed_result_215: dict = Field(default={}, description="pased result from result_215")

class Experiment(Document):
    """"""
    exp_code: str
    exp_state: ExperimentState = Field(default=ExperimentState.TO_RUN, description="state of experiment")

    # experiment parameters
    exp_condition: Experiment_condition

    # information
    exp_category: Category
    SM_info: ChemInfo
    dye_info: Optional[ChemInfo]
    activator_info: Optional[ChemInfo]
    quencher_info: Optional[ChemInfo]
    solvent_info: Optional[ChemInfo]
    IS_info: Optional[ChemInfo]

    # metadata
    inj_loop_flow_rate: dict = Field(default={}, description="Volumes for preparation of reaction mixture")
    # inj_loop_vol: dict = Field(default={}, description="Volumes for preparation of reaction mixture")
    flow_rate: dict = Field(default={}, description="flow Operation of reaction")
    time_schedule: dict = Field(default={}, description="overall time prediction")

    # date information
    created_at: datetime
    excuted_at: Optional[datetime]
    analysed_at: Optional[datetime]

    # experiment result
    hplc_result: Optional[dict]
    note: Optional[dict] = Field(default_factory=dict)

    class Settings:
        # set the pathway of MongoDB collection
        # name = "phenylcyclobutanone-old"
        name = "phenylcyclobutanone"

    @classmethod
    def set_collection_name(cls, collection_name: str):
        cls.name = collection_name

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.note = kwargs

class Experiment_archive(Document):
    # set a free space for any other information
    exp_code: str
    exp_state: ExperimentState = Field(default=ExperimentState.TO_RUN, description="state of experiment")

    # experiment parameters
    exp_condition: Experiment_condition

    # information
    exp_category: Category
    SM_info: ChemInfo
    dye_info: Optional[ChemInfo]
    activator_info: Optional[ChemInfo]
    quencher_info: Optional[ChemInfo]
    solvent_info: Optional[ChemInfo]
    IS_info: Optional[ChemInfo]

    # metadata
    inj_loop_flow_rate: dict = Field(default={}, description="Volumes for preparation of reaction mixture")
    # inj_loop_vol: dict = Field(default={}, description="Volumes for preparation of reaction mixture")
    flow_rate: dict = Field(default={}, description="flow Operation of reaction")
    time_schedule: dict = Field(default={}, description="overall time prediction")

    # date information
    created_at: datetime
    excuted_at: Optional[datetime]
    analysed_at: Optional[datetime]

    # experiment result
    hplc_result: Optional[dict]
    note: Optional[dict] = Field(default_factory=dict)

    class Settings:
        # set the pathway of MongoDB collection
        name = "phenylcyclobutanone-archive"

    @classmethod
    def set_collection_name(cls, collection_name: str):
        cls.name = collection_name

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.note = kwargs

class ControlExperiment(Document):
    """"""
    exp_code: str
    exp_state: ExperimentState = Field(default=ExperimentState.TO_RUN, description="state of experiment")

    # experiment parameters
    exp_condition: Experiment_condition

    # information
    exp_category: Category
    SM_info: ChemInfo
    dye_info: Optional[ChemInfo]
    activator_info: Optional[ChemInfo]
    quencher_info: Optional[ChemInfo]
    solvent_info: Optional[ChemInfo]
    IS_info: Optional[ChemInfo]

    # metadate
    inj_loop_flow_rate: dict = Field(default={}, description="Volumes for preparation of reaction mixture")
    # inj_loop_vol: dict = Field(default={}, description="Volumes for preparation of reaction mixture")
    flow_rate: dict = Field(default={}, description="flow Operation of reaction")
    time_schedule: dict = Field(default={}, description="overall time prediction")

    # date information
    created_at: datetime
    excuted_at: Optional[datetime]
    analysed_at: Optional[datetime]

    # experiment result
    hplc_result: Optional[dict]
    note: Optional[dict] = Field(default_factory=dict)

    class Settings:
        # set the pathway of MongoDB collection
        name = "phenylcyclobutanone-control"

    @classmethod
    def set_collection_name(cls, collection_name: str):
        cls.name = collection_name

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.note = kwargs

class General_info:
    """  save general information of the experiment """
    BV_description = Category(
        name="BV_inflow",
        description="Preforming Baeyer–Villiger oxidation with EosinY in flow"
    )
    SM_info = ChemInfo(
        name="3-phenyl-cyclobutan-1-one",
        formula="C10H10O",
        smile="O=C(C1)CC1C2=CC=CC=C2",
        CAS_nume="52784-31-3",
        MW=146.19,
        chemical_role=ChemicalRole.STARTING_MATERIAL,
        density=1.087,     #1.230,
        batch="WHH115",  # inventory code or synthesis batch TODO: check before real exp
        concentration=0.5,  # 1:1 equiv with toluene  # TODO: check
        dissolve_solvent="toluene"
    )

    dye_info = ChemInfo(
        name="eosin Y disodium salt",
        formula="C20H6Br4Na2O5",
        smile="BrC(C1=O)=CC2=C(C3=C(C(O[Na])=O)C=CC=C3)C4=CC(Br)=C(O[Na])C(Br)=C4OC2=C1Br]",
        CAS_nume="17372-87-1",
        MW=691.85,
        chemical_role=ChemicalRole.CATALYST,
        batch="inventory-3716",  # inventory code
        concentration=0.05,  # Molar concentration
        dissolve_solvent="methanol"
    )
    activator_info = ChemInfo(
        name="boric acid",
        formula="H3BO3",
        smile="OB(O)O",
        CAS_nume="10043-35-3",
        MW=61.83,
        chemical_role=ChemicalRole.ADDITIVE,
        batch="inventory-5792",  # inventory code
        concentration=1.0,  # Molar concentration
        dissolve_solvent="methanol"
    )
    quencher_info = ChemInfo(
        name="N,N-diisopropylethylamine",
        formula="C8H19N",
        smile="CC(C)N(CC)C(C)C",
        CAS_nume="7087-68-5",
        MW=129.24,
        chemical_role=ChemicalRole.ADDITIVE,
        density=0.742,  # {MW in g/mol, density in g/mL}
        batch="inventory-919"  # inventory code
    )
    solvent_info = ChemInfo(
        name="methanol",
        formula="C8H19N",
        smile="CO",
        CAS_nume="67-56-1",
        MW=32.04,
        chemical_role=ChemicalRole.SOLVENT,
        density=0.792,  # {MW in g/mol, density in g/mL}
        batch="lager_pharma"  # inventory code
    )

    # IS_info = ChemInfo(
    #     name="toluene",
    #     formula="C7H8",
    #     smile="CC1=CC=CC=C1",
    #     CAS_nume="108-88-3",
    #     MW=92.141,
    #     density=0.866,  # {MW in g/mol, density in g/mL}
    #     batch="Art-Nr.9558.1" # inventory code
    #     chemical_role = ChemicalRole.INTERNAL_STANDARD
    # )

    IS_info = ChemInfo(
        name="1,3,5-trimethoxybenzol",
        formula="C9H12O3",
        smile="COC1=CC(OC)=CC(OC)=C1",
        CAS_nume="621-23-8",
        MW=168.19,
        density=1.09,  # {MW in g/mol, density in g/mL}
        batch="inventory-4491",  # inventory code
        chemical_role=ChemicalRole.INTERNAL_STANDARD,
        # density="0.5:1",
        dissolve_solvent="toluene",
    )

class HPLCConfig:
    HPLC_FLOW_RATE = "0.25 ml/min"
    HPLC_ELUENT = {"EluentA": "100% water + 0.1% TFA", "EluentB": "100% ACN + 0.1% TFA"}

    HPLC_METHOD = r"D:\Data2q\BV\BV_General_method_r1met_40min_025mlmin_r1.MET"
    HPLC_RUNTIME = 42
    HPLC_GRADIENT = {"time (min.)": "EluentA (%)", 0: 99, 1: 99, 15: 85, 31: 40, 34: 5, 36: 5, 37: 99, 40: 99}
    DAD_METHOD = {"wavelength": {"channel_1": "254 nm", "channel_2": "215 nm", "channel_3": "205 nm"},
                  "bandwidth": "8 nm",
                  "sampling_frequency": "10 Hz",
                  "time_constant": "0.1 s",
                  "integration_time": "100 ms"}
    ASCII_FILE_FORMAT = {"delimiter": "\t", "header": 17,
                         "footer": 0, "skiprows": 0, "skipfooter": 0,
                         "y_axis": "Absorbance [mAu]", "x_axis": "time (min.)",
                         }
    ROI = [10.0, 31.0]  # before [10.0, 30.0]
    # fixme : acid might be 14.91..... 13.09
    PEAK_RT = {"acid": 13.09, "unk_1": 16.43, "ester": 20.27, "lactone": 21.27, "unk_4": 22.64, "SM": 24.33,
               "tmob": 25.88, "tol": 28.25}
    PEAK_RT_2 = {"EY_deg": 17.28, "EY_1": 29.17, "EY_2": 31.26}

    ACCEPTED_SHIFT = 0.22  # TODO: too large....
    BACKGROUD_FILES = {
        "channel_1":  r"16_04_2024_blank_16-Apr-24 3_32_55 AM_149 - DAD 2.1L- Channel 1.txt",
        "channel_2":  r"16_04_2024_blank_16-Apr-24 3_32_55 AM_149 - DAD 2.1L- Channel 2.txt"
    }
    tol_cc = {"254_cc": [0.08539, 0, 0.084, 0], "254_initial_conc": 17.219,
              "215_cc": [.1343, 0, .1027, 0], "215_initial_conc": 12.243, }
    # tol_cc = {"254_cc": [0.095185, -0.00217, 0.070554, -0.02759], "254_initial_conc": 17.219,
    #           "215_cc": [0.118741, 0.174774, 0.096041, 0.117872], "215_initial_conc": 12.243, }
    tmob_cc = {"254_cc": [0.113, 0, 0.106, 0], "254_initial_conc": 10.3518,
               "215_cc": [.0736, 0, .0849, 0], "215_initial_conc": 11.7087}

class optimize_parms:
    # load config
    config = {
        "parameters": [
            # {"name": "concentration", "type": "continuous", "low": 0.010, "high": 1.22},
            {"name": "dye_equiv", "type": "continuous", "low": 0.005, "high": 0.10},
            {"name": "activator_equiv", "type": "continuous", "low": 0.05, "high": 0.50},
            {"name": "quencher_equiv", "type": "continuous", "low": 0.5, "high": 20.0},
            {"name": "oxygen_equiv", "type": "continuous", "low": 1.5, "high": 2.2},
            {"name": "solvent_equiv", "type": "continuous", "low": 1.0, "high": 20.0},  # previously, 15-250
            {"name": "time", "type": "continuous", "low": 4.5, "high": 35},
            # todo: 23 is the high limit  # previously, 1.5-50
            {"name": "light", "type": "continuous", "low": 6.5, "high": 13},
            {"name": "pressure", "type": "continuous", "low": 3.0, "high": 6.0},
            {"name": "temperature", "type": "continuous", "low": 10, "high": 70},
        ],
        "objectives": [
            {"name": "Productivity_1", "goal": "max"},
            # {"name": "Yield_1", "goal": "max"},
            # {"name": "time", "goal": "min"},
            # {"name": "concentration", "goal": "max"},
        ],
    }
