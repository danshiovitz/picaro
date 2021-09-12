from typing import List, Tuple


def conj_list(items: List[str], conj: str) -> str:
    if len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return f" {conj} ".join(items)
    else:
        return ", ".join(items[:-1]) + f", {conj} " + items[-1]


def choose(*options: List[Tuple[str, str, int]]) -> str:
    while True:
        print("You can " + conj_list([opt[0] for opt in options], "or") + ": ", end="")
        line = input().strip()
        input_cmd, *input_args = re.split(r"\s+", line)
        for cmd_name, cmd_val, cmd_argc in options:
            if cmd_val == input_cmd:
                if len(input_args) != cmd_argc:
                    print(f"Expected {cmd_argc} args")
                else:
                    return (cmd_val, input_args)

        print(f"Unknown input {line}")
