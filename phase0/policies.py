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


class FixedArmPolicy(Policy):
    """Always select the same arm. Useful as a strong static baseline."""

    def __init__(self, arm_name: str):
        matches = [arm for arm in ARMS if arm.name == arm_name]
        if not matches:
            valid = ", ".join(arm.name for arm in ARMS)
            raise ValueError(f"unknown arm {arm_name!r}; valid arms: {valid}")
        self.arm = matches[0]

    def select(self, instance: Instance, solution) -> Arm:
        return self.arm


class RoundRobinPolicy(Policy):
    """Cycle through a fixed arm list, resetting at each stream instance."""

    def __init__(self, arm_names: tuple[str, ...]):
        by_name = {arm.name: arm for arm in ARMS}
        missing = [name for name in arm_names if name not in by_name]
        if missing:
            valid = ", ".join(arm.name for arm in ARMS)
            raise ValueError(f"unknown arms {missing!r}; valid arms: {valid}")
        self.arms = tuple(by_name[name] for name in arm_names)
        self.index = 0

    def reset_instance(self) -> None:
        self.index = 0

    def select(self, instance: Instance, solution) -> Arm:
        arm = self.arms[self.index % len(self.arms)]
        self.index += 1
        return arm


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
