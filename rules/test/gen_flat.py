from string import ascii_lowercase
from typing import Callable, Dict, List, Set, Tuple, Type, TypeVar

from picaro.common.hexmap.types import OffsetCoordinate
from picaro.server.api_types import (
    Action,
    AmountEffect,
    Challenge,
    Choice,
    Choices,
    Country,
    CreateGameRequest,
    Effect,
    EffectType,
    EntityType,
    Entity,
    Filter,
    FilterType,
    Hex,
    Job,
    JobType,
    Outcome,
    TemplateCard,
    TemplateCardType,
    TemplateDeck,
)

# Flatworld is a simple map for testing, laid out as follows:
# The left side of the map is a 5 (wide) x 11 (high) country, Alpha;
# the right side is a 5 x 11 country, Bravo, and there is an unaligned
# (ie, Wild) 1 x 11 strip in the middle. Alpha is all forest except for
# the leftmost edge, which is a strip of mountains, and the NW and SW
# corners, which are urban and have cities (the NW corner is the capitol).
# Bravo is all plains, with a single city in the very center, and a strip
# of mountains on the top and bottom edges. The wild area is all swamp.
# There are 20 skills, named Skill 1 through Skill 20, 12 zodiacs,
# named Zodiac 1 through Zodiac 12, and 5 resources, named Resource A1,
# Resource A2, Resource B1, Resource B2, Resource B3 - Alpha's resources
# are A1 and A2, and Bravo's are B1 and B2. There are 8 jobs, named
# Red Job 0, Red Job 1, Red Job 2, Red Job 3, Blue Job 1, Blue Job 2,
# Green Job 1, and Yellow Job 0. Jobs promote as implied and are
# ranked as implied (0 = lackey job).


def generate_flatworld() -> CreateGameRequest:
    return CreateGameRequest(
        name="Flatworld",
        skills=[f"Skill {i+1}" for i in range(20)],
        resources=[f"Resource {n}" for n in ["A1", "A2", "B1", "B2", "C"]],
        jobs=generate_jobs(),
        template_decks=generate_decks(),
        zodiacs=[f"Zodiac {i+1}" for i in range(12)],
        hexes=generate_hexes(),
        countries=generate_countries(),
        entities=generate_entities(),
    )


def generate_jobs() -> List[Job]:
    jobs: List[Job] = []
    jobs.append(
        Job(
            uuid="",
            name=f"Red Job 1",
            type=JobType.SOLO,
            rank=1,
            promotions=["Red Job 2"],
            deck_name="Red",
            base_skills=["Skill 1", "Skill 2", "Skill 3"],
            encounter_distances=[0, 0, 1, 1, 2, 3],
        )
    )
    jobs.append(
        Job(
            uuid="",
            name=f"Red Job 2",
            type=JobType.SOLO,
            rank=2,
            promotions=[],
            deck_name="Red",
            base_skills=["Skill 1", "Skill 2", "Skill 3"],
            encounter_distances=[0, 0, 1, 1, 2, 3],
        )
    )
    jobs.append(
        Job(
            uuid="",
            name=f"Blue Job",
            type=JobType.SOLO,
            rank=1,
            promotions=[],
            deck_name="Blue",
            base_skills=["Skill 4", "Skill 5", "Skill 6"],
            encounter_distances=[0, 0, 1, 1, 2, 3],
        )
    )
    jobs.append(
        Job(
            uuid="",
            name=f"Green Job",
            type=JobType.LACKEY,
            rank=0,
            promotions=[],
            deck_name="Green",
            base_skills=["Skill 7", "Skill 8", "Skill 9"],
            encounter_distances=[0, 0, 1, 1, 2, 3],
        )
    )
    return jobs


def generate_decks() -> List[TemplateDeck]:
    decks: List[TemplateDeck] = []

    terrains = ["Forest", "Mountains", "City", "Plains", "Swamp"]
    for terrain in terrains:
        cards = [
            TemplateCard(
                name=f"{terrain} {i+1}",
                desc="...",
                type=TemplateCardType.CHALLENGE,
                data=Challenge(
                    skills=["Skill 10", "Skill 11", "Skill 12"],
                    rewards=[Outcome.GAIN_COINS, Outcome.GAIN_REPUTATION],
                    penalties=[Outcome.DAMAGE, Outcome.LOSE_REPUTATION],
                ),
            )
            for i in range(4)
        ]
        decks.append(TemplateDeck(name=terrain, copies=[2, 2, 2, 2], cards=cards))

    jobs = ["Red", "Blue", "Green"]
    for job in jobs:
        cards = [
            TemplateCard(
                name=f"{job} {i+1}",
                desc="...",
                type=TemplateCardType.CHALLENGE,
                data=Challenge(
                    skills=["Skill 13", "Skill 14", "Skill 15"],
                    rewards=[Outcome.GAIN_COINS, Outcome.GAIN_REPUTATION],
                    penalties=[Outcome.DAMAGE, Outcome.LOSE_REPUTATION],
                ),
            )
            for i in range(4)
        ]
        decks.append(TemplateDeck(name=job, copies=[2, 2, 2, 2], cards=cards))

    specials = ["Travel"]
    for special in specials:
        choice_list = [
            Choice(
                costs=[],
                effects=[
                    AmountEffect(
                        type=EffectType.MODIFY_COINS,
                        amount=5,
                    )
                ],
            ),
            Choice(
                costs=[],
                effects=[
                    AmountEffect(
                        type=EffectType.MODIFY_HEALTH,
                        amount=5,
                    )
                ],
            ),
        ]
        cards = [
            TemplateCard(
                name=f"{special} {i+1}",
                desc="...",
                type=TemplateCardType.CHOICE,
                data=Choices(
                    min_choices=0,
                    max_choices=1,
                    choice_list=choice_list,
                ),
            )
            for i in range(2)
        ]
        decks.append(TemplateDeck(name=special, copies=[2, 2], cards=cards))
    return decks


def generate_hexes() -> List[Hex]:
    hexes: List[Hex] = []
    for row in range(0, 11):
        for column in range(0, 11):
            coord = OffsetCoordinate(row=row, column=column)
            if column < 5:
                country = "Alpha"
                terrain = "Mountains" if column == 0 else "Forest"
            elif column > 5:
                country = "Bravo"
                terrain = "Mountains" if row in (0, 10) else "Plains"
            else:
                country = "Wild"
                terrain = "Swamp"
            if coord.get_name() in ("AA01", "AK01", "AF09"):
                terrain = "City"
            hexes.append(
                Hex(
                    name=coord.get_name(),
                    coordinate=coord,
                    terrain=terrain,
                    country=country,
                    danger=1,
                )
            )
    return hexes


def generate_countries() -> List[Country]:
    return [
        Country(
            uuid="",
            name="Alpha",
            capitol_hex="AA01",
            resources=["Resource A1", "Resource A2"],
        ),
        Country(
            uuid="",
            name="Bravo",
            capitol_hex="AF09",
            resources=["Resource B1", "Resource B2"],
        ),
    ]


def generate_entities() -> List[Entity]:
    return [
        Entity(
            uuid="",
            type=EntityType.LANDMARK,
            subtype="city",
            name="Alpha City",
            titles=[],
            locations=["AA01"],
        ),
        Entity(
            uuid="",
            type=EntityType.LANDMARK,
            subtype="city",
            name="Alphaburbs",
            titles=[],
            locations=["AK01"],
        ),
        Entity(
            uuid="",
            type=EntityType.LANDMARK,
            subtype="city",
            name="Central Bravo",
            titles=[],
            locations=["AF09"],
        ),
    ]
