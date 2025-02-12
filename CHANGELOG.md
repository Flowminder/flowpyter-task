# Changelog

All notable changes to flowpyter-task will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [1.3.1]

### Changed

- Bumped FlowKit to 1.32.0

## [1.3.0]

### Changed

- Bumped FlowKit to 1.30.0
- Made open source

## 1.2.0

### Changed
- New minor version to reflect large changes
- Flowkit bumped to 1.28.1

## 1.1.5

### Changed
- Airflow bumped to 2.9.2

## 1.1.4
  
### Changed
- More lenient constraint on apache-airflow version requirement

### Fixed
- Fixed rendering of readme on pypi.org

## 1.1.3

### Added
- `nb_params` can now take a yaml string, json filepath or yaml filepath in addition to dictionaries

## 1.1.0

### Added
- `FlowpyterOperator`; `shared_data_dir` mount to share data between dagruns
  
### Changed
- `FlowpyterOperator`; `data_dir` is now `dag_data_dir`

## 1.0.0

### Added
- `FlowpyterOperator` now has flags for injecting connection environemnts into notebooks
- `template` and `static` mounts have been replaced with a generic `read_only_mounts` arg

### Changed
- `flowpyter-task` has been replaced with `FlowpyterOperator` - see the docstring for `src.flowpytertask.FlowpyterOperator` for full details

## 0.1.7

### Added

- Changelog

### Changed

- You can now set `CONTAINER_NOTEBOOK_DIR` env var to define where notebooks are kept inside the flowpyterlab container.

## 0.1.3

- Initial release

[Unreleased]: https://github.com/Flowminder/flowpyter-task/compare/1.3.0...main
[1.3.1]: https://github.com/Flowminder/flowpyter-task/compare/1.3.0...1.3.1
[1.3.0]: https://github.com/Flowminder/flowpyter-task/tree/1.3.0
