import logging
from io import BytesIO
from typing import Any, Optional, Sequence

import aiohttp
import discord
import imageio.v3 as iio
from discord.ext import commands

import boostertutor.utils.utils as utils
from boostertutor.generator import MtgPackGenerator
from boostertutor.models.mtg_pack import MtgPack
from boostertutor.models.mtgjson_sql import BoosterType

logger = logging.getLogger(__name__)

MAX_NUM_PACKS = 36
DEFAULT_INTENTS = discord.Intents.default()
DEFAULT_INTENTS.message_content = True
CUBE_ICON_URL = (
    "https://www.slightlymagic.net/forum/download/file.php?id=28613&mode=view"
)
SEALED_ICON_URL = "https://i.imgur.com/AGqN1PA.png"


def process_num_packs(num_packs: Optional[int]) -> int:
    if num_packs:
        return min(max(1, num_packs), MAX_NUM_PACKS)
    else:
        return 1


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
        pack_generator: Optional[MtgPackGenerator] = None,
        intents: discord.Intents = DEFAULT_INTENTS,
        **options: Any,
    ):
        super().__init__(
            command_prefix=config.command_prefix,
            help_command=commands.MinimalHelpCommand(no_category="Other"),
            description='A Discord bot to generate "Magic: the Gathering" '
            "boosters and sealed pools",
            intents=intents,
            **options,
        )
        self.prefix_str = config.command_prefix
        self.config = config
        self.generator = (
            pack_generator
            if pack_generator
            else MtgPackGenerator(
                path_to_mtgjson=self.config.mtgjson_path,
                validate_data=self.config.validate_data,
            )
        )
        self.standard_sets = [
            "dmu",
            "bro",
            "one",
            "mom",
            "woe",
            "lci",
            "a-mkm",
            "otj",
            "blb",
            "dsk",
            "fdn",
            "dft",
        ]
        self.explorer_sets = [
            "pio",
            "ktk",
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
            "mid",
            "vow",
            "neo",
            "snc",
        ] + self.standard_sets
        self.historic_sets = [
            "klr",
            "akr",
            "sir",
            "ltr",
            "mh3",
        ] + self.explorer_sets
        self.all_sets = [s.lower() for s in self.generator.sets_with_boosters]
        self.add_command(donate)

    async def add_boostertutor_cog(self) -> None:
        await self.add_cog(BotCommands(self))

    async def on_ready(self) -> None:
        logger.info(
            f"{self.user} has connected to {len(self.guilds)} Discord servers:"
            f" {[guild.name for guild in self.guilds]}"
        )

    async def on_message(self, message: discord.Message) -> None:
        if (
            message.author != self.user
            and message.content.startswith(self.prefix_str)
            and len(message.content) > len(self.prefix_str)
        ):
            command = (
                message.content.removeprefix(self.prefix_str)
                .split()[0]
                .lower()
            )
            if command in self.all_sets:
                message.content = message.content.replace(
                    self.prefix_str, self.prefix_str + "set ", 1
                )
                logger.info(message.content)
            elif command.removesuffix("sealed") in self.all_sets:
                message.content = message.content.replace(
                    "sealed", "", 1
                ).replace(self.prefix_str, self.prefix_str + "setsealed ", 1)
            elif command.removesuffix("box") in self.all_sets:
                message.content = message.content.replace(
                    "box", "", 1
                ).replace(self.prefix_str, self.prefix_str + "draftbox ", 1)
            elif command.removeprefix("a-") in self.all_sets:
                message.content = message.content.replace("a-", "", 1).replace(
                    self.prefix_str, self.prefix_str + "arena ", 1
                )

        ctx = await self.get_context(message)
        await self.invoke(ctx)


