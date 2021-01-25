import random
from typing import Generic, List, NamedTuple, Tuple, TypeVar

from .load import load_json
from .skills import load_skills
from .types import EncounterCheck, EncounterPenalty, EncounterReward, FullCard, TemplateCard
from .zodiacs import load_zodiacs


class EncounterDeck:
    NEXT_ID = 1

    def __init__(self, name: str, templates: List[TemplateCard], base_skills: List[str], base_difficulty: int) -> None:
        self.name = name
        self.templates = templates
        self.base_skills = base_skills
        self.base_difficulty = base_difficulty

    def actualize(self, additional: List[TemplateCard] = None) -> List[FullCard]:
        ret = []
        for tmpl in self.templates + (additional or []):
            for _ in range(tmpl.copies):
                ret.append(self._make_card(tmpl))
        random.shuffle(ret)
        for _ in range((len(ret) // 10) + 1):
            ret.pop()
        return ret

    def _make_card(self, val: TemplateCard) -> FullCard:
        if not val.skills:
            checks = []
        else:
            skill_bag = []
            skill_bag.extend(self.base_skills * 15)
            skill_bag.extend(val.skills * 15)

            all_skills = load_skills()
            reward_bag = self._make_reward_bag(val)
            penalty_bag = self._make_penalty_bag(val)
            checks = [
                self._make_check(skill_bag, reward_bag, penalty_bag),
                self._make_check(skill_bag, reward_bag, penalty_bag),
                self._make_check(skill_bag + all_skills, reward_bag, penalty_bag),
            ]

        all_zodiacs = load_zodiacs()
        signs = random.sample(all_zodiacs, 2)

        card_id = self.NEXT_ID
        self.NEXT_ID += 1
        return FullCard(id=card_id, template=val, checks=checks, signs=signs)

    def _make_check(self, skill_bag: List[str], reward_bag: List[EncounterReward], penalty_bag: List[EncounterPenalty]) -> EncounterCheck:
        tn = self.difficulty_to_target_number(self.base_difficulty)
        # fuzz the tns a bit
        tn = random.choice([
            tn, tn, tn, tn,
            tn + 1, tn + 1, tn - 1, tn - 1,
            tn + 2, tn - 2, tn + 3, tn - 3,
        ])
        return EncounterCheck(skill=random.choice(skill_bag), target_number=tn, reward=random.choice(reward_bag), penalty=random.choice(penalty_bag))

    # originally had this as a deck, but I think it works better to have more hot/cold variance
    def _make_reward_bag(self, template_card: TemplateCard) -> List[EncounterReward]:
        reward_bag = []
        reward_bag.extend([EncounterReward.COINS, EncounterReward.REPUTATION] * 4)
        reward_bag.extend(template_card.rewards * 4)
        reward_bag.extend([EncounterReward.RESOURCES, EncounterReward.HEALING, EncounterReward.QUEST, EncounterReward.NOTHING] * 1)
        return reward_bag

    def _make_penalty_bag(self, template_card: TemplateCard) -> List[EncounterPenalty]:
        penalty_bag = []
        penalty_bag.extend([EncounterPenalty.DAMAGE] * 12)
        penalty_bag.extend(template_card.penalties * 6)
        penalty_bag.extend([EncounterPenalty.NOTHING, EncounterPenalty.REPUTATION, EncounterPenalty.RESOURCES, EncounterPenalty.COINS, EncounterPenalty.TRANSPORT, EncounterPenalty.JOB] * 1)
        return penalty_bag

    def difficulty_to_target_number(self, difficulty: int) -> int:
        return difficulty * 2 + 1


class DeckStruct(NamedTuple):
    name: str
    base_skills: List[str]
    base_difficulty: int
    templates: List[TemplateCard]

class AllDecksStruct(NamedTuple):
    decks: List[DeckStruct]

def load_deck(deck_name: str) -> EncounterDeck:
    loaded = load_json("template_decks", AllDecksStruct)
    ds = [ld for ld in loaded.decks if ld.name == deck_name][0]
    deck = EncounterDeck(ds.name, ds.templates, ds.base_skills, ds.base_difficulty)
    return deck
