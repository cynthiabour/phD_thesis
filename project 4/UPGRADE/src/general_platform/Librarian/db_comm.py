"""All the functions to communication with Librarian"""
import asyncio
import json
import time
from typing import Type, TypeVar
from beanie import init_beanie, PydanticObjectId, Document
from bson import ObjectId
from loguru import logger

# MongoDB driver
from motor.motor_asyncio import AsyncIOMotorClient

# the ExperimentState is used in general for searching the experiment state
from BV_experiments.src.general_platform.Librarian.db_models import ExperimentState

# Define a generic type for Beanie documents
T = TypeVar("T", bound=Document)

class DatabaseMongo:
    """  Establish a Librarian connection  """

    # init create the connection to server and open the relevant collection
    def __init__(self,
                 experiment_document: Type[Document],
                 ctrl_document: Type[Document],
                 database_name: str,
                 collection_name=None,
                 database_uri: str = "mongodb://localhost:27017"
                 ):
        self._uri = database_uri
        # Beanie uses Motor async client under the hood
        self._client = AsyncIOMotorClient(self._uri)
        # self._client = AsyncIOMotorClient(host, port)  #TODO: test!
        self._database = self._client[database_name]
        self._collection = collection_name

        self.exp_document = experiment_document
        # change the collection name
        self.exp_document.Setting.set_collection_name(self._collection) if self._collection is not None else None
        self.ctrl_document = ctrl_document

    async def initialize(self):
        """ This is an asynchronous example, so we will access it from an async function"""
        # Initialize beanie with the Experiment document class and give the MongoDB Librarian name
        await init_beanie(database=self._database,
                          document_models=[self.exp_document])

    def create_experiment(self, doc_class: Type[T], **kwargs) -> T:
        """
        Create a new instance of a given Beanie document class with dynamic attributes.

        Args:
            doc_class (Type[T]): The Beanie Document class to instantiate.
            kwargs: Fields and values for the document.

        Returns:
            T: An instance of the document.
        """
        # Ensure datetime fields are set if not provided
        kwargs.setdefault("created_at", datetime.now())

        # Convert JSON-serializable data (if needed)
        for key, value in kwargs.items():
            if isinstance(value, dict):
                kwargs[key] = json.loads(json.dumps(value))  # Ensures serialization

        return doc_class(**kwargs)

    async def insert_new_exp(self, doc: Document) -> ObjectId:
        """
        Insert a single document into the database.

        Args:
            doc (Document): The document to insert.

        Returns:
            ObjectId: The ObjectId of the inserted document.
        """
        # insert the next experiment wanted to do into the Librarian
        await doc.insert()
        return doc.id

    async def insert_ctrl(self, doc: Document) -> ObjectId:
        """
        Insert a single ctrl into the database.
        :param doc:
        :return:
        """
        await init_beanie(database=self._database,
                          document_models=[self.ctrl_document])
        await doc.insert()  # or doc.save()
        await init_beanie(database=self._database,
                          document_models=[self.exp_document])
        return doc.id  ## type:PydanticObjectId('6404b8ce9ba90b0158406748')

    async def find_lastest_ctrl(self) -> Document:
        """to find the lastest control experiment"""
        await init_beanie(database=self._database,
                          document_models=[self.ctrl_document])
        # Sort the documents by the "created_at" field in descending order
        latest_doc = await self.ctrl_document.find_one(
            sort=[("created_at", -1)])
        await init_beanie(database=self._database,
                          document_models=[self.exp_document])
        return latest_doc

    async def find_exps_by_state(self, exp_state: ExperimentState) -> list[Document]:
        """to  find all data with the same experiment state"""
        return await self.exp_document.find(self.exp_document.exp_state == exp_state).to_list()

    async def find_lastest_suggestion(self) -> dict:
        """to find the lastest suggestion"""
        # Sort the documents by the "created_at" field in descending order
        latest_doc = await self.exp_document.find_one(
            sort=[("created_at", -1)])  # chatGPT -> class: __main__: Experiment
        return dict(latest_doc)

    async def get_experiment(self, identifier: PydanticObjectId) -> Document:
        return await self.exp_document.get(document_id=identifier)

    async def get_finished_experiment_timeout(
            self, identifier: PydanticObjectId,
            timeout: float, check_interval: float = 0.5) -> Document | bool:
        start_time = time.monotonic()
        end_time = start_time + timeout * 60
        while time.monotonic() < end_time:
            exp_state = await self.get_experiment_state(identifier)
            if exp_state == ExperimentState.FINISHED:
                return await self.exp_document.get(document_id=identifier)
            await asyncio.sleep(check_interval * 60)
        return False

    async def get_experiment_state(self, identifier: PydanticObjectId) -> ExperimentState:
        """get the state of an experiment"""
        exp = await self.get_experiment(identifier)
        return exp.exp_state

    async def change_experiment_state(self, identifier: PydanticObjectId, n_state: ExperimentState):
        """change the state of an experiment"""
        exp = await self.exp_document.get(document_id=identifier)
        if exp.exp_state == n_state:
            logger.warning(f"current state of the experiment id:[{identifier}] is already {n_state.name}")
        else:
            exp.exp_state = n_state
            await exp.save()
            logger.info(f"update the experiment state: {n_state}")

    async def load_experiment_param(self, identifier: PydanticObjectId):
        """load all experimental operating parameters"""
        # await self.change_experiment_state(identifier, ExperimentState.RUNNING)
        exp = await self.exp_document.get(document_id=identifier)
        exp.excuted_at = datetime.now()
        await exp.save()
        return exp.exp_condition.model_dump(), exp.inj_loop_flow_rate, exp.flow_rate, exp.time_schedule

    async def update_analysis_result(self, identifier: PydanticObjectId, hplc_results: dict):
        """update the analysis result"""
        # await self.change_experiment_state(identifier, ExperimentState.FINISHED)
        exp = await self.exp_document.get(document_id=identifier)
        # exp.exp_state = ExperimentState.FINISHED
        exp.analysed_at = datetime.now()
        exp.performance_result = json.loads(json.dumps(hplc_results))
        await exp.save()

    async def update_note(self, identifier: PydanticObjectId, **kwargs):
        exp = await self.exp_document.get(document_id=identifier)
        notes = exp.note if exp.note else {}
        for key, value in kwargs.items():
            notes[key] = value
        exp.note = notes
        await exp.save()

    async def retrieve_all_documents(self):
        return await self.exp_document.find({}).to_list()


