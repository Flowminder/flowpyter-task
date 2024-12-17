# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import base64
import dataclasses
import datetime
import subprocess
from pathlib import Path

import flowkit_jwt_generator.fixtures
from time import sleep
from flowkit_jwt_generator import jwt

import pytest
import os

# Careful - if you change this, you'll need to change the
# corresponding network def in dags/flowmachine_dag.py.
INT_TEST_PROJECT = "fpt_int_test"
WORKDIR = Path(__file__).parent


@pytest.fixture(scope="session")
def base_env_vars():
    env_path = Path(__file__).parent / ".env"
    print(f"Loading env vars from {env_path.absolute()}")
    env_vars = (
        line
        for line in env_path.read_text().split("\n")
        if not line.strip().startswith("#") and "=" in line
    )
    yield {ev.partition("=")[0]: ev.partition("=")[2] for ev in env_vars}


@pytest.fixture(scope="session")
def test_jwt_token(base_env_vars):
    priv_key = base64.b64decode(base_env_vars["PRIVATE_JWT_SIGNING_KEY"]).decode()
    token = jwt.generate_token(
        username="TEST_USER",
        private_key=priv_key,
        lifetime=datetime.timedelta(days=1),
        roles={"viewer": ["get_available_dates"]},
        compress=True,
        flowapi_identifier=base_env_vars["FLOWAPI_IDENTIFIER"],
    )
    yield token


@pytest.fixture(scope="session")
def session_out_dir(tmp_path_factory):
    yield tmp_path_factory.mktemp("session_out")


@pytest.fixture(scope="session")
def session_dagrun_data_dir(tmp_path_factory):
    yield tmp_path_factory.mktemp("session_task_data")


@pytest.fixture(scope="session")
def session_shared_data_dir(tmp_path_factory):
    yield tmp_path_factory.mktemp("session_dag_data")


@pytest.fixture(scope="session")
def redis_password(base_env_vars):
    yield base_env_vars["REDIS_PASSWORD"]


@dataclasses.dataclass
class FlowdbTestCreds:
    user: str
    password: str


@pytest.fixture(scope="session")
def flowdb_test_creds(base_env_vars):
    yield FlowdbTestCreds(
        user=base_env_vars["FLOWMACHINE_FLOWDB_USER"],
        password=base_env_vars["FLOWMACHINE_FLOWDB_PASSWORD"],
    )


@pytest.fixture(scope="session")
def tmp_env_vars(
    session_out_dir,
    session_dagrun_data_dir,
    session_shared_data_dir,
    redis_password,
    flowdb_test_creds,
    test_jwt_token,
):
    out = dict()
    out["HOST_PROJECT_DIR"] = str(Path(__file__).parent)
    out["HOST_NOTEBOOK_OUT_DIR"] = str(session_out_dir)
    out["HOST_DAGRUN_DATA_DIR"] = str(session_dagrun_data_dir)
    out["HOST_SHARED_DATA_DIR"] = str(session_shared_data_dir)
    out["HOST_DAGS_DIR"] = str(Path(__file__).parent / "dags")
    out["HOST_NOTEBOOK_DIR"] = str(Path(__file__).parent / "notebooks")
    out["HOST_TEMPLATES_DIR"] = str(Path(__file__).parent / "templates")
    out["HOST_STATIC_DIR"] = str(Path(__file__).parent / "static")
    out["NOTEBOOK_UID"] = str(os.getuid())
    out["NOTEBOOK_GID"] = "100"
    out["FLOWAPI_TOKEN"] = test_jwt_token
    yield out


@pytest.fixture(scope="session")
def tmp_env_file(tmp_env_vars, base_env_vars, tmp_path_factory):
    combined_vars = base_env_vars.copy()
    combined_vars.update(tmp_env_vars)
    out = "\n".join(f"{key}={value}" for key, value in combined_vars.items())
    tmp_path = tmp_path_factory.mktemp("env")
    (tmp_path / "tmp_env").write_text(out)
    print("injecting the following env file:")
    print(out)
    yield tmp_path / "tmp_env"


@pytest.fixture(scope="session")
def celery_compose_path():
    yield Path(__file__).parent / "celery-compose.yml"


@pytest.fixture(scope="session")
def flowkit_compose_path():
    yield Path(__file__).parent / "flowkit-compose.yml"


