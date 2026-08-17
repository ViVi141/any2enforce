"""Demo module: Python -> EnforceScript showcase for any2enforce v0.1."""

import math


def add(a: int, b: int) -> int:
    return a + b


def describe(count: int, label: str) -> str:
    text = f"count={count} label={label}"
    return text


def total(values: list[int]) -> int:
    result = 0
    for v in values:
        result += v
    return result


def countdown(n: int) -> None:
    for i in range(n, 0, -1):
        print(i)


def stats(values: list[float]) -> None:
    highest = values[0]
    for v in values:
        if v > highest:
            highest = v
    print(f"max = {highest}")


class Unit:
    def __init__(self, name: str, hp: int = 100):
        self.name = name
        self.hp = hp

    def damage(self, dmg: int) -> None:
        self.hp -= dmg

    def heal(self, amount: int) -> None:
        if self.hp + amount > 100:
            self.hp = 100
        else:
            self.hp += amount

    @staticmethod
    def kind() -> str:
        return "unit"


class Soldier(Unit):
    def __init__(self, name: str):
        self.rank = "private"
        self.ammo = 30

    def reload(self) -> None:
        self.ammo = 30
