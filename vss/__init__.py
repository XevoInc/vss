"""
Simple, safe parsing utilities for GENIVI's Vehicle Signal Specification.
"""

import struct
import re
from dataclasses import InitVar, dataclass, field
from typing import Dict, List, Literal, Optional, Set, Tuple, Union, get_type_hints

import pint
from typeguard import typechecked, check_type

from .tree import load_tree, VSSSpecError, VSSTree

__all__ = ['find_signal', 'registry', 'Signal', 'VSSBranchError']


# Setup default unit registry.
registry = pint.UnitRegistry()

# Add VSS-specific units.
registry.define('% = [] = percent')
registry.define('ratio = [] = _')

# VSS uses h as hour, but pint recognizes this as the Planck constant.
registry.define('@alias hour = h')

Datatype = Literal[
    'double',
    'float',
    'int16',
    'int32',
    'int64',
    'int8',
    'uint16',
    'uint32',
    'uint64',
    'uint8',
    'boolean',
    'string'
]
Instances = Union[str, List[Union[str, List[str]]]]
INT_BOUNDS = {
    'uint8': (0, 2 ** 8 - 1),
    'int8': (-2 ** 7, 2 ** 7 - 1),
    'uint16': (0, 2 ** 16 - 1),
    'int16': (-2 ** 15, 2 ** 15 - 1),
    'uint32': (0, 2 ** 32 - 1),
    'int32': (-2 ** 31, 2 ** 31 - 1),
    'uint64': (0, 2 ** 64 - 1),
    'int64': (-2 ** 63, 2 ** 63 - 1)
}
FLOAT_BOUNDS = struct.unpack('>ff', b'\xff\x7f\xff\xff\x7f\x7f\xff\xff')
DOUBLE_BOUNDS = (struct.unpack('>dd', b'\xff\xef\xff\xff\xff\xff\xff\xff\x7f\xef\xff\xff\xff\xff\xff\xff'))


class VSSBranchError(KeyError):
    pass


