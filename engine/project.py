#!/usr/bin/python3
import json
import random
from dataclasses import dataclass
from enum import Enum, auto as enum_auto
from itertools import groupby
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

from picaro.common.utils import clamp

from .board import load_board
from .entity import (
    Entity,
    EntityField,
    IntEntityField,
    SimpleIntEntityField,
)
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
    Action,
    Choices,
    Effect,
    EffectType,
    EntityType,
    Event,
    ProjectStageStatus,
    ProjectStageType,
    ProjectStatus,
    SpecialChoiceType,
)


class ProjectStage(Entity, ReadOnlyWrapper):
    ENTITY_TYPE = EntityType.PROJECT_STAGE
    FIELDS = [
        lambda evs: ModifyResourcesMetaField.make_fields(evs),
        lambda _vs: [TimePassesMetaField()],
        lambda _vs: [ExploreHexMetaField()],
        # project stages don't have subtype for xp, unlike characters
        lambda _vs: [ModifyXpField()],
    ]

    @classmethod
    def create_challenge(
        cls,
        name: Optional[str],
        project_name: str,
        stage_num: int,
        base_skills: List[str],
        difficulty: int,
        cost: List[Effect],
    ) -> None:
        extra = ProjectStageChallenge(base_skills=base_skills, difficulty=difficulty)
        cls._create_common(
            name, project_name, stage_num, ProjectStageType.CHALLENGE, extra, cost
        )

    @classmethod
    def create_resource(
        cls,
        name: Optional[str],
        project_name: str,
        stage_num: int,
        wanted_resources: Set[str],
        cost: List[Effect],
    ) -> None:
        extra = ProjectStageResource(
            wanted_resources=wanted_resources, given_resources={}
        )
        cls._create_common(
            name, project_name, stage_num, ProjectStageType.RESOURCE, extra, cost
        )

    @classmethod
    def create_waiting(
        cls, name: Optional[str], project_name: str, stage_num: int, cost: List[Effect]
    ) -> None:
        extra = ProjectStageWaiting(turns_waited=0)
        cls._create_common(
            name, project_name, stage_num, ProjectStageType.WAITING, extra, cost
        )

    @classmethod
    def create_discovery(
        cls,
        name: Optional[str],
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
            name, project_name, stage_num, ProjectStageType.DISCOVERY, extra, cost
        )

    @classmethod
    def _create_common(
        cls,
        name: Optional[str],
        project_name: str,
        stage_num: int,
        type: ProjectStageType,
        extra: Any,
        cost: List[Effect],
    ) -> None:
        if name is None:
            name = f"{project_name} Stage {stage_num}"
        data = ProjectStageData(
            name=name,
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
    def load(cls, project_stage_name: str) -> "ProjectStageContext":
        return ProjectStageContext(project_stage_name)

    @classmethod
    def load_for_character(cls, character_name: str) -> "ProjectStagesContext":
        return ProjectStagesContext(
            lambda: [
                d
                for d in ProjectStageStorage.load()
                if character_name in d.participants
            ]
        )

    def get_snapshot(self) -> snapshot_ProjectStage:
        if self._data.type == ProjectStageType.CHALLENGE:
            extra = cast(ProjectStageChallenge, self._data.extra)
            snapshot_extra = snapshot_ProjectStageChallenge(
                base_skills=tuple(extra.base_skills), difficulty=extra.difficulty
            )
        elif self._data.type == ProjectStageType.RESOURCE:
            extra = cast(ProjectStageResource, self._data.extra)
            snapshot_extra = snapshot_ProjectStageResource(
                wanted_resources=extra.wanted_resources,
                given_resources=extra.given_resources,
            )
        elif self._data.type == ProjectStageType.WAITING:
            extra = cast(ProjectStageWaiting, self._data.extra)
            snapshot_extra = snapshot_ProjectStageWaiting(
                turns_waited=extra.turns_waited
            )
        elif self._data.type == ProjectStageType.DISCOVERY:
            extra = cast(ProjectStageDiscovery, self._data.extra)
            snapshot_extra = snapshot_ProjectStageDiscovery(
                ref_hexes=extra.ref_hexes,
                possible_hexes=extra.possible_hexes,
                explored_hexes=extra.explored_hexes,
            )
        else:
            raise Exception(f"Unknown type {self._data.type.name}")

        return snapshot_ProjectStage(
            name=self.name,
            project_name=self._data.project_name,
            stage_num=self._data.stage_num,
            desc=self._data.desc,
            type=self._data.type,
            participants=self._data.participants,
            status=self._data.status,
            xp=self._data.xp,
            max_xp=self._data.xp,
            extra=snapshot_extra,
        )

    def start(self, character_name: str, events: List[Event]) -> None:
        if self.status != ProjectStageStatus.UNASSIGNED:
            raise BadStateException(f"Stage is in {self.status.name}, not unassigned")
        self._data.participants = [character_name]
        self._data.status = ProjectStageStatus.IN_PROGRESS
        events.append(
            Event.for_project_stage(
                self.name,
                EffectType.START_PROJECT_STAGE,
                None,
                None,
                character_name,
                [],
            )
        )

    def do_return(self, character_name: str, events: List[Event]) -> None:
        if self.status != ProjectStageStatus.IN_PROGRESS:
            raise BadStateException(f"Stage is in {self.status.name}, not in progress")
        self._data.participants.remove(character_name)
        if not self._data.participants:
            self._data.status = ProjectStageStatus.UNASSIGNED
        events.append(
            Event.for_project_stage(
                self.name,
                EffectType.RETURN_PROJECT_STAGE,
                None,
                None,
                character_name,
                [],
            )
        )


class ProjectStageContext:
    def __init__(self, project_stage_name: str) -> None:
        self.project_stage_name = project_stage_name

    def __enter__(self) -> "ProjectStage":
        self._data = ProjectStageStorage.load_by_name(self.project_stage_name)
        return ProjectStage(self._data)

    def __exit__(self, *exc: Any) -> None:
        ProjectStageStorage.update(self._data)


class ProjectStagesContext:
    def __init__(self, load_func: Callable[[], List[ProjectStage]]) -> None:
        self.load_func = load_func

    def __enter__(self) -> List[ProjectStage]:
        self._data_list = self.load_func()
        return [ProjectStage(d) for d in self._data_list]

    def __exit__(self, *exc: Any) -> None:
        for d in self._data_list:
            ProjectStageStorage.update(d)


class ModifyResourcesMetaField(IntEntityField):
    def __init__(self, subtype: str):
        super().__init__(
            f"resources_{subtype}",
            EffectType.MODIFY_RESOURCES,
            subtype,
            self._get_init,
            self._do_deliver,
        )

    def _get_init(self, entity: Entity) -> int:
        if entity._data.type != ProjectStageType.RESOURCE:
            return 0
        extra = cast(ProjectStageResource, entity._data.extra)
        return extra.given_resources.get(self._subtype, 0)

    def _do_deliver(self, entity: Entity, val: int) -> bool:
        if entity._data.type != ProjectStageType.RESOURCE:
            return False
        extra = cast(ProjectStageResource, entity._data.extra)
        if self._subtype not in extra.wanted_resources:
            raise IllegalMoveException(
                f"Resource {self._subtype} is not needed by {entity.name}!"
            )

        inc = val - self._init_value
        if self._subtype not in extra.given_resources:
            if inc <= 0:
                return False
            extra.given_resources[self._subtype] = inc
        else:
            extra.given_resources[self._subtype] += inc

        self._split_effects[(EffectType.MODIFY_XP, None)].append(
            Effect(
                EffectType.MODIFY_XP,
                inc * 5,
            )
        )

        # generate a regular event for the project gaining resources
        return True

    @classmethod
    def make_fields(
        cls,
        split_effects: Dict[Tuple[EntityType, Optional[str]], List[Effect]],
    ) -> List[EntityField]:
        subtypes = [
            k[1]
            for k in split_effects
            if k[0] == EffectType.MODIFY_RESOURCES and k[1] is not None
        ]
        return [cls(subtype) for subtype in subtypes]


class TimePassesMetaField(IntEntityField):
    def __init__(self):
        super().__init__(
            "waiting",
            EffectType.TIME_PASSES,
            None,
            init_v=lambda e: 0,
            set_v=self._do_wait,
        )

    def _do_wait(self, entity: Entity, val: int) -> bool:
        if entity._data.type != ProjectStageType.WAITING:
            return False
        if val <= 0:
            raise Exception("Don't know how to un-wait yet")
        extra = cast(ProjectStageWaiting, entity._data.extra)
        extra.turns_waited += val
        self._split_effects[(EffectType.MODIFY_XP, None)].append(
            Effect(
                EffectType.MODIFY_XP,
                val,
                comment=f"Time passes",
            )
        )
        return False


class ExploreHexMetaField(EntityField):
    def __init__(self):
        super().__init__(
            "exploration",
            EffectType.EXPLORE,
            None,
        )

    def _update(self, effect: Effect, is_first: bool, is_last: bool) -> None:
        if self._entity._data.type != ProjectStageType.DISCOVERY:
            return
        extra = cast(ProjectStageDiscovery, self._entity._data.extra)
        if effect.value not in extra.possible_hexes:
            return
        extra.possible_hexes.discard(effect.value)
        extra.explored_hexes.add(effect.value)
        if effect.value == extra.secret_hex:
            self._split_effects[(EffectType.MODIFY_XP, None)].append(
                Effect(
                    EffectType.MODIFY_XP,
                    self._entity.max_xp,
                    comment=f"Secret hex located!",
                )
            )


class ModifyXpField(IntEntityField):
    def __init__(self):
        super().__init__(
            "xp",
            EffectType.MODIFY_XP,
            None,
            init_v=lambda e: e.xp,
            set_v=self._do_set,
            max_value=lambda e: e.max_xp,
        )

    def _do_set(self, entity: Entity, val: int) -> bool:
        entity._data.xp = val
        if entity._data.xp == entity._data.max_xp:
            entity._data.status = ProjectStageStatus.FINISHED
        return True  # just generate the standard event


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
            actions=[
                Action(
                    name="Deliver",
                    choices=Choices.make_special(
                        type=SpecialChoiceType.DELIVER, entity=name
                    ),
                ),
            ],
            events=[],
        )

    @classmethod
    def load(cls, name: str) -> "ProjectContext":
        return ProjectContext(name)

    @classmethod
    def load_for_character(cls, character_name: str) -> "ProjectsContext":
        return ProjectsContext(lambda: list(ProjectStorage.load()))

    def get_snapshot(self, character_name: str, include_all: bool) -> snapshot_Project:
        stages = [
            ProjectStage(d).get_snapshot()
            for d in ProjectStageStorage.load_by_project(self.name)
            if include_all or character_name in d.participants
        ]
        stages.sort(key=lambda s: (s.stage_num))
        return snapshot_Project(
            name=self.name,
            desc=self.desc,
            type=self.type,
            status=self.status,
            target_hex=self.target_hex,
            stages=tuple(stages),
        )

    def add_stage(self, stage_type: Optional[ProjectStageType], **kwargs) -> None:
        cur_stages = ProjectStageStorage.load_by_project(self.name)

        if stage_type is None:
            stage_type = random.choice(list(ProjectStageType))
        cost = kwargs.get("cost", None) or [
            Effect(type=EffectType.MODIFY_COINS, value=-10)
        ]

        stage_name = kwargs.get("name", None)

        if stage_type == ProjectStageType.CHALLENGE:
            project_type = ProjectTypeStorage.load_by_name(self.type)
            base_skills = kwargs.get("base_skills", None) or project_type.base_skills
            # difficulty should come off some combo of base project difficulty (?) and number of stages so far
            difficulty = kwargs.get("difficulty", None) or 3
            ProjectStage.create_challenge(
                stage_name,
                self.name,
                len(cur_stages) + 1,
                base_skills,
                difficulty,
                cost,
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
                stage_name, self.name, len(cur_stages) + 1, resources, cost
            )
        elif stage_type == ProjectStageType.WAITING:
            ProjectStage.create_waiting(
                stage_name, self.name, len(cur_stages) + 1, cost
            )
        elif stage_type == ProjectStageType.DISCOVERY:
            start_hex = kwargs.get("start_hex", None)
            secret_hex = kwargs.get("secret_hex", None)
            if not start_hex and not secret_hex:
                start_hex = self.target_hex
            ProjectStage.create_discovery(
                stage_name,
                self.name,
                len(cur_stages) + 1,
                start_hex=start_hex,
                secret_hex=secret_hex,
                cost=cost,
            )
        else:
            raise Exception(f"Bad stage type: {stage_type}")

    def finish(self) -> None:
        self._data.status = ProjectStatus.FINISHED
        board = load_board()
        board.remove_token(f"Site: {self.name}")


class ProjectContext:
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> Project:
        self._data = ProjectStorage.load_by_name(self.name)
        return Project(self._data)

    def __exit__(self, *exc: Any) -> None:
        ProjectStorage.update(self._data)


class ProjectsContext:
    def __init__(self, load_func: Callable[[], List[Project]]) -> None:
        self.load_func = load_func

    def __enter__(self) -> List[Project]:
        self._data_list = self.load_func()
        return [Project(d) for d in self._data_list]

    def __exit__(self, *exc: Any) -> None:
        for d in self._data_list:
            ProjectStorage.update(d)


@dataclass()
class ProjectStageData:
    name: str
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
    def load_by_name(cls, name: str) -> ProjectStageData:
        stages = cls._select_helper(
            ["name = :name"],
            {"name": name},
        )
        if not stages:
            raise IllegalMoveException(f"No such stage: {name}")
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
