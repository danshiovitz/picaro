#!/usr/bin/python3
import json
from typing import Any, Dict, List, NamedTuple, Tuple

from .deck import EncounterDeck, load_deck
from .storage import ObjectStorageBase
from .types import Hex, FullCard, JobType, TemplateCard


class Job(NamedTuple):
    name: str
    type: JobType
    rank: int
    promotions: List[str]
    deck_name: str
    encounter_distances: List[int]

    def make_deck(self, additional: List[TemplateCard] = None) -> List[FullCard]:
        # template_deck = load_deck(self.deck_name)
        template_deck = load_deck("Raider")
        return template_deck.actualize(self.rank + 1, additional)

    def fits_hex(self, hx: Hex) -> bool:
        # later: some jobs filter by country and/or terrain type
        return True


def load_jobs() -> List[Job]:
    return JobsStorage.load()


def load_job(job_name: str) -> Job:
    return JobsStorage.load_by_name(job_name)


class JobsStorage(ObjectStorageBase[Job]):
    TABLE_NAME = "job"
    TYPE = Job
    PRIMARY_KEY = "name"

    @classmethod
    def load(cls) -> List[Job]:
        return cls._select_helper([], {}, active_conn=None)

    @classmethod
    def load_by_name(cls, name) -> Job:
        jobs = cls._select_helper(["name = :name"], {"name": name}, active_conn=None)
        if not jobs:
            raise Exception(f"No such job: {name}")
        return jobs[0]
