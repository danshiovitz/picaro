from collections import defaultdict
from typing import Any

from picaro.server.api_types import *
from .read import ReadClientBase


class BoardCommand:
    def add_command(self, subparsers: Any) -> None:  # Any -> add_subparsers retval
        get_board_parser = subparsers.add_parser("board")
        get_board_parser.set_defaults(cmd=lambda cli: self.get_board(cli))
        get_board_parser.add_argument("--country", "--countries", action="store_true")
        get_board_parser.add_argument("--large", action="store_true")
        get_board_parser.add_argument("--center", type=str, default=None)

    def get_board(self, client: ReadClientBase) -> None:
        hexes = client.hexes.get_all()
        entity_list = client.entities.get_all()

        coords = {hx.coordinate: hx for hx in hexes}
        entities: Dict[str, List[Entity]] = defaultdict(list)
        for entity in entity_list:
            for location in entity.locations:
                entities[location].append(entity)

        if client.args.large:
            center_name = client.args.center or client.character.location
            center_coord = client.hexes.get_by_name(center_name).coordinate

            for line in client.render_large_map(
                entities,
                center=center_coord,
                radius=2,
                show_country=client.args.country,
            ):
                print(line)
        else:
            for line in client.render_small_map(show_country=client.args.country):
                print(line)

        if entity_list:
            print()
            for entity in entity_list:
                if entity.type == EntityType.CHARACTER:
                    print(entity)

        if client.args.country:
            ccount: Dict[str, int] = defaultdict(int)
            for hx in hexes:
                ccount[hx.country] += 1
            print(sorted(ccount.items()))
