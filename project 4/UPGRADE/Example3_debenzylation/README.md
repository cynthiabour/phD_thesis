# Database Document Structure for Debenzylation Experiment

## Overview
The `db_doc` module defines the document structure for the database used in the debenzylation experiment. It includes classes for experiment conditions, chemical information, flow setup, and optimization parameters.

## Features
- **Experiment Conditions**: Define experimental parameters using equivalence ratios or gas-liquid ratios.
- **Chemical Information**: Store details about starting materials, catalysts, solvents, and other chemicals.
- **Flow Setup**: Represent the flow system using directed or undirected graphs.
- **Optimization Parameters**: Define optimization algorithms and their configurations.
- **Experiment Metadata**: Include metadata such as creation date, execution date, and analysis results.

## Classes

### `ExpCondEquiv`
Defines experiment conditions with equivalence ratios.
- **Attributes**:
  - `concentration`: Reactant concentration.
  - `gas`: Gas type.
  - `oxygen_equiv`: Oxygen equivalence.
  - `ddq_equiv`: DDQ equivalence.
  - `tbn_equiv`: TBN equivalence.
  - `acn_equiv`: Acetonitrile equivalence.
  - `dcm_equiv`: Dichloromethane equivalence.
  - `time`: Reaction time.
  - `light_intensity`: Light intensity.
  - `light_wavelength`: Light wavelength.
  - `pressure`: Reaction pressure.
  - `temperature`: Reaction temperature.

### `ExpCondRatio`
Defines experiment conditions with gas-liquid ratios.
- **Attributes**:
  - Similar to `ExpCondEquiv`, but includes `gl_ratio` instead of `oxygen_equiv`.

### `BaseExperiment`
Base class for experiment documents, including metadata and results.
- **Attributes**:
  - `exp_code`: Experiment code.
  - `exp_state`: State of the experiment.
  - `exp_condition`: Experimental conditions.
  - `opt_algorithm`: Optimization algorithm.
  - `opt_parameters`: Optimization parameters.
  - `exp_category`: Experiment category.
  - `flow_setup`: Flow system setup.
  - `setup_note`: Flow setup details.
  - `created_at`: Creation date.
  - `performance_result`: Analysis results.

### `Experiment`
Specific experiment document for debenzylation experiments.
- **Settings**:
  - Collection name: `debenzylation_2bn_glucoside`.

### `CtrlExperiment`
Control experiment document for debenzylation experiments.
- **Settings**:
  - Collection name: `ctrl_2bn_glucoside`.

### `FirstDebenzylation`
Contains general information and setup for the first debenzylation experiment.
- **Attributes**:
  - `exp_description`: Experiment description.
  - `SM_info`: Starting material information.
  - `IS_info`: Internal standard information.
  - `oxidant_info_1`: Oxidant information.
  - `catalyst_info`: Catalyst information.
  - `solvent_info_1`: Solvent 1 information.
  - `solvent_info_2`: Solvent 2 information.
  - `gas_info`: Gas information.
  - `dad_info`: DAD method configuration.
  - `hplc_config_info`: HPLC configuration.

### `SecondDebenzylation`
Similar to `FirstDebenzylation`, but for the second debenzylation experiment.

### `Optimize_parameters`
Defines optimization parameters for the experiment.
- **Attributes**:
  - `algorithm`: Optimization algorithm.
  - `config`: Configuration for optimization.

### `FlowSetCollection`
Represents the flow system setup using an undirected graph.
- **Attributes**:
  - `G`: Graph representation of the flow system.
  - `physical_info_setup_list`: Physical setup details.

### `FlowSetupDad`
Represents an alternative flow system setup using a directed graph.
- **Attributes**:
  - `G`: Directed graph representation of the flow system.
  - `physical_info_setup_list`: Physical setup details.

## Dependencies
- `beanie`: For MongoDB document modeling.
- `pydantic`: For data validation and settings management.
- `networkx`: For graph-based flow system representation.
- `ureg`: Custom unit registry for unit-aware calculations.
- `convert_graph_to_dict`: Utility for graph-to-dictionary conversion.

## Usage
This module is designed to be used in the context of chemical experiments, particularly for the debenzylation process. It provides a structured way to define and manage experiment parameters, flow setups, and optimization configurations.

## Citation
For optimization algorithms, refer to the following citation:
@article{phoenics, title = {Phoenics: A Bayesian Optimizer for Chemistry}, author = {Florian Häse and Loïc M. Roch and Christoph Kreisbeck and Alán Aspuru-Guzik}, year = {2018} journal = {ACS Central Science}, number = {9}, volume = {4}, pages = {1134--1145} }