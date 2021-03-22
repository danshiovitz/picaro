#!/usr/bin/python3
import json
from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union, cast

from .board import load_board
from .exceptions import IllegalMoveException
from .storage import ObjectStorageBase, ReadOnlyWrapper
from .types import EffectType, Event


class ProjectStageType(Enum):
    CHALLENGE = enum_auto()
    RESOURCE = enum_auto()
    WAITING = enum_auto()
    DISCOVERY = enum_auto()


class ProjectStageStatus(Enum):
    PENDING = enum_auto()
    IN_PROGRESS = enum_auto()
    FINISHED = enum_auto()


class ProjectStatus(Enum):
    IN_PROGRESS = enum_auto()
    FINISHED = enum_auto()


@dataclass()
class ProjectStageChallenge:
    base_skills: List[str]
    difficulty: int


@dataclass()
class ProjectStageResource:
    wanted_resources: Set[str]
    given_resources: Dict[str, int]


@dataclass()
class ProjectStageWaiting:
    turns_waited: int


@dataclass()
class ProjectStageDiscovery:
    secret_hex: str
    ref_hexes: List[Tuple[str, int]]
    possible_hexes: Set[str]
    explored_hexes: Set[str]


class ProjectStage(ReadOnlyWrapper):
    @classmethod
    def create_challenge(
        cls, project_name: str, stage_num: int, base_skills: List[str], difficulty: int
    ) -> None:
        extra = ProjectStageChallenge(base_skills=base_skills, difficulty=difficulty)
        cls._create_common(project_name, stage_num, ProjectStageType.CHALLENGE, extra)

    @classmethod
    def create_resource(
        cls, project_name: str, stage_num: int, wanted_resources: Set[str]
    ) -> None:
        extra = ProjectStageResource(wanted_resources={"Wine"}, given_resources={})
        cls._create_common(project_name, stage_num, ProjectStageType.RESOURCE, extra)

    @classmethod
    def create_waiting(cls, project_name: str, stage_num: int) -> None:
        extra = ProjectStageWaiting(turns_waited=0)
        cls._create_common(project_name, stage_num, ProjectStageType.WAITING, extra)

    @classmethod
    def create_discovery(
        cls, project_name: str, stage_num: int, start_hex: str
    ) -> None:
        board = load_board()
        ref_hex = board.random_hex_near_hex(target_hex, min_distance=8, max_distance=12)
        possible_hexes = board.find_hexes_near_hex(
            ref_hex, min_distance=0, max_distance=3
        )
        extra = ProjectStageDiscovery(
            secret_hex=random.choice(possible_hexes),
            ref_hexes=[(ref_hex, 3)],
            possible_hexes=set(possible_hexes),
            explored_hexes=set(),
        )
        cls._create_common(project_name, stage_num, ProjectStageType.DISCOVERY, extra)

    @classmethod
    def _create_common(
        cls, project_name: str, stage_num: int, type: ProjectStageType, extra: Any
    ) -> None:
        data = ProjectStageData(
            project_name=project_name,
            stage_num=stage_num,
            desc="...",
            type=type,
            status=ProjectStageStatus.PENDING,
            xp=0,
            max_xp=25,
            extra=extra,
        )
        project_stage = ProjectStage(data)
        ProjectStageStorage.create(data)

    @classmethod
    def load(cls, project_name: str, stage_num: int) -> "ProjectStageContext":
        return ProjectStageContext(project_name, stage_num)

    @property
    def name(self) -> str:
        return f"{self.project_name} Stage {self.stage_num}"

    def hex_explored(self, hex_name: str, events: List[Event]) -> bool:
        if self.type != ProjectStageType.DISCOVERY:
            return False
        extra = cast(ProjectStageDiscovery, self.extra)
        if hex_name not in extra.possible_hexes:
            return False
        extra.possible_hexes.discard(hex_name)
        extra.explored_hexes.add(hex_name)
        if hex_name == extra.secret_hex:
            old_xp = self.xp
            self.xp = self.max_xp
            self.status = ProjectStageStatus.FINISHED
            events.append(
                Event.for_project(
                    self.name, EffectType.MODIFY_XP, None, old_xp, self.xp, ["Secret hex located!"]
                )
            )
            return True
        return False

    def resource_delivered(self, resrc: str, events: List[Event]) -> bool:
        if self.type != ProjectStageType.RESOURCE:
            return False
        extra = cast(ProjectStageResource, self.extra)
        if resrc not in extra.wanted_resources:
            raise IllegalMoveException(f"Resource {resrc} is not needed by {self.name}!")
        if resrc not in extra.given_resources:
            extra.given_resources[resrc] = 1
        else:
            extra.given_resources[resrc] += 1
        old_xp = self.xp
        self.xp = min(self.xp + 5, self.max_xp)
        events.append(
            Event.for_project(
                self.name, EffectType.MODIFY_XP, None, old_xp, self.xp, [f"Delivered {resrc}"]
            )
        )
        if self.xp >= self.max_xp:
            self.status = ProjectStageStatus.FINISHED
            return True
        return False

    def turn_finished(self, events: List[Event]) -> bool:
        if self.type != ProjectStageType.WAITING:
            return False
        extra = cast(ProjectStageWaiting, self.extra)
        extra.turns_waited += 1
        old_xp = self.xp
        if self.xp < self.max_xp:
            self.xp += 1
        events.append(
            Event.for_project(
                self.name, EffectType.MODIFY_XP, None, old_xp, self.xp, ["Turn finished"]
            )
        )
        if self.xp >= self.max_xp:
            self.status = ProjectStageStatus.FINISHED
            return True
        return False

    def modify_xp(self, xp_mod: int, events: List[Event]) -> bool:
        old_xp = self.xp
        if self.xp < self.max_xp:
            self.xp += xp_mod
        events.append(
            Event.for_project(
                self.name, EffectType.MODIFY_XP, None, old_xp, self.xp, [f"{xp_mod:+}"]
            )
        )
        if self.xp >= self.max_xp:
            self.status = ProjectStageStatus.FINISHED
            return True
        return False


