"""Arm-selection policies for the ceiling experiment.

- UniformRandomPolicy: sanity floor (baseline c).
- EpsilonGreedyPolicy: BALANS-style non-contextual bandit. With
  reset_per_instance=True it mimics BALANS (baseline d): all statistics are
  discarded at every new instance. With False it is the simplest persistent
  variant (a preview of the paper's method, without context).
- OraclePolicy is intentionally NOT here: the oracle is implemented in the
  experiment runner by exhaustively evaluating every arm each round, since
  best-arm-in-hindsight is a measurement, not a policy.
"""

from __future__ import annotations

import random
from collections import defaultdict

from .harness import ARMS, Arm, Policy
from .streams import Instance


class UniformRandomPolicy(Policy):
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def select(self, instance: Instance, solution) -> Arm:
        return self.rng.choice(ARMS)


class EpsilonGreedyPolicy(Policy):
    """Non-contextual epsilon-greedy over mean reward per arm."""

    def __init__(self, epsilon: float = 0.2, seed: int = 0,
                 reset_per_instance: bool = True):
        self.epsilon = epsilon
        self.rng = random.Random(seed)
        self.reset_per_instance = reset_per_instance
        self._init_stats()

    def _init_stats(self):
        self.counts: dict[str, int] = defaultdict(int)
        self.mean_reward: dict[str, float] = defaultdict(float)

    def reset_instance(self) -> None:
        if self.reset_per_instance:
            self._init_stats()

    def select(self, instance: Instance, solution) -> Arm:
        untried = [a for a in ARMS if self.counts[a.name] == 0]
        if untried:
            return self.rng.choice(untried)
        if self.rng.random() < self.epsilon:
            return self.rng.choice(ARMS)
        return max(ARMS, key=lambda a: self.mean_reward[a.name])

    def update(self, arm: Arm, reward: float, improved: bool) -> None:
        n = self.counts[arm.name] + 1
        self.counts[arm.name] = n
        self.mean_reward[arm.name] += (reward - self.mean_reward[arm.name]) / n
