import pathlib
import sys
sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent))

from picaro.engine import Engine
from picaro.server import Server

if __name__ == "__main__":
    engine = Engine()

    engine.add_character("Conan", 103, "random", "Raider")
    engine.start_season()

    server = Server(engine)
    server.run()
