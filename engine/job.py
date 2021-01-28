#!/usr/bin/python3
import random
from typing import List, NamedTuple, Tuple

from .deck import EncounterDeck, load_deck
from .load import load_json
from .types import Hex, FullCard, JobType, TemplateCard


class Job:
    def __init__(self, name: str, type: JobType, rank: int, promotions: List[str], deck_name: str, encounter_distances: List[int]):
        self.name = name
        self.type = type
        self.rank = rank
        self.promotions = promotions
        self.deck_name = deck_name
        self.encounter_distances = encounter_distances

    def make_deck(self, additional: List[TemplateCard] = None) -> List[FullCard]:
        # template_deck = load_deck(self.deck_name)
        template_deck = load_deck("Raider")
        return template_deck.actualize(self.rank + 1, additional)

    def fits_hex(self, hx: Hex) -> bool:
        # later: some jobs filter by country and/or terrain type
        return True

class JobStruct(NamedTuple):
    name: str
    type: JobType
    rank: int
    promotions: List[str]
    deck_name: str
    encounter_distances: List[int]


class AllJobsStruct(NamedTuple):
    jobs: List[JobStruct]


def load_job(job_name: str) -> Job:
    loaded = load_json("jobs", AllJobsStruct)
    j = [ld for ld in loaded.jobs if ld.name == job_name][0]
    return Job(j.name, j.type, j.rank, j.promotions, j.deck_name, j.encounter_distances)


def load_jobs() -> List[Job]:
    loaded = load_json("jobs", AllJobsStruct)
    return loaded.jobs
