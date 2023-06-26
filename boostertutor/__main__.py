import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import boostertutor.utils.mtgjson_downloader as mtgjson
import boostertutor.utils.set_symbols_downloader as symbols
from boostertutor.bot import DiscordBot
from boostertutor.utils.utils import get_config


def main():
    parser = argparse.ArgumentParser(
        prog="boostertutor",
        description=(
            "A Discord bot to generate 'Magic: the Gathering' boosters and "
            "sealed pools."
        ),
        epilog=(
            "Run without subcommands to run the Discord bot, or add one of "
            "the subcommands to run the downloader subutils (some subcommand "
            "might have specific arguments, check subcommands' help for them)."
        ),
    )
    parser.add_argument(
        "--config",
        help="config file path (default: ./config.yaml)",
        default="config.yaml",
    )
    subparsers = parser.add_subparsers(
        title="Donwloaders",
        description=(
            "Utilities to download helpful data. When a downloader is run, "
            "the Discord bot is not started."
        ),
        dest="downloader",
    )
    subparsers.add_parser(
        "symbols",
        help="Download set symbols",
        description="Download set symbols",
    )
    subparsers.add_parser(
        "mtgjson",
        help="Download MTGJSON data",
        description="Download MTGJSON data",
    )
    args = parser.parse_args()
    config = get_config(Path(args.config))
    file_handler = RotatingFileHandler(
        "boostertutor.log", maxBytes=1024 * 1024 * 50
    )
    console_handler = logging.StreamHandler()
    logging.basicConfig(
        level=config.logging_level,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
        handlers=[file_handler, console_handler],
    )

    if args.downloader == "symbols":
        if config.set_img_path:
            symbols.main(
                local_path=Path(config.set_img_path),
                path_to_mtgjson=Path(config.mtgjson_path),
            )
        else:
            logging.error(
                "Config does not contain set_img_path setting, doing nothing."
            )
    elif args.downloader == "mtgjson":
        mtgjson.main(config)
    else:
        bot = DiscordBot(config)
        bot.run(config.discord_token)


if __name__ == "__main__":
    main()
