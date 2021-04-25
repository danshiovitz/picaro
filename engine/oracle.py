from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from .exceptions import BadStateException, IllegalMoveException
from .snapshot import Oracle as snapshot_Oracle
from .storage import ObjectStorageBase, ReadOnlyWrapper
from .types import Effect, Event, OracleStatus, make_id

class Oracle(ReadOnlyWrapper):
    @classmethod
    def create(cls, character_name: str, request: str) -> str:
        data = OracleData(
            guid=make_id(),
            status=OracleStatus.WAITING,
            petitioner=character_name,
            request=request,
            granter=None,
            response=None,
            proposal=None,
        )
        oracle = Oracle(data)
        OracleStorage.create(data)
        return data.guid

    @classmethod
    def load(cls, guid: str) -> "OracleContext":
        return OracleContext(guid)

    @classmethod
    def load_for_petitioner(cls, character_name: str) -> "OraclesContext":
        return OraclesContext(lambda: [o for o in OracleStorage.load_by_statuses(OracleStatus.WAITING, OracleStatus.ANSWERED) if o.petitioner == character_name])

    @classmethod
    def load_for_granter(cls, character_name: str) -> "OraclesContext":
        return OraclesContext(lambda: [o for o in OracleStorage.load_by_statuses(OracleStatus.WAITING, OracleStatus.ANSWERED) if o.granter == character_name])

    @classmethod
    def load_unassigned(cls, character_name: str) -> "OraclesContext":
        return OraclesContext(lambda: [o for o in OracleStorage.load_by_statuses(OracleStatus.WAITING) if o.petitioner != character_name])

    def get_snapshot(self) -> snapshot_Oracle:
        return snapshot_Oracle(
            id=self.guid,
            status=self.status,
            petitioner=self.petitioner,
            request=self.request,
            granter=self.granter,
            response=self.response,
            proposal=self.proposal,
        )

    def answer(self, character_name: str, response: str, proposal: List[Event]) -> None:
        if self.status != OracleStatus.WAITING:
            raise BadStateException(f"This oracle is in {self.state.name}, not waiting")
        if self.petitioner == character_name:
            raise IllegalMoveException("This oracle must be answered by someone else")
        self._data.granter = character_name
        self._data.response = response
        self._data.proposal = proposal
        self._data.status = OracleStatus.ANSWERED

    # note we don't execute the proposal here, we do it in the engine
    # (to avoid a circular dependency around the apply-event code)
    def finish(self, character_name: str, confirm: bool) -> None:
        if self.status != OracleStatus.ANSWERED:
            raise BadStateException(f"This oracle is in {self.state.name}, not answered")
        if self.petitioner != character_name:
            raise IllegalMoveException("This oracle must be confirmed or rejected by the petitioner")
        self._data.status = OracleStatus.CONFIRMED if confirm else OracleStatus.REJECTED


class OracleContext:
    def __init__(self, guid: str) -> None:
        self.guid = guid

    def __enter__(self) -> Oracle:
        self._data = OracleStorage.load_by_guid(self.guid)
        return Oracle(self._data)

    def __exit__(self, *exc: Any) -> None:
        OracleStorage.update(self._data)


class OraclesContext:
    def __init__(self, load_func: Callable[[], List[Oracle]]) -> None:
        self.load_func = load_func

    def __enter__(self) -> List[Oracle]:
        self._data_list = self.load_func()
        return [Oracle(d) for d in self._data_list]

    def __exit__(self, *exc: Any) -> None:
        for d in self._data_list:
            OracleStorage.update(d)


@dataclass()
class OracleData:
    guid: str
    status: OracleStatus
    petitioner: str
    request: str
    granter: Optional[str]
    response: Optional[str]
    proposal: Optional[List[Effect]]


class OracleStorage(ObjectStorageBase[OracleData]):
    TABLE_NAME = "oracle"
    PRIMARY_KEYS = {"guid"}

    @classmethod
    def load(cls) -> List[OracleData]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_guid(cls, guid) -> OracleData:
        oracles = cls._select_helper(["guid = :guid"], {"guid": guid})
        if not oracles:
            raise IllegalMoveException(f"No such oracle: {guid}")
        return oracles[0]

    @classmethod
    def load_by_statuses(cls, *statuses: List[OracleStatus]) -> List[OracleData]:
        clause = " OR ".join(f"(status = :status{idx})" for idx, _ in enumerate(statuses))
        props = {f"status{idx}": status.name for idx, status in enumerate(statuses)}
        return cls._select_helper([clause], props)

    @classmethod
    def create(cls, oracle: OracleData) -> int:
        return cls._insert_helper([oracle])

    @classmethod
    def update(cls, oracle: OracleData) -> None:
        cls._update_helper(oracle)
