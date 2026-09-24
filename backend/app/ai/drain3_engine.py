import os
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from app.core.config import settings

class Drain3Engine:
    def __init__(self):
        config = TemplateMinerConfig()
        config.load(os.path.dirname(__file__) + "/drain3.ini") if os.path.exists(os.path.dirname(__file__) + "/drain3.ini") else None
        config.profiling_enabled = False
        self.miner = TemplateMiner(config=config)

    def extract_template(self, log_line: str):
        result = self.miner.add_log_message(log_line)
        return result

    def get_variables(self, log_line: str, template: str) -> dict:
        # Simplistic variable extractor based on Drain3 template <*> 
        # For a production system this needs more robust regex matching 
        # derived from the template exact tokens.
        extracted = self.miner.extract_parameters(template, log_line)
        if not extracted:
            return {}
        # Returns list of dicts or list of strings depending on Drain3 version
        vars_dict = {}
        for i, val in enumerate(extracted):
            vars_dict[f"var_{i}"] = val if isinstance(val, str) else val.value
        return vars_dict

drain3_engine = Drain3Engine()
