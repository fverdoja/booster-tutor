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


class BoosterTutor(commands.Cog):
    def __init__(self, bot: commands.Bot, config: utils.Config):
        self.bot = bot
        self.config = config
        self.generator = MtgPackGenerator(
            path_to_mtgjson=self.config.mtgjson_path,
            path_to_jmp=self.config.jmp_decklists_path,
            jmp_arena=True,
        )
        self.standard_sets = [
            "znr",
            "khm",
            "stx",
            "afr",
            "mid",
            "vow",
            "neo",
            "snc",
        ]
        self.historic_sets = [
            "klr",
            "akr",
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
        ]
        self.all_sets = [s.lower() for s in self.generator.sets_with_boosters]

    def __random(self, num_packs: int) -> Sequence[MtgPack]:
        return self.generator.get_random_packs(n=num_packs, replace=True)

    def __historic(self, num_packs: int) -> Sequence[MtgPack]:
        return self.generator.get_random_packs(
            self.historic_sets, n=num_packs, replace=True
        )

    def __chaos_sealed(self) -> Sequence[MtgPack]:
        return self.generator.get_random_packs(self.historic_sets, n=6)

    def __standard(self, num_packs: int) -> Sequence[MtgPack]:
        return self.generator.get_random_packs(
            self.standard_sets, n=num_packs, replace=True
        )

    def __jmp(self, num_packs: int) -> Sequence[MtgPack]:
        return (
            self.generator.get_random_jmp_decks(n=num_packs, replace=True)
            if self.generator.has_jmp
            else []  # TODO: consider exception?
        )

    async def __cube(  # TODO: throws exception, should it handle it?
        self, cube_id: str, num_packs: int
    ) -> Sequence[MtgPack]:
        cube = await utils.get_cube(cube_id)
        return self.generator.get_cube_packs(cube, n=num_packs)

    def __set(self, set: str, num_packs: int) -> Sequence[MtgPack]:
        return (
            self.generator.get_packs(set, n=num_packs)
            if set in self.all_sets
            else []  # TODO: consider exception?
        )

    def emoji(self, name: str, guild: Optional[discord.Guild] = None) -> str:
        """Return an emoji if it exists on the server or empty otherwise"""
        for e in guild.emojis if guild else self.bot.emojis:
            if e.name == name:
                return str(e)
        return ""

    async def send_pack_msg(
        self,
        p: MtgPack,
        message: discord.Message,
        member: discord.Member,
        emoji: str,
    ) -> None:
        # First send the booster text with a loading message for the image
        embed = discord.Embed(
            description=":hourglass: Summoning a vision of your booster "
            "from the aether...",
            color=discord.Color.orange(),
        )

        m = await message.channel.send(
            f"**{emoji}{(' ' if len(emoji) else '')}{p.name}**\n"
            f"{member.mention}\n"
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
                img_file, self.config.imgur_client_id
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
            embed = discord.Embed(
                color=discord.Color.dark_green(), description=link
            )
            embed.set_image(url=link)

        await m.edit(embed=embed)

    async def send_pool_msg(
        self,
        pool: Sequence[MtgPack],
        message: discord.Message,
        member: discord.Member,
        emoji: str,
    ) -> None:
        pool_file = StringIO("\r\n".join([p.arena_format() for p in pool]))
        sets = ", ".join([p.set.code for p in pool])
        json_pool = [card_json for p in pool for card_json in p.json()]

        # First send the pool content with a loading message for the image
        embed = discord.Embed(
            description=":hourglass: Summoning a vision of your rares "
            "from the aether...",
            color=discord.Color.orange(),
        )
        title = "Sealed pool" if len(pool) == 6 else f"{len(pool)} packs"
        m = await message.channel.send(
            f"**{emoji}{(' ' if len(emoji) else '')}{title}**\n"
            f"{member.mention}\n"
            f"Content: [{sets}]",
            embed=embed,
            file=discord.File(pool_file, filename=f"{member.nick}_pool.txt"),
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
            link = await utils.upload_img(r_file, self.config.imgur_client_id)
        except aiohttp.ClientResponseError:
            # Send an error message if the upload failed...
            embed = discord.Embed(
                description=":x: Sorry, it seems your rares are lost in "
                "the Blind Eternities...",
                color=discord.Color.red(),
            )
        else:
            # ...or edit the message by embedding the link
            embed = discord.Embed(
                color=discord.Color.dark_green(), description=link
            )
            embed.set_image(url=link)

        await m.edit(embed=embed)

    async def send_plist_msg(
        self, p_list, ctx: commands.Context, emoji: str = ""
    ) -> None:
        if p_list:
            assert ctx.message
            message: discord.Message = ctx.message
            member = (
                message.mentions[0]
                if len(message.mentions)
                else message.author
            )
            if len(p_list) == 1:
                await self.send_pack_msg(p_list[0], message, member, emoji)
            else:
                await self.send_pool_msg(p_list, message, member, emoji)

    @commands.command(name="random")
    async def random(self, ctx: commands.Context, num_packs: int = 1) -> None:
        p_list = self.__random(num_packs)
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="historic")
    async def historic(
        self, ctx: commands.Context, num_packs: int = 1
    ) -> None:
        p_list = self.__historic(num_packs)
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="chaossealed")
    async def chaos_sealed(self, ctx: commands.Context) -> None:
        p_list = self.__chaos_sealed()
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="standard")
    async def standard(
        self, ctx: commands.Context, num_packs: int = 1
    ) -> None:
        p_list = self.__standard(num_packs)
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="jmp")
    async def jmp(self, ctx: commands.Context, num_packs: int = 1) -> None:
        p_list = self.__jmp(num_packs)
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="jmpsealed")
    async def jmp_sealed(self, ctx: commands.Context) -> None:
        p_list = self.__jmp(6)
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="cube")
    async def cube(
        self, ctx: commands.Context, cube_id: str, num_packs: int = 1
    ) -> None:
        p_list = self.__cube(cube_id, num_packs)
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="cubesealed")
    async def cube_sealed(self, ctx: commands.Context, cube_id: str) -> None:
        p_list = self.__cube(cube_id, 6)
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="set")
    async def set(
        self, ctx: commands.Context, set: str, num_packs: int = 1
    ) -> None:
        p_list = self.__set(set, num_packs)
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="setsealed")
    async def set_sealed(self, ctx: commands.Context, set: str) -> None:
        p_list = self.__set(set, 6)
        await self.send_plist_msg(p_list, ctx)

    @commands.command(name="addpack")
    async def add_pack(
        self, ctx: commands.Context, sealeddeck_id: str
    ) -> None:
        assert ctx.message
        message: discord.Message = ctx.message
        if not message.reference:
            await message.channel.send(
                f"{message.author.mention}\n"
                "To add packs to the sealeddeck.tech pool `xyz123`, reply"
                " to my message with the pack content with the command "
                f"`{self.config.command_prefix}addpack xyz123`"
            )
            return

        ref = await message.channel.fetch_message(message.reference.message_id)
        if ref.author != self.bot.user or (
            len(ref.content.split("```")) < 2 and not ref.attachments
        ):
            await message.channel.send(
                f"{message.author.mention}\n"
                "The message you are replying to does not contain "
                "packs I have generated"
            )
            return

        if len(ref.content.split("```")) >= 2:
            ref_pack = ref.content.split("```")[1].strip()
        else:
            ref_pack = (await ref.attachments[0].read()).decode()

        pack_json = utils.arena_to_json(ref_pack)
        m = await message.channel.send(
            f"{message.author.mention}\n" f":hourglass: Adding pack to pool..."
        )
        try:
            new_id = await utils.pool_to_sealeddeck(pack_json, sealeddeck_id)
        except aiohttp.ClientResponseError as e:
            logger.error(f"Sealeddeck error: {e}")
            content = (
                f"{message.author.mention}\n"
                f"The packs could not be added to sealeddeck.tech "
                f"pool with ID `{sealeddeck_id}`. Please, verify "
                f"the ID.\n"
                f"If the ID is correct, sealeddeck.tech might be "
                f"having some issues right now, try again later."
            )

        else:
            content = (
                f"{message.author.mention}\n"
                f"The packs have been added to the pool.\n\n"
                f"**Updated sealeddeck.tech pool**\n"
                f"link: https://sealeddeck.tech/{new_id}\n"
                f"ID: `{new_id}`"
            )
        await m.edit(content=content)
