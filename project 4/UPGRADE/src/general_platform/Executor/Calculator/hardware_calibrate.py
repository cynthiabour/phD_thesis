"""
create a common class for hardware calibration
"""
from loguru import logger
import networkx as nx

from BV_experiments.src.general_platform import ureg


class HardwareCalibrator:
    def __init__(self, G: nx.Graph, setup_vol_dict: dict):

        self.setup_dict = setup_vol_dict
        self.G = G

        for key, value in setup_vol_dict.items():
            setattr(self, key, value[0])

    def calibrate_syringe_rate(self, calc_inj_rate: dict) -> dict:
        """correction_factor for each pump to give accurate operation parameters"""
        SPUMP_SM_CALIBR = 1
        SPUMP_DYE_CALIBR = 1
        SPUMP_ACTV_CALIBR = 1
        SPUMP_QUNCH_CALIBR = 1
        SPUMP_SOLV_CALIBR = 1

        return {'SMIS': calc_inj_rate['SMIS'] / SPUMP_SM_CALIBR,
                'Dye': calc_inj_rate['Dye'] / SPUMP_DYE_CALIBR,
                'Activator': calc_inj_rate['Activator'] / SPUMP_ACTV_CALIBR,
                'Quencher': calc_inj_rate['Quencher'] / SPUMP_QUNCH_CALIBR,
                'Solvent': calc_inj_rate['Solvent'] / SPUMP_SOLV_CALIBR,
                }

    def closed_pump(self, pump_list: list):
        # List of pump nodes
        # pump_list = ["PumpA", "PumpB", "PumpM"]

        # Find the closest pump to the tee_gl mixer
        upstream_pumps_mixer = [pump for pump in pump_list if nx.has_path(self.G, pump, "tee_gl")]
        shortest_paths_mixer = {pump: nx.shortest_path_length(self.G, pump, "tee_gl") for pump in upstream_pumps_mixer}
        closest_pump_mixer = min(shortest_paths_mixer, key=shortest_paths_mixer.get, default=None)

        # Find the closest pump upstream to the Separator
        upstream_pumps_sep = [pump for pump in pump_list if nx.has_path(self.G, pump, "Separator")]
        shortest_paths_sep = {pump: nx.shortest_path_length(self.G, pump, "Separator") for pump in upstream_pumps_sep}
        closest_pump_sep = min(shortest_paths_sep, key=shortest_paths_sep.get, default=None)

        # Find the closest pump upstream to the HplcLoop
        upstream_pumps_hplc = [pump for pump in pump_list if nx.has_path(self.G, pump, "HplcLoop")]
        shortest_paths_hplc = {pump: nx.shortest_path_length(self.G, pump, "HplcLoop") for pump in upstream_pumps_hplc}
        closest_pump_hplc = min(shortest_paths_hplc, key=shortest_paths_hplc.get, default=None)

        return closest_pump_mixer, closest_pump_sep, closest_pump_hplc

    def calibrate_flow_rate(self, flow_rate: dict) -> dict:
        # PUMPA_CALIBR: float = 0.993  # ml while setting 1.0 ml/min old_vapourtec pumpA 0.9905
        # PUMPB_CALIBR = 0.9618
        # PUMPM_CALIBR = 0.947
        calibration_factors = {
            "PumpA": 0.993,
            "PumpB": 0.9618,
            "PumpM": 0.947
        }

        closest_pump_mixer, closest_pump_sep, closest_pump_hplc = self.closed_pump(["PumpA", "PumpB", "PumpM"])

        # --- Safety checks ---
        pumps = [closest_pump_mixer, closest_pump_sep, closest_pump_hplc]

        # Check for None
        if any(p is None for p in pumps):
            logger.error("One or more pumps are None")
            raise ValueError("Pump configuration contains None values")

        # Check for uniqueness
        if len(set(pumps)) != 3:
            logger.error("Pump roles are not assigned to unique pumps")
            raise ValueError("Pump configuration must have unique pumps for each role")

        # Check that calibration factors exist
        missing_factors = [p for p in pumps if p not in calibration_factors]
        if missing_factors:
            logger.error(f"Missing calibration factors for: {missing_factors}")
            raise ValueError(f"Missing calibration factors for: {missing_factors}")

        # --- Calibration ---
        return {'total_flow': flow_rate['total_flow'],
                'liquid_flow': flow_rate['liquid_flow'] / calibration_factors[closest_pump_mixer],
                'gas_flow': flow_rate['gas_flow'],
                'pre_liquid_flow': flow_rate['pre_liquid_flow'] / calibration_factors[closest_pump_mixer],
                'pre_gas_flow': flow_rate['pre_gas_flow'],
                'dilute_flow_bf_seperator': flow_rate['dilute_flow_bf_seperator'] / calibration_factors[closest_pump_sep],
                'bf_sep_rate': flow_rate['bf_sep_rate'],
                'makeup_flow_for_hplc': flow_rate['makeup_flow_for_hplc'] / calibration_factors[closest_pump_hplc],
                'flow_to_hplc': flow_rate['flow_to_hplc'],
                }

    def check_gl_ratio(self, flow_rate: dict) -> bool:
        """
        limitation of the operation limits for the delivery of gas.
        :param flow_rate:
        :return:
        """
        ratio = flow_rate['gas_flow'] / flow_rate['liquid_flow']
        logger.debug(f"gas to liquid ratio: {ratio}")
        if ratio > 10:
            logger.debug("gas to liquid ratio is greater than 10. Easy to operate the system")
        elif ratio > 2:
            logger.debug("gas to liquid ratio is btw 10 to 2. Gradually decrease the gas flow to reach 2 might be stable")
            return True
        elif 1 < ratio < 2:
            logger.warning("gas to liquid ratio is less than 2")
            return True
        else:
            logger.error("gas to liquid ratio is less than 1. High chance the system will not work properly")
            return False

    def check_param_doable(self, syringe_rate: dict, flow_rate: dict) -> bool:
        """check the operating parameters is in the operating range"""
        # TODO: check pump limitation

        PUMP_MODELS = {
            "PumpA": "Kanuar",
            "PumpM": "Kanuar",
            "PumpB": "R2"
        }

        PUMP_MODEL_LIMITS = {
            "Kanuar": {"min": 0.1, "max": 9.9},
            "R2": {"min": 0.01, "max": 9.9}
        }

        MFC_MODEL_LIMITS = {
            "BronkhorstMFC": {
                "min": 0.2,  # ml/min
                "max": 10.0  # ml/min
            }}

        PC_MODEL_LIMITS = {
            "BronkhorstEPC": {
                "min": 0.2,  # bar
                "max": 10.0  # bar
            }}

        BronkhorstMFC_LIMIT_MAX = 10.0  # ml/min
        # fixme: the gas flow rate minimum is 0.2 ml/min (0.12 ml/min doable only if slowly decline the flow rate) for the liquid flow rate)
        BronkhorstMFC_LIMIT_MIN = 0.2  # ml/min (0.1 ml/min unstable) todo: to reach 0.1 ml/min, 0.5 ml/min -> 0.1 ml/min



        closest_pump_mixer, closest_pump_sep, closest_pump_hplc = self.closed_pump(["PumpA", "PumpB", "PumpM"])
        # the limits for the pumps are defined in the PUMP_MODEL_LIMITS dictionary:
        # Build role-to-pump mapping
        role_to_pump = {
            "mixer": closest_pump_mixer,
            "separator": closest_pump_sep,
            "hplc": closest_pump_hplc,
        }

        # Required flow keys and their roles
        flow_check_map = {
            "liquid_flow": "mixer",
            "dilute_flow_bf_seperator": "separator",
            "makeup_flow_for_hplc": "hplc"
        }

        # check the gas flow rate
        for flow_key, role in flow_check_map.items():
            pump = role_to_pump[role]
            pump_model = PUMP_MODELS[pump]  # e.g., "Kanuar" or "R2"
            limits = PUMP_MODEL_LIMITS[pump_model]

            flow_value = flow_rate[flow_key]

            if flow_key == "liquid_flow":
                if flow_value < limits["min"]:
                    logger.error(f"{flow_key} {flow_value} < {pump}'s min {limits['min']}")
                    return False
            else:
                if flow_value > limits["max"]:
                    logger.error(f"{flow_key} {flow_value} > {pump}'s max {limits['max']}")
                    return False

        # check the gas flow rate
        if flow_rate["gas_flow"] >= BronkhorstMFC_LIMIT_MAX:
            logger.error(f"gas_flow: {flow_rate['gas_flow']} is greater than maximum MFC limit")
            return False
        elif flow_rate["gas_flow"] <= BronkhorstMFC_LIMIT_MIN:
            logger.error(f"gas_flow: {flow_rate['gas_flow']} is less than minimum MFC limit")
            return False

        elif all(i < 0 for i in syringe_rate.values()):
            logger.error(f"at least one of syringe_rate less than 0")
            return False
        else:
            logger.debug("all parameters are in the operating range")
            if self.check_gl_ratio(flow_rate):
                return True
            else:
                logger.warning("gas to liquid ratio is less than 1. High chance the system will not work properly")
                return False


if __name__ == "__main__":
    all_flow = {'total_flow': 0.5772, 'liquid_flow': 0.5093890171035715, 'gas_flow': 0.2034329486892854,
                'pre_liquid_flow': 2, 'pre_gas_flow': 0.7987331562271293,
                'dilute_flow_bf_seperator': 0.49061098289642846, 'bf_sep_rate': 1.0,
                'makeup_flow_for_hplc': 6.568190055404964, 'flow_to_hplc': 7.568190055404964}

    syr_rate = {'SYRINGE0': 0.007150720164012728, 'SYRINGE5': 0.09559026130810268,
                'SYRINGE3': 0.34946388787383326, 'SYRINGE4': 0.04779513065405134, 'SYRINGE6': 0.0}
    from BV_experiments.Example3_debenzylation.db_doc import FlowSetupDad
    calibrator = HardwareCalibrator(FlowSetupDad.G, FlowSetupDad.physical_info_setup_list)
    r, d, m = calibrator.closed_pump(["PumpA", "PumpB", "PumpM"])

    sent_to = calibrator.calibrate_flow_rate(all_flow)
    print("sent to pumps: ", sent_to)
    sys_check = calibrator.check_param_doable(syr_rate, all_flow)
    print("system check: ", sys_check)