from collections import defaultdict
from typing import Any

from picaro.server.api_types import *
from .read import ReadClientBase


class EntityCommand:
    def add_command(self, subparsers: Any) -> None:  # Any -> add_subparsers retval
        get_entity_parser = subparsers.add_parser("entity")
        get_entity_parser.set_defaults(cmd=lambda cli: self.get_entities(cli))

    def get_entities(self, client: ReadClientBase) -> None:
        print("Entities:")
        for entity in client.entities.get_all():
            print()
            print("\n".join(client.render_entity_extended(entity)))
