from dataclasses import dataclass
from typing import Any, List, Sequence

from .base import StandardStorage, StandardWrapper
from .common_types import JobType


@dataclass
class JobStorage(StandardStorage["JobStorage"]):
    TABLE_NAME = "job"

    uuid: str
    name: str
    type: JobType
    rank: int
    promotions: List[str]
    deck_name: str
    base_skills: List[str]
    encounter_distances: List[int]

    @classmethod
    def load_by_name(cls, name: str) -> "JobStorage":
        jobs = cls._select_helper(["name = :name"], {"name": name})
        if not jobs:
            raise IllegalMoveException(f"No such job: {name}")
        return jobs[0]


class Job(StandardWrapper[JobStorage]):
    @classmethod
    def load(cls, name: str) -> "Job":
        data = JobStorage.load_by_name(name)
        return Job(data)

    @classmethod
    def load_for_write(cls, name: str) -> "Job":
        data = JobStorage.load_by_name(name)
        return Job(data, can_write=True)
