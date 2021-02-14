from pathlib import Path
import sys
sys.path.append(str(Path(__file__).absolute().parent.parent.parent))

from picaro.engine import Engine
from picaro.server import Server

if __name__ == "__main__":
    json_dir = Path(__file__).absolute().parent.parent / "engine" / "data"
    engine = Engine(db_path=None, json_path=json_dir)

    engine.generate_hexes()
    engine.add_character("Conan", 103, "random", "Raider")
    engine.start_season()

    server = Server(engine)
    server.run()
