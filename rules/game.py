import dataclasses
import random
from collections import defaultdict
from typing import List, Optional, Sequence

from picaro.common.storage import ConnectionManager, make_uuid

from .board import BoardRules
from .character import CharacterRules
from .encounter import EncounterRules
from .lib import translate
from .lib.apply import SimpleIntField, SimpleDictIntField, apply_effects
from .lib.fields import (
    LeadershipMetaField,
    ModifyJobField,
    ResourceDrawMetaField,
    TransportField,
    ModifyLocationField,
    ModifyActivityField,
    AddEmblemField,
    QueueEncounterField,
    ModifyFreeXpField,
)
from .lib.special_cards import (
    actualize_special_card,
    queue_bad_reputation_check,
    queue_discard_resources,
)
from .types.common import (
    Choice,
    Choices,
    Effect,
    EffectType,
    Encounter,
    EncounterContextType,
    EntityType,
    TableauCard,
)
from .types.snapshot import CreateGameData, Record as snapshot_Record
from .types.store import (
    Character,
    Country,
    Entity,
    Gadget,
    Game,
    Hex,
    HexDeck,
    Job,
    Record,
    ResourceDeck,
    TemplateDeck,
    Token,
    TurnFlags,
)


class GameRules:
    @classmethod
    def create_game(cls, data: CreateGameData) -> Game:
        Game.create(
            name=data.name,
            skills=data.skills,
            resources=data.resources,
            zodiacs=data.zodiacs,
        )
        game = Game.load_by_name(data.name)
        ConnectionManager.fix_game_uuid(game.uuid)
        TemplateDeck.insert(
            translate.from_snapshot_template_deck(d) for d in data.template_decks
        )
        Job.insert(translate.from_snapshot_job(j) for j in data.jobs)
        Country.insert(translate.from_snapshot_country(c) for c in data.countries)
        Hex.insert(translate.from_snapshot_hex(h) for h in data.hexes)
        hex_types = {hx.terrain for hx in data.hexes}
        HexDeck.insert(HexDeck.create_detached(name=t, cards=[]) for t in hex_types)
        ResourceDeck.insert(
            ResourceDeck.create_detached(name=c.name, cards=[]) for c in data.countries
        )
        ResourceDeck.insert([ResourceDeck.create_detached(name="Wild", cards=[])])
        entities: List[snapshot_Entity] = []
        gadgets: List[snapshot_Gadget] = []
        tokens: List[snapshot_Token] = []
        for snapshot_entity in data.entities:
            cur_entity, cur_gadgets, cur_tokens = translate.from_snapshot_entity(
                snapshot_entity
            )
            entities.append(cur_entity)
            gadgets.extend(cur_gadgets)
            tokens.extend(cur_tokens)
        Entity.insert(entities)
        Gadget.insert(gadgets)
        Token.insert(tokens)
        return game

    @classmethod
    def add_character(
        cls,
        character_name: str,
        player_uuid: str,
        job_name: str,
        location: Optional[str],
    ) -> str:
        ch_uuid = cls._create_entity(
            name=character_name,
            type=EntityType.CHARACTER,
            subtype=None,
            locations=[location] if location else [],
        )
        CharacterRules.create(ch_uuid, player_uuid, job_name)
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            cls.start_season(ch, records)

    @classmethod
    def _create_entity(
        cls,
        name: str,
        type: EntityType,
        subtype: Optional[str],
        locations: Sequence[str],
    ) -> str:
        uuid = Entity.create(name=name, type=type, subtype=subtype)
        for location in locations:
            if location == "random":
                location = BoardRules.get_random_hex().name
            Token.create(entity=uuid, location=location)
        return uuid

    @classmethod
    def start_season(cls, ch: Character, records: List[Record]) -> None:
        ch.remaining_turns = CharacterRules.get_init_turns(ch)
        ch.luck = CharacterRules.get_max_luck(ch)
        cls.start_turn(ch, records)

    @classmethod
    def start_turn(cls, ch: Character, records: List[Record]) -> None:
        ch.speed = CharacterRules.get_init_speed(ch)
        ch.turn_flags.clear()

        while len(ch.tableau) < CharacterRules.get_max_tableau_size(ch):
            job = Job.load(ch.job_name)
            if not ch.job_deck:
                ch.job_deck = EncounterRules.load_deck(job.deck_name)

            dst = random.choice(job.encounter_distances)
            neighbors = BoardRules.find_entity_neighbors(ch.uuid, dst, dst)
            if not neighbors:
                # assume character is off the board, so they can't have encounters
                break

            card = EncounterRules.reify_card(
                ch.job_deck.pop(0),
                job.base_skills,
                job.rank + 1,
                EncounterContextType.JOB,
            )
            ch.tableau.append(
                TableauCard(
                    card=card,
                    age=CharacterRules.get_init_tableau_age(ch),
                    location=random.choice(neighbors).name,
                )
            )

    @classmethod
    def end_turn(cls, ch: Character, records: List[Record]) -> None:
        cls.intra_turn(ch, records)
        if cls.encounter_check(ch):
            return

        queue_bad_reputation_check(ch)
        if cls.encounter_check(ch):
            return

        queue_discard_resources(ch)
        if cls.encounter_check(ch):
            return

        # age out tableau
        ch.tableau = [dataclasses.replace(t, age=t.age - 1) for t in ch.tableau]
        neighbors = {
            ngh.name for ngh in BoardRules.find_entity_neighbors(ch.uuid, 0, 5)
        }
        ch.tableau = [t for t in ch.tableau if t.age > 1 and t.location in neighbors]

        ch.remaining_turns -= 1

        if ch.remaining_turns > 0:
            cls.start_turn(ch, records)
        else:
            cls.end_season(ch, records)

    @classmethod
    def end_season(cls, ch: Character, records: List[Record]) -> None:
        # do end of season stuff
        pass

    @classmethod
    def intra_turn(cls, ch: Character, records: List[Record]) -> None:
        # check if dead
        cls.encounter_check(ch)

    @classmethod
    def encounter_check(cls, ch: Character) -> bool:
        if ch.encounter:
            return True
        elif ch.queued:
            ch.encounter = EncounterRules.make_encounter(ch, ch.queued.pop(0))
            return True
        else:
            return False

    @classmethod
    def save_translate_records(
        cls,
        records: Sequence[Record],
    ) -> Sequence[snapshot_Record]:
        Record.insert(records)
        return [translate.to_snapshot_record(Record.load(r.uuid)) for r in records]

    # This one is for when the character has done a thing, and this is the outcome,
    # which applies in all cases. If the character has 3 coins, and this has an effect
    # of -10 coins, the character ends up with 0 coins and life goes on.
    @classmethod
    def apply_regardless(
        cls,
        ch: Character,
        effects: List[Effect],
        records: List[Record],
    ) -> None:
        cls._apply_shared(ch, effects, records, enforce_costs=False)

    # This one is for when the character is doing a thing in exchange for another thing
    # (like trading a Steel resource for 5 xp). If the character has 3 coins, and this has
    # an effect of -10 coins, it'll raise an exception and the whole thing will fail.
    @classmethod
    def apply_bargain(
        cls,
        ch: Character,
        effects: List[Effect],
        records: List[Record],
    ) -> None:
        cls._apply_shared(ch, effects, records, enforce_costs=True)

    @classmethod
    def _apply_shared(
        cls,
        ch: Character,
        effects: List[Effect],
        records: List[Record],
        enforce_costs: bool,
    ) -> None:
        default_list: List[Effect] = []
        others_dict: Dict[str, List[Effect]] = defaultdict(list)
        for eff in effects:
            if eff.entity_uuid is None or eff.entity_uuid == ch.uuid:
                default_list.append(eff)
            else:
                others_dict[eff.entity_uuid].append(eff)
        others = list(others_dict.items())

        if default_list:
            apply_effects(
                default_list, ch, cls.APPLY_FIELDS, records, enforce_costs=enforce_costs
            )
        for other_uuid, other_list in others:
            with Character.load_for_write(other_uuid) as other_ch:
                apply_effects(
                    other_list,
                    other_ch,
                    cls.APPLY_FIELDS,
                    records,
                    enforce_costs=enforce_costs,
                )

    APPLY_FIELDS = [
        lambda _vs: [LeadershipMetaField()],
        lambda _vs: [ModifyJobField()],
        lambda _vs: [ResourceDrawMetaField()],
        lambda recs: SimpleDictIntField.make_fields(
            recs, "resources", "resources", EffectType.MODIFY_RESOURCES
        ),
        lambda _vs: [TransportField()],
        lambda _vs: [ModifyLocationField()],
        lambda _vs: [ModifyActivityField()],
        lambda _vs: [SimpleIntField("coins", "coins", EffectType.MODIFY_COINS)],
        lambda _vs: [AddEmblemField()],
        lambda _vs: [QueueEncounterField()],
        lambda _vs: [SimpleIntField("luck", "luck", EffectType.MODIFY_LUCK)],
        lambda _vs: [
            SimpleIntField("reputation", "reputation", EffectType.MODIFY_REPUTATION)
        ],
        lambda _vs: [
            SimpleIntField(
                "health",
                "health",
                EffectType.MODIFY_HEALTH,
                max_value=lambda e: CharacterRules.get_max_health(e),
            )
        ],
        lambda _vs: [
            SimpleIntField("turns", "remaining_turns", EffectType.MODIFY_TURNS)
        ],
        # speed gets reset to its max each turn, but we allow it to go over
        # within a turn
        lambda _vs: [SimpleIntField("speed", "speed", EffectType.MODIFY_SPEED)],
        lambda recs: SimpleDictIntField.make_fields(
            recs, "xp", "skill_xp", EffectType.MODIFY_XP
        ),
        lambda _vs: [ModifyFreeXpField()],
    ]
