# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from __future__ import annotations

from collections import UserDict
from keyword import iskeyword
from pathlib import Path
from typing import Union

import yaml
from airflow.models import Variable
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.utils.context import Context
from docker.types import Mount
import docker
from jinja2 import Environment


class NotebookExtensionError(Exception):
    pass


class ReservedParameterError(Exception):
    pass


class ReservedMountError(Exception):
    pass


class RelativePathError(Exception):
    pass


class BadParameterError(Exception):
    pass


class FlowkitEnvError(Exception):
    pass


class ParameterFileError(Exception):
    pass


def is_running_on_docker() -> bool:
    """Checks for "/.dockerenv as a test"""
    return Path("/.dockerenv").exists()


class PapermillOperator(DockerOperator):
    """
    An operator that runs a parameterised notebook in a specified container.

    Parameters
    ----------
    notebook_name : str
        The name of the notebook to execute (including extension)
    host_notebook_dir : str
        Folder on the host containing the notebooks to be executed. Mounted read-only.
    host_notebook_out_dir : str
        Folder on the host that will contain the rendered and executed notebooks. See note.
    dagrun_data_dir : str, optional
        Folder on host that will be used to store data for inter-notebook communication.
    nb_params : dict[str, str], optional
        Parameters for Papermill to inject into the notebook. Keys must be valid Python identifiers. Templated.
    image : str
        The Docker image to run the notebook on. Must have papermill already installed.
    read_only_mounts : dict[str, str], optional
        A mapping of {variable_name : host_path} of read-only folders to be mounted. They are injected into nb_params
        with `variable_name` pointing to the mount location on the container.
    network_mode : str, optional
        The docker compose network mode; see docs for corresponding
        parameter in https://airflow.apache.org/docs/apache-airflow-providers-docker/stable/_api/airflow/providers/docker/operators/docker/index.html
    environment : dict, optional
        Environment variables to be injected into the running Docker environment.

    Notes
    -----
    Completed notebooks are stored at the following Airflow template:
    "host_notebook_out_base_dir/{{ds}}/{{dag.dag_id}}__{{task_instance.task_id}}__{{run_id}}/{{dag.dag_id}}__{{task_instance.task_id}}__{{run_id}}__notebook_name.ipynb/"


    """

    CONTAINER_NOTEBOOK_DIR = Path("/opt/airflow/notebooks")
    CONTAINER_NOTEBOOK_OUT_DIR = Path("/opt/airflow/notebooks_out")
    CONTAINER_DAGRUN_DATA_DIR = Path("/opt/airflow/task_data")
    CONTAINER_SHARED_DATA_DIR = Path("/opt/airflow/dag_data")
    template_fields = (
        "notebook_name",
        "host_notebook_dir",
        "mounts",
        "nb_params",
        "nb_yaml",
        "image",
        "host_notebook_out_base_dir",
        "host_notebook_out_taskrun_dir",
        "host_notebook_out_dir",
        "host_notebook_out_path",
        "container_notebook_out_path",
        "container_notebook_out_name",
        "notebook_uid",
        "notebook_gid",
        "host_dagrun_data_dir",
        "host_shared_data_dir",
        "host_data_root",
        "host_run_dagrun_data_dir",
        "user",
        *DockerOperator.template_fields,
    )
    template_fields_renderers = {"nb_params": "yaml", "nb_yaml": "yaml"}
    template_ext = (".yml", ".yaml")

    def __init__(
        self,
        *,
        notebook_name: str,
        host_notebook_dir: str,
        host_notebook_out_dir: str,
        host_dagrun_data_dir: str = None,
        host_shared_data_dir: str = None,
        read_only_mounts: dict = None,
        nb_params: dict | str | None = None,
        image=None,
        environment=None,
        **kwargs,
    ):
        if Path(notebook_name).suffix not in [".json", ".ipynb"]:
            raise NotebookExtensionError("Notebooks must have ipynb or json extension")
        if nb_params is None:
            nb_params = {}
        if environment is None:
            environment = {}
        if read_only_mounts is None:
            read_only_mounts = {}
        self.nb_params = nb_params
        self.log.info(f"Creating docker task to run for {notebook_name}")
        self.notebook_uid = Variable.get("NOTEBOOK_UID")
        self.notebook_gid = Variable.get("NOTEBOOK_GID")
        self._user_string = f"{self.notebook_uid}:{self.notebook_gid}"
        self.notebook_name = notebook_name
        self.read_only_mounts = read_only_mounts

        self._setup_notebook_paths(
            host_notebook_dir, host_notebook_out_dir, notebook_name
        )
        if host_dagrun_data_dir:
            self._setup_dagrun_data_dir(host_dagrun_data_dir)
        self.host_shared_data_dir = host_shared_data_dir

        self.mount_yaml = yaml.safe_dump(self._setup_mounts())
        self.nb_yaml = (
            self.nb_params
            if isinstance(self.nb_params, str)
            else "{{ macros.flowpytertask.dump_yaml(task.nb_params) }}"
        )
        # We call this as a macro because the Airflow plugin system doesn't seem to talk to the filter system
        param_string = "-b {{macros.flowpytertask.b64_encode(task.nb_yaml)}} -b {{macros.flowpytertask.b64_encode(task.mount_yaml)}}"
        self.log.info("Param string")
        self.log.info(param_string)
        environment[
            "PYTHONPATH"
        ] = f"{str(self.CONTAINER_NOTEBOOK_DIR)}:${{PYTHONPATH}}"
        command = f"papermill {param_string} {self.container_notebook_path} {self.container_notebook_out_path}"
        print(command)

        super().__init__(
            command=command,
            user=self._user_string,
            auto_remove="force",
            image=image,
            mounts=self.mounts,
            environment=environment,
            mount_tmp_dir=False,
            **kwargs,
        )

    @staticmethod
    def _injected_key_check(param_dict):
        bad_params = [
            p
            for p in param_dict.keys()
            if not isinstance(p, str) or not p.isidentifier() or iskeyword(p)
        ]
        if bad_params:
            raise BadParameterError(f"{bad_params} are invalid Python identifiers")

    @staticmethod
    def _reserved_param_check(nb_params, mount_params):
        reserved_params = set(mount_params.keys())
        dups = set(nb_params.keys()).intersection(reserved_params)
        if dups != set():
            raise ReservedParameterError(
                f"{dups} are reserved parameters. Check you have no overlap"
                f" between nb_params keys and read_only_mount keys, including "
                f"'dagrun_data_dir' and 'shared_data_dir"
            )

    def _setup_mounts(self):
        mount_params = {}
        self.mounts = [
            Mount(
                source=str(self.host_notebook_dir),
                target=str(self.CONTAINER_NOTEBOOK_DIR),
                type="bind",
                read_only=True,
            ),
            Mount(
                source=str(self.host_notebook_out_dir),
                target=str(self.CONTAINER_NOTEBOOK_OUT_DIR),
                type="bind",
            ),
        ]
        if self.host_dagrun_data_dir:
            self.mounts.append(
                Mount(
                    source=str(self.host_dagrun_data_dir),
                    target=str(self.CONTAINER_DAGRUN_DATA_DIR),
                    type="bind",
                )
            )
            mount_params["dagrun_data_dir"] = str(self.CONTAINER_DAGRUN_DATA_DIR)

        if self.host_shared_data_dir:
            self.mounts.append(
                Mount(
                    source=str(self.host_shared_data_dir),
                    target=str(self.CONTAINER_SHARED_DATA_DIR),
                    type="bind",
                )
            )
            mount_params["shared_data_dir"] = str(self.CONTAINER_SHARED_DATA_DIR)

        for name, host_path in self.read_only_mounts.items():
            if name in ["dagrun_data_dir", "shared_data_dir"]:
                raise ReservedParameterError(
                    "Read-only mounts cannot include 'dagrun_data_dir' or "
                    "'shared_data_dir'; these should be set by their respective"
                    " parameters"
                )
            container_path = f"/opt/airflow/{name}"
            self.mounts.append(
                Mount(
                    source=host_path, target=container_path, type="bind", read_only=True
                )
            )
            mount_params[name] = container_path

        mount_string = "\n".join(f"{m['Source']} to {m['Target']}" for m in self.mounts)
        self.log.info(f"Mounts:\n {mount_string}")
        return mount_params

    def _setup_notebook_paths(
        self, host_notebook_dir, host_notebook_out_dir, notebook_name
    ):
        self.host_notebook_dir = host_notebook_dir
        self.host_notebook_out_base_dir = host_notebook_out_dir
        self.host_notebook_out_taskrun_dir = (
            "{{ds}}/{{dag.dag_id}}__{{task_instance.task_id}}__{{run_id}}"
        )
        self.host_notebook_out_dir = (
            f"{self.host_notebook_out_base_dir}/{self.host_notebook_out_taskrun_dir}"
        )
        self.container_notebook_out_name = (
            "{{dag.dag_id}}__{{task_instance.task_id}}__{{run_id}}__{{task_instance.try_number}}__"
            f"{Path(notebook_name).name}"
        )
        self.host_notebook_out_path = (
            f"{self.host_notebook_out_dir}/{self.container_notebook_out_name}"
        )
        self.container_notebook_path = f"{self.CONTAINER_NOTEBOOK_DIR}/{notebook_name}"
        self.container_notebook_out_path = (
            f"{self.CONTAINER_NOTEBOOK_OUT_DIR}/{self.container_notebook_out_name}"
        )

    def _setup_dagrun_data_dir(self, host_dagrun_data_dir):
        self.host_data_root = host_dagrun_data_dir
        self.host_run_dagrun_data_dir = "{{ds}}/{{dag.dag_id}}__{{run_id}}"
        self.host_dagrun_data_dir = (
            f"{self.host_data_root}/{self.host_run_dagrun_data_dir}"
        )

    def create_path_on_host(
        self, host_root: Union[Path, str], relative_path: Union[Path, str]
    ):
        self.log.info(f"Attempting to create {relative_path} at {host_root}")
        host_root = Path(host_root)
        relative_path = Path(relative_path)
        if relative_path.is_absolute():
            raise RelativePathError("Path to be created on host cannot be absolute")
        if not is_running_on_docker():
            self.log.info(
                f"Operator running on host, creating {host_root}/{relative_path}"
            )
            (host_root / relative_path).mkdir(exist_ok=True, parents=True)
        else:
            client = docker.DockerClient()
            self.log.info(
                f"Spawning busybox container to create {relative_path} in {host_root}"
                f" using uid {self.notebook_uid} gid {self.notebook_gid}"
            )
            client.containers.run(
                "busybox",
                f"mkdir -p /opt/{relative_path}",
                volumes=[f"{host_root}:/opt"],
                user=self._user_string,
                remove=True,
            )

    def render_template_fields(
        self,
        context: Context,
        jinja_env: Environment | None = None,
    ) -> None:
        super().render_template_fields(context, jinja_env)
        nb_params = yaml.safe_load(self.nb_yaml)
        mount_params = yaml.safe_load(self.mount_yaml)
        self._injected_key_check(mount_params)
        self._injected_key_check(nb_params)
        self._reserved_param_check(nb_params, mount_params)

    def execute(self, context: Context):
        # Various of yamls-to-be should now be rendered and hence real
        self.create_path_on_host(
            self.host_notebook_out_base_dir, self.host_notebook_out_taskrun_dir
        )
        if self.host_dagrun_data_dir:
            self.create_path_on_host(self.host_data_root, self.host_run_dagrun_data_dir)
        super().execute(context)


