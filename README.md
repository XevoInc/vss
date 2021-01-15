# VSS

![Build status](https://img.shields.io/github/workflow/status/XevoInc/vss/Push%20CI/master)
[![PyPI](https://img.shields.io/pypi/v/vss)](https://pypi.org/project/vss/)
![PyPI - License](https://img.shields.io/pypi/l/vss)

Simple, safe parsing utilities for [GENIVI's Vehicle Signal Specification](https://github.com/GENIVI/vehicle_signal_specification). [Pint](https://github.com/hgrecco/pint) is used for unit parsing and [typeguard](https://github.com/agronholm/typeguard) is used for type safety.

## Compatibility
This package works for specifications compatible with VSS spec 2.0.

## Install
You may install this via git:
```bash
pip3 install git+ssh://git@github.com/XevoInc/vss.git#egg=vss
```

## Development
When developing, it is recommended to use Pipenv. To create your development environment:
```bash
pipenv install --dev
```

### Testing
TODO
