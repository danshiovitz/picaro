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
    Task as snapshot_Task,
    TaskExtraChallenge as snapshot_TaskExtraChallenge,
    TaskExtraResource as snapshot_TaskExtraResource,
    TaskExtraWaiting as snapshot_TaskExtraWaiting,
    TaskExtraDiscovery as snapshot_TaskExtraDiscovery,
    Project as snapshot_Project,
)
from .storage import ObjectStorageBase, ReadOnlyWrapper
from .types import (
    Action,
    Challenge,
    Choices,
    Effect,
    EffectType,
    EncounterEffect,
    EntityType,
    Event,
    TaskStatus,
    TaskType,
    ProjectStatus,
    SpecialChoiceType,
    TemplateCard,
)


class Task(Entity, ReadOnlyWrapper):
    ENTITY_TYPE = EntityType.TASK
    FIELDS = [
        lambda evs: ModifyResourcesMetaField.make_fields(evs),
        lambda _vs: [TimePassesMetaField()],
        lambda _vs: [ExploreHexMetaField()],
        # project tasks don't have subtype for xp, unlike characters
        lambda _vs: [ModifyXpField()],
    ]

    @classmethod
    def create_challenge(
        cls,
        name: Optional[str],
        project_name: str,
        task_idx: int,
        cost: List[Effect],
        difficulty: int,
        skills: List[str],
    ) -> None:
        extra = TaskExtraChallenge(skills=skills)
        cls._create_common(
            name, project_name, task_idx, TaskType.CHALLENGE, cost, difficulty, extra
        )

    @classmethod
    def create_resource(
        cls,
        name: Optional[str],
        project_name: str,
        task_idx: int,
        cost: List[Effect],
        difficulty: int,
        wanted_resources: Set[str],
    ) -> None:
        extra = TaskExtraResource(wanted_resources=wanted_resources, given_resources={})
        cls._create_common(
            name, project_name, task_idx, TaskType.RESOURCE, cost, difficulty, extra
        )

    @classmethod
    def create_waiting(
        cls,
        name: Optional[str],
        project_name: str,
        task_idx: int,
        cost: List[Effect],
        difficulty: int,
    ) -> None:
        extra = TaskExtraWaiting(turns_waited=0)
        cls._create_common(
            name, project_name, task_idx, TaskType.WAITING, cost, difficulty, extra
        )

    @classmethod
    def create_discovery(
        cls,
        name: Optional[str],
        project_name: str,
        task_idx: int,
        cost: List[Effect],
        difficulty: int,
        start_hex: Optional[str],
        secret_hex: Optional[str],
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
        extra = TaskExtraDiscovery(
            secret_hex=secret_hex,
            ref_hexes=[(ref_hex, 3)],
            possible_hexes=set(possible_hexes),
            explored_hexes=set(),
        )
        cls._create_common(
            name, project_name, task_idx, TaskType.DISCOVERY, cost, difficulty, extra
        )

    @classmethod
    def _create_common(
        cls,
        name: Optional[str],
        project_name: str,
        task_idx: int,
        type: TaskType,
        cost: List[Effect],
        difficulty: int,
        extra: Any,
    ) -> None:
        if name is None:
            name = f"{project_name} Task {task_idx}"
        data = TaskData(
            name=name,
            project_name=project_name,
            task_idx=task_idx,
            desc="...",
            type=type,
            cost=cost,
            difficulty=difficulty,
            participants=[],
            status=TaskStatus.UNASSIGNED,
            xp=0,
            max_xp=25,
            extra=extra,
        )
        task = Task(data)
        TaskStorage.create(data)

    @classmethod
    def load(cls, task_name: str) -> "TaskContext":
        return TaskContext(task_name)

    @classmethod
    def load_for_character(cls, character_name: str) -> "TasksContext":
        return TasksContext(
            lambda: [d for d in TaskStorage.load() if character_name in d.participants]
        )

    def get_snapshot(self) -> snapshot_Task:
        if self._data.type == TaskType.CHALLENGE:
            extra = cast(TaskExtraChallenge, self._data.extra)
            snapshot_extra = snapshot_TaskExtraChallenge(skills=tuple(extra.skills))
        elif self._data.type == TaskType.RESOURCE:
            extra = cast(TaskExtraResource, self._data.extra)
            snapshot_extra = snapshot_TaskExtraResource(
                wanted_resources=extra.wanted_resources,
                given_resources=extra.given_resources,
            )
        elif self._data.type == TaskType.WAITING:
            extra = cast(TaskExtraWaiting, self._data.extra)
            snapshot_extra = snapshot_TaskExtraWaiting(turns_waited=extra.turns_waited)
        elif self._data.type == TaskType.DISCOVERY:
            extra = cast(TaskExtraDiscovery, self._data.extra)
            snapshot_extra = snapshot_TaskExtraDiscovery(
                ref_hexes=extra.ref_hexes,
                possible_hexes=extra.possible_hexes,
                explored_hexes=extra.explored_hexes,
            )
        else:
            raise Exception(f"Unknown type {self._data.type.name}")

        return snapshot_Task(
            name=self.name,
            project_name=self._data.project_name,
            task_idx=self._data.task_idx,
            desc=self._data.desc,
            type=self._data.type,
            cost=self._data.cost,
            difficulty=self._data.difficulty,
            participants=self._data.participants,
            status=self._data.status,
            xp=self._data.xp,
            max_xp=self._data.xp,
            extra=snapshot_extra,
        )

    def start(self, character_name: str, events: List[Event]) -> None:
        if self.status != TaskStatus.UNASSIGNED:
            raise BadStateException(f"Task is in {self.status.name}, not unassigned")
        self._data.participants = [character_name]
        self._data.status = TaskStatus.IN_PROGRESS
        events.append(
            Event.for_task(
                self.name,
                EffectType.START_TASK,
                None,
                None,
                character_name,
                [],
            )
        )

    def do_return(self, character_name: str, events: List[Event]) -> None:
        if self.status != TaskStatus.IN_PROGRESS:
            raise BadStateException(f"Task is in {self.status.name}, not in progress")
        self._data.participants.remove(character_name)
        if not self._data.participants:
            self._data.status = TaskStatus.UNASSIGNED
        events.append(
            Event.for_task(
                self.name,
                EffectType.RETURN_TASK,
                None,
                None,
                character_name,
                [],
            )
        )

    def get_templates(self) -> List[TemplateCard]:
        if self.status != TaskStatus.IN_PROGRESS:
            return []
        if self.type == TaskType.CHALLENGE:
            extra = cast(TaskExtraChallenge, self._data.extra)
            return [
                TemplateCard(
                    copies=2,
                    name=f"A {self.name} Challenge!",
                    desc=f"A new development in this task.",
                    challenge=Challenge(
                        skills=extra.skills + extra.skills,
                        rewards=[EncounterEffect.GAIN_PROJECT_XP] * 4,
                        penalties=[EncounterEffect.DAMAGE, EncounterEffect.LOSE_COINS],
                        difficulty=self._data.difficulty,
                    ),
                    entity_type=EntityType.TASK,
                    entity_name=self.name,
                )
            ]
        else:
            return []


class TaskContext:
    def __init__(self, task_name: str) -> None:
        self.task_name = task_name

    def __enter__(self) -> "Task":
        self._data = TaskStorage.load_by_name(self.task_name)
        return Task(self._data)

    def __exit__(self, *exc: Any) -> None:
        TaskStorage.update(self._data)


class TasksContext:
    def __init__(self, load_func: Callable[[], List[Task]]) -> None:
        self.load_func = load_func

    def __enter__(self) -> List[Task]:
        self._data_list = self.load_func()
        return [Task(d) for d in self._data_list]

    def __exit__(self, *exc: Any) -> None:
        for d in self._data_list:
            TaskStorage.update(d)


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
        if entity._data.type != TaskType.RESOURCE:
            return 0
        extra = cast(TaskExtraResource, entity._data.extra)
        return extra.given_resources.get(self._subtype, 0)

    def _do_deliver(self, entity: Entity, val: int) -> bool:
        if entity._data.type != TaskType.RESOURCE:
            return False
        extra = cast(TaskExtraResource, entity._data.extra)
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
        if entity._data.type != TaskType.WAITING:
            return False
        if val <= 0:
            raise Exception("Don't know how to un-wait yet")
        extra = cast(TaskExtraWaiting, entity._data.extra)
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

    def _update(self, effect: Effect, is_first: bool, is_last: bool, enforce_costs: bool) -> None:
        if self._entity._data.type != TaskType.DISCOVERY:
            return
        extra = cast(TaskExtraDiscovery, self._entity._data.extra)
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
            entity._data.status = TaskStatus.FINISHED
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
            name=name,
            type=EntityType.PROJECT,
            location=target_hex,
            actions=[
                Action(
                    name="Deliver",
                    choices=Choices.make_special(type=SpecialChoiceType.DELIVER),
                ),
            ],
            events=[],
        )

    @classmethod
    def load(cls, name: str) -> "ProjectContext":
        return ProjectContext(name)

    @classmethod
    def load_in_progress(cls) -> "ProjectsContext":
        return ProjectsContext(lambda: list(ProjectStorage.load_by_status(ProjectStatus.IN_PROGRESS)))

    def get_snapshot(self, character_name: str, include_all: bool) -> snapshot_Project:
        tasks = [
            Task(d).get_snapshot()
            for d in TaskStorage.load_by_project(self.name)
            if include_all or character_name in d.participants
        ]
        tasks.sort(key=lambda s: (s.task_idx))
        return snapshot_Project(
            name=self.name,
            desc=self.desc,
            type=self.type,
            status=self.status,
            target_hex=self.target_hex,
            tasks=tuple(tasks),
        )

    def add_task(self, task_type: Optional[TaskType], **kwargs) -> None:
        cur_tasks = TaskStorage.load_by_project(self.name)

        if task_type is None:
            task_type = random.choice(list(TaskType))
        cost = kwargs.get("cost", None) or [
            Effect(type=EffectType.MODIFY_COINS, value=-10)
        ]

        task_name = kwargs.get("name", None)

        # difficulty should come off some combo of base project difficulty (?) and number of tasks so far
        difficulty = kwargs.get("difficulty", None) or 3

        common_args = (task_name, self.name, len(cur_tasks) + 1, cost, difficulty)

        if task_type == TaskType.CHALLENGE:
            project_type = ProjectTypeStorage.load_by_name(self.type)
            skills = kwargs.get("skills", None) or project_type.skills
            Task.create_challenge(*common_args, skills)
        elif task_type == TaskType.RESOURCE:
            board = load_board()
            all_resources = list(board.get_base_resources())
            project_type = ProjectTypeStorage.load_by_name(self.type)
            all_resources.extend(project_type.resources * 3)
            resources = set(
                kwargs.get("resources", None) or random.sample(all_resources, 2)
            )
            Task.create_resource(*common_args, resources)
        elif task_type == TaskType.WAITING:
            Task.create_waiting(*common_args)
        elif task_type == TaskType.DISCOVERY:
            start_hex = kwargs.get("start_hex", None)
            secret_hex = kwargs.get("secret_hex", None)
            if not start_hex and not secret_hex:
                start_hex = self.target_hex
            Task.create_discovery(
                *common_args, start_hex=start_hex, secret_hex=secret_hex
            )
        else:
            raise Exception(f"Bad task type: {task_type}")

    def finish(self) -> None:
        self._data.status = ProjectStatus.FINISHED
        board = load_board()
        board.remove_token(self.name)


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
class TaskData:
    name: str
    project_name: str
    task_idx: int
    desc: Optional[str]
    type: TaskType
    cost: List[Effect]
    difficulty: int
    participants: List[str]
    status: TaskStatus
    xp: int
    max_xp: int
    extra: Any

    @classmethod
    def type_field(cls) -> str:
        return "type"

    @classmethod
    def any_type(cls, type_val: Union[TaskType, str]) -> type:
        if type(type_val) is str:
            type_val = TaskType[type_val]

        if type_val == TaskType.CHALLENGE:
            return TaskExtraChallenge
        elif type_val == TaskType.RESOURCE:
            return TaskExtraResource
        elif type_val == TaskType.WAITING:
            return TaskExtraWaiting
        elif type_val == TaskType.DISCOVERY:
            return TaskExtraDiscovery
        else:
            raise Exception("Unknown type")


