from airflow.plugins_manager import AirflowPlugin

from . import base64_jinja


class FptMacros(AirflowPlugin):
    name = "flowpytertask"
    macros = [base64_jinja.b64_encode, base64_jinja.dump_yaml]
