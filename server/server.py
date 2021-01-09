from typing import Any, Dict

from picaro.engine import Engine

from . import bottle
from .api_types import Hexmap
from .serializer import recursive_to_dict, recursive_from_dict

class Server:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_map(self) -> Dict[str, Any]:
        player_id = self._extract_player_id()
        return recursive_to_dict(self._engine.get_map(player_id))

    def run(self) -> None:
        bottle.route(path="/map", callback=self.get_map)
        bottle.run(host="localhost", port=8080, debug=True)

    def _extract_player_id(self) -> int:
        return 103
