#!/usr/bin/python3
import random
from typing import List, NamedTuple, Tuple

from .deck import EncounterDeck, load_deck
from .load import load_json
from .types import FullCard, TemplateCard


class Job:
    def __init__(self, name: str, deck_name: str, encounter_distances: List[int]):
        self.name = name
        self.deck_name = deck_name
        self.encounter_distances = encounter_distances

    def make_deck(self, additional: List[TemplateCard] = None) -> List[FullCard]:
        template_deck = load_deck(self.deck_name)
        return template_deck.actualize(additional)


class JobStruct(NamedTuple):
    name: str
    deck_name: str
    encounter_distances: List[int]


class AllJobsStruct(NamedTuple):
    jobs: List[JobStruct]


def load_job(job_name: str) -> Job:
    loaded = load_json("jobs", AllJobsStruct)
    j = [ld for ld in loaded.jobs if ld.name == job_name][0]
    return Job(j.name, j.deck_name, j.encounter_distances)
