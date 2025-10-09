"""
remote control hplc
"""

# This could become a mess...
# what needs to be done is switch the lamps on, which works over serial.
# the rest is just sending commands to the console, possibly also to another machine

# https://www.dataapex.com/documentation/Content/Help/110-technical-specifications/110.020-command-line-parameters/110.020-command-line-parameters.htm?Highlight=command%20line

import tenacity
import subprocess
import asyncio
from typing import Union
from pathlib import Path
from loguru import logger
from collections import deque


command_queue = deque()


class ClarityExecutioner:
    """

    """
    command_prepend = 'claritychrom.exe'

    def __init__(self):
        pass


    async def exectute_forever(self):
        while True:
            if len(command_queue) > 0:
                self.execute_command(command_queue.pop())
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(1)

    def execute_command(self, command: str, folder_of_executable: Union[Path, str] = r'C:\claritychrom\bin\\'):
        prefix = 'claritychrom.exe'
        # sanitize input a bit
        if command.split(' ')[0] != prefix:
            command = folder_of_executable + prefix + ' ' + command
            print(f"command line for claritychrom: {command}")
        try:
            x = subprocess
            x.run(command, shell=True, capture_output=False, timeout=3)
        except x.TimeoutExpired:
            print('Damn, Subprocess')

class Async_Listener:

    def __init__(self, port, allowed_client='192.168.10.107', host_ip='192.168.10.11'):
        self.port = port
        self.allowed_client = allowed_client
        self.host_ip = host_ip

    async def initialize(self):
        self.server = await asyncio.start_server(self.get_commands, host=self.host_ip, port=self.port)
        async with self.server:
            print(f"start to listening from {self.host_ip}!")
            await self.server.serve_forever()

    async def accept_new_connection(self, reader, writer):
        address, conn = writer.get_extra_info('peername')
        print(f"Conneted by {(address, conn)}")
        if address == self.allowed_client:
            # if below code is executed, that means the sender is connected
            print(f"[+] {address} succeed to connected.")
            data = await reader.read(1024)
            if not data:
                # TODO: data could be ""?
                print("empty string was received!")
                writer.close()
                await writer.wait_closed()
                return
            request = data.decode('utf-8')
            print(f"Received {request!r}")
            writer.close()
            await writer.wait_closed()
            print("Close the connection")
            return request
        else:
            print(f'nice try {address}')
            writer.close()
            await writer.wait_closed()
            return

    async def get_commands(self, reader, writer):
        request = await self.accept_new_connection(reader, writer)
        print(f"request: {request}")
        find_equal = request.find("=")
        if find_equal != -1:
            command_queue.append(request)
            await asyncio.sleep(1)
        else:
            import logging
            logging.warning(f"{request}")
        await asyncio.sleep(1)
        print('listening')

# Todo should have a command constructor dataclass, would be more neat. For now, will do without to get it running asap
class Async_ClarityExecutioner:
    """ This needs to run on the computer having claritychrom installed, except for one uses the same PC. However,
    going via socket and localhost would also work, but seems a bit cumbersome.
    open up server socket. Everything coming in will be prepended with claritychrom.exe (if it is not already)"""
    command_prepend = 'claritychrom.exe'

    def __init__(self, port, allowed_client='192.168.10.107', host_ip='192.168.10.11'):
        self.port = port
        self.allowed_client = allowed_client
        self.host_ip = host_ip

    async def initialize(self):
        self.server = await asyncio.start_server(self.get_commands_and_execute, host=self.host_ip, port=self.port)
        async with self.server:
            logger.debug(f"start to listening from {self.host_ip}!")
            await self.server.serve_forever()

    async def accept_new_connection(self, reader, writer):
        address, conn = writer.get_extra_info('peername')
        logger.debug(f"Conneted by {(address, conn)}")
        if address == self.allowed_client:
            logger.debug(f"[+] {address} succeed to connected.")
            data = await reader.read(1024)
            if not data:
                # TODO: data could be ""?
                logger.debug("empty string was received!")
                writer.close()
                await writer.wait_closed()
                return
            request = data.decode('utf-8')
            logger.debug(f"Received {request!r}")
            writer.close()
            await writer.wait_closed()
            logger.debug("Close the connection")
            return request
        else:
            logger.debug(f'nice try {address}')
            writer.close()
            await writer.wait_closed()
            return


    # TODO: instrument number has to go into command execution
    def execute_command(self, command: str, folder_of_executable: Union[Path, str] = r'C:\claritychrom\bin\\'):
        prefix = 'claritychrom.exe'
        # sanitize input a bit
        if command.split(' ')[0] != prefix:
            command = folder_of_executable + prefix + ' ' + command
            logger.debug(f"command line for claritychrom: {command}")
        try:
            x = subprocess
            x.run(command, shell=True, capture_output=False, timeout=3)
        except x.TimeoutExpired:
            logger.debug('Damn, Subprocess')

    async def get_commands_and_execute(self, reader, writer):
        request = await self.accept_new_connection(reader, writer)
        logger.debug(f"request: {request}")
        self.execute_command(request)
        await asyncio.sleep(1)
        logger.debug('listening')