class BotCommands(commands.Cog, name="Bot"):  # type: ignore
    def __init__(self, bot: DiscordBot):
        super().__init__()
        self.bot = bot
        self.generator = self.bot.generator

    async def send_pack_msg(
        self,
        p: MtgPack,
        message: discord.Message,
        member: Optional[discord.Member] = None,
    ) -> None:
        # First send the booster text with a preview for the image
        embed = discord.Embed(
            title=p.type_str,
            description=f"```\n{p.arena_format()}\n```",
            colour=discord.Colour.dark_gold(),
        )
        if p.type == BoosterType.CUBE:
            set_icon_url = CUBE_ICON_URL
        else:
            set_icon_url = utils.set_symbol_link(p.set.code)
        embed.set_author(name=p.name, icon_url=set_icon_url)
        embed.set_image(url="attachment://pack.webp")
        if member:
            embed.set_footer(
                text=f"Generated for {member.display_name}",
                icon_url=member.display_avatar,
            )

        m = await message.reply(embed=embed)
        back_img = utils.card_backs_img(
            len(p.cards), a30=(p.set.code.upper() == "30A")
        )
        back_img_file = BytesIO()
        iio.imwrite(back_img_file, back_img, extension=".webp")
        back_img_file.seek(0)
        await m.add_files(discord.File(back_img_file, filename="pack.webp"))

        try:
            # Then generate the image of booster content (takes a while)
            img_list = await p.get_images(size="png")
            p_img = utils.cards_img(img_list)
            img_file = BytesIO()
            iio.imwrite(img_file, p_img, extension=".webp")
            img_file.seek(0)
        except aiohttp.ClientResponseError:
            embed.colour = discord.Colour.dark_red()
            await m.edit(embed=embed)
        else:
            # Edit the message by embedding the image
            embed.colour = discord.Colour.dark_green()
            await m.edit(
                embed=embed,
                attachments=[discord.File(img_file, filename="pack.webp")],
            )

    async def send_pool_msg(
        self,
        pool: Sequence[MtgPack],
        message: discord.Message,
        member: Optional[discord.Member] = None,
    ) -> None:
        pool_file = BytesIO(
            bytes("\n".join([p.arena_format() for p in pool]), "utf-8")
        )
        sets = [p.set.code for p in pool]
        set_types = [p.type for p in pool]
        all_same_set = len(set(sets)) <= 1
        is_cube = set(set_types) == {BoosterType.CUBE}
        is_a30 = all(s.upper() == "30A" for s in sets)
        json_pool = [card_json for p in pool for card_json in p.json()]
        rare_list = [
            c
            for p in pool
            for c in p.cards
            if c.meta.rarity in ["rare", "mythic"]
        ]

        # First send the pool content with a preview for the image
        title = "Sealed pool" if len(pool) == 6 else f"{len(pool)} boosters"
        name = member.display_name if member else message.author.display_name
        embed = discord.Embed(title=title, colour=discord.Colour.dark_gold())
        if is_cube:
            pool_icon_url = CUBE_ICON_URL
            pool_name = pool[0].name
        elif all_same_set:
            pool_icon_url = utils.set_symbol_link(pool[0].set.code)
            pool_name = pool[0].name
        else:
            pool_icon_url = SEALED_ICON_URL
            pool_name = ", ".join(sets)
        if pool_icon_url:
            embed.set_author(name=pool_name, icon_url=pool_icon_url)
        embed.set_image(url="attachment://rares.webp")
        if member:
            embed.set_footer(
                text=f"Generated for {member.display_name}",
                icon_url=member.display_avatar,
            )

        m = await message.reply(
            embed=embed,
            file=discord.File(pool_file, filename=f"{name}_pool.txt"),
        )

        back_img = utils.card_backs_img(len(rare_list), a30=is_a30)
        back_img_file = BytesIO()
        iio.imwrite(back_img_file, back_img, extension=".webp")
        back_img_file.seek(0)
        await m.add_files(discord.File(back_img_file, filename="rares.webp"))

        try:
            sealeddeck_id = await utils.pool_to_sealeddeck(json_pool)
        except aiohttp.ClientResponseError as e:
            logger.error(f"SealedDeck.Tech error: {e}")
            sealeddeck_link = ":warning: Error"
            sealeddeck_id = "-"
        else:
            sealeddeck_link = f"https://sealeddeck.tech/{sealeddeck_id}"

        embed.add_field(
            name="SealeDeck.Tech link", value=sealeddeck_link, inline=True
        )
        embed.add_field(
            name="SealedDeck.Tech ID", value=f"`{sealeddeck_id}`", inline=True
        )
        await m.edit(embed=embed)

        try:
            # Then generate the image of rares in pool (takes a while)
            img_list = [await c.get_image(size="png") for c in rare_list]
            r_img = utils.cards_img(img_list)
            r_file = BytesIO()
            iio.imwrite(r_file, r_img, extension=".webp")
            r_file.seek(0)
        except aiohttp.ClientResponseError:
            embed.colour = discord.Colour.dark_red()
            await m.edit(embed=embed)
        else:
            # Edit the message by embedding the image
            embed.colour = discord.Colour.dark_green()
            pool_file_from_msg = m.attachments[0]
            await m.edit(
                embed=embed,
                attachments=[
                    pool_file_from_msg,
                    discord.File(r_file, filename="rares.webp"),
                ],
            )

    async def send_plist_msg(
        self,
        p_list: Sequence[MtgPack],
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ) -> None:
        if p_list:
            assert ctx.message
            msg: discord.Message = ctx.message
            if len(p_list) == 1:
                await self.send_pack_msg(p_list[0], message=msg, member=member)
            else:
                await self.send_pool_msg(p_list, message=msg, member=member)

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
        num_packs = process_num_packs(num_packs)
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
        num_packs = process_num_packs(num_packs)
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
        num_packs = process_num_packs(num_packs)
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
        num_packs = process_num_packs(num_packs)
        p_list = self.generator.get_random_packs(
            self.bot.explorer_sets, n=num_packs, replace=True
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        name="from",
        help=help_msg(
            "Generates random packs from a list of sets",
            has_num_packs=True,
            args={
                "sets": "A list of set codes separated only by '|', no "
                "spaces. If a set code is preceeded by 'a-' an Arena pack of "
                "that set is generated instead"
            },
            examples={
                "from inv|pls|apc": (
                    "generates one pack at random from either *Invasion*, "
                    "*Planeshift*, or *Apocalypse*"
                ),
                "from inv|pls|apc 4": (
                    "generates four packs at random from either *Invasion*, "
                    "*Planeshift*, or *Apocalypse*"
                ),
            },
        ),
    )
    async def from_list(
        self,
        ctx: commands.Context,
        sets: str,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        set_list = sets.split("|")
        num_packs = process_num_packs(num_packs)
        p_list = self.generator.get_random_packs(
            set_list, n=num_packs, replace=True
        )
        await self.send_plist_msg(p_list, ctx, member)

    @from_list.error
    async def from_list_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        assert ctx.message
        message: discord.Message = ctx.message
        if isinstance(error, commands.CommandInvokeError) and isinstance(
            error.original, AssertionError
        ):
            await message.reply(f":warning: {error.original}")
        else:
            logger.error(error)

    @commands.command(
        name="pool",
        help=help_msg(
            "Generates a a pack each from a list of sets",
            args={
                "sets": "A list of set codes separated only by '|', no "
                "spaces. If a set code is preceeded by 'a-' an Arena pack of "
                "that set is generated instead. If a set code is preceeded by "
                "'cube-' then it is interpreted as a CubeCobra cube_id and a "
                "pack from the corresponding cube is generated"
            },
            examples={
                "pool inv|pls|apc": (
                    "generates one pack each from *Invasion*, "
                    "*Planeshift*, or *Apocalypse*"
                ),
                "pool a-mkm|cube-modovintage|cube-modovintage": (
                    "generates one Arena pack from *Murders at Karlov Manor* "
                    "and two *MTGO Vintage Cube* packs "
                ),
            },
        ),
    )
    async def pool(
        self,
        ctx: commands.Context,
        sets: str,
        member: Optional[discord.Member] = None,
    ) -> None:
        set_list = sets.split("|")
        p_list = []
        for set in set_list:
            if set.startswith("cube-"):
                cube = await utils.get_cube(set.lstrip("cube-"))
                p = self.generator.get_cube_pack(cube)
            else:
                p = self.generator.get_pack(set)
            p_list.append(p)
        await self.send_plist_msg(p_list, ctx, member)

    @pool.error
    async def pool_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        assert ctx.message
        message: discord.Message = ctx.message
        if isinstance(error, commands.CommandInvokeError) and isinstance(
            error.original, AssertionError
        ):
            await message.reply(f":warning: {error.original}")
        elif isinstance(error, commands.CommandInvokeError) and isinstance(
            error.original, aiohttp.ClientResponseError
        ):
            await message.reply(
                ":warning: The provided Cube ID cannot be found on CubeCobra."
            )
        else:
            logger.error(error)

    @commands.command(
        help=help_msg(
            "Generates ramdom *Jumpstart* decks (without Arena replacements)",
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
        num_packs = process_num_packs(num_packs)
        p_list = self.generator.get_random_decks(
            set="JMP", n=num_packs, replace=True
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        help=help_msg(
            "Generates ramdom *Jumpstart 2022* decks",
            has_num_packs=True,
            examples={
                "j22": "generates one deck",
                "j22 3": "generates three decks",
            },
        )
    )
    async def j22(
        self,
        ctx: commands.Context,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = process_num_packs(num_packs)
        p_list = self.generator.get_random_decks(
            set="J22", n=num_packs, replace=True
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        help=help_msg(
            "Generates ramdom *Foundations Jumpstart* decks",
            has_num_packs=True,
            examples={
                "j25": "generates one deck",
                "j25 3": "generates three decks",
            },
        )
    )
    async def j25(
        self,
        ctx: commands.Context,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = process_num_packs(num_packs)
        p_list = self.generator.get_random_decks(
            set="J25", n=num_packs, replace=True
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        name="a-jmp",
        help=help_msg(
            "Generates ramdom *Jumpstart* decks (with Arena replacements)",
            has_num_packs=True,
            examples={
                "a-jmp": "generates one deck",
                "a-jmp 3": "generates three decks",
            },
        ),
    )
    async def ajmp(
        self,
        ctx: commands.Context,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = process_num_packs(num_packs)
        p_list = self.generator.get_random_arena_jmp_decks(
            n=num_packs, replace=True
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
        num_packs = process_num_packs(num_packs)
        cube = await utils.get_cube(cube_id)
        p_list = self.generator.get_cube_packs(cube, n=num_packs)
        await self.send_plist_msg(p_list, ctx, member)

    @cube.error
    async def cube_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        assert ctx.message
        message: discord.Message = ctx.message
        if isinstance(error, commands.CommandInvokeError) and isinstance(
            error.original, aiohttp.ClientResponseError
        ):
            await message.reply(
                ":warning: The provided Cube ID cannot be found on CubeCobra."
            )
        else:
            logger.error(error)

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
        num_packs = process_num_packs(num_packs)
        p_list = (
            self.generator.get_packs(set_code, num_packs)
            if set_code.lower() in self.bot.all_sets
            else []
        )
        await self.send_plist_msg(p_list, ctx, member)

    @commands.command(
        help=help_msg(
            "Generates collector packs from the indicated set",
            has_num_packs=True,
            args={
                "set_code": "Three-letter code of the set to generate packs "
                "from"
            },
            examples={
                "collector znr": "generates one *Zendikar Rising* collector "
                "pack",
                "collector stx 4": "generates four *Strixhaven* collector "
                "packs",
            },
        )
    )
    async def collector(
        self,
        ctx: commands.Context,
        set_code: str,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = process_num_packs(num_packs)
        try:
            p_list = (
                self.generator.get_packs(
                    set_code, num_packs, booster_type=BoosterType.COLLECTOR
                )
                if set_code.lower() in self.bot.all_sets
                else []
            )
            await self.send_plist_msg(p_list, ctx, member)
        except ValueError:
            assert ctx.message
            message: discord.Message = ctx.message
            await message.reply(
                ":warning: The provided set does not have collector boosters."
            )

    @commands.command(
        help=help_msg(
            "Generates arena draft packs from the indicated set",
            long_description="It can also be called with the shortcut "
            "`a-{set_code}`",
            has_num_packs=True,
            args={
                "set_code": "Three-letter code of the set to generate packs "
                "from"
            },
            examples={
                "arena znr": "generates one *Zendikar Rising* arena draft"
                "pack",
                "arena stx 4": "generates four *Strixhaven* arena draft packs",
            },
        )
    )
    async def arena(
        self,
        ctx: commands.Context,
        set_code: str,
        num_packs: Optional[int] = None,
        member: Optional[discord.Member] = None,
    ) -> None:
        num_packs = process_num_packs(num_packs)
        try:
            p_list = (
                self.generator.get_packs(
                    set_code, num_packs, booster_type=BoosterType.DRAFT_ARENA
                )
                if set_code.lower() in self.bot.all_sets
                else []
            )
            await self.send_plist_msg(p_list, ctx, member)
        except ValueError:
            assert ctx.message
            message: discord.Message = ctx.message
            await message.reply(
                ":warning: The provided set does not have arena boosters."
            )

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
        name="draftbox",
        help=help_msg(
            "Generates a draft boooster box from the indicated set",
            long_description="It can also be called as `{set_code}box`",
            args={
                "set_code": "Three-letter code of the set to generate packs "
                "from"
            },
            examples={
                "draftbox znr": "generates 36 *Zendikar Rising* packs",
                "emabox": "generates 24 *Eternal Masters* packs",
            },
        ),
    )
    async def draft_box(
        self,
        ctx: commands.Context,
        set_code: str,
        member: Optional[discord.Member] = None,
    ) -> None:
        if set_code.lower() in self.bot.all_sets:
            # set = self.generator.data.sets[set_code.upper()]
            num_packs = 36
            # if hasattr(set, "sealedProduct"):
            #     for product in set.sealedProduct:
            #         if (
            #             product.get("category") == "booster_box"
            #             and product.get("subtype") == "draft"
            #         ):
            #             num_packs = product.get("productSize", 36)

            await self.set(ctx, set_code, num_packs, member)

    @commands.command(
        name="addpack",
        help=help_msg(
            "Adds packs to a previously generated SealedDeck.Tech pool",
            long_description="This command must be issued in reply to a "
            "message by the bot containing one or more generated packs. Those "
            "packs will be added to the indicated pool.",
            has_member=False,
            args={
                "sealeddeck_id_or_url": "The ID of the SealedDeck.Tech pool "
                "to add the additional packs to"
            },
            examples={
                "addpack xyz123": "adds packs to the previously generated "
                "SealedDeck.Tech pool with ID xyz123"
            },
        ),
    )
    async def add_pack(
        self, ctx: commands.Context, sealeddeck_id_or_url: str
    ) -> None:

        async def extract_cards_from_message(
            m: discord.Message,
        ) -> Optional[str]:
            if (
                m.embeds
                and m.embeds[0].description
                and len(m.embeds[0].description.split("```")) >= 2
            ):
                cards = m.embeds[0].description.split("```")[1].strip()
            elif m.attachments:
                cards = (await m.attachments[0].read()).decode()
            else:
                cards = None
            return cards

        assert ctx.message
        message: discord.Message = ctx.message
        if not message.reference:
            await message.reply(
                ":warning: To add packs to the SealedDeck.Tech pool `xyz123`, "
                "reply to my message with the pack content with the command "
                f"`{self.bot.prefix_str}addpack xyz123`"
            )
            return

        assert message.reference.message_id
        ref = await message.channel.fetch_message(message.reference.message_id)
        ref_pack = await extract_cards_from_message(ref)
        if ref.author != self.bot.user or ref_pack is None:
            await message.reply(
                ":warning: The message you are replying to does not contain "
                "packs I have generated"
            )
            return

        pack_json = utils.arena_to_json(ref_pack)
        sealeddeck_id = sealeddeck_id_or_url.replace(
            "https://sealeddeck.tech/", ""
        )
        m = await message.reply(":hourglass: Adding pack to pool...")
        try:
            new_id = await utils.pool_to_sealeddeck(pack_json, sealeddeck_id)
        except aiohttp.ClientResponseError as e:
            logger.error(f"SealedDeck.Tech error: {e}")
            content = (
                f":warning: The packs could not be added to SealedDeck.Tech "
                f"pool with ID `{sealeddeck_id}`. Please, verify the ID.\n"
                f"If the ID is correct, SealedDeck.Tech might be having some "
                f"issues right now, try again later."
            )

        else:
            content = (
                f"The packs have been added to the pool.\n\n"
                f"**Updated SealedDeck.Tech pool**\n"
                f"link: https://sealeddeck.tech/{new_id}\n"
                f"ID: `{new_id}`"
            )
        await m.edit(content=content)

    # Cog error handler
    async def cog_command_error(
        self, ctx: commands.Context, error: Exception
    ) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            message: discord.Message = ctx.message
            await message.reply(
                f":warning: {error}\nFor more help, "
                f"use `{self.bot.prefix_str}help {ctx.invoked_with}`."
            )
