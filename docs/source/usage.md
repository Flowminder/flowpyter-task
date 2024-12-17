# Usage

For more examples of how to use the operators with FlowKit, see our [cookie-cutter repository](https://github.com/Flowminder/flowbot-pipeline-root).

Here's a simple example which executes one notebook, passing in a papermill parameter using an image with papermill installed:

```python
import pendulum

from flowpytertask import PapermillOperator
from airflow import DAG
import pathlib

PROJECT_ROOT = pathlib.Path(Variable.get("FLOWBOT_HOST_ROOT_DIR"))

with DAG(
    dag_id="papermill_demo",
    schedule="@once",
    start_date=pendulum.now(pendulum.tz.UTC),
    default_args=dict(
        host_notebook_out_dir=str(PROJECT_ROOT / "executed_notebooks"),
        host_notebook_dir=str(PROJECT_ROOT / "notebooks"),
        host_dagrun_data_dir=str(PROJECT_ROOT / "data" / "dagruns"),
        host_shared_data_dir=str(PROJECT_ROOT / "data" / "shared"),
        notebook_uid=Variable.get("notebook_uid"),
        notebook_gid=Variable.get("notebook_gid"),
    ),
) as dag:
    papermill_task = PapermillOperator(
        notebook_name="notebook.ipynb",
        task_id="papermill_task",
        image="<jupyter image>",
        nb_params=dict(
            an_argument="Some value",
        ),
    )
```