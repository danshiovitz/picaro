import pathlib
import sys
sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent))

from picaro.engine import Engine
from picaro.server import Server

if __name__ == "__main__":
    from picaro.engine.job import Job
    from picaro.engine.types import EncounterPenalty, EncounterReward, TemplateCard
    raider_job = Job(
        "Raider",
        ["Ride", "Endurance", "Stealth"],
        2,
        [
            # reward goal: 3 coins, reputation, resources; 2 xp, healing; 1 quest
            # penalty goal: 5 damage; 3 reputation; 2 coins; 1 nothing, resources, job, transport
            TemplateCard("Caravan Raid", "...", ["Shoot", "Speed", "Command"], rewards=[EncounterReward.COINS, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard("Scouting Mission", "...", ["Observation", "Climb", "Appraisal"], rewards=[EncounterReward.XP, EncounterReward.REPUTATION], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.TRANSPORT]),
            TemplateCard("Another Band", "...", ["Might", "Carousing", "Debate"], rewards=[EncounterReward.RESOURCES, EncounterReward.QUEST], penalties=[EncounterPenalty.RESOURCES, EncounterPenalty.REPUTATION]),
            TemplateCard("Guard Patrol", "...", ["Stealth", "Formation Fighting", "Speed"], rewards=[EncounterReward.COINS, EncounterReward.REPUTATION], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.JOB]),
            TemplateCard("Hunting Expedition", "...", ["Speed", "Shoot", "Observation"], rewards=[EncounterReward.XP, EncounterReward.RESOURCES], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.REPUTATION]),
            TemplateCard("Test of Skill", "...", ["Shoot", "Animal Training", "Ride"], rewards=[EncounterReward.HEALING, EncounterReward.REPUTATION], penalties=[EncounterPenalty.DAMAGE, EncounterPenalty.COINS]),
            TemplateCard("Victory Celebration", "...", ["Carousing", "Charm", "Acrobatics"], rewards=[EncounterReward.COINS, EncounterReward.HEALING], penalties=[EncounterPenalty.NOTHING, EncounterPenalty.COINS])
        ],
        [0, 1, 1, 1, 2, 3]
    )

    engine = Engine()

    engine.add_character("Conan", 103, "random", raider_job)
    engine.start_season()

    server = Server(engine)
    server.run()
