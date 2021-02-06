import pathlib
import sys
sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent))

import re
from dataclasses import dataclass
from typing import List, Tuple
from picaro.common.serializer import serialize
from picaro.engine.types import TemplateCard, FullCard, EncounterReward, EncounterPenalty

@dataclass(frozen=True)
class DeckStruct:
    name: str
    base_difficulty: int
    base_skills: List[str]
    cards: List[TemplateCard]

@dataclass(frozen=True)
class AllDecksStruct:
    decks: List[DeckStruct]

sk = AllDecksStruct(decks=[
    DeckStruct(
        name="Raider",
        base_skills=["Ride", "Endurance", "Stealth"],
        base_difficulty=2,
        cards=[
            TemplateCard(4, "Caravan Raid", "...", ["Shoot", "Speed", "Command"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard(2, "Scouting Mission", "...", ["Observation", "Climb", "Appraisal"], rewards=[EncounterReward.XP, EncounterReward.REPUTATION], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.TRANSPORT]),
            TemplateCard(2, "Guard Patrol", "...", ["Stealth", "Formation Fighting", "Speed"], rewards=[EncounterReward.COINS, EncounterReward.REPUTATION], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.JOB]),
            TemplateCard(1, "Another Band", "...", ["Might", "Carousing", "Debate"], rewards=[EncounterReward.RESOURCES, EncounterReward.QUEST], penalties=[EncounterPenalty.RESOURCES, EncounterPenalty.REPUTATION]),
            TemplateCard(1, "Hunting Expedition", "...", ["Speed", "Shoot", "Observation"], rewards=[EncounterReward.XP, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard(1, "Test of Skill", "...", ["Shoot", "Animal Training", "Ride"], rewards=[EncounterReward.HEALING, EncounterReward.REPUTATION], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.COINS]),
            TemplateCard(copies=1, name="Victory Celebration", desc="...", skills=["Carousing", "Charm", "Acrobatics"], rewards=[EncounterReward.COINS, EncounterReward.HEALING], penalties=[EncounterPenalty.NOTHING, EncounterPenalty.COINS]),
        ],
    ),
    DeckStruct(
        name="Desert",
        base_skills=["Desert Lore", "Desert Lore", "Endurance"],
        base_difficulty=3,
        cards=[
            TemplateCard(2, "Oasis", "...", ["Carousing", "Observation", "Doctor"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard(2, "Sandstorm", "...", ["Navigation", "Endurance", "Might"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard(2, "Desert Beast", "...", ["Charm", "Stealth", "Animal Training"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard(2, "Extreme Heat", "...", ["Endurance", "Endurance", "Desert Lore"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard(2, "Strange Constellations", "...", ["Spirit Binding", "Navigation", "Mesmerism"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard(2, "Mirage", "...", ["Observation", "Architecture", "Mesmerism"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
        ],
    ),
])

print(serialize(sk))