def poll_service(container_key: str):
    print(f"Polling for {container_key}...")
    result = subprocess.run(
        "docker compose ls", shell=True, capture_output=True, text=True
    ).stdout
    if not result:
        return False
    result_line = next((c for c in result.split("\n") if container_key in c), "")
    return "running" in result_line


def build_compose_fixture(
    compose_path, tmp_env_file, timeout_poll_count=5, poll_interval_secs=3
):
    def inner():
        print(f"Running dockerfile at {compose_path}")
        out = subprocess.run(
            f"docker compose --project-directory {WORKDIR}"
            f" --env-file {tmp_env_file}"
            f" -f {compose_path}"
            f" -p {INT_TEST_PROJECT}"
            f" up --build --detach",
            shell=True,
            capture_output=True,
        )
        if out.returncode != 0:
            raise Exception(out.stderr)
        timeout = 0
        while not poll_service(str(compose_path)):
            timeout += 1
            sleep(poll_interval_secs)
            if timeout >= timeout_poll_count:
                raise Exception("Service setup timed out")

        yield
        print("Stopping docker file ")
        subprocess.run(
            f"docker compose -f {compose_path} -p {INT_TEST_PROJECT} down --volumes",
            shell=True,
        )

    return inner


@pytest.fixture(scope="session")
def celery_compose_file(tmp_env_file, celery_compose_path):
    print("Starting celery services")
    f = build_compose_fixture(celery_compose_path, tmp_env_file)
    yield from f()


@pytest.fixture(scope="session")
def flowkit_compose_file(flowkit_compose_path, tmp_env_file):
    print("Starting flowmachine services")
    f = build_compose_fixture(
        flowkit_compose_path, tmp_env_file, timeout_poll_count=5, poll_interval_secs=5
    )
    yield from f()


def set_airflow_variable(key, value):
    subprocess.run(
        f"docker exec flowpyter_task_scheduler airflow variables set {key} {value}",
        shell=True,
    )


def test_example_dag(celery_compose_file, session_out_dir):
    subprocess.run(
        "docker exec flowpyter_task_scheduler airflow dags test example_dag", shell=True
    )
    finished_notebooks = list(session_out_dir.glob("**/example_dag*.ipynb"))
    assert len(finished_notebooks) == 3
    read_nb = next(f for f in finished_notebooks if str(f).endswith("read_nb.ipynb"))
    assert "DEADBEEF" in read_nb.read_text()


@pytest.fixture()
def set_flowapi_variables(test_jwt_token):
    set_airflow_variable("FLOWAPI_URL", "http://flowapi:9090")
    set_airflow_variable("FLOWAPI_TOKEN", test_jwt_token)
    set_airflow_variable("FLOWAPI_SSL_CERT", "dontcarenow")


@pytest.fixture()
def set_flowdb_variables(redis_password, flowdb_test_creds):
    set_airflow_variable("REDIS_HOST", "flowmachine_query_locker")
    set_airflow_variable("REDIS_PORT", "6379")
    set_airflow_variable("REDIS_PASSWORD", redis_password)
    set_airflow_variable("FLOWDB_HOST", "flowdb")
    set_airflow_variable("FLOWDB_PORT", "5432")
    set_airflow_variable("FLOWMACHINE_FLOWDB_USER", flowdb_test_creds.user)
    set_airflow_variable("FLOWMACHINE_FLOWDB_PASSWORD", flowdb_test_creds.password)


def test_flowmachine_dag(
    celery_compose_file,
    flowkit_compose_file,
    session_out_dir,
    set_flowapi_variables,
    set_flowdb_variables,
):
    subprocess.run(
        "docker exec flowpyter_task_scheduler airflow dags test flowmachine_dag",
        shell=True,
    )
    flowapi_notebook = next(session_out_dir.glob("**/*flowapi_nb.ipynb"))
    assert "Notebook run success" in flowapi_notebook.read_text()
    flowdb_notebook = next(session_out_dir.glob("**/*flowmachine_nb.ipynb"))
    assert "Notebook run success" in flowdb_notebook.read_text()
    flowall_notebook = next(session_out_dir.glob("**/*flow_all_nb.ipynb"))
    assert "Notebook run success" in flowall_notebook.read_text()
