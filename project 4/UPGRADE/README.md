# 



## Overview
the platform general structure is as follows:

the concept of the platform is to have a set of experiments that are run on a set of devices. each experiment is a set of tasks that are run on a device. each task is a set of commands that are run on the device. each command is a set of actions that are run on the device. each action is a set of operations that are run on the device. each operation is a set of instructions that are run on the device.

## ci/cd
the platform is built using a ci/cd pipeline that is triggered by a commit to the -- branch

## structure
in the meantime, the platform is structured as follows:

```
BV_experiments/
│   README.md
│   pyproject.toml
├── Example3_debenzylation/
│   ├── db_doc.py
│   ├── calc_gl_para.py
│   ├── calculator_operating.py
│   ├── executor.py
│   ├── main_anal.py
│   ├── main_planner.py
├── src/general_platform/
│   ├── Analysis/
│   │   ├── 
│   ├── Executor
│   ├── Librarian/
│   ├── Planner/
│   │   ├── 
│   │── Executor/
│   ├── platform_error.py
```
### Analysis
analysis was in charge of process the raw data of different analytic methods:
 
hplc analysis

ir analysis

nmr analysis

uv analysis

### Calculator


### Executor 
Executor includes the following classes:




- `main.py` is the main file that runs the platform
- `config.py` is the configuration file that contains the configuration of the platform
- `data` is the folder that contains the raw data of the platform
- `results` is the folder that contains the results of the platform
- `logs` is the folder that contains the logs of the platform
- `tests` is the folder that contains the tests of the platform
- `docs` is the folder that contains the documentation of the platform
- `requirements.txt` is the file that contains the requirements of the platform
- `Dockerfile` is the file that contains the docker configuration of the platform
- `Makefile` is the file that contains the make commands of the platform
- `Jenkinsfile` is the file that contains the jenkins configuration of the platform
- `LICENSE` is the file that contains the license of the platform
- `README.md` is the file that contains the documentation of the platform
- `CHANGELOG.md` is the file that contains the changes of the platform
- `CONTRIBUTING.md` is the file that contains the contributing of the platform

## devices

## tasks

## commands

## actions

## operations


## instructions

