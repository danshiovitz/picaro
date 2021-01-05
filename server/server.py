import random
from string import ascii_uppercase

from . import bottle
from .api_types import Hexmap
from .generate import generate, generate_from_mini
from .serializer import recursive_to_dict, recursive_from_dict

class Server:
    def __init__(self) -> None:
        self._map = self._init_map()

    def get_map(self) -> None:
        return recursive_to_dict(self._map)

    def _init_map(self) -> None:
        # return Hexmap(hexes=generate(50, 50, {}))
        minimap = [
            '^n::n::~',
            'n:n."..~',
            '"."."".~',
            '^n."".nn',
            '^.~~~~~~',
            '..""~..:',
            '""""^::n',
            '&&"^n:::',
        ]
        return Hexmap(hexes=generate_from_mini(50, 50, minimap))

    def run(self) -> None:
        bottle.route(path="/map", callback=self.get_map)
        bottle.run(host="localhost", port=8080, debug=True)
