# Install

flowpyter-task is a regular python package and can be installed using `pip` by running `pip install flowpyter-task`, however we recommend using the `flowminder/flowbot` docker image, which includes Airflow and FlowETL.

## Dependencies

 - Docker
 - Python 3.10+

## Host user

We recommend that you create a machine user on the host system, to enable Docker to read and write notebooks and other outputs. You will need to ensure that this user has read and write access to the folders on the host defined by:


| Environment variable | Airflow variable name | Description |
| -------------------- | --------------------- | ----------- |
| `AIRFLOW_VAR_FLOWBOT_HOST_ROOT_DIR` | flowbot_host_root_dir | Path on the host to root directory where notebooks and associated data files will live |


And that the uid is provided either via an env var named `AIRFLOW_VAR_NOTEBOOK_UID`, or by creating an Airflow variable named `notebook_uid`. You may optionally provide a gid as well using `AIRFLOW_VAR_NOTEBOOK_GID`, but in the majority of cases this should be set to `'100'` to avoid permissions issues.

Note that the _Airflow_ user will also need read only access to this directory, to allow it to pick up dag files.


## Sample compose file

A sample compose file intended for use an an overlay on an existing dockerised FlowETL deployment. See the full documentation for [FlowKit](https://flowminder.github.io/FlowKit) for more details on deploying FlowETL.

```yaml
#
# Flowbot stackfile
#
x-flowbot-common: &flowbot-common
  image: flowminder/flowbot:${FLOWBOT_CONTAINER_TAG:-latest}
  volumes:
    - ${FLOWBOT_HOST_DAG_DIR:?}:/opt/airflow/dags/flowbot:ro
  environment:
    AIRFLOW_VAR_NOTEBOOK_UID: ${FLOWBOT_UID:?}
    AIRFLOW_VAR_NOTEBOOK_GID: 100
    AIRFLOW_VAR_FLOWBOT_HOST_ROOT_DIR: ${FLOWBOT_HOST_DAG_DIR:?}
  secrets:
    - source: REDIS_PASSWORD
      target: AIRFLOW_VAR_REDIS_PASSWORD
services:
  flowetl_init_db:
    <<: *flowbot-common
  flowetl_scheduler:
    <<: *flowbot-common
  flowetl_worker:
    <<: *flowbot-common
    volumes:
      - ${FLOWBOT_HOST_DAG_DIR:?}:/opt/airflow/dags/flowbot:ro
      - type: bind
        source: ${DOCKER_SOCKET:-/var/run/docker.sock}
        target: /var/run/docker.sock
  flowetl_webserver:
    <<: *flowbot-common
  flowetl_flower:
    <<: *flowbot-common
  flowetl_triggerer:
    <<: *flowbot-common
```