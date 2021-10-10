# The player has tried to make a move which is plausible but illegal (trying to travel four hexes
# when their max is three, trying to move from a hex to a non-adjacent hex, etc). The client should
# display the error message and maintain the current UI position (repeat the prompt or whatever)
class IllegalMoveException(Exception):
    pass


# The player has tried to make a move that doesn't make sense given their current state (trying to
# activate an encounter not in their tableau, trying to travel when they're out of turns or have an
# encounter active). The client should display the error message and discard the current UI position,
# then re-request state and recalculate position.
class BadStateException(Exception):
    pass
