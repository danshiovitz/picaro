import sys
from pathlib import Path

sys.path.append(str(Path(__file__).absolute().parent.parent.parent))

from picaro.engine import Engine
from picaro.engine.types import TaskType
from picaro.server import Server

if __name__ == "__main__":
    json_dir = Path(__file__).absolute().parent.parent / "engine" / "data"
    engine = Engine(db_path=None)

    PLAYER_ID = 103
    game_id = engine.create_game(
        player_id=PLAYER_ID, name="Test Game", json_dir=json_dir
    )
    engine.add_character(
        game_id=game_id,
        player_id=PLAYER_ID,
        character_name="Conan",
        location="random",
        job_name="Raider",
    )
    engine.add_character(
        game_id=game_id,
        player_id=PLAYER_ID + 1,
        character_name="Taurus",
        location="random",
        job_name="Merchant",
    )
    engine.xyzzy(
        game_id=game_id,
        player_id=PLAYER_ID,
        character_name="Conan",
    )

    server = Server(engine)
    server.run()
