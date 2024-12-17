# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pendulum

from flowpytertask import FlowpyterOperator
from airflow import DAG

with DAG(
    dag_id="flowmachine_dag",
    schedule="@once",
    start_date=pendulum.now(pendulum.tz.UTC) - pendulum.duration(days=3),
    default_args={
        "host_notebook_out_dir": "{{var.value.HOST_NOTEBOOK_OUT_DIR}}",
        "host_notebook_dir": "{{var.value.HOST_NOTEBOOK_DIR}}",
        "host_dagrun_data_dir": "{{var.value.HOST_DAGRUN_DATA_DIR}}",
    },
) as dag:
    flowapi_task = FlowpyterOperator(
        notebook_name="flowapi_nb.ipynb",
        task_id="flowapi_task",
        requires_flowapi=True,
        network_mode="fpt_int_test_api",
    )
    flowmachine_task = FlowpyterOperator(
        notebook_name="flowmachine_nb.ipynb",
        task_id="flowmachine_task",
        requires_flowdb=True,
        network_mode="fpt_int_test_db",
    )
    all_task = FlowpyterOperator(
        notebook_name="flow_all_nb.ipynb",
        task_id="all_task",
        requires_flowapi=True,
        requires_flowdb=True,
        network_mode='container:flowapi'
    )
    flowapi_task >> flowmachine_task >> all_task
