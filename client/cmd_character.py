from collections import defaultdict
from typing import Any

from picaro.server.api_types import *
from .read import ReadClientBase


class CharacterCommand:
    def add_command(self, subparsers: Any) -> None:  # Any -> add_subparsers retval
        get_character_parser = subparsers.add_parser("character")
        get_character_parser.set_defaults(cmd=lambda cli: self.get_character(cli))
        get_character_parser.add_argument("--all", action="store_true")

    def get_character(self, client: ReadClientBase) -> None:
        ch = client.character
        print(f"{ch.name} ({ch.player_uuid}) - a {ch.job} [{ch.location}]")
        print(f"Health: {ch.health}   Coins: {ch.coins}   Reputation: {ch.reputation}")
        resources = ", ".join(f"{v} {n}" for n, v in ch.resources.items())
        print(f"Resources: {resources}")
        print("Skills:")
        for sk, v in sorted(ch.skills.items()):
            if client.args.all or v > 0 or ch.skill_xp[sk] > 0:
                print(f"  {sk}: {v} ({ch.skill_xp[sk]} xp)")
        if not client.args.all:
            print("(Use --all to see all skills)")
        print()
        print("Emblems:")
        for emblem in ch.emblems:
            print(f"* {client.render_gadget(emblem)}")
        if not ch.emblems:
            print("* None")
        print()