@dataclass()
class TaskExtraChallenge:
    skills: List[str]


@dataclass()
class TaskExtraResource:
    wanted_resources: Set[str]
    given_resources: Dict[str, int]


@dataclass()
class TaskExtraWaiting:
    turns_waited: int


@dataclass()
class TaskExtraDiscovery:
    secret_hex: str
    ref_hexes: List[Tuple[str, int]]
    possible_hexes: Set[str]
    explored_hexes: Set[str]


@dataclass(frozen=True)
class ProjectType:
    name: str
    desc: str
    skills: List[str]
    resources: List[str]


@dataclass()
class ProjectData:
    name: str
    desc: str
    type: str
    status: ProjectStatus
    target_hex: str


class TaskStorage(ObjectStorageBase[TaskData]):
    TABLE_NAME = "task"
    PRIMARY_KEYS = {"project_name", "task_idx"}

    @classmethod
    def load(cls) -> List[TaskData]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_project(cls, project_name: str) -> List[TaskData]:
        return cls._select_helper(
            ["project_name = :project_name"], {"project_name": project_name}
        )

    @classmethod
    def load_by_name(cls, name: str) -> TaskData:
        tasks = cls._select_helper(
            ["name = :name"],
            {"name": name},
        )
        if not tasks:
            raise IllegalMoveException(f"No such task: {name}")
        return tasks[0]

    @classmethod
    def create(cls, task: TaskData) -> int:
        return cls._insert_helper([task])

    @classmethod
    def update(cls, task: TaskData) -> None:
        cls._update_helper(task)


class ProjectStorage(ObjectStorageBase[ProjectData]):
    TABLE_NAME = "project"
    PRIMARY_KEYS = {"name"}

    @classmethod
    def load(cls) -> List[ProjectData]:
        return cls._select_helper([], {})

    @classmethod
    def load_by_name(cls, name: str) -> ProjectData:
        projects = cls._select_helper(["name = :name"], {"name": name})
        if not projects:
            raise IllegalMoveException(f"No such project: {name}")
        return projects[0]

    @classmethod
    def load_by_status(cls, status: ProjectStatus) -> List[ProjectData]:
        return cls._select_helper(["status = :status"], {"status": status})

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
    def load_by_name(cls, name: str) -> List[TaskData]:
        types = cls._select_helper(["name = :name"], {"name": name})
        if not types:
            raise IllegalMoveException(f"No such project type: {name}")
        return types[0]
