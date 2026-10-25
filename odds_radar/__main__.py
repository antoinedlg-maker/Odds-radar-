import logging

from .bot import OddsRadar
from .config import Config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = Config.from_env()
    OddsRadar(cfg).run(cfg.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
