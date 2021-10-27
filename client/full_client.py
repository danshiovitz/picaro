from argparse import Namespace

from .cmd_board import BoardCommand
from .cmd_character import CharacterCommand
from .cmd_entity import EntityCommand
from .cmd_generate import GenerateCommand
from .cmd_play import PlayCommand
from .read import ReadClientBase


class FullClient(ReadClientBase):
    COMMANDS = [
        BoardCommand(),
        CharacterCommand(),
        EntityCommand(),
        GenerateCommand(),
        PlayCommand(),
    ]
