from typing import Any, Dict, List, Optional, Sequence

from .character import CharacterRules
from .translate import TranslateRules
from .types.common import Action
from .types.snapshot import (
    Action as snapshot_Action,
    Board as snapshot_Board,
    Character as snapshot_Character,
    Country as snapshot_Country,
    Entity as snapshot_Entity,
    Game as snapshot_Game,
    Hex as snapshot_Hex,
    Job as snapshot_Job,
)
from .types.store import (
    Character,
    Country,
    Entity,
    Gadget,
    Game,
    Hex,
    Token,
)


class SearchRules:
    @classmethod
    def search_boards(cls) -> snapshot_Board:
        hexes = Hex.load_all()
        countries = Country.load_all()

        return snapshot_Board(
            hexes=tuple(TranslateRules.to_snapshot_hex(hx) for hx in hexes),
            countries=tuple(TranslateRules.to_snapshot_country(c) for c in countries),
        )

    @classmethod
    def search_skills(cls) -> List[str]:
        return Game.load().skills

    @classmethod
    def search_resources(cls) -> List[str]:
        return Game.load().resources

    @classmethod
    def search_zodiacs(cls) -> List[str]:
        return Game.load().zodiacs

    @classmethod
    def search_games(cls, name: Optional[str]) -> List[snapshot_Game]:
        if name is not None:
            games = [Game.load_by_name(name)]
        else:
            games = Game.load_all()
        return [TranslateRules.to_snapshot_game(g) for g in games]

    @classmethod
    def search_entities(cls, details: bool) -> List[snapshot_Entity]:
        entities = Entity.load_all()
        return [TranslateRules.to_snapshot_entity(e, details) for e in entities]

    @classmethod
    def search_jobs(cls) -> List[snapshot_Job]:
        jobs = Job.load_all()
        return [TranslateRules.to_snapshot_job(v) for v in jobs]

    @classmethod
    def search_characters(cls, character_name: str) -> List[snapshot_Character]:
        characters = [Character.load_by_name(character_name)]
        return [TranslateRules.to_snapshot_character(v) for v in characters]

    @classmethod
    def search_actions(cls, character_name: str) -> List[snapshot_Action]:
        ch = Character.load_by_name(character_name)
        actions, routes = CharacterRules.get_relevant_actions(ch)
        return [TranslateRules.to_snapshot_action(v, routes[v.uuid]) for v in actions]
