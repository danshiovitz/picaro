#!/usr/bin/python3
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from .deck import load_deck
from .exceptions import IllegalMoveException
from .snapshot import Hex
from .storage import ObjectStorageBase
from .types import EncounterContextType, FullCard, JobType, TemplateCard


@dataclass(frozen=True)
class Job:
    name: str
    type: JobType
    rank: int
    promotions: Sequence[str]
    deck_name: str
    encounter_distances: Sequence[int]

    def make_deck(self, additional: List[TemplateCard] = None) -> List[FullCard]:
        # template_deck = load_deck(self.deck_name)
        template_deck = load_deck("Raider")
        return template_deck.actualize(
            self.rank + 1, EncounterContextType.JOB, additional
        )

    def make_single(self, single: TemplateCard) -> FullCard:
        # template_deck = load_deck(self.deck_name)
        template_deck = load_deck("Raider")
        return template_deck.make_card(single, self.rank + 1, EncounterContextType.JOB)

    def fits_hex(self, hx: Hex) -> bool:
        # later: some jobs filter by country and/or terrain type
        return True


def load_jobs() -> List[Job]:
    return JobsStorage.load()


def load_job(job_name: str) -> Job:
    return JobsStorage.load_by_name(job_name)


class JobsStorage(ObjectStorageBase[Job]):
    TABLE_NAME = "job"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[Job]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name) -> Job:
        jobs = cls._select_helper(["name = :name"], {"name": name})
        if not jobs:
            raise IllegalMoveException(f"No such job: {name}")
        return jobs[0]
