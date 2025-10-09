"""
the model of data struction and general information of all experiments
"""
from typing import Optional
from pydantic import BaseModel, Field
import enum
from datetime import datetime

# Define a structure for physical setup information


class TubeInfo(BaseModel):
    """  tube information for experiments  """
    volume: float
    length: str | None
    diameter: str | None
    notes: str | None = None


class SyringeInfo(BaseModel):
    """  syringe information for experiments  """
    volume: float
    contents: str
    brand: str
    diameter: str
    notes: str | None = None


class Category(BaseModel):
    """
    general information of the experiments
    """
    name: str
    description: str


class ChemicalPhase(enum.Enum):
    """enum containing the phases of a chemical"""
    SOLID = "solid"
    LIQUID = "liquid"
    GAS = "gas"
    PLASMA = "plasma"
    UNKNOWN = "unknown"


class ChemicalRole(enum.Enum):
    """enum containing the roles of a chemical"""
    SOLVENT = "solvent"
    CATALYST = "catalyst"
    PRODUCT = "product"
    STARTING_MATERIAL = "starting_material"
    REAGENT = "reagent"  # stoichiometric reagent
    ADDITIVE = "additive"  # acid, base, salts, photo-sensitizer, ligands, desiccants
    BYPRODUCT = "byproduct"
    INTERNAL_STANDARD = "internal_standard"


class ChemInfo(BaseModel):
    """  chemical information for experiments  """
    nickname: str
    name: str
    formula: str
    smile: str
    CAS_nume: str
    MW: str
    phase: ChemicalPhase
    chemical_role: Optional[ChemicalRole] = None
    density: Optional[str] = None
    batch: Optional[str] = None  # code or synthesis batch
    concentration: Optional[str] = None
    dissolve_solvent: Optional[str] = None


class ExperimentState(enum.Enum):
    """  enum containing the possible experiment states  """
    TO_RUN = "run"
    RUNNING = "running"
    ANALYSING = "analysing"
    FINISHED = "finished"
    FAILED = "failed"
    INVALID = "invalid"


class HplcConfig(BaseModel):
    """  hplc configuration  """
    HPLC_SAMPLE_CONC: float
    HPLC_COLUMN: str

    HPLC_FLOW_RATE: str
    HPLC_ELUENT: dict
    HPLC_METHOD: str
    HPLC_RUNTIME: float
    HPLC_GRADIENT: dict
    ACQUISITION: dict
    ASCII_FILE_FORMAT: dict
    ROI: list
    PEAK_RT: dict = Field(default={})
    PEAK_RT_2: dict = Field(default={})
    ACCEPTED_SHIFT: float  # this will be an issue
    CALIBRATION: dict = Field(default={})
    BACKGROUND_FILES: dict = Field(default={})
    START_RAMP: dict = Field(default={})
