"""
this section was built to control the syringe pump for the platform
to prepare the syringe for the next experiment
"""

import asyncio
import time
from loguru import logger

from BV_experiments.src.general_platform.Executor._hw_control import *
from BV_experiments.src.general_platform.Executor._hw_control import command_session
from BV_experiments.src.general_platform.platform_error import PlatformError

async def syr_initilization():
    """initialize the ml600 syringe pump to have 2.5 mL solvent"""
    ...
async def refill_syringe(
        infuse_speed: float,
        speed: float,
        withdraw_vol: float,
        infuse_vol: float,
        waste_vol: float,
        wait_to_finish_infuse: bool = True,
):

    valve_mapping = {"withdraw_p": "syr-front" , "waste_p": "syr-left", "infuse_p": "syr-right"}
    ml600_syr_size = 5.0

    # check the volume is doable
    if withdraw_vol > ml600_syr_size or infuse_vol > ml600_syr_size or waste_vol > ml600_syr_size:
        raise PlatformError(f"the max transfer vol only {ml600_syr_size} ml.")
    if infuse_vol + waste_vol > withdraw_vol:
        raise PlatformError(f"the withdraw volume should be larger than infuse plus waste volume.")


    async def check_pumping(timeout: float = 5.0):
        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:
            is_pumping = sess.get(ml600_endpoint + "/pump/is-pumping").json()
            if not is_pumping:
                return False
            await asyncio.sleep(1)
        raise PlatformError(f"pump is still pumping after {timeout} sec")

    # initialize the syringe
    with command_session() as sess:

        # first around withdraw
        sess.put(ml600_endpoint + "/valve/position", params={"position": valve_mapping["withdraw_p"]})
        sess.put(ml600_endpoint + "/pump/withdraw", params={"rate": f"{speed} ml/min", "volume": f"{withdraw_vol} ml"})
        await asyncio.sleep(60 * withdraw_vol / speed)

        await check_pumping()

        # first around empty air to waste
        sess.put(ml600_endpoint + "/valve/position", params={"position": valve_mapping["waste_p"]})
        sess.put(ml600_endpoint + "/pump/infuse", params={"rate": f"{speed} ml/min", "volume": f"{waste_vol} ml"})
        await asyncio.sleep(60 * waste_vol / speed)

        await check_pumping()

    while True:
        #infuse to prepare loop
        sess.put(ml600_endpoint + "/valve/position", params={"position": valve_mapping["infuse_p"]})
        sess.put(ml600_endpoint + "/pump/infuse", params={"rate": f"{infuse_speed} ml/min", "volume": f"{infuse_vol} ml"})
        if not wait_to_finish_infuse:
            return None

        await asyncio.sleep(60 * infuse_vol / infuse_speed)

        await check_pumping()

        # reinitailize to fullfilled and wait for next round
        sess.put(ml600_endpoint + "/valve/position", params={"position": valve_mapping["withdraw_p"]})
        sess.put(ml600_endpoint + "/pump/withdraw", params={"rate": f"{speed} ml/min", "volume": f"{infuse_vol+waste_vol} ml"})
        await asyncio.sleep(60 * withdraw_vol / speed)

        await check_pumping()

        # empty air to waste
        sess.put(ml600_endpoint + "/valve/position", params={"position": valve_mapping["waste_p"]})
        sess.put(ml600_endpoint + "/pump/infuse", params={"rate": f"{speed} ml/min", "volume": f"{waste_vol} ml"})
        await asyncio.sleep(60 * waste_vol / speed)

        await check_pumping()

#         todo get the position of the sringe
        "get position"
         # async def get_position(self) -> str:
         #        """Get current valve position."""
         #        position = await self.hw_device.get_valve_Position(self.valve_code)
         #        # self.hw_device.last_state.valve[self.valve_number]
         #        return "inlet is %s" % self._reverse_position_mapping[position]
         #
         #    async def set_position(self, position: str) -> bool:
         #        """Move valve to position."""
         #        target_pos = self.position_mapping[position]
         #        await self.hw_device.trigger_key_press(
         #            str(self.valve_code * 2 + int(target_pos)),
         #        )
         #        return True

async def main():
    await refill_syringe(infuse_vol=1.5, infuse_speed=10.0,
                         withdraw_vol=5,
                         waste_vol=2.5, speed=10.0, wait_to_finish_infuse=True)

    # await ml600_syringe_for_loop(0.23, 0.25, 0.25, 0.25, True)
if __name__ == "__main__":
    asyncio.run(main())
