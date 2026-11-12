"""Counts for the captured-pieces sidebar."""
from collections import Counter

from game import new_position


def missing_pieces(position):
    initial = Counter(new_position()[0].values())
    current = Counter(position[0].values())
    return sorted((initial - current).elements())
