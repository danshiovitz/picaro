import pathlib
import sys
sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent))

from picaro.engine import Engine
from picaro.server import Server

if __name__ == "__main__":
    engine = Engine()

    engine.add_player(0, "inky")
    engine.add_character(103, "Conan")
    import random
    hex_name = random.choice([hx.name for hx in engine._map.hexes])
    engine._map.tokens[0] = engine._map.tokens[0]._replace(location=hex_name)

    server = Server(engine)
    server.run()