@dataclass(frozen=True)
class Signal:
    """
    Vehicle Signal Specification signal.
    """
    datatype: Datatype
    description: str
    namespace: Tuple[str, ...]
    pint_unit: pint.Unit = field(init=False)
    reg: InitVar[pint.UnitRegistry]
    type: Literal['sensor', 'attribute', 'actuator']
    uuid: str
    default: Optional[Union[str, bool, float, int]] = None
    enum: Optional[Set[str]] = field(default=None, hash=False)
    max: Optional[Union[float, int]] = None
    min: Optional[Union[float, int]] = None
    unit: str = 'dimensionless'

    def clamp(self, value: Union[float, int]) -> Union[float, int]:
        if self.datatype in ('string', 'boolean'):
            raise ValueError(f'cannot clamp numeric value to non-numeric datatype {self.datatype}')

        type_ = float if self.datatype in ('float', 'double') else int
        return type_(max(min(value, self.max), self.min))

    def __post_init__(self, reg: pint.UnitRegistry) -> None:
        # VSS uses some Pascal-cased data types, so lower-case them then let super type check them.
        # noinspection PyCallByClass
        object.__setattr__(self, 'datatype', self.datatype.lower())

        # Process enum into a more agreeable format.
        if self.enum is not None:
            if self.datatype != 'string':
                raise ValueError(f'enum provided for non-string datatype {self.datatype}')

            # noinspection PyCallByClass
            object.__setattr__(self, 'enum', set(self.enum))

        # Set min and max based on datatype for numeric signals.
        if self.datatype not in ('string', 'boolean'):
            if 'int' in self.datatype:
                try:
                    low, high = INT_BOUNDS[self.datatype]
                except KeyError:
                    raise ValueError(f'unrecognized datatype {self.datatype}') from None
            elif self.datatype == 'float':
                low, high = FLOAT_BOUNDS
            elif self.datatype == 'double':
                low, high = DOUBLE_BOUNDS
            else:
                raise ValueError(f'unrecognized datatype {self.datatype}')

            if self.min is None:
                object.__setattr__(self, 'min', low)
            else:
                object.__setattr__(self, 'min', max(self.min, low))
            if self.max is None:
                object.__setattr__(self, 'max', high)
            else:
                object.__setattr__(self, 'max', min(self.max, high))

        # Ensure default value matches datatype and bounds.
        if self.default is not None:
            if (isinstance(self.default, float) and self.datatype not in ('float', 'double')) or \
                    (isinstance(self.default, int) and 'int' not in self.datatype) or \
                    (isinstance(self.default, bool) and self.datatype != 'boolean') or \
                    (isinstance(self.default, str) and self.datatype != 'string'):
                raise ValueError(f'default value type {type(self.default)} does not match '
                                 f'expected datatype {self.datatype}')

            if self.clamp(self.default) != self.default:
                raise ValueError(f'default value {self.default} is illegal for datatype {self.datatype}')

        # Parse pint unit from unit string.
        try:
            # noinspection PyCallByClass
            object.__setattr__(self, 'pint_unit', reg.parse_units(self.unit))
        except Exception:
            raise ValueError(f'illegal unit {self.unit!r}') from None

        # Non-numeric data types must not have a unit.
        if self.datatype in ('string', 'boolean') and not self.pint_unit.dimensionless:
            raise ValueError(f'datatype {self.datatype} is not compatible with unit {self.pint_unit:~}')

        # Ensure namespace is valid.
        if len(self.namespace) == 0:
            raise ValueError('namespace must contain at least one key')
        for key in self.namespace:
            if len(key) == 0:
                raise ValueError('namespace cannot contain an empty key')

        self.__type_check()

    def __type_check(self) -> None:
        if hasattr(self, '__dataclass_fields__') and __debug__:
            hints = get_type_hints(self.__class__)
            for var in self.__dataclass_fields__.keys():
                try:
                    type_ = hints[var]
                except KeyError:
                    continue

                if not isinstance(type_, InitVar):
                    check_type(var, getattr(self, var), type_)

    def __str__(self) -> str:
        return '.'.join(self.namespace)


def _expand_instances(instances: str, namespace: Tuple[str, ...], idx: int) -> List[str]:
    assert 0 <= idx <= len(namespace), f'illegal index {idx} not in [0, {len(namespace)}]'

    # Expand condensed range format.
    match = re.fullmatch(r'(.*)\[(\d+),(\d+)\]', instances)
    if match is None:
        found = '.'.join(namespace[:idx])
        raise VSSSpecError(f'malformed instance {instances!r} on {found!r}')

    name = match.group(1)
    lower = int(match.group(2))
    upper = int(match.group(3))

    if upper <= lower:
        found = '.'.join(namespace[:idx])
        raise VSSSpecError(f'empty range [{lower},{upper}] on instance {name!r} for {found!r}')

    # Range bounds are inclusive.
    return [f'{name}{i}' for i in range(lower, upper + 1)]


def _consume_instance(instances: List[str], namespace: Tuple[str, ...], idx: int) -> int:
    assert 0 <= idx <= len(namespace), f'illegal index {idx} not in [0, {len(namespace)}]'

    try:
        name = namespace[idx]
    except IndexError:
        found = '.'.join(namespace[:idx])
        raise VSSBranchError(f'node {found!r} has instances, expected one of {instances} after {namespace[idx - 1]}') \
            from None

    if name not in instances:
        found = '.'.join(namespace[:idx])
        raise VSSBranchError(f'illegal instance of {found!r}, got {name!r} but must be one of {instances}')

    return idx + 1


