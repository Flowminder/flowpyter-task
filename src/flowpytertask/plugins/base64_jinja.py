import base64

from airflow.utils import yaml


def b64_encode(yaml_str: str) -> str:
    params_base64 = base64.b64encode(yaml_str.encode()).decode()
    return params_base64

def dump_yaml(in_dict):
    return yaml.safe_dump(in_dict)

