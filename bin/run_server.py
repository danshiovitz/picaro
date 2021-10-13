import sys
from pathlib import Path

sys.path.append(str(Path(__file__).absolute().parent.parent.parent))

from picaro.server import Server


if __name__ == "__main__":
    server = Server(db_path=None)
    server.run()