@typechecked(always=True)
def _parse_instances(instances: Instances, namespace: Tuple[str, ...], idx: int) -> int:
    assert 0 <= idx <= len(namespace), f'illegal index {idx} not in [0, {len(namespace)}]'

    if isinstance(instances, str):
        instances = _expand_instances(instances, namespace, idx)
    elif len(instances) == 0:
        found = '.'.join(namespace[:idx])
        raise VSSSpecError(f'empty instances array on {found!r}')

    try:
        instances = [_expand_instances(i, namespace, idx) if isinstance(i, str) else i for i in instances]
    except VSSSpecError:
        pass

    if all(isinstance(i, str) for i in instances):
        # All children are strings, so the next name in the namespace must be one of the children.
        return _consume_instance(instances, namespace, idx)

    if all(isinstance(i, list) for i in instances):
        # All children are lists, so we recursively match.
        for pos, instance in enumerate(instances):
            # Check for illegal nesting.
            for i in instance:
                if not isinstance(i, str):
                    found = '.'.join(namespace[:idx])
                    raise VSSSpecError(f'illegal nested instance[{pos}][{i}] on {found!r}')

            idx = _consume_instance(instance, namespace, idx)

        return idx

    found = '.'.join(namespace[:idx])
    raise VSSSpecError(f'malformed instances {instances!r} for {found!r}')


@typechecked(always=True)
def _find_signal(reg: pint.UnitRegistry, branch: Dict, namespace: Tuple[str, ...], idx: int) -> Signal:
    assert 0 <= idx <= len(namespace), f'illegal index {idx} not in [0, {len(namespace)}]'

    # Instantiate any instances of this branch node.
    try:
        instances = branch['instances']
    except KeyError:
        pass
    else:
        idx = _parse_instances(instances, namespace, idx)

    # We've reached the desired node.
    if idx == len(namespace):
        # Ensure we're instantiating a leaf node.
        type_ = branch.get('type', 'branch')
        if type_ == 'branch':
            found = '.'.join(namespace[:idx])
            raise VSSBranchError(f'node {found!r} is a branch, not a signal')

        # Drop instances if it's specified.
        if 'instances' in branch:
            branch = {k: v for k, v in branch.items() if k != 'instances'}

        try:
            return Signal(namespace=namespace, reg=reg, **branch)
        except (ValueError, TypeError) as e:
            found = '.'.join(namespace[:idx])
            raise VSSSpecError(f'malformed sensor specification for {found!r}') from e

    # Still searching. Recurse into children.
    try:
        children = branch['children']
    except KeyError:
        found = '.'.join(namespace[:idx])
        remaining = '.'.join(namespace[idx:])
        raise VSSBranchError(f'attempted to follow branch {remaining!r} from leaf node {found!r}') from None

    try:
        child = children[namespace[idx]]
    except KeyError:
        found = '.'.join(namespace[:idx])
        raise VSSBranchError(f'branch {found!r} has no such child {namespace[idx]!r}') from None

    return _find_signal(reg, child, namespace, idx + 1)



@typechecked(always=True)
def find_signal(
        name: Union[Tuple[str, ...], str],
        spec: VSSTree = None,
        reg: pint.UnitRegistry = registry) -> Signal:
    """
    Look up a VSS signal.

    :param name: path to signal as tuple of strings or dot-delimited namespace.
    :param spec: VSS tree or None to use built-in.
    :param reg: pint registry to use for signal unit parsing.
    :return: VSS signal.
    :raises FileNotFoundError: if spec is not specified and the built-in cannot be loaded.
    :raises VSSSpecError: if specification is invalid.
    :raises ValueError: if name is empty.
    :raises VSSBranchError: if named signal cannot be found.
    """
    if len(name) == 0:
        raise ValueError("namespace must contain at least one key")
    if isinstance(name, str):
        name = tuple(name.split('.'))
    for key in name:
        if len(key) == 0:
            raise ValueError("namespace cannot contain an empty key")

    if spec is None:
        try:
            spec = load_tree()
        except TypeError as e:
            raise VSSSpecError('invalid VSS tree JSON') from e

    key = name[0]
    try:
        branch = spec[key]
    except KeyError:
        raise VSSBranchError(f'no such domain {key!r}') from None

    try:
        return _find_signal(reg, branch, name, 1)
    except TypeError:
        raise VSSSpecError('invalid VSS tree structure') from e
