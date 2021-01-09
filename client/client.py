from argparse import ArgumentParser, Namespace
from collections import defaultdict
from typing import Type, TypeVar
from urllib.request import Request, urlopen

from picaro.client.colors import colors
from picaro.common.hexmap.display import DisplayInfo, OffsetCoordinate, render_simple, render_large
from picaro.server.serializer import deserialize
from picaro.server.api_types import Hexmap

T = TypeVar("T")

class Client:
    @classmethod
    def run(cls) -> None:
        args = cls.parse_args()
        client = Client(args)
        client.args.cmd(client)

    @classmethod
    def parse_args(cls) -> None:
        parser = ArgumentParser()
        parser.add_argument("--host", type=str, default="http://localhost:8080")
        parser.set_defaults(cmd=lambda cli: parser.print_help())
        subparsers = parser.add_subparsers()
        get_map_parser = subparsers.add_parser("map")
        get_map_parser.set_defaults(cmd=lambda cli: cli.get_map())
        get_map_parser.add_argument('--country', '--countries', action='store_true')
        get_map_parser.add_argument('--large', action='store_true')
        get_map_parser.add_argument('--center', type=str, default=None)
        return parser.parse_args()

    def __init__(self, args: Namespace) -> None:
        self.args = args
        self.base_url = self.args.host
        if self.base_url and self.base_url[-1] == "/":
            self.base_url = self.base_url[:-1]
        self.terrains = {
            "Forest": (colors.fg.green, "\""),
            "Jungle": (colors.bold + colors.fg.green, "%"),
            "Hills": (colors.fg.orange, "n"),
            "Mountains": (colors.fg.darkgrey, "^"),
            "Plains": (colors.fg.lightgrey, "."),
            "Desert": (colors.fg.yellow, ":"),
            "Water": (colors.fg.blue, "~"),
            "City": (colors.fg.red, "#"),
            "Swamp": (colors.fg.magenta, "&"),
            "Coastal": (colors.fg.cyan, ";"),
            "Arctic": (colors.bold, "/"),
        }

    def get_map(self) -> None:
        hexmap = self._get("/map", Hexmap)
        coords = {
            hx.coordinate: hx for hx in hexmap.hexes
        }

        tokens = defaultdict(list)
        for tok in hexmap.tokens:
            tokens[tok.location].append(tok)

        if self.args.large:
            def display(coord: OffsetCoordinate) -> DisplayInfo:
                hx = coords[coord]
                # return self.terrains[hx.terrain][0] + hx.country[0] + colors.reset
                color, symbol = self.terrains[hx.terrain]
                body1 = hx.name + " "
                body2 = (hx.country + "     ")[0:5]

                if hx.name in tokens:
                    body2 = colors.bold + (tokens[hx.name][0].name + "     ")[0:5] + colors.reset
                return DisplayInfo(
                    fill=color + symbol + colors.reset,
                    body1=body1,
                    body2=body2,
                )

            center_hx = [hx for hx in hexmap.hexes if hx.name == hexmap.tokens[0].location][0]
            for line in render_large(set(coords), display, center=center_hx.coordinate, radius=2):
                print(line)

        else:
            def display(coord: OffsetCoordinate) -> str:
                hx = coords[coord]

                if hx.name in tokens:
                    return colors.bold + "@" + colors.reset

                color, symbol = self.terrains[hx.terrain]
                return (
                    color +
                    (hx.country[0] if self.args.country else symbol) +
                    colors.reset
                )

            for line in render_simple(set(coords), 1, display):
                print(line)

        if hexmap.tokens:
            print()
            for tok in hexmap.tokens:
                print(tok)

    def _get(self, path: str, cls: Type[T]) -> T:
        url = self.base_url
        url += path
        with urlopen(url) as req:
            data = req.read().decode("utf-8")
            return deserialize(data, cls)


if __name__ == "__main__":
    args = parse_args()
    args.cmd(args)
