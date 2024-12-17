# flowpyter-task
[![CircleCI](https://dl.circleci.com/status-badge/img/gh/Flowminder/flowpyter-task/tree/main.svg?style=shield)](https://dl.circleci.com/status-badge/redirect/gh/Flowminder/flowpyter-task/tree/main)  [![License: MPL 2.0](https://img.shields.io/github/license/Flowminder/flowpyter-task.svg?style=flat-square)](https://opensource.org/licenses/MPL-2.0) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/python/black)

flowpyter-task is a Python package which provides [Airflow](https://airflow.apache.org) operators for executing Jupyter notebooks using [papermill](https://github.com/nteract/papermill), running in a Docker container. It is designed for use with Flowminder's FlowKit toolkit for CDR analysis, and in particular the FlowETL container. We also provide a Docker image, [flowminder/flowbot](https://hub.docker.com/repository/docker/flowminder/flowbot), which extends the FlowETL image to include flowpyter-task.

## Installation

Install with pip:

`pip install flowpyter-task`

## Documentation

Documentation is available [here](https://flowminder.github.io/flowpyter-task/).