class Async_ClarityRemoteInterface:
    """to remote control hplc"""
    def __init__(self,
                 remote: bool = True,
                 host: str = '192.168.10.11',
                 port: int = 10015,
                 path_to_executable: str = None,  # TODO: necessary?
                 instrument_number: int = 1
                 ):
        self.remote = remote
        self.host = host
        self.port = port
        #  path to executable
        self.instrument = instrument_number
        self.path_to_executable = path_to_executable

    @tenacity.retry(stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_fixed(2), reraise=True)
    async def execute_command(self, command_string):
        reader, writer = await asyncio.open_connection(self.host, self.port)

        logger.debug(f'Send: {command_string!r}')
        writer.write(command_string.encode())
        await writer.drain()

        data = await reader.read(1024)
        logger.debug(f'Received: {data.decode()!r}')

        logger.debug('Close the connection')
        writer.close()
        await writer.wait_closed()


    # Todo: check the DAD address and port
    async def switch_lamp_on(self, address="192.168.10.102", port=10001):
        """
        Has to be performed BEFORE starting clarity, otherwise sockets get blocked
        Args:
            address:
            port:

        Returns:

        """
        # send the  respective two commands and check return. Send to socket
        reader, writer = await asyncio.open_connection(address, port)
        command_string = 'LAMP_D2 1\n\r'
        logger.debug(f'Send: {command_string!r}')
        writer.write(command_string.encode())
        await writer.drain()
        logger.debug('Close the connection')
        writer.close()
        await writer.wait_closed()
        # await asyncio.sleep(15)

    async def switch_lamp_off(self, address="192.168.10.104", port=10001):
        """
        Has to be performed BEFORE starting clarity, otherwise sockets get blocked
        Args:
            address:
            port:

        Returns:

        """
        # send the  respective two commands and check return. Send to socket
        reader, writer = await asyncio.open_connection(address, port)
        command_string = 'LAMP_D2 0\n\r'
        logger.debug(f'Send: {command_string!r}')
        writer.write(command_string.encode())
        await writer.drain()
        logger.debug('Close the connection')
        writer.close()
        await writer.wait_closed()

    async def open_clarity_chrom(self, user: str, config_file: str, password: str = None, start_method: str = ''):
        """
        start_method: supply the path to the method to start with, this is important for a soft column start
        config file: if you want to start with specific instrumment configuration, specify location of config file here
        """
        if not password:
            await self.execute_command(f"i={self.instrument} cfg={config_file} u={user} {start_method}")
        else:
            await self.execute_command(f"i={self.instrument} cfg={config_file} u={user} p={password} {start_method}")
        await asyncio.sleep(20)

    # TODO should be OS agnostic
    async def slow_flowrate_ramp(self, path: str, method_list: tuple = ()):
        """
        path: path where the methods are located
        method list
        TODO: try to trplace by one starting method

        """
        for current_method in method_list:
            await self.execute_command(f"i={self.instrument} {path}\\{current_method}")
            # not very elegant, but sending and setting method takes at least 10 seconds,
            # only has to run during platform startup and can't see more elegant way how to do that
            await asyncio.sleep(25)

    async def load_method(self, path_to_file: str):
        """has to be done to open project, then method. Take care to select 'Send Method to Instrument' option in Method
         Sending Options dialog in System Configuration."""
        await self.execute_command(f"i={self.instrument} {path_to_file}")
        await asyncio.sleep(10)

    async def set_sample_name(self, sample_name: str):
        """Sets the sample name for the next single run"""
        await self.execute_command(f"i={self.instrument} set_sample_name={sample_name}")
        await asyncio.sleep(1)

    async def run(self):
        """Runs the instrument. Care should be taken to activate automatic data export on HPLC.(can be done via command,
         but that only makes it more complicated). Takes at least 2 sec until run starts"""
        await self.execute_command(f'run={self.instrument}')

    async def exit(self):
        """Exit Clarity Chrom"""
        await self.execute_command('exit')
        await asyncio.sleep(10)

    async def send_message(self, message: str):
        """Send a warning message to the clarity console"""
        await self.execute_command(f"{message}")

async def main():
    computer_w_Clarity = False

    if computer_w_Clarity == True:
        Analyser = Async_ClarityExecutioner(10015, '192.168.10.8', '192.168.10.11')
        await Analyser.initialize()

    elif computer_w_Clarity == False:
        commander = Async_ClarityRemoteInterface(remote=True, host='192.168.10.11', port=10015, instrument_number=1)
        # await commander.exit()
        # await commander.switch_lamp_on(address="192.168.10.104", port=10001) #address and port hardcoded
        # mongo_id = "640506b73fedbeb2be0c13a8-faketest"
        await commander.open_clarity_chrom("admin",
                                           config_file=r"C:\ClarityChrom\Cfg\automated_exp.cfg",
                                           start_method=r"D:\Data2q\BV\autostartup_analysis\autostartup_000_BV_c18_shortened.MET",)

        await commander.slow_flowrate_ramp(r"D:\Data2q\BV\autostartup_analysis",
                                           method_list=("autostartup_005_BV_c18_shortened.MET",
                                                        "autostartup_010_BV_c18_shortened.MET",
                                                        "autostartup_015_BV_c18_shortened.MET",
                                                        "autostartup_020_BV_c18_shortened.MET",
                                                        "autostartup_025_BV_c18_shortened.MET",
                                                        )
                                           )

        # await commander.load_method(r"D:\Data2q\BV\BV_General_method_r1met_30min_025mlmin.MET")
        # await commander.load_method(r"D:\Data2q\BV\BV_General_method_r1met_34min_025mlmin.MET")

        from BV_experiments.src.general_platform.Analysis.anal_hplc_chromatogram import HPLC_METHOD
        await commander.load_method(HPLC_METHOD)

        # await commander.load_file("opendedicatedproject") # open a project for measurements
        # await commander.set_sample_name(f"{mongo_id}")
        # await commander.run()
        # await asyncio.sleep(20*60)
        # stop the pump
        # await commander.load_method(r"D:\Data2q\BV\autostartup_analysis\autostartup_000_BV_c18_shortened.MET")

if __name__ == "__main__":
    asyncio.run(main())


