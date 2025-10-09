"""code form Jakob (sugar platform) which used Thread
change it to asyncio
"""
import asyncio
import time
from pathlib import Path
from loguru import logger


class FileWatch:
    """
    Class to easily monitor the existence of a file and if it is getting written to.
    Timout wrappers allow for flexible checking, trying in regular timesteps to find the file or checking if it is
    modified. These will return the final state after timeout, eg if i file is not created after withing timeout,
    FileExists is False
    """

    def __init__(self, folder_path: str, file_extension: str = ""):
        """
        initialise class with folder path to check for files in
        optionally, file-extension can be passed  and will be appended in all operations
        """
        # should hold path to folder that should be watched
        self.folder_path = Path(folder_path)
        self.file_extension = file_extension.strip(".")

    def append_file_extension(self, file_name: str) -> str:
        """
        wrapper to append a file extension set as class attribute to file_name argument.
        """
        if self.file_extension:
            if self.file_extension == file_name.split(".")[-1]:
                return file_name
            else:
                return file_name + "." + self.file_extension
        else:
            return file_name

    async def check_file_existence(self, file_name: str) -> bool:
        """
        Checks if a file exists and returns True if the file exists and False otherwise
        """
        file_name = self.append_file_extension(file_name)
        file_to_check = self.folder_path / Path(file_name)
        try:
            assert file_to_check.exists()
            return True
        except AssertionError:
            return False

    async def check_file_existence_timeout(
        self, file_name: str, timeout: int, check_interval: int = 1
    ) -> Path | bool:
        """
        Checks if a file exists in spcific time, returns True if the file exists within timeout and False otherwise
        File_name: file name without folder_path, for example, "453u0562i4.txt"
        timeout: wait the file to create (in seconds)
        check_interval: check per sec
        """
        file_name = self.append_file_extension(file_name)
        file_to_check = self.folder_path / Path(file_name)
        start_time = time.monotonic()
        end_time = start_time + timeout
        while time.monotonic() < end_time:
            try:
                assert file_to_check.exists()
                return file_to_check
            except AssertionError:
                await asyncio.sleep(check_interval)
        return False

    def file_getting_modified(self, file_name, time_between_mods: int = 1) -> bool:
        """Checks if a file is written to: returns True if file is written to, and returns false if writing is done"""
        from time import sleep

        file_name = self.append_file_extension(file_name)
        file_to_check = self.folder_path / Path(file_name)

        initial_check = file_to_check.stat().st_mtime
        sleep(time_between_mods)
        second_check = file_to_check.stat().st_mtime

        if initial_check - second_check == 0:
            return False
        else:
            return True

    async def file_getting_modified_timeout(
        self,
        file_name: str,
        timeout: int,
        check_interval: int = 1,
        time_between_mods: int = 1,
    ) -> bool:
        """Checks if a file is written to: returns True if after timeout file is still written, and returns false if writing is done within timeout"""

        file_name = self.append_file_extension(file_name)

        for time_step in range(round(timeout / check_interval)):
            if not self.file_getting_modified(
                file_name, time_between_mods=time_between_mods
            ):
                return False
            else:
                await asyncio.sleep(time_step)
        return self.file_getting_modified(
            file_name, time_between_mods=time_between_mods
        )

    def return_file_path(self, file_name: str) -> Path:
        return self.folder_path / Path(self.append_file_extension(file_name))


async def main():
    analysed_samples_folder = r"W:\BS-FlowChemistry\data\exported_chromatograms"
    filewatcher = FileWatch(folder_path=analysed_samples_folder, file_extension="txt")

    # mongo_id = "640506b73fedbeb2be0c13a8_fake_test"
    mongo_id = "27_03_2023_test_2_whhsu117 - DAD 2.1L- Channel 1"
    # wait 15 min.....(after 4 min purging system)
    file_existed = await filewatcher.check_file_existence_timeout(file_name=f"{mongo_id}.txt", timeout=900, check_interval= 3)

    from BV_experiments.src.general_platform.Analysis.anal_hplc_chromatogram import hplc_txt_to_peaks
    if file_existed:
        return hplc_txt_to_peaks(mongo_id, file_existed)
    else:
        logger.error(f"The hplc file isn't found! check manually.....")

if __name__ == "__main__":
    asyncio.run(main())
