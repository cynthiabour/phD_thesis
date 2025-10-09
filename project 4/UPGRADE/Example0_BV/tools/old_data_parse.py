import json

from typing import Optional
from beanie import init_beanie, Document
from pydantic import Field
from datetime import datetime
from loguru import logger

import pandas as pd

from motor.motor_asyncio import AsyncIOMotorClient
from BV_experiments.src.general_platform.Librarian.db_models import ExperimentState, Category, ChemInfo, Experiment_condition, \
    ChemicalRole


class old_General_info:
    """save general information of the experiment """
    BV_description = Category(name="BV_inflow", description="Preforming Baeyer–Villiger oxidation with EosinY in flow")
    SM_info = ChemInfo(
        name="3-phenyl-cyclobutan-1-one",
        formula="C10H10O",
        smile="O=C(C1)CC1C2=CC=CC=C2",
        CAS_nume="52784-31-3",
        MW=146.19,
        chemcal_role=ChemicalRole.STARTING_MATERIAL,
        density=1.230,
        batch="WHH",  # inventory code or synthesis batch
        concentration=None,  # 1:1 equiv with toluene
        dissolve_solvent=None
    )
    dye_info = ChemInfo(
        name="eosin Y disodium salt",
        formula="C20H6Br4Na2O5",
        smile="BrC(C1=O)=CC2=C(C3=C(C(O[Na])=O)C=CC=C3)C4=CC(Br)=C(O[Na])C(Br)=C4OC2=C1Br]",
        CAS_nume="17372-87-1",
        MW=691.85,
        chemcal_role=ChemicalRole.CATALYST,
        batch="inventory-3716",  # inventory code
        concentration=None,  # Molar concentration
        dissolve_solvent=None
    )
    activator_info = ChemInfo(
        name="boric acid",
        formula="H3BO3",
        smile="OB(O)O",
        CAS_nume="10043-35-3",
        MW=61.83,
        chemcal_role=ChemicalRole.ADDITIVE,
        batch="inventory-5792",  # inventory code
        concentration=None,  # Molar concentration
        dissolve_solvent=None
    )
    quencher_info = ChemInfo(
        name="N,N-diisopropylethylamine",
        formula="C8H19N",
        smile="CC(C)N(CC)C(C)C",
        CAS_nume="7087-68-5",
        MW=129.24,
        chemcal_role=ChemicalRole.ADDITIVE,
        density=0.742,  # {MW in g/mol, density in g/mL}
        batch="inventory-919"  # inventory code
    )
    solvent_info = ChemInfo(
        name="methanol",
        formula="C8H19N",
        smile="CO",
        CAS_nume="67-56-1",
        MW=32.04,
        chemcal_role=ChemicalRole.SOLVENT,
        density=0.792,  # {MW in g/mol, density in g/mL}
        batch="lager_pharma"  # inventory code
    )
    IS_info = ChemInfo(
        name="toluene",
        formula="C7H8",
        smile="CC1=CC=CC=C1",
        CAS_nume="108-88-3",
        MW=92.141,
        density=0.866,  # {MW in g/mol, density in g/mL}
        batch="Art-Nr.9558.1"  # inventory code
    )
    IS_info_2 = ChemInfo(
        name="mesitylene",
        formula="C9H12",
        smile="CC1=CC(=CC(=C1)C)C",
        CAS_nume="108-67-8",
        MW=120.19,
    )
    IS_info_3 = ChemInfo(
        name="1,3,5-trimethoxybenzene",
        formula="C9H12O3",
        smile="COC1=CC(=CC(=C1)OC)OC",
        CAS_nume="621-23-8",
        MW=168.19,
    )
class Old_Experiment(Document):
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
    Solvent_info: Optional[ChemInfo]
    IS_info: Optional[ChemInfo]

    # date information
    created_at: datetime

    # experiment result
    hplc_result: Optional[dict]

    class Settings:
        # set the pathway of MongoDB collection
        name = "phenylcyclobutanone-old"


