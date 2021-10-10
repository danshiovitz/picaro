from abc import ABC, abstractmethod
from typing import List

from picaro.server.api_types import Entity, Hex, Job


class LookupCache(ABC):
    @abstractmethod
    def lookup_entity(self, entity_uuid: str) -> Entity:
        ...

    @abstractmethod
    def lookup_entities(self) -> List[Entity]:
        ...

    @abstractmethod
    def lookup_hexes(self) -> List[Hex]:
        ...

    @abstractmethod
    def lookup_resources(self) -> List[str]:
        ...

    @abstractmethod
    def lookup_skills(self) -> List[str]:
        ...

    @abstractmethod
    def lookup_jobs(self) -> List[Job]:
        ...
