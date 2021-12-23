from boostertutor.bot import DiscordBot

if __name__ == "__main__":
    bot = DiscordBot()
    bot.run(bot.config["discord_token"])
