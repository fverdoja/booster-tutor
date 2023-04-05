import logging
from io import BytesIO, StringIO
from typing import Optional, Sequence

import aiohttp
import discord
import imageio
from discord.ext import commands

import boostertutor.utils.utils as utils
from boostertutor.generator import MtgPackGenerator
from boostertutor.models.mtg_pack import MtgPack

logger = logging.getLogger(__name__)

MAX_NUM_PACKS = 36


def help_msg(
    brief: str,
    long_description: Optional[str] = None,
    has_num_packs: bool = False,
    has_member: bool = True,
    args: dict[str, str] = {},
    examples: dict[str, str] = {},
) -> str:
    help = f"{brief}"
    if long_description:
        help += f"\n\n{long_description}"
    if args or has_num_packs or has_member:
        help += "\n\n__**Args:**__"
        for name, description in args.items():
            help += f"\n*{name}*: {description}"
        if has_num_packs:
            help += (
                "\n*num_packs* (optional): Number of packs to generate. "
                f"Defaults to 1, maximum {MAX_NUM_PACKS}."
            )
        if has_member:
            help += (
                "\n*member* (optional): the member to be mentioned in the "
                "reply. Defaults to the member who issued the command."
            )
    if examples:
        help += "\n\n__**Examples:**__"
        for name, description in examples.items():
            help += f"\n`{name}`: {description}"

    return help


@commands.command(
    help=help_msg(
        "Gives info on how to support Booster Tutor development",
        has_member=False,
    ),
)
async def donate(ctx: commands.Context) -> None:
    assert ctx.message
    message: discord.Message = ctx.message
    await message.reply(
        "If you are having fun using Booster Tutor, consider sponsoring "
        "my next draft with a donation! Thanks!!\n"
        "Donate on Ko-fi: https://ko-fi.com/boostertutor"
    )


class DiscordBot(commands.Bot):
    def __init__(
        self,
        config: utils.Config,
        **options,
    ):
        super().__init__(
            command_prefix=config.command_prefix,
            help_command=commands.MinimalHelpCommand(no_category="Other"),
            description='A Discord bot to generate "Magic: the Gathering" '
            "boosters and sealed pools",
            **options,
        )
        self.config = config
        self.generator = MtgPackGenerator(
            path_to_mtgjson=self.config.mtgjson_path,
            path_to_jmp=self.config.jmp_decklists_path,
            jmp_arena=True,
        )
        self.standard_sets = ["mid", "vow", "neo", "snc", "dmu", "bro", "one"]
        self.explorer_sets = [
            "xln",
            "rix",
            "dom",
            "m19",
            "grn",
            "rna",
            "war",
            "m20",
            "eld",
            "thb",
            "iko",
            "m21",
            "znr",
            "khm",
            "stx",
            "afr",
        ] + self.standard_sets
        self.historic_sets = ["klr", "akr", "sir"] + self.explorer_sets
        self.all_sets = [s.lower() for s in self.generator.sets_with_boosters]
        self.add_cog(BotCommands(self))
        self.add_command(donate)

    async def on_ready(self) -> None:
        logger.info(
            f"{self.user} has connected to {len(self.guilds)} Discord servers:"
            f" {[guild.name for guild in self.guilds]}"
        )

    async def on_message(self, message: discord.Message) -> None:
        if message.author != self.user and message.content.startswith(
            self.command_prefix
        ):
            command = (
                message.content.removeprefix(self.command_prefix)
                .split()[0]
                .lower()
            )
            if command in self.all_sets:
                message.content = message.content.replace(
                    self.command_prefix, self.command_prefix + "set ", 1
                )
                logger.info(message.content)
            elif command.removesuffix("sealed") in self.all_sets:
                message.content = message.content.replace(
                    "sealed", "", 1
                ).replace(
                    self.command_prefix, self.command_prefix + "setsealed ", 1
                )

        ctx = await self.get_context(message)
        await self.invoke(ctx)


