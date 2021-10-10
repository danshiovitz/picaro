import sys
from pathlib import Path

sys.path.append(str(Path(__file__).absolute().parent.parent.parent))

from picaro.engine import Engine
from picaro.server import Server


if __name__ == "__main__":
    engine = Engine(db_path=None)

    # this whole chunk here is a temp hack to get things set up
    engine.xyzzy()

    server = Server(engine)
    server.run()