async def main(DB):
    await DB.initialize()
    new_exp_data = DB.create_experiment(
        CtrlExperiment,  # Pass the Beanie Document class
        exp_code="ctrl001",
        exp_state=ExperimentState.TO_RUN,
        exp_condition=ExpCondRatio(**ctrl_condition),
        exp_category=FirstDebenzylation.exp_description,
        SM_info=FirstDebenzylation.SM_info,
        ddq_info=FirstDebenzylation.oxidant_info_1,
        catalyst_info=FirstDebenzylation.catalyst_info,
        solvent1_info=FirstDebenzylation.solvent_info_1,
        solvent2_info=FirstDebenzylation.solvent_info_2,
        IS_info=FirstDebenzylation.IS_info,
        gas_info=FirstDebenzylation.gas_info,
        # flow_setup=nx.to_dict_of_dicts(FlowSetupDad.G),
        dad_info=FirstDebenzylation.dad_info,
        opt_parameters=Optimize_parameters.config,
        created_at=datetime.now(),
        hplc_result={

        },
        note={"test": "anything"}  # fixme: fix the note
    )
    # a = await DB.insert_new_exp(new_exp_data)
    a = await DB.insert_ctrl(new_exp_data)
    print(a)
    n_note = {"20240306": "re-run same condition due to failing of control."}
    notes = new_exp_data.note if new_exp_data.note else {}
    notes.update(n_note)

    # await DB.change_experiment_state(PydanticObjectId('65e8e3d9815baae75db09c56'), ExperimentState.TO_RUN)
    exp_to_run_list = await DB.find_exps_by_state(ExperimentState.TO_RUN)
    ordered_exp_list = sorted(exp_to_run_list, key=lambda exp: int(exp.exp_code.split("-")[2]))

    print(ordered_exp_list)
    print(ordered_exp_list[-1].exp_code)
    for exp in exp_to_run_list:
        n_note = {"note": "change the optimization range. Restore the previous suggestion to archive.",
                  "old_id": exp.id}
        notes = exp.note if exp.note else {}
        notes.update(n_note)
        exp.note = notes
        await exp.save()


    # sort exps by time
    exps_by_time = sorted(exp_to_run_list, key=lambda exp: exp.analysed_at)

    # get all exps by time
    exps_by_time = await Experiment.find(
        Experiment.analysed_at > datetime.now() - datetime.datetime.timedelta(days=30)).to_list()
    for exp in exps_by_time:
        print(exp.exp_code, exp.exp_state, exp.analysed_at)


if __name__ == "__main__":
    import socket
    import networkx as nx
    from datetime import datetime
    from BV_experiments.Example3_debenzylation.db_doc import (FirstDebenzylation, FlowSetupDad,
                                                              Experiment, CtrlExperiment, ExpCondRatio,
                                                              Optimize_parameters)

    # test
    ctrl_condition = {"tbn_equiv": 6, "acn_equiv": 700, "ddq_equiv": 0.25, "dcm_equiv": 0,
                      "gas": "oxygen", "gl_ratio": 1.0,
                      "temperature": 30, "time": 5,
                      'light_wavelength': "440nm", "light_intensity": 24, "pressure": 3}
    from BV_experiments.Example3_debenzylation.calculator_operating import CalculatorOperating

    Calc = CalculatorOperating(setup_vol_dict=FlowSetupDad.physical_info_setup_list,
                               sm_info=FirstDebenzylation.SM_info,
                               is_info=FirstDebenzylation.IS_info,
                               component_1=FirstDebenzylation.oxidant_info_1,
                               component_2=FirstDebenzylation.catalyst_info,
                               component_3=FirstDebenzylation.solvent_info_1,
                               component_4=FirstDebenzylation.solvent_info_2
                               )
    ctrl_condition["concentration"] = Calc.calc_concentration(condition=ctrl_condition, unit_include=False)

    if socket.gethostname() == '':

        DB = DatabaseMongo(experiment_document=Experiment,
                           ctrl_document=CtrlExperiment,
                           database_name="GL_data_1", database_uri="mongodb://localhost:27017")

    elif socket.gethostname() == '141.14.52.210':
        DB = DatabaseMongo(experiment_document=Experiment,
                           ctrl_document=CtrlExperiment,
                           database_name="GL_data_1",
                           database_uri="mongodb://*:*@141.14.52.210:27017")

    asyncio.run(main(DB))
