import functools
from traceback import print_exc
from typing import Any, Callable, Dict, Type, TypeVar

from picaro.common.exceptions import IllegalMoveException, BadStateException
from picaro.common.serializer import deserialize, serialize
from picaro.common.storage import ConnectionManager
from picaro.rules.activity import ActivityRules
from picaro.rules.base import RulesManager
from picaro.rules.game import GameRules
from picaro.rules.search import SearchRules

from . import bottle
from .api_types import *


def wrap_errors() -> Callable[[Callable[..., Any]], Callable[..., bottle.HTTPResponse]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., bottle.HTTPResponse]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> bottle.HTTPResponse:
            type: ErrorType
            message = ""
            try:
                response = func(*args, **kwargs)
                return bottle.HTTPResponse(status=200, body=serialize(response))  # type: ignore
            except IllegalMoveException as ime:
                type = ErrorType.ILLEGAL_MOVE
                message = str(ime)
            except BadStateException as bse:
                type = ErrorType.BAD_STATE
                message = str(bse)
            except Exception as e:
                type = ErrorType.UNKNOWN
                message = f"Unexpected: {e.__class__.__name__} {e}"
                print_exc()
            response = ErrorResponse(type=type, message=message)
            return bottle.HTTPResponse(status=418, body=serialize(response))  # type: ignore

        return wrapper

    return decorator


T = TypeVar("T")


