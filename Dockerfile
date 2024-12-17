ARG FLOWETL_VERSION=latest
FROM flowminder/flowetl:$FLOWETL_VERSION


# Install flowpyter-task module

ARG SOURCE_VERSION=0+unknown
ENV SOURCE_VERSION=${SOURCE_VERSION}
ENV SOURCE_TREE=flowpyter-task-${SOURCE_VERSION}
WORKDIR /${SOURCE_TREE}

COPY --chown=airflow . /${SOURCE_TREE}/
RUN cd /${SOURCE_TREE}/ && pip install -r requirements.txt && pip install --no-deps --no-cache-dir .
