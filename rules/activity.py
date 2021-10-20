from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple, cast

from picaro.common.exceptions import BadStateException, IllegalMoveException
from picaro.common.utils import pop_func, with_s

from .board import BoardRules
from .character import CharacterRules
from .encounter import EncounterRules
from .game import GameRules
from .lib.deck import shuffle_discard
from .types.external import EncounterCommands, Record as external_Record
from .types.internal import (
    Character,
    Choice,
    Choices,
    Effect,
    EffectType,
    Encounter,
    EncounterCheck,
    EncounterContextType,
    FullCard,
    FullCardType,
    Gadget,
    Hex,
    HexDeck,
    Outcome,
    Record, Token,
    TravelCard,
    TravelCardType,
    TurnFlags,
)


class ActivityRules:
    @classmethod
    def do_job(cls, character_name: str, card_uuid: str) -> Sequence[external_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if GameRules.encounter_check(ch):
                raise BadStateException("An encounter is currently active.")
            if ch.check_set_flag(TurnFlags.ACTED):
                raise BadStateException("You have already acted this turn.")

            try:
                card = pop_func(ch.tableau, lambda c: c.card.uuid == card_uuid)
            except IndexError:
                raise BadStateException(f"No such card in tableau: {card_uuid}")
            location = Token.load_single_by_entity(ch.uuid).location
            if card.location != location:
                raise IllegalMoveException(
                    f"You must be in hex {card.location} for that encounter."
                )
            ch.queued.append(card.card)
            GameRules.intra_turn(ch, records)
        return GameRules.save_translate_records(records)

    @classmethod
    def perform_action(
        cls, character_name: str, action_uuid: str
    ) -> Sequence[external_Record]:
        records: List[Record] = []
        action = Gadget.load_action_by_uuid(action_uuid)
        with Character.load_by_name_for_write(character_name) as ch:
            if GameRules.encounter_check(ch):
                raise BadStateException("An encounter is currently active.")
            CharacterRules.check_filters(ch, action.filters)
            GameRules.apply_effects(ch, action.costs, action.effects, records)
            GameRules.intra_turn(ch, records)
            return GameRules.save_translate_records(records)

    @classmethod
    def camp(cls, character_name: str) -> Sequence[external_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if GameRules.encounter_check(ch):
                raise BadStateException("An encounter is currently active.")
            GameRules.intra_turn(ch, records)
            return GameRules.save_translate_records(records)

    @classmethod
    def travel(cls, character_name: str, hex: str) -> Sequence[external_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if GameRules.encounter_check(ch):
                raise BadStateException("An encounter is currently active.")
            if ch.speed <= 0:
                raise IllegalMoveException(f"You have no remaining speed.")
            BoardRules.move_token_for_entity(ch.uuid, hex, adjacent=True)
            # moving and decreasing speed are normal effects, so we don't report them
            # in records (this might be wrong, especially if we eventually want records
            # to be a true undo log, but it makes the client easier for now)
            ch.speed -= 1
            # CharacterRules.run_triggers(ch, TriggerType.TRAVEL_TO_HEX, records)

            if TurnFlags.HAD_TRAVEL_ENCOUNTER not in ch.turn_flags:
                card = cls._draw_travel_card(ch, hex)
                if card:
                    ch.queued.append(card)
                    ch.turn_flags.add(TurnFlags.HAD_TRAVEL_ENCOUNTER)

            GameRules.intra_turn(ch, records)
            return GameRules.save_translate_records(records)

    @classmethod
    def _draw_travel_card(cls, ch: Character, location: str) -> Optional[FullCard]:
        if not ch.travel_deck:
            ch.travel_deck = cls._make_travel_deck()

        card = ch.travel_deck.pop(0)
        if card.type == TravelCardType.NOTHING:
            return None
        elif card.type == TravelCardType.DANGER:
            hx = Hex.load(location)
            if hx.danger >= card.value:
                return cls._draw_hex_card(hx)
            else:
                return None
        elif card.type == TravelCardType.SPECIAL:
            hx = Hex.load(location)
            return EncounterRules.reify_card(
                card.value, [], hx.danger, EncounterContextType.TRAVEL
            )
        else:
            raise Exception(f"Unknown card type: {card.type}")

    @classmethod
    def _make_travel_deck(cls) -> List[TravelCard]:
        specials = EncounterRules.load_deck("Travel")
        cards = []
        cards.extend([TravelCard(type=TravelCardType.NOTHING, value=0)] * 14)
        for i in range(1, 6):
            cards.extend([TravelCard(type=TravelCardType.DANGER, value=i)] * 3)
        for _ in range(2):
            cards.append(TravelCard(type=TravelCardType.SPECIAL, value=specials.pop(0)))
        return shuffle_discard(cards)

    @classmethod
    def _draw_hex_card(cls, hx: Hex) -> FullCard:
        deck_name = hx.terrain
        with HexDeck.load_for_write(deck_name) as deck:
            if not deck.cards:
                deck.cards = EncounterRules.load_deck(deck_name)
            return EncounterRules.reify_card(
                deck.cards.pop(0), [], hx.danger, EncounterContextType.TRAVEL
            )

    @classmethod
    def end_turn(cls, character_name: str) -> Sequence[external_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if GameRules.encounter_check(ch):
                raise BadStateException("An encounter is currently active.")
            GameRules.end_turn(ch, records)
            return GameRules.save_translate_records(records)

    @classmethod
    def resolve_encounter(
        cls, character_name: str, commands: EncounterCommands
    ) -> Sequence[external_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if not GameRules.encounter_check(ch):
                raise BadStateException("No encounter is currently active.")
            encounter = ch.encounter
            ch.encounter = None
            costs, effects = cls._perform_commands(ch, encounter, commands)
            GameRules.apply_effects(ch, costs, effects, records)
            GameRules.intra_turn(ch, records)
            return GameRules.save_translate_records(records)

    @classmethod
    def _perform_commands(
        cls, ch: Character, encounter: Encounter, commands: EncounterCommands
    ) -> Tuple[List[Effect], List[Effect]]:
        if commands.encounter_uuid != encounter.card.uuid:
            raise BadStateException(
                f"Command uuid {commands.encounter_uuid} mismatch with expected uuid {encounter.card.uuid}"
            )

        if encounter.card.type == FullCardType.CHALLENGE:
            return cls._perform_challenge(
                ch,
                encounter,
                commands,
            )
        elif encounter.card.type == FullCardType.CHOICE:
            choices = cast(Choices, encounter.card.data)
            return cls._perform_choices(
                ch,
                encounter,
                commands.choices,
            )
        else:
            raise Exception(f"Bad card type: {encounter.card.type.name}")

    @classmethod
    def _perform_challenge(
        cls,
        ch: Character,
        encounter: Encounter,
        commands: EncounterCommands,
    ) -> Tuple[List[Effect], List[Effect]]:
        checks = cast(Sequence[EncounterCheck], encounter.card.data)
        rolls = [er[-1] for er in encounter.rolls]
        luck_spent = 0

        costs: List[Effect] = []
        effects: List[Effect] = []

        # validate the commands by rerunning them (note this also updates luck)
        for adj in commands.adjusts or []:
            luck_spent += 1
            rolls[adj] += 1

        for from_c, to_c in commands.transfers or []:
            if rolls[from_c] < 2:
                raise BadStateException("From not enough for transfer")
            rolls[from_c] -= 2
            rolls[to_c] += 1

        if commands.flee:
            luck_spent += 1

        if luck_spent != commands.luck_spent:
            raise BadStateException(
                "Computed luck doesn't match? Expected "
                f"{luck_spent}, got {commands.luck_spent}"
            )

        rolls = tuple(rolls)
        if rolls != tuple(commands.rolls):
            raise BadStateException(
                "Computed rolls doesn't match? Expected "
                f"{rolls}, got {commands.rolls}"
            )

        if luck_spent > 0:
            costs.append(
                Effect(
                    EffectType.MODIFY_LUCK, -luck_spent, comment="encounter commands"
                )
            )
        if commands.flee:
            return costs, effects

        ocs = defaultdict(int)
        failures = 0

        for idx, check in enumerate(checks):
            if rolls[idx] >= check.target_number:
                ocs[check.reward] += 1
            else:
                ocs[check.penalty] += 1
                failures += 1

        mcs = defaultdict(int)

        sum_til = lambda v: (v * v + v) // 2
        for outcome, cnt in ocs.items():
            effects.extend(
                EncounterRules.convert_outcome(outcome, cnt, ch, encounter.card)
            )
        if failures > 0:
            effects.append(
                Effect(
                    type=EffectType.MODIFY_XP,
                    subtype=checks[0].skill,
                    value=failures,
                )
            )

        return costs, effects

    @classmethod
    def _perform_choices(
        cls,
        ch: Character,
        encounter: Encounter,
        selections: Dict[int, int],
    ) -> Tuple[List[Effect], List[Effect]]:
        choices = cast(Choices, encounter.card.data)

        costs: List[Effect] = []
        effects: List[Effect] = []

        tot = 0
        for choice_idx, cnt in selections.items():
            if choice_idx < 0 or choice_idx >= len(choices.choice_list):
                raise BadStateException(f"Choice out of range: {choice_idx}")
            choice = choices.choice_list[choice_idx]
            tot += cnt
            if cnt < choice.min_choices:
                raise IllegalMoveException(
                    f"Must choose {choice.name or 'this'} at least {with_s(choice.min_choices, 'time')}."
                )
            if cnt > choice.max_choices:
                raise IllegalMoveException(
                    f"Must choose {choice.name or 'this'} at most {with_s(choice.max_choices, 'time')}."
                )
        if tot < choices.min_choices:
            raise IllegalMoveException(
                f"Must select at least {with_s(choices.min_choices, 'choice')}."
            )
        if tot > choices.max_choices:
            raise IllegalMoveException(
                f"Must select at most {with_s(choices.max_choices, 'choice')}."
            )

        if selections:
            costs.extend(choices.costs)
            effects.extend(choices.effects)
        for choice_idx, cnt in selections.items():
            choice = choices.choice_list[choice_idx]
            for _ in range(cnt):
                costs.extend(choice.costs)
                effects.extend(choice.effects)
        return costs, effects