class ProjectStageContext:
    def __init__(self, project_name: str, stage_num: int) -> None:
        self.project_name = project_name
        self.stage_num = stage_num

    def __enter__(self) -> "ProjectStage":
        self._data = ProjectStageStorage.load_by_project_stage(
            self.project_name, self.stage_num
        )
        return ProjectStage(self._data)

    def __exit__(self, *exc: Any) -> None:
        ProjectStageStorage.update(self._data)


class Project(ReadOnlyWrapper):
    @classmethod
    def create(cls, name: str, project_type: str, target_hex: str) -> None:
        type_obj = ProjectTypeStorage.load_by_name(project_type)

        data = ProjectData(
            name=name,
            desc="...",
            type=type_obj.name,
            status=ProjectStatus.IN_PROGRESS,
            target_hex=target_hex,
        )

        project = Project(data)
        ProjectStorage.create(data)

        board = load_board()
        board.add_token(
            name=f"Site: {name}",
            type="Other",
            location=target_hex,
            actions=None,
            events=[],
        )

    @classmethod
    def load(cls, name: str) -> "ProjectContext":
        return ProjectContext(name)

    def add_stage(self, stage_type: Optional[ProjectStageType]) -> None:
        cur_stages = ProjectStageStorage.load_by_project(self.name)

        if stage_type is None:
            stage_type = random.choice(list(ProjectStageType))

        if stage_type == ProjectStageType.CHALLENGE:
            project_type = ProjectTypeStorage.load_by_name(self.type)
            base_skills = project_type.base_skills
            # difficulty should come off some combo of base project difficulty (?) and number of stages so far
            difficulty = 3
            ProjectStage.create_challenge(
                self.name, len(cur_stages) + 1, base_skills, difficulty
            )
        elif stage_type == ProjectStageType.RESOURCE:
            board = load_board()
            resources = board.get_base_resources()
            project_type = ProjectTypeStorage.load_by_name(self.type)
            resources.extend(project_type.resources * 3)
            ProjectStage.create_resource(
                self.name, len(cur_stages) + 1, set(random.sample(resources, 2))
            )
        elif stage_type == ProjectStageType.WAITING:
            ProjectStage.create_waiting(self.name, len(cur_stages) + 1)
        elif stage_type == ProjectStageType.DISCOVERY:
            ProjectStage.create_discovery(
                self.name, len(cur_stages) + 1, self.target_hex
            )
        else:
            raise Exception(f"Bad stage type: {stage_type}")


class ProjectContext:
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> "Project":
        self._data = ProjectStorage.load_by_name(self.name)
        return Project(self._data)

    def __exit__(self, *exc: Any) -> None:
        ProjectStorage.update(self._data)


@dataclass()
class ProjectStageData:
    project_name: str
    stage_num: int
    desc: Optional[str]
    type: ProjectStageType
    status: ProjectStageStatus
    xp: int
    max_xp: int
    extra: Any

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[ProjectStageType, str]) -> type:
        if type(type_val) is str:
            type_val = ProjectStageType[type_val]

        if type_val == ProjectStageType.CHALLENGE:
            return ProjectStageChallenge
        elif type_val == ProjectStageType.RESOURCE:
            return ProjectStageResource
        elif type_val == ProjectStageType.WAITING:
            return ProjectStageWaiting
        elif type_val == ProjectStageType.DISCOVERY:
            return ProjectStageDiscovery
        else:
            raise Exception("Unknown type")


