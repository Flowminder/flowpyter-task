# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest
import os
from pathlib import Path

TEST_NOTEBOOK_DIR = Path(__file__).parent / "notebooks"
TEST_STATIC_DIR = Path(__file__).parent / "static"
TEST_TEMPLATE_DIR = Path(__file__).parent / "template_dir"



@pytest.fixture
def tmp_out_dir(tmp_path_factory):
    yield tmp_path_factory.mktemp("out")


@pytest.fixture
def tmp_dagrun_data_dir(tmp_path_factory):
    yield tmp_path_factory.mktemp("task_data")


@pytest.fixture()
def tmp_shared_data_dir(tmp_path_factory):
    yield tmp_path_factory.mktemp("dag_data")


@pytest.fixture
def dag_setup(monkeypatch, tmp_out_dir, tmp_dagrun_data_dir):
    monkeypatch.setenv("FLOWAPI_TOKEN", "unused")
    monkeypatch.setenv("AIRFLOW__CORE__DAGS_FOLDER", str(Path(__file__).parent))
    from airflow.utils.db import upgradedb
    from airflow.models import Variable

    upgradedb()
    Variable.set("flowapi_token", "unused")
    Variable.set("host_dag_path", Path(__file__).parent)
    Variable.set("NOTEBOOK_UID", os.getuid())
    Variable.set("NOTEBOOK_GID", 100)


@pytest.fixture(autouse=True)
def tmp_airflow_home(tmpdir, monkeypatch):
    monkeypatch.setenv("AIRFLOW_HOME", str(tmpdir))
    monkeypatch.setenv("AIRFLOW__CORE__DAGS_FOLDER", str(Path(__file__).parent))
    monkeypatch.setenv("AIRFLOW__CORE__LOAD_EXAMPLES", "False")
    yield tmpdir
