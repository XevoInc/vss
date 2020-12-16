""" Loader for packaged VSS trees. """

import json
from pathlib import Path
from typing import Dict

import pkg_resources
from typeguard import typechecked

__all__ = ['load_tree', 'VSSTree']


VSSTree = Dict


class VSSSpecError(Exception):
    pass


@typechecked(always=True)
def load_tree(name: str = 'vss_rel_2.0.0-alpha+006@87155cc.json') -> VSSTree:
    """
    Loads a VSS tree from the named JSON file.

    :param name: name of the packaged JSON tree or an absolute path to any JSON tree.
    :returns: deserialized JSON tree.
    :raises TypeError: if JSON tree is not an object.
    :raises FileNotFoundError: if tree is not found.
    :raises VSSSpecError: if tree JSON is invalid.
    """
    if Path(name).is_absolute():
        path = name
    else:
        path = pkg_resources.resource_filename(__package__, name)

    try:
        with open(path, 'r') as f:
            return json.load(f)
    except OSError as e:
        raise FileNotFoundError(f'failed to open VSS tree from {name}') from e
    except json.JSONDecodeError as e:
        raise VSSSpecError(f'invalid VSS tree JSON') from e