class BotCommands(commands.Cog, name="Bot"):  # type: ignore
    def __init__(self, bot: DiscordBot):
        super().__init__()
        self.bot = bot
        self.generator = self.bot.generator

    def emoji(self, name: str, guild: Optional[discord.Guild] = None) -> str:
        """Return an emoji if it exists on the server or empty otherwise"""
        for e in guild.emojis if guild else self.bot.emojis:
            if e.name == name:
                return str(e)
        return ""

    def process_num_packs(self, num_packs: Optional[int]) -> int:
        if num_packs:
            return min(max(1, num_packs), MAX_NUM_PACKS)
        else:
            return 1

    async def send_pack_msg(
        self,
        p: MtgPack,
        message: discord.Message,
        emoji: str,
        member: Optional[discord.Member] = None,
    ) -> None:
        # First send the booster text with a loading message for the image
        embed = discord.Embed(
            description=":hourglass: Summoning a vision of your booster "
            "from the aether...",
            color=discord.Color.orange(),
        )

        m = await message.reply(
            f"**{emoji}{(' ' if len(emoji) else '')}{p.name}**\n"
            f"{member.mention if member else ''}\n"
            f"```\n{p.arena_format()}\n```",
            embed=embed,
        )

        try:
            # Then generate the image of booster content (takes a while)
            img_list = await p.get_images(size="normal")
            p_img = utils.pack_img(img_list)
            img_file = BytesIO()
            imageio.imwrite(img_file, p_img, format="jpeg")

            # Upload it to imgur.com
            link = await utils.upload_img(
                img_file, self.bot.config.imgur_client_id
            )
        except aiohttp.ClientResponseError:
            # Send an error message if the upload failed...
            embed = discord.Embed(
                description=":x: Sorry, it seems your booster is lost in "
                "the Blind Eternities...",
                color=discord.Color.red(),
            )
        else:
            # ...or edit the message by embedding the link
            embed = discord.Embed(color=discord.Color.dark_green())
            embed.set_image(url=link)

        await m.edit(embed=embed)

    async def send_pool_msg(
        self,
        pool: Sequence[MtgPack],
        message: discord.Message,
        emoji: str,
        member: Optional[discord.Member] = None,
    ) -> None:
        pool_file = StringIO("\n".join([p.arena_format() for p in pool]))
        sets = ", ".join([p.set.code for p in pool])
        json_pool = [card_json for p in pool for card_json in p.json()]

        # First send the pool content with a loading message for the image
        embed = discord.Embed(
            description=":hourglass: Summoning a vision of your rares "
            "from the aether...",
            color=discord.Color.orange(),
        )
        title = "Sealed pool" if len(pool) == 6 else f"{len(pool)} packs"
        name = member.display_name if member else message.author.display_name
        m = await message.reply(
            f"**{emoji}{(' ' if len(emoji) else '')}{title}**\n"
            f"{member.mention if member else ''}\n"
            f"Content: [{sets}]",
            embed=embed,
            file=discord.File(
                pool_file,
                filename=f"{name}_pool.txt",
            ),
        )

        content = m.content
        try:
            sealeddeck_id = await utils.pool_to_sealeddeck(json_pool)
        except aiohttp.ClientResponseError as e:
            logger.error(f"Sealeddeck error: {e}")
            content += "\n\n**Sealeddeck.tech:** Error\n"
        else:
            content += (
                f"\n\n**Sealeddeck.tech link:** "
                f"https://sealeddeck.tech/{sealeddeck_id}"
                f"\n**Sealeddeck.tech ID:** "
                f"`{sealeddeck_id}`"
            )

        await m.edit(content=content)

        try:
            # Then generate the image of rares in pool (takes a while)
            img_list = [
                await c.get_image(size="normal")
                for p in pool
                for c in p.cards
                if c.card.rarity in ["rare", "mythic"]
            ]
            r_img = utils.rares_img(img_list)
            r_file = BytesIO()
            imageio.imwrite(r_file, r_img, format="jpeg")

            # Upload it to imgur.com
            link = await utils.upload_img(
                r_file, self.bot.config.imgur_client_id
            )
        except aiohttp.ClientResponseError:
            # Send an error message if the upload failed...
            embed = discord.Embed(
                description=":x: Sorry, it seems your rares are lost in "
                "the Blind Eternities...",
                color=discord.Color.red(),
            )
        else:
            # ...or edit the message by embedding the link
            embed = discord.Embed(color=discord.Color.dark_green())
            embed.set_image(url=link)

        await m.edit(embed=embed)

    async def send_plist_msg(
        self,
        p_list: Sequence[MtgPack],
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
        emoji: str = "",
    ) -> None:
        if p_list:
            assert ctx.message
            message: discord.Message = ctx.message
            if len(p_list) == 1:
                await self.send_pack_msg(
                    p_list[0], message=message, member=member, emoji=emoji
                )
            else:
                await self.send_pool_msg(
                    p_list, message=message, member=member, emoji=emoji
                )

    @commands.command(
        help=help_msg(
            "Generates random packs from the whole history of Magic",
            has_num_packs=True,
            examples={
                "random": "generates one pack",
                "random 4": "generates four packs",
            },
        )
    )
    async def random(
        self,
        ctx: commands.Context,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = self.process_num_packs(num_packs)
        p_list = self.generator.get_random_packs(n=num_packs, replace=True)
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        help=help_msg(
            "Generates random (non-alchemy) historic packs",
            has_num_packs=True,
            examples={
                "historic": "generates one pack",
                "historic 4": "generates four packs",
            },
        )
    )
    async def historic(
        self,
        ctx: commands.Context,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = self.process_num_packs(num_packs)
        p_list = self.generator.get_random_packs(
            self.bot.historic_sets, n=num_packs, replace=True
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        name="chaossealed",
        help=help_msg(
            "Generates 6 random (non-alchemy) historic packs",
            examples={
                "chaossealed": "generates six packs",
            },
        ),
    )
    async def chaos_sealed(
        self, ctx: commands.Context, member: Optional[discord.Member] = None
    ) -> None:
        p_list = self.generator.get_random_packs(self.bot.historic_sets, n=6)
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        help=help_msg(
            "Generates random standard packs",
            has_num_packs=True,
            examples={
                "standard": "generates one pack",
                "standard 4": "generates four packs",
            },
        )
    )
    async def standard(
        self,
        ctx: commands.Context,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = self.process_num_packs(num_packs)
        p_list = self.generator.get_random_packs(
            self.bot.standard_sets, n=num_packs, replace=True
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        help=help_msg(
            "Generates random explorer packs",
            has_num_packs=True,
            examples={
                "explorer": "generates one pack",
                "explorer 4": "generates four packs",
            },
        )
    )
    async def explorer(
        self,
        ctx: commands.Context,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = self.process_num_packs(num_packs)
        p_list = self.generator.get_random_packs(
            self.bot.explorer_sets, n=num_packs, replace=True
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        help=help_msg(
            "Generates ramdom *Jumpstart* decks (with Arena replacements)",
            has_num_packs=True,
            examples={
                "jmp": "generates one deck",
                "jmp 3": "generates three decks",
            },
        )
    )
    async def jmp(
        self,
        ctx: commands.Context,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = self.process_num_packs(num_packs)
        p_list = (
            self.generator.get_random_jmp_decks(n=num_packs, replace=True)
            if self.generator.has_jmp
            else []  # TODO: consider exception?
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        help=help_msg(
            "Generates packs from the cube indicated by the ID `cube_id`",
            has_num_packs=True,
            args={
                "cube_id": "CubeCobra cube ID of the cube from which to "
                "generate the pack"
            },
            examples={
                "cube modovintage": "generates one pack from the *MTGO "
                "Vintage Cube*",
                "cube modovintage 4": "generates four packs from the *MTGO "
                "Vintage Cube*",
            },
        )
    )
    async def cube(
        self,
        ctx: commands.Context,
        cube_id: str,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = self.process_num_packs(num_packs)
        cube = await utils.get_cube(cube_id)
        p_list = self.generator.get_cube_packs(cube, n=num_packs)
        await self.send_plist_msg(p_list, ctx, member)

    @cube.error
    async def cube_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        assert ctx.message
        message: discord.Message = ctx.message
        if isinstance(error, commands.CommandInvokeError) and isinstance(
            error.original, aiohttp.ClientResponseError
        ):
            await message.reply(
                ":warning: The provided Cube ID cannot be found on CubeCobra."
            )

    @commands.command(
        name="cubesealed",
        help=help_msg(
            "Generates six packs from the cube indicated by the ID `cube_id`",
            args={
                "cube_id": "CubeCobra cube ID of the cube from which to "
                "generate the pack"
            },
            examples={
                "cubesealed modovintage": "generates six pack from the *MTGO "
                "Vintage Cube*",
            },
        ),
    )
    async def cube_sealed(
        self,
        ctx: commands.Context,
        cube_id: str,
        member: Optional[discord.Member] = None,
    ) -> None:
        await self.cube(ctx, cube_id, 6, member)

    @commands.command(
        help=help_msg(
            "Generates packs from the indicated set",
            long_description="It can also be called directly as `{set_code}` "
            "(forgoing `set`)",
            has_num_packs=True,
            args={
                "set_code": "Three-letter code of the set to generate packs "
                "from"
            },
            examples={
                "set znr": "generates one *Zendikar Rising* pack",
                "stx": "generates one *Strixhaven* pack",
                "set znr 4": "generates four *Zendikar Rising* packs",
                "stx 4": "generates four *Strixhaven* packs",
            },
        )
    )
    async def set(
        self,
        ctx: commands.Context,
        set_code: str,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = self.process_num_packs(num_packs)
        p_list = (
            self.generator.get_packs(set_code, num_packs)
            if set_code.lower() in self.bot.all_sets
            else []
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        name="setsealed",
        help=help_msg(
            "Generates six packs from the indicated set",
            long_description="It can also be called as `{set_code}sealed`",
            args={
                "set_code": "Three-letter code of the set to generate packs "
                "from"
            },
            examples={
                "setsealed znr": "generates six *Zendikar Rising* packs",
                "stxsealed": "generates six *Strixhaven* packs",
            },
        ),
    )
    async def set_sealed(
        self,
        ctx: commands.Context,
        set_code: str,
        member: Optional[discord.Member] = None,
    ) -> None:
        await self.set(ctx, set_code, 6, member)

    @commands.command(
        name="addpack",
        help=help_msg(
            "Adds packs to a previously generated sealeddeck.tech pool",
            long_description="This command must be issued in reply to a "
            "message by the bot containing one or more generated packs. Those "
            "packs will be added to the indicated pool.",
            has_member=False,
            args={
                "sealeddeck_id_or_url": "The ID of the sealeddeck.tech pool "
                "to add the additional packs to"
            },
            examples={
                "addpack xyz123": "adds packs to the previously generated "
                "sealeddeck.tech pool with ID xyz123"
            },
        ),
    )
    async def add_pack(
        self, ctx: commands.Context, sealeddeck_id_or_url: str
    ) -> None:
        assert ctx.message
        message: discord.Message = ctx.message
        if not message.reference:
            await message.reply(
                ":warning: To add packs to the sealeddeck.tech pool `xyz123`, "
                "reply to my message with the pack content with the command "
                f"`{self.bot.command_prefix}addpack xyz123`"
            )
            return

        ref = await message.channel.fetch_message(message.reference.message_id)
        if ref.author != self.bot.user or (
            len(ref.content.split("```")) < 2 and not ref.attachments
        ):
            await message.reply(
                ":warning: The message you are replying to does not contain "
                "packs I have generated"
            )
            return

        if len(ref.content.split("```")) >= 2:
            ref_pack = ref.content.split("```")[1].strip()
        else:
            ref_pack = (await ref.attachments[0].read()).decode()

        pack_json = utils.arena_to_json(ref_pack)
        sealeddeck_id = sealeddeck_id_or_url.replace(
            "https://sealeddeck.tech/", ""
        )
        m = await message.reply(":hourglass: Adding pack to pool...")
        try:
            new_id = await utils.pool_to_sealeddeck(pack_json, sealeddeck_id)
        except aiohttp.ClientResponseError as e:
            logger.error(f"Sealeddeck error: {e}")
            content = (
                f":warning: The packs could not be added to sealeddeck.tech "
                f"pool with ID `{sealeddeck_id}`. Please, verify the ID.\n"
                f"If the ID is correct, sealeddeck.tech might be having some "
                f"issues right now, try again later."
            )

        else:
            content = (
                f"The packs have been added to the pool.\n\n"
                f"**Updated sealeddeck.tech pool**\n"
                f"link: https://sealeddeck.tech/{new_id}\n"
                f"ID: `{new_id}`"
            )
        await m.edit(content=content)

    # Cog error handler
    async def cog_command_error(self, ctx, error):
        message: discord.Message = ctx.message
        if isinstance(error, commands.MissingRequiredArgument):
            await message.reply(
                f":warning: {error}\nFor more help, "
                f"use `{self.bot.command_prefix}help {ctx.invoked_with}`."
            )