def calc_solvent_equiv(old_condition: dict) -> float:
    SOLN = {"EY": 0.05, "H3BO3": 1.00}  # in M (mol/L = mmol/ml)
    SUB = {"SM": {"MW": 146.19, "density": 1.230},
           "Tol": {"MW": 92.14, "density": 0.866},
           "DIPEA": {"MW": 129.25, "density": 0.742}}  # {MW in g/mol, density in g/mL}
    SOL = {"MeOH": {"MW": 32.04, "density": 0.792}, "MeCN": {"MW": 41.05, "density": 0.786}}
    # vol_ratio : 1 mmol SM
    vol_ratio_wo_sol = {"SMIS": 0.001 * (SUB["SM"]["MW"] / SUB["SM"]["density"] + SUB["Tol"]["MW"] / SUB["Tol"]["density"]),
                        "Dye": old_condition["dye_equiv"] / SOLN["EY"],
                        "Activator": old_condition["activator_equiv"] / SOLN["H3BO3"],
                        "Quencher": old_condition["quencher_equiv"] * SUB["DIPEA"]["MW"] * 0.001 / SUB["DIPEA"]["density"],
                        }
    solvent_vol = 1 / old_condition["concentration"] - sum(vol_ratio_wo_sol.values())
    return solvent_vol / SOL["MeOH"]["MW"] / 0.001 * SOL["MeOH"]["density"]

def calc_solvent_equiv_save_csv():
    old_data = pd.read_csv(r"W:\BS-FlowChemistry\People\Wei-Hsin\data_0221.csv")

    SOLN = {"EY": 0.05, "H3BO3": 1.00}  # in M (mol/L = mmol/ml)
    SUB = {"SM": {"MW": 146.19, "density": 1.230},
           "Tol": {"MW": 92.14, "density": 0.866},
           "DIPEA": {"MW": 129.25, "density": 0.742}}  # {MW in g/mol, density in g/mL}
    SOL = {"MeOH": {"MW": 32.04, "density": 0.792}, "MeCN": {"MW": 41.05, "density": 0.786}}
    # vol_ratio : 1 mmol SM
    vol_ratio_wo_sol = {
        "SMIS": 0.001 * (SUB["SM"]["MW"] / SUB["SM"]["density"] + SUB["Tol"]["MW"] / SUB["Tol"]["density"]),
        "Dye": old_data["Dye"] / SOLN["EY"],
        "Activator": old_data["Activator"] / SOLN["H3BO3"],
        "Quencher": old_data["Quencher"] * SUB["DIPEA"]["MW"] * 0.001 / SUB["DIPEA"]["density"],
        }
    solvent_vol = 1 / old_data["conc"] - sum(vol_ratio_wo_sol.values())
    old_data["solvent"] =solvent_vol / SOL["MeOH"]["MW"] / 0.001 * SOL["MeOH"]["density"]
    old_data.to_csv(rf'W:\BS-FlowChemistry\People\Wei-Hsin\old_data_data_0221_w_sol.csv',
                    header=True
                    )

