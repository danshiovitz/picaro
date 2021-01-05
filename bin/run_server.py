import pathlib
import sys
sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent))

from picaro.server import Server

if __name__ == "__main__":
    server = Server()
    server.run()
