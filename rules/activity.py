from typing import List, Optional, Sequence, Tuple

from picaro.common.exceptions import BadStateException, IllegalMoveException
from picaro.common.utils import pop_func
from picaro.store.board import Hex, Token
from picaro.store.character import Character, TurnFlags
from picaro.store.common_types import (
    EncounterContextType,
    FullCard,
    TravelCard,
    TravelCardType,
)
from picaro.store.gadget import Gadget
from picaro.store.record import Record

from .board import BoardRules
from .character import CharacterRules
from .deck import DeckRules
from .encounter import EncounterRules
from .game import GameRules
from .snapshot import EncounterCommands, Record as snapshot_Record


class ActivityRules:
    @classmethod
    def do_job(cls, character_name: str, card_uuid: str) -> Sequence[snapshot_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if ch.has_encounters():
                raise BadStateException("An encounter is currently active.")
            if not ch.check_set_flag(TurnFlags.ACTED):
                raise BadStateException("You have already acted this turn.")

            card = pop_func(ch.tableau, lambda c: c.card.uuid == card_uuid)
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
    ) -> Sequence[snapshot_Record]:
        records: List[Record] = []
        action = Gadget.load_action_by_uuid(action_uuid)
        with Character.load_by_name_for_write(character_name) as ch:
            if ch.has_encounters():
                raise BadStateException("An encounter is currently active.")
            CharacterRules.check_filters(ch, action.filters)
            GameRules.apply_bargain(ch, action.cost, records)
            GameRules.apply_regardless(ch, action.benefit, records)
            GameRules.intra_turn(ch, records)
            return GameRules.save_translate_records(records)

    @classmethod
    def camp(cls, character_name: str) -> Sequence[snapshot_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if ch.has_encounters():
                raise BadStateException("An encounter is currently active.")
            GameRules.intra_turn(ch, records)
            return GameRules.save_translate_records(records)

    @classmethod
    def travel(cls, character_name: str, hex: str) -> Sequence[snapshot_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if ch.has_encounters():
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
                return BoardRules.draw_hex_card(location)
            else:
                return None
        elif card.type == TravelCardType.SPECIAL:
            hx = Hex.load(location)
            return DeckRules.make_card(
                card.value, [], hx.danger, EncounterContextType.TRAVEL
            )
        else:
            raise Exception(f"Unknown card type: {card.type}")

    @classmethod
    def _make_travel_deck(cls) -> List[TravelCard]:
        specials = DeckRules.load_deck("Travel")
        cards = []
        cards.extend([TravelCard(type=TravelCardType.NOTHING, value=0)] * 14)
        for i in range(1, 6):
            cards.extend([TravelCard(type=TravelCardType.DANGER, value=i)] * 3)
        for _ in range(2):
            cards.append(TravelCard(type=TravelCardType.SPECIAL, value=specials.pop(0)))
        return DeckRules.shuffle(cards)

    @classmethod
    def end_turn(cls, character_name: str) -> Sequence[snapshot_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if ch.has_encounters():
                raise BadStateException("An encounter is currently active.")
            GameRules.end_turn(ch, records)
            return GameRules.save_translate_records(records)

    @classmethod
    def resolve_encounter(
        cls, character_name: str, commands: EncounterCommands
    ) -> Sequence[snapshot_Record]:
        records: List[Record] = []
        with Character.load_by_name_for_write(character_name) as ch:
            if not ch.has_encounters():
                raise BadStateException("No encounter is currently active.")
            encounter = ch.encounter
            ch.encounter = None
            cost, benefit = EncounterRules.perform_commands(ch, encounter, commands)
            GameRules.apply_bargain(ch, cost, records)
            GameRules.apply_regardless(ch, benefit, records)
            GameRules.intra_turn(ch, records)
            return GameRules.save_translate_records(records)
