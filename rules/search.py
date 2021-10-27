from typing import Any, Dict, List, Optional, Sequence

from .character import CharacterRules
from .include import translate
from .types.external import (
    Action as external_Action,
    Character as external_Character,
    Country as external_Country,
    Entity as external_Entity,
    Game as external_Game,
    Hex as external_Hex,
    Job as external_Job,
)
from .types.internal import (
    Character,
    Country,
    Entity,
    Game,
    Hex,
    Job,
    RouteType,
)


class SearchRules:
    @classmethod
    def search_hexes(cls) -> List[Hex]:
        hexes = Hex.load_all()
        return tuple(translate.to_external_hex(hx) for hx in hexes)

    @classmethod
    def search_countries(cls) -> List[Country]:
        countries = Country.load_all()
        return tuple(translate.to_external_country(c) for c in countries)

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
    def search_games(cls, name: Optional[str] = None) -> List[external_Game]:
        if name is not None:
            games = [Game.load_by_name(name)]
        else:
            games = Game.load_all()
        return [translate.to_external_game(g) for g in games]

    @classmethod
    def search_jobs(cls) -> List[external_Job]:
        jobs = Job.load_all()
        return [translate.to_external_job(v) for v in jobs]

    @classmethod
    def search_entities(cls, details: bool) -> List[external_Entity]:
        entities = Entity.load_all()
        return [translate.to_external_entity(e, details) for e in entities]

    @classmethod
    def search_characters(
        cls, character_name: Optional[str] = None
    ) -> List[external_Character]:
        characters = (
            [Character.load_by_name(character_name)]
            if character_name
            else Character.load_all()
        )
        return [translate.to_external_character(v) for v in characters]

    @classmethod
    def search_actions(cls, character_name: str) -> List[external_Action]:
        ch = Character.load_by_name(character_name)
        actions, routes = CharacterRules.get_relevant_actions(ch)
        actions = [a for a in actions if routes[a.uuid].type != RouteType.UNAVAILABLE]
        return [translate.to_external_action(v, routes[v.uuid]) for v in actions]
