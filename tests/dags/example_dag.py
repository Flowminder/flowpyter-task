# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pendulum

from flowpytertask import FlowpyterOperator
from airflow import DAG


with DAG(
    dag_id="example_dag",
    schedule="@daily",
    start_date=pendulum.now(pendulum.tz.UTC) - pendulum.duration(days=3),
    default_args={
        "host_notebook_out_dir": "{{var.value.HOST_NOTEBOOK_OUT_DIR}}",
        "host_notebook_dir": "{{var.value.HOST_NOTEBOOK_DIR}}",
        "host_dagrun_data_dir": "{{var.value.HOST_DAGRUN_DATA_DIR}}",
    },
) as dag:
    first_task = FlowpyterOperator(notebook_name="test_nb.ipynb", task_id="test_task")
    glue_task = FlowpyterOperator(
        notebook_name="glue_nb.ipynb",
        nb_params={"artifact_out": "my_artifact.txt"},
        task_id="glue_task",
    )
    read_task = FlowpyterOperator(
        notebook_name="read_nb.ipynb",
        nb_params={"artifact_in": "my_artifact.txt"},
        task_id="read_task",
    )
    volume_mount_task = FlowpyterOperator(
        notebook_name="test_nb.ipynb", task_id="test_task"
    )
    first_task
    glue_task >> read_task
