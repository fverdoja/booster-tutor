import logging
from logging.handlers import RotatingFileHandler
from boostertutor.bot import DiscordBot

if __name__ == "__main__":
    file_handler = RotatingFileHandler(
        "boostertutor.log", maxBytes=1024 * 1024 * 50
    )
    console_handler = logging.StreamHandler()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
        handlers=[file_handler, console_handler],
    )

    bot = DiscordBot()
    bot.run(bot.config["discord_token"])