class FlowpyterOperator(PapermillOperator):
    """
    An operator that runs a parameterised Flowpyter notebook with a shared data area

    Parameters
    ----------
    notebook_name : str
        The name of the notebook to execute (including extension)
    host_notebook_dir : str
        Folder on the host containing the notebooks to be executed. Mounted read-only.
    host_notebook_out_dir : str
        Folder on the host that will contain the rendered and executed notebooks. See note.
    dagrun_data_dir : str, optional
        Folder on host that will be used to store data for inter-notebook communication. See note.
    nb_params : dict[str, str], optional
        Parameters for Papermill to inject into the notebook. Keys must be valid Python identifiers. Templated.
    image : str, default "flowminder/flowpyterlab:api-analyst-latest"
        The Docker image to run the notebook on. Must have papermill already installed.
    read_only_mounts : dict[str, str], optional
        A mapping of {variable_name : host_path} of read-only folders to be mounted. They are injected into nb_params
        with `variable_name` pointing to the mount location on the container.
    requires_flowapi: bool, default False
        If True, reads a set of flowapi connection variables from airflow and injects them into the notebook environment
    requires_flowdb: bool, default False
        If True, reads a set of flowdb connection variables from airflow and injects them into the notebook environemtn.
    network_mode : str, optional
        The docker compose network mode; see docs for corresponding
        parameter in https://airflow.apache.org/docs/apache-airflow-providers-docker/stable/_api/airflow/providers/docker/operators/docker/index.html
    environment : dict, optional
        Environment variables to be injected into the running Docker environment.

    Notes
    -----

    - If defined, `dagrun_data_dir` is a shared folder that can be used to
      pass artefacts between notebooks and other tasks within a dagrun. The following jinja string should give the
      path to the shared data folder;

      ``{{ var.value.host_dagrun_data_dir }}/{{ ds }}/{{ dag.id }}__{{ run_id }}``
    - The completed notebooks are saved in task-individual folders within ``host_notebook_out_dir``
    - `nb_params` keys and values can also use jinja templating, but this has not been tested yet

    The Airflow variables needed for this operator to run

    - `notebook_uid, notebook_gid`
        The uid and gid to run the notebook container as

    If `requires_flowapi` is True:
     - FLOWAPI_URL, FLOWAPI_SSL_CERT, FLOWAPI_TOKEN
    If `requires_flowdb` is True:
     - REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, FLOWDB_HOST, FLOWDB_PORT, FLOWMACHINE_FLOWDB_USER, FLOWMACHINE_FLOWDB_PASSWORD

    Examples
    --------
    This example demonstrates using the dagrun_data_dir injected variable to write an artefact to the shared area
    in one notebook, and read and print its contents in the other:

    >>> # glue_nb.ipynb
    ... dagrun_data_dir = "unset"
    ... artifact_out = "unset"
    ... from pathlib import Path
    ... ( Path(dagrun_data_dir) / artifact_out).write_text("DEADBEEF")
    ...
    ... # read_nb.ipynb
    ... dagrun_data_dir = "unset"
    ... artifact_in = "unset"
    ... from pathlib import Path
    ... print(( Path(dagrun_data_dir) / artifact_in).read_text())
    ...
    ... # example_dag.py
    ... first_nb = FlowpyterOperator(
    ...    task_id="first_task",
    ...    notebook_name="glue_nb.ipynb",
    ...    dagrun_data_dir = "/tmp/data"
    ...    notebook_params={"artifact_out": "test_artifact.txt"},
    ... )
    ... second_nb = FlowpyterOperator(
    ...    task_id="second_task",
    ...    notebook_name="read_nb.ipynb",
    ...    dagrun_data_dir = "/tmp/data"
    ...    notebook_params={"artifact_in": "test_artifact.txt"},
    ... )
    ... first_nb >> second_nb
    """

    FLOWAPI_VARS = ["FLOWAPI_URL", "FLOWAPI_SSL_CERT", "FLOWAPI_TOKEN"]
    FLOWDB_VARS = [
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_PASSWORD",
        "FLOWDB_HOST",
        "FLOWDB_PORT",
        "FLOWMACHINE_FLOWDB_USER",
        "FLOWMACHINE_FLOWDB_PASSWORD",
    ]

    def __init__(
        self,
        image: str = "flowminder/flowpyterlab:api-analyst-latest",
        requires_flowapi: bool = False,
        requires_flowdb: bool = False,
        **kwargs,
    ):
        env = kwargs.pop("environment", {})
        if requires_flowapi:
            env = self._inject_af_variables(env, self.FLOWAPI_VARS)
        if requires_flowdb:
            env = self._inject_af_variables(env, self.FLOWDB_VARS)

        super().__init__(image=image, environment=env, **kwargs)

    def _inject_af_variables(self, old_env: dict, var_list: list[str]):
        env = old_env.copy()
        missing_keys = []
        for flowapi_var in var_list:
            if flowapi_var in env.keys():
                self.log.warning(
                    f"{flowapi_var} already present in env; this will be overwritten"
                )
            try:
                env[flowapi_var] = Variable.get(flowapi_var)
            except KeyError:
                missing_keys.append(flowapi_var)
        if missing_keys:
            raise FlowkitEnvError(
                f"Please set the following Airflow variables: {missing_keys}"
            )
        return env


class TemplateOperator(FlowpyterOperator):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