class Server:
    def __init__(self, db_path: Optional[str]) -> None:
        ConnectionManager.initialize(db_path=db_path)
        self.hacky_setup()
        # self.flat_setup()

    def hacky_setup(self) -> None:
        # buncha hacky initial setup:
        from pathlib import Path

        from picaro.client.generate import generate_game_v2

        player_uuid = "inkyinkyinky"
        other_player_uuid = "snickersabcd"
        with ConnectionManager(game_uuid=None, player_uuid=player_uuid):
            json_dir = Path(__file__).absolute().parent.parent / "hyboria"
            data = generate_game_v2("Hyboria", json_dir)
            game = GameRules.create_game(data)

        with ConnectionManager(game_uuid=game.uuid, player_uuid=player_uuid):
            with RulesManager("Conan"):
                ch = GameRules.add_character("Conan", player_uuid, "Raider", "random")
                ch = GameRules.add_character(
                    "Taurus", other_player_uuid, "Merchant", "random"
                )

                title = Title(
                    name="Cloak of Elvenkind",
                    overlays=[
                        SkillAmountOverlay(
                            uuid="123.456",
                            type=OverlayType.SKILL_RANK,
                            skill="Stealth",
                            amount=1,
                            is_private=True,
                            filters=(),
                        ),
                        SkillAmountOverlay(
                            uuid="123.457",
                            type=OverlayType.SKILL_RANK,
                            skill="Stealth",
                            amount=1,
                            is_private=True,
                            filters=(
                                SkillFilter(
                                    type=FilterType.SKILL_GTE,
                                    skill="Stealth",
                                    value=2,
                                ),
                            ),
                        ),
                        SkillAmountOverlay(
                            uuid="123.458",
                            type=OverlayType.RELIABLE_SKILL,
                            skill="Stealth",
                            amount=3,
                            is_private=True,
                            filters=(),
                        ),
                    ],
                )

                zeta_loc = [c for c in data.countries if c.name == "Zeta"][
                    0
                ].capitol_hex
                sword_overlays = [
                    ResourceAmountOverlay(
                        uuid="",
                        type=OverlayType.TRADE_PRICE,
                        resource="Steel",
                        amount=-1,
                        is_private=False,
                        filters=[
                            CountryFilter(
                                type=FilterType.IN_COUNTRY,
                                country="Zeta",
                            ),
                        ],
                    ),
                    ResourceAmountOverlay(
                        uuid="",
                        type=OverlayType.TRADE_PRICE,
                        resource="Wine",
                        amount=1,
                        is_private=False,
                        filters=[
                            CountryFilter(
                                type=FilterType.IN_COUNTRY,
                                country="Zeta",
                            ),
                        ],
                    ),
                    ResourceAmountOverlay(
                        uuid="",
                        type=OverlayType.TRADE_PRICE,
                        resource="Steel",
                        amount=1,
                        is_private=False,
                        filters=[
                            CountryFilter(
                                type=FilterType.IN_COUNTRY,
                                country="Zeta",
                                reverse=True,
                            ),
                        ],
                    ),
                ]
                sword_triggers = [
                    HexTrigger(
                        uuid="",
                        type=TriggerType.ENTER_HEX,
                        hex=None,
                        is_private=False,
                        filters=[
                            HexFilter(
                                type=FilterType.NEAR_HEX,
                                hex=zeta_loc,
                                distance=3,
                            ),
                        ],
                        effects=[
                            EntityAmountEffect(
                                type=EffectType.MODIFY_HEALTH,
                                amount=-1,
                            ),
                        ],
                    ),
                ]
                fight_template = TemplateCard(
                    name="Fight a Sword",
                    desc="This sword is itchin' for a fight.",
                    type=TemplateCardType.CHALLENGE,
                    data=Challenge(
                        skills=["Speed", "Dueling", "Thaumaturgy"],
                        rewards=[Outcome.GAIN_COINS, Outcome.GAIN_RESOURCES],
                        penalties=[Outcome.LOSE_REPUTATION, Outcome.LOSE_SPEED],
                    ),
                )
                sword_actions = [
                    Action(
                        uuid="",
                        name="Ride a Sword",
                        is_private=False,
                        filters=[],
                        costs=[
                            EntityAmountEffect(
                                type=EffectType.MODIFY_HEALTH,
                                amount=-5,
                            ),
                        ],
                        effects=[
                            LocationEffect(
                                type=EffectType.MODIFY_LOCATION,
                                hex=zeta_loc,
                            ),
                            EntityAmountEffect(
                                type=EffectType.MODIFY_SPEED,
                                amount=0,
                                is_absolute=True,
                            ),
                        ],
                        route=None,
                    ),
                    Action(
                        uuid="",
                        name="Fight a Sword",
                        is_private=False,
                        filters=[
                            HexFilter(
                                type=FilterType.NEAR_HEX,
                                hex=zeta_loc,
                                distance=5,
                            ),
                        ],
                        costs=[
                            EnableEffect(
                                type=EffectType.MODIFY_ACTIVITY,
                                enable=False,
                            ),
                        ],
                        effects=[
                            EncounterEffect(
                                type=EffectType.QUEUE_ENCOUNTER,
                                encounter=fight_template,
                            ),
                        ],
                        route=None,
                    ),
                ]

                entity = Entity(
                    type=EntityType.EVENT,
                    subtype=None,
                    name="Storm of Swords",
                    desc="Swords are just flying through the air, it's weird.",
                    titles=[
                        Title(
                            name=None,
                            overlays=sword_overlays,
                            triggers=sword_triggers,
                            actions=sword_actions,
                        ),
                    ],
                    locations=[],
                    uuid="",
                )

                ch = SearchRules.search_characters("Conan")[0]

                pig_actions = [
                    Action(
                        uuid="",
                        name="Feed the Pig",
                        is_private=False,
                        filters=[
                            TokenFilter(
                                type=FilterType.NEAR_TOKEN,
                                entity_uuid="##entity:uuid##",
                                distance=0,
                            ),
                        ],
                        costs=[
                            EntityAmountEffect(
                                type=EffectType.MODIFY_COINS,
                                amount=-1,
                            ),
                        ],
                        effects=[
                            MeterAmountEffect(
                                type=EffectType.TICK_METER,
                                entity_uuid="##entity:uuid##",
                                meter_uuid="##ph:coins_meter##",
                                amount=1,
                            ),
                        ],
                        route=None,
                    ),
                    Action(
                        uuid="",
                        name="Smash the Pig",
                        is_private=False,
                        filters=[
                            TokenFilter(
                                type=FilterType.NEAR_TOKEN,
                                entity_uuid="##entity:uuid##",
                                distance=0,
                            ),
                        ],
                        costs=[
                            MeterAmountEffect(
                                type=EffectType.TICK_METER,
                                entity_uuid="##entity:uuid##",
                                meter_uuid="##ph:coins_meter##",
                                amount=-10,
                            ),
                        ],
                        effects=[
                            EntityAmountEffect(
                                type=EffectType.MODIFY_COINS,
                                amount=10,
                            ),
                        ],
                        route=None,
                    ),
                ]

                pig_entity = Entity(
                    type=EntityType.LANDMARK,
                    subtype=None,
                    name="Piggy Bank",
                    desc="...",
                    titles=[
                        Title(
                            name=None,
                            meters=[
                                Meter(
                                    uuid="##ph:coins_meter##",
                                    name="Piggy Coins",
                                    min_value=0,
                                    max_value=100,
                                    cur_value=0,
                                ),
                            ],
                            actions=pig_actions,
                        ),
                    ],
                    locations=[ch.location],
                    uuid="",
                )

                from picaro.rules.types.internal import Character as internal_Character

                with internal_Character.load_by_name_for_write("Conan") as ch:
                    GameRules.apply_effects(
                        ch,
                        [],
                        [
                            EntityAmountEffect(type=EffectType.MODIFY_COINS, amount=50),
                            ResourceAmountEffect(
                                type=EffectType.MODIFY_RESOURCES,
                                resource=None,
                                amount=10,
                            ),
                            SkillAmountEffect(
                                type=EffectType.MODIFY_XP,
                                skill="Stealth",
                                amount=20,
                            ),
                            SkillAmountEffect(
                                type=EffectType.MODIFY_XP,
                                skill="Brutal Fighting",
                                amount=25,
                            ),
                            AddTitleEffect(
                                type=EffectType.ADD_TITLE,
                                title=title,
                            ),
                            AddEntityEffect(
                                type=EffectType.ADD_ENTITY,
                                entity=entity,
                            ),
                            AddEntityEffect(
                                type=EffectType.ADD_ENTITY,
                                entity=pig_entity,
                            ),
                        ],
                        [],
                    )

    def flat_setup(self) -> None:
        # buncha hacky initial setup:
        from picaro.rules.test.gen_flat import generate_flatworld

        player_uuid = "inkyinkyinky"
        with ConnectionManager(game_uuid=None, player_uuid=player_uuid):
            data = generate_flatworld()
            game = GameRules.create_game(data)

        with ConnectionManager(game_uuid=game.uuid, player_uuid=player_uuid):
            with RulesManager("AFGNCAAP"):
                ch = GameRules.add_character(
                    "AFGNCAAP", player_uuid, "Red Job 1", "random"
                )

                from picaro.rules.types.internal import (
                    Character,
                    Overlay,
                    OverlayType,
                    Filter,
                    FilterType,
                )

                with Character.load_by_name_for_write("AFGNCAAP") as ch:
                    GameRules.apply_effects(
                        ch,
                        [],
                        [
                            EntityAmountEffect(type=EffectType.MODIFY_COINS, amount=50),
                            ResourceAmountEffect(
                                type=EffectType.MODIFY_RESOURCES,
                                resource=None,
                                amount=10,
                            ),
                            SkillAmountEffect(
                                type=EffectType.MODIFY_XP,
                                resource="Skill 3",
                                amount=20,
                            ),
                            SkillAmountEffect(
                                type=EffectType.MODIFY_XP,
                                resource="Skill 5",
                                amount=25,
                            ),
                        ],
                        [],
                    )

    @wrap_errors()
    def search_entities(
        self, game_uuid: str, character_name: str
    ) -> SearchEntitiesResponse:
        player_uuid = self._extract_player_uuid()
        details = self._parse_bool(bottle.request.query.details)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchEntitiesResponse(
                    entities=SearchRules.search_entities(details=details)
                )

    @wrap_errors()
    def search_hexes(self, game_uuid: str, character_name: str) -> SearchHexesResponse:
        player_uuid = self._extract_player_uuid()
        details = self._parse_bool(bottle.request.query.details)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchHexesResponse(hexes=SearchRules.search_hexes())

    @wrap_errors()
    def get_character(self, game_uuid: str, character_name: str) -> Character:
        player_uuid = self._extract_player_uuid()
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchRules.search_characters(character_name)[0]

    @wrap_errors()
    def search_actions(
        self, game_uuid: str, character_name: str
    ) -> SearchActionsResponse:
        player_uuid = self._extract_player_uuid()
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchActionsResponse(
                    actions=SearchRules.search_actions(character_name),
                )

    @wrap_errors()
    def search_resources(
        self, game_uuid: str, character_name: str
    ) -> SearchResourcesResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchResourcesResponse(
                    resources=SearchRules.search_resources(),
                )

    @wrap_errors()
    def search_skills(
        self, game_uuid: str, character_name: str
    ) -> SearchSkillsResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchSkillsResponse(
                    skills=SearchRules.search_skills(),
                )

    @wrap_errors()
    def search_jobs(self, game_uuid: str, character_name: str) -> SearchJobsResponse:
        player_uuid = self._extract_player_uuid()
        include_all = self._parse_bool(bottle.request.query.all)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                return SearchJobsResponse(
                    jobs=SearchRules.search_jobs(),
                )

    @wrap_errors()
    def do_job(self, game_uuid: str, character_name: str) -> JobResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(JobRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.do_job(character_name, req.card_uuid)
        return JobResponse(records=records)

    @wrap_errors()
    def perform_action(self, game_uuid: str, character_name: str) -> ActionResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(ActionRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.perform_action(character_name, req.action_uuid)
        return ActionResponse(records=records)

    @wrap_errors()
    def travel(self, game_uuid: str, character_name: str) -> Any:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(TravelRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.travel(character_name, req.step)
        return TravelResponse(records=records)

    @wrap_errors()
    def camp(self, game_uuid: str, character_name: str) -> CampResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(CampRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.camp(character_name)
        if not req.rest:
            raise BadStateException("Rest is false!")
        else:
            return CampResponse(records=records)

    @wrap_errors()
    def resolve_encounter(self, game_uuid: str, character_name: str) -> Any:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(ResolveEncounterRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.resolve_encounter(character_name, req.commands)
        return ResolveEncounterResponse(records=records)

    @wrap_errors()
    def end_turn(self, game_uuid: str, character_name: str) -> EndTurnResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(EndTurnRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                records = ActivityRules.end_turn(character_name)
        return EndTurnResponse(records=records)

    @wrap_errors()
    def create_game(self) -> CreateGameResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(CreateGameRequest)
        with ConnectionManager(game_uuid=None, player_uuid=player_uuid):
            game = GameRules.create_game(req)
        return CreateGameResponse(game.uuid)

    @wrap_errors()
    def search_games(self) -> SearchGamesResponse:
        player_uuid = self._extract_player_uuid()
        name = bottle.request.query.name
        with ConnectionManager(game_uuid=None, player_uuid=player_uuid):
            return SearchGamesResponse(games=SearchRules.search_games(name=name))

    @wrap_errors()
    def add_character(
        self, game_uuid: str, character_name: str
    ) -> AddCharacterResponse:
        player_uuid = self._extract_player_uuid()
        req = self._read_body(AddCharacterRequest)
        with ConnectionManager(game_uuid=game_uuid, player_uuid=player_uuid):
            with RulesManager(character_name):
                ch = GameRules.add_character(
                    character_name, player_uuid, req.job_name, req.location or "random"
                )
        return AddCharacterResponse(ch.uuid)

    def _parse_bool(self, val: str) -> bool:
        return val and val[0].lower() == "t"

    def run(self) -> None:
        bottle.route(
            path="/games",
            method="GET",
            callback=self.search_games,
        )
        bottle.route(
            path="/games/create",
            method="POST",
            callback=self.create_game,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/add",
            method="POST",
            callback=self.add_character,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/entities",
            callback=self.search_entities,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/hexes",
            callback=self.search_hexes,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/character",
            callback=self.get_character,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/actions",
            callback=self.search_actions,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/resources",
            callback=self.search_resources,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/skills",
            callback=self.search_skills,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/jobs",
            callback=self.search_jobs,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/job",
            method="POST",
            callback=self.do_job,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/action",
            method="POST",
            callback=self.perform_action,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/travel",
            method="POST",
            callback=self.travel,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/camp",
            method="POST",
            callback=self.camp,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/resolve_encounter",
            method="POST",
            callback=self.resolve_encounter,
        )
        bottle.route(
            path="/game/<game_uuid>/<character_name>/play/end_turn",
            method="POST",
            callback=self.end_turn,
        )
        bottle.run(host="localhost", port=8080, debug=True)  # type: ignore

    def _extract_player_uuid(self) -> int:
        return 103

    def _read_body(self, cls: Type[T]) -> T:
        return deserialize(bottle.request.body.read(), cls)
