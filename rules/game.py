import dataclasses
import random
from collections import defaultdict
from typing import List, Optional, Sequence

from picaro.common.storage import ConnectionManager, make_uuid

from .board import BoardRules
from .character import CharacterRules
from .encounter import EncounterRules
from .include import translate
from .include.apply import (
    ActivityApplier,
    AddEntityApplier,
    AddTitleApplier,
    AmountApplier,
    LeadershipApplier,
    ModifyJobApplier,
    ModifyLocationApplier,
    QueueEncounterApplier,
    ResourceApplier,
    TickMeterApplier,
    TransportApplier,
    XpApplier,
    apply_effects,
)
from .include.special_cards import (
    actualize_special_card,
    queue_bad_reputation_check,
    queue_discard_resources,
)
from .types.external import CreateGameData, Record as external_Record
from .types.internal import (
    Character,
    Choice,
    Choices,
    Country,
    Effect,
    EffectType,
    Encounter,
    EncounterContextType,
    EntityType,
    Entity,
    Game,
    Hex,
    HexDeck,
    Job,
    Meter,
    Overlay,
    Record,
    ResourceDeck,
    TableauCard,
    TemplateDeck,
    Token,
    Trigger,
    TriggerType,
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
            translate.from_external_template_deck(d) for d in data.template_decks
        )
        Job.insert(translate.from_external_job(j) for j in data.jobs)
        Country.insert(translate.from_external_country(c) for c in data.countries)
        Hex.insert(translate.from_external_hex(h) for h in data.hexes)
        entities: List[Entity] = []
        tokens: List[Token] = []
        overlays: List[Overlay] = []
        triggers: List[Trigger] = []
        meters: List[Meter] = []
        for external_entity in data.entities:
            (
                cur_entity,
                cur_tokens,
                cur_overlays,
                cur_triggers,
                cur_meters,
            ) = translate.from_external_entity(external_entity)
            entities.append(cur_entity)
            tokens.extend(cur_tokens)
            overlays.extend(cur_overlays)
            triggers.extend(cur_triggers)
            meters.extend(cur_meters)
        Entity.insert(entities)
        Token.insert(tokens)
        Overlay.insert(overlays)
        Trigger.insert(triggers)
        Meter.insert(meters)
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
        return ch_uuid

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

        if cls.run_triggers(ch, TriggerType.START_TURN, None, records):
            cls.intra_turn(ch, records)

    @classmethod
    def end_turn(cls, ch: Character, records: List[Record]) -> None:
        cls.intra_turn(ch, records)
        if cls.encounter_check(ch):
            return

        if not ch.check_set_flag(TurnFlags.RAN_END_TURN_TRIGGERS):
            if cls.run_triggers(ch, TriggerType.END_TURN, None, records):
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
        ch.tableau = [t for t in ch.tableau if t.age > 0 and t.location in neighbors]

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
    def run_triggers(
        cls,
        ch: Character,
        type: TriggerType,
        subtype: Optional[str],
        records: List[Record],
    ) -> bool:
        effects = CharacterRules.run_triggers(ch, type, subtype)
        cls.apply_effects(ch, [], effects, records)

    @classmethod
    def save_translate_records(
        cls,
        records: Sequence[Record],
    ) -> Sequence[external_Record]:
        Record.insert(records)
        return [translate.to_external_record(Record.load(r.uuid)) for r in records]

    # In these args, effects is for when the character has done a thing, and this
    # is the outcome, which applies in all cases. If the character has 3 coins,
    # and this has an effect of -10 coins, the character ends up with 0 coins
    # and life goes on. Whereas costs is for when the character is doing a thing
    # in exchange for another thing (like trading a Steel resource for 5 xp).
    # If the character has 3 coins, and this has an effect of -10 coins, it'll
    # raise an exception and the whole thing will fail.
    @classmethod
    def apply_effects(
        cls,
        ch: Character,
        costs: List[Effect],
        effects: List[Effect],
        records: List[Record],
    ) -> None:
        cls._apply_shared(ch, costs, records, enforce_costs=True)
        cls._apply_shared(ch, effects, records, enforce_costs=False)

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
            if eff.ch_uuid is None or eff.ch_uuid == ch.uuid:
                default_list.append(eff)
            else:
                others_dict[eff.ch_uuid].append(eff)
        others = list(others_dict.items())

        if default_list:
            apply_effects(
                default_list, ch, cls.APPLIERS, records, enforce_costs=enforce_costs
            )
        for other_uuid, other_list in others:
            with Character.load_for_write(other_uuid) as other_ch:
                apply_effects(
                    other_list,
                    other_ch,
                    cls.APPLIERS,
                    records,
                    enforce_costs=enforce_costs,
                )

    APPLIERS = [
        LeadershipApplier(),
        ModifyJobApplier(),
        ResourceApplier(),
        TransportApplier(),
        ModifyLocationApplier(),
        ActivityApplier(),
        AmountApplier(EffectType.MODIFY_COINS, "coins", "coins"),
        AddEntityApplier(),
        AddTitleApplier(),
        QueueEncounterApplier(),
        AmountApplier(EffectType.MODIFY_LUCK, "luck", "luck"),
        AmountApplier(EffectType.MODIFY_REPUTATION, "reputation", "reputation"),
        AmountApplier(
            EffectType.MODIFY_HEALTH,
            "health",
            "health",
            max_value=lambda e: CharacterRules.get_max_health(e),
        ),
        AmountApplier(EffectType.MODIFY_TURNS, "turns", "remaining_turns"),
        # speed gets reset to its max each turn, but we allow it to go over
        # within a turn
        AmountApplier(EffectType.MODIFY_SPEED, "speed", "speed"),
        XpApplier(),
        TickMeterApplier(),
    ]