@dataclass()
class ProjectStageChallenge:
    base_skills: List[str]
    difficulty: int


@dataclass()
class ProjectStageResource:
    wanted_resources: Set[str]
    given_resources: Dict[str, int]


@dataclass()
class ProjectStageWaiting:
    turns_waited: int


@dataclass()
class ProjectStageDiscovery:
    secret_hex: str
    possible_hexes: Set[str]


@dataclass(frozen=True)
class ProjectType:
    name: str
    desc: str
    base_skills: List[str]
    resources: List[str]


@dataclass()
class ProjectData:
    name: str
    desc: str
    type: str
    status: ProjectStatus
    target_hex: str


# what if instead you declare your stage count when you start a project and that's just it,
# so the player interaction is just picking up stages. GMs and/or the system might still require
# being able to add stages, though. Use cases:
# 1) Player creates a project, specifying type etc, and the number of stages; actual stages are autogenned
# 2) GM creates a project, specifying type etc, and if they want, also the explicit stages
# 3) Player picks up a stage / puts back a stage
# 4) Tick some xp for a stage
# 5) GM updates random bits on a project
# 6) GM updates random bits on a stage
# 7) get a project (by name) and all its stages
# 8) get all projects with their stages
# 9) see all the stages owned by a character

# type-specific stage data is like:
# for resource type stages, the hex to deliver resources to (and the resources that have been collected, and the resources that are required?)
# for discovery stages, the secret hex, I guess the clues, and the remaining possible hexes
# for challenge stages, the preferred skills (?), the base difficulty
# for time stages, nothing extra

# character drives all the logic?
# what drives -> when xp is ticked, if more than max, move stage to finished
# what drives -> character travels to square X, search any stages of type travel that are there


class ProjectManager:  # heh
    # this class is stateless, it just loads stuff as needed

    def create_project(self, project: Project) -> None:
        # validate project and stage details
        pass

    def take_stage(
        self, stage_name: str, project_name: str, character_name: str
    ) -> None:
        # assigns character to stage, but does not validate additional requirements
        pass

    def get_stages_for_character(self, character_name: str) -> List["ProjectStage"]:
        pass

    def search_hex(
        self, stage_name: str, project_name: str, character_name: str, hex_name: str
    ) -> bool:
        # returns whether this was the secret hex or not
        pass

    def deliver_resource(
        self,
        stage_name: str,
        project_name: str,
        character_name: str,
        resource_name: str,
    ) -> bool:
        # returns whether the resource was accepted or not
        pass

    def add_xp(
        self, stage_name: str, project_name: str, character_name: str, xp: int
    ) -> bool:
        # returns whether the stage is now finished or not
        pass


class ProjectStageStorage(ObjectStorageBase[ProjectStageData]):
    TABLE_NAME = "project_stage"
    PRIMARY_KEYS = {"project_name", "stage_num"}

    @classmethod
    def load(cls) -> List[ProjectStageData]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_project(cls, project_name: str) -> List[ProjectStageData]:
        return cls._select_helper(
            ["project_name = :project_name"], {"project_name": project_name}
        )

    @classmethod
    def load_by_project_stage(
        cls, project_name: str, stage_num: int
    ) -> ProjectStageData:
        stages = cls._select_helper(
            ["project_name = :project_name", "stage_num = :stage_num"],
            {"project_name": project_name, "stage_num": stage_num},
        )
        if not stages:
            raise IllegalMoveException(
                f"No such project or stage: {project_name} {stage_num}"
            )
        return stages[0]

    @classmethod
    def create(cls, stage: ProjectStageData) -> int:
        return cls._insert_helper([stage])

    @classmethod
    def update(cls, stage: ProjectStageData) -> None:
        cls._update_helper(stage)


class ProjectStorage(ObjectStorageBase[ProjectData]):
    TABLE_NAME = "project"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[ProjectData]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name) -> ProjectData:
        projects = cls._select_helper(["name = :name"], {"name": name})
        if not projects:
            raise IllegalMoveException(f"No such project: {name}")
        return projects[0]

    @classmethod
    def create(cls, project: ProjectData) -> int:
        return cls._insert_helper([project])

    @classmethod
    def update(cls, project: ProjectData) -> None:
        cls._update_helper(project)


class ProjectTypeStorage(ObjectStorageBase[ProjectType]):
    TABLE_NAME = "project_type"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[ProjectType]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name: str) -> List[ProjectStageData]:
        types = cls._select_helper(
            ["name = :name"], {"name": name}
        )
        if not types:
            raise IllegalMoveException(f"No such project type: {name}")
        return types[0]
