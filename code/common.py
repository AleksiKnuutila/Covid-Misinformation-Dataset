import sys
from loguru import logger
import yaml
from docopt import docopt

with open("config.yaml", "r") as conf, open("secret.yaml", "r") as secr:
    config = yaml.safe_load(conf) or {}
    secret_config = yaml.safe_load(secr) or {}
cli_args = {}
if (
    sys.modules["__main__"].__package__ is None
    or "pytest" not in sys.modules["__main__"].__package__
):
    cli_args = docopt(
        sys.modules["__main__"].__doc__, version="telegram_collection 0.1"
    )
    cli_args = {
        k.replace("-", "").replace("<", "").replace(">", ""): v
        for k, v in cli_args.items()
        if "-" in k or "<" in k
    }
config = {**config, **secret_config, **cli_args}