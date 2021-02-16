import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent.parent))

from picaro.client import Client

if __name__ == "__main__":
    Client.run()
