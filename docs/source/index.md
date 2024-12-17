flowpyter-task is a Python package which provides [Airflow](https://airflow.apache.org) operators for executing Jupyter notebooks using [papermill](https://github.com/nteract/papermill), running in a Docker container. It is designed for use with Flowminder's FlowKit toolkit for CDR analysis, and in particular the FlowETL container. 

We also provide a Docker image, [flowminder/flowbot](https://hub.docker.com/repository/docker/flowminder/flowbot), which extends the FlowETL image to include flowpyter-task.

See also our [cookie-cutter repository](https://github.com/Flowminder/flowbot-pipeline-root), which creates Airflow pipelines for a selection of CDR derived mobility reports, designed for use with this package.