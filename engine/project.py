#!/usr/bin/python3
import json
import random
from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from itertools import groupby
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union, cast

from picaro.common.utils import clamp

from .board import load_board
from .exceptions import BadStateException, IllegalMoveException
from .snapshot import (
    ProjectStage as snapshot_ProjectStage,
    ProjectStageChallenge as snapshot_ProjectStageChallenge,
    ProjectStageResource as snapshot_ProjectStageResource,
    ProjectStageWaiting as snapshot_ProjectStageWaiting,
    ProjectStageDiscovery as snapshot_ProjectStageDiscovery,
    Project as snapshot_Project,
)
from .storage import ObjectStorageBase, ReadOnlyWrapper
from .types import (
    Effect,
    EffectType,
    Event,
    ProjectStageStatus,
    ProjectStageType,
    ProjectStatus,
)


class ProjectStage(ReadOnlyWrapper):
    @classmethod
    def create_challenge(
        cls,
        project_name: str,
        stage_num: int,
        base_skills: List[str],
        difficulty: int,
        cost: List[Effect],
    ) -> None:
        extra = ProjectStageChallenge(base_skills=base_skills, difficulty=difficulty)
        cls._create_common(
            project_name, stage_num, ProjectStageType.CHALLENGE, extra, cost
        )

    @classmethod
    def create_resource(
        cls,
        project_name: str,
        stage_num: int,
        wanted_resources: Set[str],
        cost: List[Effect],
    ) -> None:
        extra = ProjectStageResource(
            wanted_resources=wanted_resources, given_resources={}
        )
        cls._create_common(
            project_name, stage_num, ProjectStageType.RESOURCE, extra, cost
        )

    @classmethod
    def create_waiting(
        cls, project_name: str, stage_num: int, cost: List[Effect]
    ) -> None:
        extra = ProjectStageWaiting(turns_waited=0)
        cls._create_common(
            project_name, stage_num, ProjectStageType.WAITING, extra, cost
        )

    @classmethod
    def create_discovery(
        cls,
        project_name: str,
        stage_num: int,
        start_hex: Optional[str],
        secret_hex: Optional[str],
        cost: List[Effect],
    ) -> None:
        if (start_hex is None) == (secret_hex is None):
            raise Exception("Exactly one of start hex and secret hex must be given.")

        board = load_board()

        if start_hex:
            ref_hex = board.random_hex_near_hex(
                start_hex, min_distance=8, max_distance=12
            )
            possible_hexes = board.find_hexes_near_hex(
                ref_hex, min_distance=0, max_distance=3
            )
            secret_hex = random.choice(possible_hexes)
        else:
            ref_hex = board.random_hex_near_hex(
                secret_hex, min_distance=0, max_distance=3
            )
            possible_hexes = board.find_hexes_near_hex(
                ref_hex, min_distance=0, max_distance=3
            )
            if secret_hex not in possible_hexes:
                raise Exception(
                    f"Bad selection of ref hex ({ref_hex}) from secret hex ({secret_hex})"
                )
        extra = ProjectStageDiscovery(
            secret_hex=secret_hex,
            ref_hexes=[(ref_hex, 3)],
            possible_hexes=set(possible_hexes),
            explored_hexes=set(),
        )
        cls._create_common(
            project_name, stage_num, ProjectStageType.DISCOVERY, extra, cost
        )

    @classmethod
    def _create_common(
        cls,
        project_name: str,
        stage_num: int,
        type: ProjectStageType,
        extra: Any,
        cost: List[Effect],
    ) -> None:
        data = ProjectStageData(
            project_name=project_name,
            stage_num=stage_num,
            desc="...",
            type=type,
            cost=cost,
            participants=[],
            status=ProjectStageStatus.UNASSIGNED,
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
        return f"{self._data.project_name} Stage {self._data.stage_num}"

    def start(self, character_name: str) -> None:
        if self.status != ProjectStageStatus.UNASSIGNED:
            raise BadStateException(f"Stage is in {self.status.name}, not pending")
        self._data.participants = [character_name]
        self._data.status = ProjectStageStatus.IN_PROGRESS

    def hex_explored(self, hex_name: str, events: List[Event]) -> bool:
        if self._data.type != ProjectStageType.DISCOVERY:
            return False
        extra = cast(ProjectStageDiscovery, self._data.extra)
        if hex_name not in extra.possible_hexes:
            return False
        extra.possible_hexes.discard(hex_name)
        extra.explored_hexes.add(hex_name)
        if hex_name == extra.secret_hex:
            old_xp = self._data.xp
            self._data.xp = self._data.max_xp
            self._data.status = ProjectStageStatus.FINISHED
            events.append(
                Event.for_project(
                    self.name,
                    EffectType.MODIFY_XP,
                    None,
                    old_xp,
                    self._data.xp,
                    ["Secret hex located!"],
                )
            )
            return True
        return False

    def resource_delivered(self, resrc: str, events: List[Event]) -> bool:
        if self._data.type != ProjectStageType.RESOURCE:
            return False
        extra = cast(ProjectStageResource, self._data.extra)
        if resrc not in extra.wanted_resources:
            raise IllegalMoveException(
                f"Resource {resrc} is not needed by {self.name}!"
            )
        if resrc not in extra.given_resources:
            extra.given_resources[resrc] = 1
        else:
            extra.given_resources[resrc] += 1
        old_xp = self._data.xp
        self._data.xp = clamp(self._data.xp + 5, min=0, max=self._data.max_xp)
        events.append(
            Event.for_project(
                self.name,
                EffectType.MODIFY_XP,
                None,
                old_xp,
                self._data.xp,
                [f"Delivered {resrc}"],
            )
        )
        if self._data.xp >= self._data.max_xp:
            self._data.status = ProjectStageStatus.FINISHED
            return True
        return False

    def turn_finished(self, events: List[Event]) -> bool:
        if self._data.type != ProjectStageType.WAITING:
            return False
        extra = cast(ProjectStageWaiting, self._data.extra)
        extra.turns_waited += 1
        old_xp = self._data.xp
        self._data.xp = clamp(self._data.xp + 1, min=0, max=self._data.max_xp)
        events.append(
            Event.for_project(
                self.name,
                EffectType.MODIFY_XP,
                None,
                old_xp,
                self._data.xp,
                ["Turn finished"],
            )
        )
        if self._data.xp >= self._data.max_xp:
            self._data.status = ProjectStageStatus.FINISHED
            return True
        return False

    def modify_xp(self, xp_mod: int, events: List[Event]) -> bool:
        old_xp = self._data.xp
        self._data.xp = clamp(self._data.xp + xp_mod, min=0, max=self._data.max_xp)
        events.append(
            Event.for_project(
                self.name,
                EffectType.MODIFY_XP,
                None,
                old_xp,
                self._data.xp,
                [f"{xp_mod:+}"],
            )
        )
        if self._data.xp >= self._data.max_xp:
            self._data.status = ProjectStageStatus.FINISHED
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

    @classmethod
    def get_snapshots(
        cls, character_name: str, include_all: bool
    ) -> List[snapshot_Project]:
        stages = [
            cls._to_stage_snapshot(d)
            for d in ProjectStageStorage.load()
            if include_all or character_name in d.participants
        ]
        stages.sort(key=lambda s: (s.project_name, s.stage_num))
        project_stages = {
            k: list(g) for k, g in groupby(stages, lambda s: s.project_name)
        }
        if include_all:
            raw_projects = list(ProjectStorage.load())
        else:
            raw_projects = [ProjectStorage.load_by_name(p) for p in project_stages]
        projects = [
            cls._to_snapshot(d, project_stages.get(d.name, [])) for d in raw_projects
        ]
        projects.sort(key=lambda p: p.name)
        return projects

    @classmethod
    def _to_snapshot(
        cls, project: "ProjectData", stages: List[snapshot_ProjectStage]
    ) -> snapshot_Project:
        return snapshot_Project(
            name=project.name,
            desc=project.desc,
            type=project.type,
            status=project.status,
            target_hex=project.target_hex,
            stages=tuple(stages),
        )

    @classmethod
    def _to_stage_snapshot(cls, stage: "ProjectStageData") -> snapshot_ProjectStage:
        if stage.type == ProjectStageType.CHALLENGE:
            extra = cast(ProjectStageChallenge, stage.extra)
            snapshot_extra = snapshot_ProjectStageChallenge(
                base_skills=tuple(extra.base_skills), difficulty=extra.difficulty
            )
        elif stage.type == ProjectStageType.RESOURCE:
            extra = cast(ProjectStageResource, stage.extra)
            snapshot_extra = snapshot_ProjectStageResource(
                wanted_resources=extra.wanted_resources,
                given_resources=extra.given_resources,
            )
        elif stage.type == ProjectStageType.WAITING:
            extra = cast(ProjectStageWaiting, stage.extra)
            snapshot_extra = snapshot_ProjectStageWaiting(
                turns_waited=extra.turns_waited
            )
        elif stage.type == ProjectStageType.DISCOVERY:
            extra = cast(ProjectStageDiscovery, stage.extra)
            snapshot_extra = snapshot_ProjectStageDiscovery(
                ref_hexes=extra.ref_hexes,
                possible_hexes=extra.possible_hexes,
                explored_hexes=extra.explored_hexes,
            )
        else:
            raise Exception(f"Unknown type {stage.type.name}")

        stage_obj = ProjectStage(stage)
        return snapshot_ProjectStage(
            name=stage_obj.name,
            project_name=stage.project_name,
            stage_num=stage.stage_num,
            desc=stage.desc,
            type=stage.type,
            participants=stage.participants,
            status=stage.status,
            xp=stage.xp,
            max_xp=stage.xp,
            extra=snapshot_extra,
        )

    def add_stage(self, stage_type: Optional[ProjectStageType], **kwargs) -> None:
        cur_stages = ProjectStageStorage.load_by_project(self.name)

        if stage_type is None:
            stage_type = random.choice(list(ProjectStageType))
        cost = kwargs.get("cost", None) or [
            Effect(type=EffectType.MODIFY_COINS, value=-10)
        ]

        if stage_type == ProjectStageType.CHALLENGE:
            project_type = ProjectTypeStorage.load_by_name(self.type)
            base_skills = kwargs.get("base_skills", None) or project_type.base_skills
            # difficulty should come off some combo of base project difficulty (?) and number of stages so far
            difficulty = kwargs.get("difficulty", None) or 3
            ProjectStage.create_challenge(
                self.name, len(cur_stages) + 1, base_skills, difficulty, cost
            )
        elif stage_type == ProjectStageType.RESOURCE:
            board = load_board()
            all_resources = list(board.get_base_resources())
            project_type = ProjectTypeStorage.load_by_name(self.type)
            all_resources.extend(project_type.resources * 3)
            resources = set(
                kwargs.get("resources", None) or random.sample(all_resources, 2)
            )
            ProjectStage.create_resource(
                self.name, len(cur_stages) + 1, resources, cost
            )
        elif stage_type == ProjectStageType.WAITING:
            ProjectStage.create_waiting(self.name, len(cur_stages) + 1, cost)
        elif stage_type == ProjectStageType.DISCOVERY:
            start_hex = kwargs.get("start_hex", None)
            secret_hex = kwargs.get("secret_hex", None)
            if not start_hex and not secret_hex:
                start_hex = self.target_hex
            ProjectStage.create_discovery(
                self.name,
                len(cur_stages) + 1,
                start_hex=start_hex,
                secret_hex=secret_hex,
                cost=cost,
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
    cost: List[Effect]
    participants: List[str]
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
    ref_hexes: List[Tuple[str, int]]
    possible_hexes: Set[str]
    explored_hexes: Set[str]


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
        types = cls._select_helper(["name = :name"], {"name": name})
        if not types:
            raise IllegalMoveException(f"No such project type: {name}")
        return types[0]
