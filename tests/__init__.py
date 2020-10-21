""" Unit tests for VSS package. """

from copy import deepcopy
from unittest import TestCase

from vss import Signal, VSSBranchError, find_signal, load_tree


class FindSignalTestCase(TestCase):
    # noinspection PyTypeChecker
    def test_illegal_args(self):
        with self.assertRaisesRegex(TypeError, 'name.*str.*got int'):
            find_signal(1)
        with self.assertRaisesRegex(TypeError, 'name.*str.*got None'):
            find_signal(None)
        with self.assertRaisesRegex(TypeError, 'spec.*Dict.*got int'):
            find_signal('abc', 1)

    def test_find_avg_speed(self) -> None:
        self._assert_is_avg_speed(find_signal(('Vehicle', 'AverageSpeed')))

    def test_find_avg_speed_str(self) -> None:
        self._assert_is_avg_speed(find_signal('Vehicle.AverageSpeed'))

    def _assert_is_avg_speed(self, sig: Signal) -> None:
        self.assertEqual(sig.namespace, ('Vehicle', 'AverageSpeed'))
        self.assertEqual(sig.type, 'sensor')
        self.assertEqual(sig.datatype, 'int32')
        self.assertEqual(sig.max, 250)
        self.assertEqual(sig.min, -250)
        self.assertEqual(sig.unit, 'km/h')
        self.assertEqual(sig.pint_unit, 'kilometer / hour')
        self.assertIsNone(sig.default)
        self.assertIsNone(sig.enum)
        self.assertIsNotNone(sig.uuid)

    def test_find_past_leaf(self, base: str = 'Vehicle.AverageSpeed', extra: str = 'FooBar') -> None:
        with self.assertRaisesRegex(VSSBranchError, f"attempted to follow branch {extra!r} from leaf node {base!r}"):
            find_signal(f'{base}.{extra}')
        with self.assertRaisesRegex(VSSBranchError, f"attempted to follow branch {extra!r} from leaf node {base!r}"):
            find_signal(tuple(base.split('.')) + (extra,))

    def test_empty_namespace(self) -> None:
        with self.assertRaisesRegex(ValueError, 'namespace must contain at least one key'):
            find_signal(())
        with self.assertRaisesRegex(ValueError, 'namespace must contain at least one key'):
            find_signal('')
        with self.assertRaisesRegex(ValueError, 'namespace cannot contain an empty key'):
            find_signal('.')
        with self.assertRaisesRegex(ValueError, 'namespace cannot contain an empty key'):
            find_signal('Foo.Bar..Baz')
        with self.assertRaisesRegex(ValueError, 'namespace cannot contain an empty key'):
            find_signal('Foo.Bar.Baz.')
        with self.assertRaisesRegex(ValueError, 'namespace cannot contain an empty key'):
            find_signal('.Foo.Bar.Baz')
        with self.assertRaisesRegex(ValueError, 'namespace cannot contain an empty key'):
            find_signal(('Foo', '', 'Baz'))

    def test_empty_root(self) -> None:
        with self.assertRaisesRegex(VSSBranchError, "no such domain 'Vehicle'"):
            find_signal('Vehicle.Foo.Bar', {})
        with self.assertRaisesRegex(VSSBranchError, "no such domain 'Vehicle'"):
            find_signal(('Vehicle', 'Foo', 'Bar'), {})
        with self.assertRaisesRegex(VSSBranchError, "no such domain 'Bar'"):
            find_signal(('Bar', 'Baz', 'Qux'), {})

    def test_find_non_existent(self, base: str = 'Vehicle.Cabin', extra: str = 'Foo') -> None:
        with self.assertRaisesRegex(VSSBranchError, f'branch {base!r} has no such child {extra!r}'):
            find_signal(f'{base}.{extra}')

    def test_find_branch(self, namespace: str = 'Vehicle.Cabin.HVAC'):
        with self.assertRaisesRegex(VSSBranchError, f'node {namespace!r} is a branch, not a signal'):
            find_signal(namespace)

    def test_find_with_instances(self) -> None:
        find_signal('Vehicle.Cabin.Lights.Spotlight.Row1.IsSharedOn')
        find_signal('Vehicle.Cabin.HVAC.Station.Row1.Left.FanSpeed')
        find_signal('Vehicle.Cabin.HVAC.Station.Row2.Right.FanSpeed')
        find_signal('Vehicle.Cabin.HVAC.Station.Row4.Left.Temperature')

    def test_find_with_instances_missing(self) -> None:
        with self.assertRaisesRegex(VSSBranchError,
                                    r"got 'IsSharedOn' but must be one of .*"):
            find_signal('Vehicle.Cabin.Lights.Spotlight.IsSharedOn')
        with self.assertRaisesRegex(VSSBranchError,
                                    "node 'Vehicle.Cabin.Lights.Spotlight' has instances, "
                                    'expected one of .* after Spotlight'):
            find_signal('Vehicle.Cabin.Lights.Spotlight')

    def test_find_with_illegal_instances(self) -> None:
        with self.assertRaisesRegex(VSSBranchError,
                                    r"got 'Row7' but must be one of .*"):
            find_signal('Vehicle.Cabin.Lights.Spotlight.Row7.IsSharedOn')

    def test_find_does_not_modify_root(self) -> None:
        root = load_tree()
        copy = deepcopy(root)

        self.test_find_avg_speed()
        self.test_find_with_illegal_instances()

        self.assertDictEqual(root, copy)

    @staticmethod
    def test_signal_with_kpa_unit() -> None:
        find_signal('Vehicle.Powertrain.CombustionEngine.Engine.MAP')

    @staticmethod
    def test_signal_with_ratio_unit() -> None:
        find_signal('Vehicle.OBD.CommandedEquivalenceRatio')
