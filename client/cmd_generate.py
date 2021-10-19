from pathlib import Path
from typing import Any

from picaro.server.api_types import *
from .generate import generate_game_v2
from .read import ReadClientBase


class GenerateCommand:
    def add_command(self, subparsers: Any) -> None:  # Any -> add_subparsers retval
        generate_parser = subparsers.add_parser("generate")
        generate_parser.set_defaults(cmd=lambda cli: self.generate_game(cli))
        generate_parser.add_argument("--json_dir", type=str, required=True)

    def generate_game(self, client: ReadClientBase) -> None:
        game_name = client.args.game_name
        json_dir = Path(client.args.json_dir)
        data = generate_game_v2(game_name, json_dir)
        game_id = client.create_game(data)
        print(f"Generated game named {client.args.game_name} (id {game_id})")
