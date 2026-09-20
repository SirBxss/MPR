"""Semantic parity and work bounds for whole-recording timestamp pairing."""

from __future__ import annotations

import itertools
import random
import unittest

from lane_residuals.domain.pairing import (
    MutualNearestTimestampAudit,
    TimestampPair,
    _unique_nearest_positions,
    mutual_nearest_timestamp_pairs,
)


def _exhaustive_audit(first, second, gate=None):
    """Independent all-distance oracle, kept intentionally small and quadratic."""

    def nearest(source, target):
        result, ambiguous = {}, set()
        for position, time in enumerate(source):
            if time is None:
                continue
            distances = {
                other: abs(int(time) - int(other_time))
                for other, other_time in enumerate(target)
                if other_time is not None
            }
            if not distances:
                continue
            minimum = min(distances.values())
            winners = [other for other, distance in distances.items() if distance == minimum]
            if len(winners) == 1:
                result[position] = winners[0]
            else:
                ambiguous.add(position)
        return result, ambiguous

    forward, ambiguous_first = nearest(first, second)
    backward, ambiguous_second = nearest(second, first)
    candidates = [
        TimestampPair(i, j, int(first[i]) - int(second[j]))
        for i, j in forward.items()
        if backward.get(j) == i
    ]
    candidates.sort(key=lambda pair: (int(first[pair.first_position]), pair.first_position, pair.second_position))
    accepted = tuple(pair for pair in candidates if gate is None or abs(pair.delta_ns) <= gate)
    rejected = tuple(pair for pair in candidates if gate is not None and abs(pair.delta_ns) > gate)
    used_first = {pair.first_position for pair in accepted}
    used_second = {pair.second_position for pair in accepted}
    return MutualNearestTimestampAudit(
        pairs=accepted,
        rejected_by_gate=rejected,
        unmatched_first_positions=tuple(i for i in range(len(first)) if i not in used_first),
        unmatched_second_positions=tuple(i for i in range(len(second)) if i not in used_second),
        missing_time_first_positions=tuple(i for i, value in enumerate(first) if value is None),
        missing_time_second_positions=tuple(i for i, value in enumerate(second) if value is None),
        ambiguous_first_positions=tuple(sorted(ambiguous_first)),
        ambiguous_second_positions=tuple(sorted(ambiguous_second)),
    )


class TimestampPairingScalabilityTests(unittest.TestCase):
    def test_exhaustive_small_streams_match_all_audit_fields(self):
        streams = [
            values
            for length in range(4)
            for values in itertools.product((None, 0, 2), repeat=length)
        ]
        for first, second, gate in itertools.product(streams, streams, (None, 0, 1, 2)):
            with self.subTest(first=first, second=second, gate=gate):
                self.assertEqual(
                    mutual_nearest_timestamp_pairs(first, second, maximum_delta_ns=gate),
                    _exhaustive_audit(first, second, gate),
                )

    def test_seeded_unsorted_streams_match_exhaustive_oracle(self):
        rng = random.Random(19092026)
        for _ in range(300):
            first, second = [
                [None if rng.randrange(5) == 0 else rng.randrange(-30, 31)
                 for _ in range(rng.randrange(25))]
                for _ in range(2)
            ]
            gate = rng.choice((None, 0, 1, 5, 50))
            with self.subTest(first=first, second=second, gate=gate):
                self.assertEqual(
                    mutual_nearest_timestamp_pairs(first, second, maximum_delta_ns=gate),
                    _exhaustive_audit(first, second, gate),
                )

    def test_large_integer_nanoseconds_keep_one_ns_distinctions(self):
        for epoch in (1_700_000_000_000_000_000, 2**64, -2**64):
            first = [epoch + 10, epoch, None, epoch + 5, epoch + 30]
            second = [epoch + 31, epoch + 1, epoch + 6, epoch + 11]
            audit = mutual_nearest_timestamp_pairs(first, second, maximum_delta_ns=1)
            self.assertEqual(audit, _exhaustive_audit(first, second, 1))
            self.assertEqual(audit.pairs, (
                TimestampPair(1, 1, -1), TimestampPair(3, 2, -1),
                TimestampPair(0, 3, -1), TimestampPair(4, 0, -1),
            ))

    def test_ties_duplicates_and_inclusive_gate_remain_visible(self):
        cases = (
            ([10], [10, 10]),
            ([9], [10, 10]),
            ([11], [10, 10]),
            ([10, 10], [10]),
            ([10], [9, 11]),
            ([10], [9, 9, 11]),
            ([0, 100, 300], [10, 89, 300]),
            ([0, 1], [10]),  # The nearer second message alone is mutual.
        )
        for first, second in cases:
            for gate in (None, 0, 10):
                with self.subTest(first=first, second=second, gate=gate):
                    self.assertEqual(
                        mutual_nearest_timestamp_pairs(first, second, maximum_delta_ns=gate),
                        _exhaustive_audit(first, second, gate),
                    )
        audit = mutual_nearest_timestamp_pairs([0, 100, 300], [10, 89, 300], maximum_delta_ns=10)
        self.assertEqual(audit.pairs, (TimestampPair(0, 0, -10), TimestampPair(2, 2, 0)))
        self.assertEqual(audit.rejected_by_gate, (TimestampPair(1, 1, 11),))
        self.assertEqual(audit.unmatched_first_positions, (1,))
        self.assertEqual(audit.unmatched_second_positions, (1,))

    def test_long_stream_retains_original_positions_without_mutation(self):
        count = 34_081  # Summary-advertised largest batch02 stream; synthetic values.
        first = tuple(1_700_000_000_000_000_000 + i * 50_000_000 for i in range(count))
        second = tuple(value + 10_000_000 for value in reversed(first))
        audit = mutual_nearest_timestamp_pairs(first, second, maximum_delta_ns=10_000_000)
        self.assertEqual(audit.pairs, tuple(TimestampPair(i, count - 1 - i, -10_000_000) for i in range(count)))
        self.assertEqual(audit.rejected_by_gate, ())
        self.assertEqual(audit.unmatched_first_positions, ())
        self.assertEqual(audit.unmatched_second_positions, ())
        self.assertEqual(audit.ambiguous_first_positions, ())
        self.assertEqual(audit.ambiguous_second_positions, ())
        self.assertEqual(second[0], first[-1] + 10_000_000)

    def test_distance_work_does_not_grow_as_cartesian_product(self):
        count = 4096
        operations = 0

        class CountedTimestamp(int):
            def __sub__(self, other):
                nonlocal operations
                operations += 1
                if operations > 8 * count:
                    raise AssertionError("nearest search exceeded linear distance-work budget")
                return int(self) - int(other)

        source = [(i, CountedTimestamp(10 * i)) for i in range(count)]
        target = [(i, CountedTimestamp(10 * i + 1)) for i in reversed(range(count))]
        nearest, ambiguous = _unique_nearest_positions(source, target)
        self.assertEqual(nearest, {i: i for i in range(count)})
        self.assertFalse(ambiguous)
        self.assertLessEqual(operations, 8 * count)