async def save_old_data_to_db():
    # Beanie uses Motor async client under the hood
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.BV_data_1, document_models=[Old_Experiment])
    # read in the old data
    old_data = pd.read_csv(r"W:\BS-FlowChemistry\People\Wei-Hsin\old_data_data_0426_w_sol.csv", parse_dates=True)
    old_data_dict = old_data.T.to_dict()
    for x in old_data_dict.items():
        data = x[1]
        condition = {"concentration": data["concentration"],
                     "dye_equiv": data["dye_equiv"],
                     "activator_equiv": data["activator_equiv"],
                     "quencher_equiv": data["quencher_equiv"],
                     "oxygen_equiv": data["oxygen_equiv"],
                     "solvent_equiv": data["solvent_equiv"],
                     "time": data["time"],
                     "light": data["light"],
                     "pressure": data["pressure"],
                     "temperature": data["temperature"],
                     }
        experiment_code = data["Name"]
        state = ExperimentState.FINISHED
        exp_condition = Experiment_condition(**condition)

        if not pd.isna(data["IS"]):
            purse_result = {"acid": data["Acid"], "ester": data["Ester"],
                            "lactone": data["Lactone"], "unk_4": data["Unk_4"], "SM": data["SM"],
                            "Yield_1": data["Yield_1"], "Conversion_1": data["Conv_1"],
                            "Producivity_1": data["Producivity_1"],
                            "Yield_2": data["Yield_2"], "Conversion_2": data["Conv_2"],
                            "Producivity_2": data["Producivity_2"]

                            }
            hplc = HPLC_results(pursed_result_254=purse_result)
            # Beanie documents work just like pydantic models
            new_exp_data = Old_Experiment(exp_code=experiment_code,
                                          exp_state=state,
                                          exp_condition=condition,
                                          exp_category=old_General_info.BV_description,
                                          SM_info=old_General_info.SM_info,
                                          dye_info=old_General_info.dye_info,
                                          activator_info=old_General_info.activator_info,
                                          quencher_info=old_General_info.quencher_info,
                                          Solvent_info=old_General_info.solvent_info,
                                          IS_info=old_General_info.IS_info,
                                          created_at=datetime.now(),
                                          hplc_result=hplc
                                          )
        else:
            purse_result = {"acid": data["Acid"], "ester": data["Ester"],
                            "lactone": data["Lactone"], "unk_4": data["Unk_4"], "SM": data["SM"],
                            "Yield_1": data["Yield_1"], "Conversion_1": data["Conv_1"],
                            "Producivity_1": data["Producivity_1"],
                            }
            hplc = HPLC_results(pursed_result_254=purse_result)
            new_exp_data = Old_Experiment(exp_code=experiment_code,
                                          exp_state=state,
                                          exp_condition=condition,
                                          exp_category=old_General_info.BV_description,
                                          SM_info=old_General_info.SM_info,
                                          dye_info=old_General_info.dye_info,
                                          activator_info=old_General_info.activator_info,
                                          quencher_info=old_General_info.quencher_info,
                                          Solvent_info=old_General_info.solvent_info,
                                          created_at=datetime.now(),
                                          hplc_result=hplc
                                          )

        # insert the next experiment wanted to do into the Librarian
        await new_exp_data.insert()  # or new_exp.save()
        ## type:PydanticObjectId('6404b8ce9ba90b0158406748')
        logger.info(f"save old experiment _id:({new_exp_data.id}) to database!")

def save_to_list():
    old_data = pd.read_csv(r"W:\BS-FlowChemistry\People\Wei-Hsin\old_data_data_0426_w_sol.csv", parse_dates=True)
    old_data_dict = old_data.T.to_dict()
    trained_data = []
    for x in old_data_dict.items():
        data = x[1]
        overall = {"exp_code": data["Name"],
                   "concentration": data["concentration"],
                   "dye_equiv": data["dye_equiv"],
                   "activator_equiv": data["activator_equiv"],
                   "quencher_equiv": data["quencher_equiv"],
                   "oxygen_equiv": data["oxygen_equiv"],
                   "solvent_equiv": data["solvent_equiv"],
                   "time": data["time"],
                   "light": data["light"],
                   "pressure": data["pressure"],
                   "temperature": data["temperature"],
                   "Yield_1": data["Yield_1"], "Conversion_1": data["Conv_1"],
                   "Producivity_1": data["Producivity_1"],
                   "Yield_2": data["Yield_2"], "Conversion_2": data["Conv_2"],
                   "Producivity_2": data["Producivity_2"],
                   }
        trained_data.append(overall)
    return trained_data

if __name__ == "__main__":
    # import json
    old_data = pd.read_csv(r"W:\BS-FlowChemistry\People\Wei-Hsin\old_data_data_0426_w_sol.csv", parse_dates=True)
    result = old_data.to_json(orient="records")
    parsed = json.loads(result)
    # print(json.dumps(parsed, indent=4))
    with open("../training_set", "w") as fp:  #Pickling
        json.dump(parsed, fp, indent=4)



