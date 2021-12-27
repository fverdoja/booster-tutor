import logging
from logging.handlers import RotatingFileHandler
from boostertutor.bot import DiscordBot

from boostertutor.utils.utils import get_config

if __name__ == "__main__":
    config = get_config()
    file_handler = RotatingFileHandler(
        "boostertutor.log", maxBytes=1024 * 1024 * 50
    )
    console_handler = logging.StreamHandler()
    logging.basicConfig(
        level=config.logging_level,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
        handlers=[file_handler, console_handler],
    )

    bot = DiscordBot(config)
    bot.run(config.discord_token)
