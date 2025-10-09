"""
Lev deprotection experiment

for example        RM-deliver(p)                            waste
                           |                                  |
        L-deliver(p) -- loop(v) --- reactor --- BPR --- collector(v) -- vial

"""
import datetime
import asyncio
import time
from loguru import logger

# Flowchem devices
from flowchem.client.client import get_all_flowchem_devices
from BV_experiments.platform_error import PlatformError

# metadata
metadata = {
    "expType": "sugar_reaction",
    "expName": f"whhsu170_lev_deprotection",
    "author": "Wei-Hsin Hsu <wei-hsin.hsu@mpikg.mpg.de>",
    "description": "exp for demonstration"
}

class DeprotectionExperiment:
    """
    DeprotectionExperiment Object
    """
    def __init__(self,
                 devices_info: dict,
                 tube_info: dict,
                 valve_info: dict,
                 sugar_info: dict,
                 metadata: dict = None):

        # self.graph = Graph(graph)

        self.metadata = metadata
        self.devices_info = devices_info
        self.tube_information = tube_info
        self.sugar_information = sugar_info
        self.valve_information = valve_info
        # fixed condition
        self.bpr = 2.8
        self.sugar_concentration = 0.0125  # in M
        self.hydrazine_concentration = 0.15  # in M

        # fixed operation condition
        self.room_temperature = "22°C"
        self.loop_filing_time = 0.5  # in min

        self.devices = get_all_flowchem_devices()
        # specific for this experiment
        try:
            self.hplc_pump = self.devices[self.devices_info["hplc_pump"][0]][self.devices_info["hplc_pump"][1]]
            self.loop_valve = self.devices[self.devices_info["loop_valve"][0]][self.devices_info["loop_valve"][1]]
            self.sugar_pump = self.devices[self.devices_info["sugar_pump"][0]][self.devices_info["sugar_pump"][1]]
            self.hydrazine_pump = self.devices[self.devices_info["hydrazine_pump"][0]][self.devices_info["hydrazine_pump"][1]]
            self.reactor = self.devices[self.devices_info["reactor"][0]][self.devices_info["reactor"][1]]
            self.collect_valve = self.devices[self.devices_info["collect_valve"][0]][self.devices_info["collect_valve"][1]]
            self.r2_power = self.devices["r2"]["Power"]
        except KeyError as e:
            pass
            logger.error(f"Error: {e}")
            raise PlatformError("Some devices are not found")

    def calc_loop_filling(self, equiv_hydrazine: float):
        vol_ratio = equiv_hydrazine / self.hydrazine_concentration * self.sugar_concentration
        sugar_vol = self.tube_information["loop"] / (1 + vol_ratio)
        hydrazine_vol = sugar_vol * vol_ratio
        vol = {"sugar_vol": sugar_vol, "hydrazine_vol": hydrazine_vol}
        rate = {"sugar_rate": sugar_vol / self.loop_filing_time,
                "hydrazine_rate": hydrazine_vol / self.loop_filing_time,
                "total_rate": self.tube_information["loop"] / self.loop_filing_time
                }
        return rate, vol

    def calc_hplc_rate(self, time: float) -> float:
        return self.tube_information["reactor"] / time

    def calc_schedule(self, condition: dict) -> dict[str: float]:
        # calculate the time needed for the experiment
        hplc_rate = self.calc_hplc_rate(condition["time"])

        syr_rate, syr_vol = self.calc_loop_filling(condition["equiv_hydrazine"])

        sched = {
            "pre_run": 1,
            "purge_loop": (self.tube_information["Y_mixer"] +
                           self.tube_information["mixer_to_loop"]) / syr_rate["total_rate"],
            "pre_loop": (self.tube_information["Y_mixer"] +
                         self.tube_information["mixer_to_loop"] + 0.025) / syr_rate["total_rate"],
            "loop_filling": self.loop_filing_time,
            "reaction": condition["time"],
            "to_collect": (self.tube_information["bpr"] +
                           self.tube_information["tube_reactor_to_collector"]) / hplc_rate,
            "collector_to_vial": self.tube_information["tube_collector_to_vial"] / hplc_rate,
            "collect": self.tube_information["loop"] / hplc_rate,
            "purge_reactor": 1,
        }

        # to calculate total time by sum all the value in the sched
        sched["total_time"] = sum(sched.values())

        return sched

    async def initialize(self):
        logger.info("____ initialize all hardware ____")
        # reactor
        self.reactor.put("temperature", params={"temperature": f"22°C", "heating": "true", })

        # syringe/hplc pump
        self.sugar_pump.put("stop")
        self.hydrazine_pump.put("stop")
        self.hplc_pump.put("stop")

        # valve: todo used the new logic???
        self.loop_valve.put("position", params={"position": self.valve_information["loop_valve"]["load"]})
        self.collect_valve.put("position", params={"position": self.valve_information["collector_valve"]["waste"]})
        logger.info("____ all hardware are initialized ____")
        self.r2_power.put("power-on")

    async def stop(self):
        logger.info("____ stop all hardware ____")
        # reactor
        await self.initialize()
        # turn off r2 general
        self.r2_power.put("power-off")
        logger.info("____ all hardware are stopped or shut down____")

    async def run_experiment(self, condition: dict, exp_code: str = ""):
        # create a logger
        exp_name = f"{self.metadata['expName']}-{self.sugar_information['code']}-{exp_code}"

        # logger.add(f"logger/{self.metadata['expName']}-{exp_code}.log")
        logger.add(
            fr"W:\BS-FlowChemistry\People\Wei-Hsin\202405_sugar\logger\{datetime.datetime.now().strftime('%Y%m%d')}-{exp_name}.log")

        logger.info(f"____ Experiment: {exp_name} ____")
        # calculate all operational parameters
        syr_rates, syr_vol = self.calc_loop_filling(condition["equiv_hydrazine"])
        hplc_rate = self.calc_hplc_rate(condition["time"])
        sched = self.calc_schedule(condition)
        logger.debug(f"condition: {condition}")
        logger.debug(f"syringe rates: {syr_rates} in ml/min; syringe volume: {syr_vol} in ml")
        logger.debug(f"hplc rate: {hplc_rate} in ml/min")
        logger.debug(f"schedule: {sched} in min")

        logger.info("____ start running experiment ____")

        # pre-run
        logger.info("____ prepare the system ____")
        self.reactor.put("temperature", params={"temperature": condition["temperature"], "heating": "true", })
        self.hplc_pump.put("infuse", params={"rate": f"{hplc_rate} ml/min"})
        await asyncio.sleep(sched["pre_run"] * 60)

        # check temperature is reach the target
        logger.info("____ check the temperature ____")
        start_check_t = time.monotonic()
        end_check_t = start_check_t + 2 * 60

        while time.monotonic() < end_check_t:
            # check temp (R2)
            if self.reactor.get("temperature").json():
                logger.info("Stable temperature reached!")
                break
            await asyncio.sleep(1)
        else:
            raise PlatformError("Temperature is not reached the target")

        # start prepare reaction mixture in loop
        logger.info("____ prepare reaction mixture ____")
        self.loop_valve.put("position", params={"position": self.valve_information["loop_valve"]["load"]})
        self.sugar_pump.put("infuse", params={"rate": f"{syr_rates['total_rate']/2} ml/min"})
        self.hydrazine_pump.put("infuse", params={"rate": f"{syr_rates['total_rate']/2} ml/min"})
        await asyncio.sleep(sched["purge_loop"] * 60)
        logger.debug("the loop is purged")

        self.sugar_pump.put("infuse", params={"rate": f"{syr_rates['sugar_rate']} ml/min"})
        self.hydrazine_pump.put("infuse", params={"rate": f"{syr_rates['hydrazine_rate']} ml/min"})
        await asyncio.sleep(sched["pre_loop"] * 60)
        await asyncio.sleep(sched["loop_filling"] * 60)
        self.sugar_pump.put("stop")
        self.hydrazine_pump.put("stop")
        logger.debug(f'the loop preparation finished. Start to check the system (temp).')

        # start the experiment
        logger.info("____ start experiment ____")
        self.loop_valve.put("position", params={"position":  self.valve_information["loop_valve"]["inject"]})
        # wait until the experiment is done
        await asyncio.sleep(sched["reaction"] * 60)
        logger.debug("the reaction is done and start coming out of the reactor")

        await asyncio.sleep(sched["to_collect"] * 60)
        # wait until the reaction mixture reach the collector
        logger.info("____ start collecting the reaction mixture ____")
        self.collect_valve.put("position", params={"position":  self.valve_information["collector_valve"]["collect"]})
        await asyncio.sleep(sched["collector_to_vial"] * 60)  # wait until the reaction mixture reach the vial
        await asyncio.sleep(sched["collect"] * 60)
        await asyncio.sleep(sched["collector_to_vial"] * 60)  # pushing all the reaction mixture to the vial

        logger.info("____ finish the collection. start purge the reactor ____")
        # post-run: purge the reactor
        self.collect_valve.put("position", params={"position": self.valve_information["collector_valve"]["waste"]})
        await asyncio.sleep(sched["purge_reactor"] * 60)

        logger.info("____ finish purge. initialize the system ____")
        # stop the experiment
        await self.initialize()
        logger.info("____ finish all procedure ____")
        logger.remove()

if __name__ == "__main__":
    # import the setup information
    from BV_experiments.Example5_lev_deprotection.setup_info import (devices_names_01, tube_information_01,
                                                                     sugar_information_mei, valve_information_01)
    # condition should only include the information that is needed for the experiment. For instance:
    condition = {"time": 5, "temperature": "40°C", "equiv_hydrazine": 3}

    exp_mei = DeprotectionExperiment(devices_info=devices_names_01,
                                     tube_info=tube_information_01,
                                     valve_info=valve_information_01,
                                     sugar_info=sugar_information_mei,
                                     metadata=metadata
                                     )

    asyncio.run(exp_mei.run_experiment(condition, exp_code="real_run_01"))