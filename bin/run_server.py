import pathlib
import sys
sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent))

from picaro.engine import Engine
from picaro.server import Server

if __name__ == "__main__":
    from picaro.engine.job import Job
    from picaro.engine.types import TemplateCard
    raider_job = Job(
        "Raider",
        ["Ride", "Endurance", "Stealth"],
        2,
        [
            TemplateCard("Caravan Raid", "...", ["Shoot", "Speed", "Command"]),
            TemplateCard("Scouting Mission", "...", ["Observation", "Climb", "Appraisal"]),
            TemplateCard("Another Band", "...", ["Might", "Carousing", "Debate"]),
            TemplateCard("Guard Patrol", "...", ["Stealth", "Formation Fighting", "Speed"]),
            TemplateCard("Hunting Expedition", "...", ["Speed", "Shoot", "Observation"]),
            TemplateCard("Test of Skill", "...", ["Shoot", "Animal Training", "Ride"]),
            TemplateCard("Victory Celebration", "...", ["Carousing", "Charm", "Acrobatics"])
        ],
        [0, 1, 1, 1, 2, 3]
    )

    engine = Engine()

    engine.add_character("Conan", 103, "random", raider_job)
    engine.start_season()

    server = Server(engine)
    server.run()
