#!/usr/bin/python3
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from .deck import load_deck
from .exceptions import IllegalMoveException
from .snapshot import Hex
from .storage import ObjectStorageBase
from .types import EncounterContextType, FullCard, Job, JobType, TemplateCard


def load_jobs() -> List[Job]:
    return JobsStorage.load()


def load_job(job_name: str) -> Job:
    return JobsStorage.load_by_name(job_name)


def create_jobs(
    jobs: List[Job],
) -> None:
    JobsStorage.insert(jobs)


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

    @classmethod
    def insert(cls, jobs: List[Job]) -> None:
        cls._insert_helper(jobs)
