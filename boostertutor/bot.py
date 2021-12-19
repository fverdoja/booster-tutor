import os
from io import BytesIO, StringIO
from typing import Optional, Sequence, Union

import aiohttp
import discord
import imageio
import numpy as np
import yaml

from boostertutor.generator import MtgPackGenerator

dir_path = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(dir_path, "..", "config.yaml")) as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

jmp: Optional[str] = (
    config["jmp_decklists_path"] if "jmp_decklists_path" in config else None
)
log: bool = config["pack_logging"] if "pack_logging" in config else True

client = discord.Client()
generator = MtgPackGenerator(
    path_to_mtgjson=config["mtgjson_path"], path_to_jmp=jmp, jmp_arena=True
)
standard_sets = ["znr", "khm", "stx", "afr", "mid", "vow"]
historic_sets = [
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
]
all_sets: list[str] = [s.lower() for s in generator.sets_with_boosters]
prefix: str = config["command_prefix"]


async def pool_to_sealeddeck(
    pool: Sequence[dict], sealeddeck_id: Optional[str] = None
) -> str:
    """Upload a sealed pool to sealeddeck.tech and returns the id"""
    url = "https://sealeddeck.tech/api/pools"

    deck: dict[str, Union[Sequence[dict], str]] = {"sideboard": pool}
    if sealeddeck_id:
        deck["poolId"] = sealeddeck_id

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=deck) as resp:
            resp.raise_for_status()
            resp_json = await resp.json()

    return resp_json["poolId"]


async def upload_img(file: np.ndarray) -> str:
    """Upload an image file to imgur.com and returns the link"""
    url = "https://api.imgur.com/3/image"

    headers = {"Authorization": f"Client-ID {config['imgur_client_id']}"}
    payload = {"image": file.getvalue()}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=payload) as resp:
            resp.raise_for_status()
            resp_json = await resp.json()

    return resp_json["data"]["link"]


def cards_img(
    im_list: Sequence[np.ndarray], max_row_length: int = 10
) -> np.ndarray:
    """Generate an image of the cards in im_list"""
    assert len(im_list)
    num_rows = int(np.ceil(len(im_list) / max_row_length))
    cards_per_row = int(np.ceil(len(im_list) / num_rows))

    cards = None
    for row_i in range(num_rows):
        offset = row_i * cards_per_row
        row = im_list[offset]
        num_cards = min(len(im_list) - offset, cards_per_row)
        for i in range(1 + offset, num_cards + offset):
            row = np.hstack((row, im_list[i]))
        if cards is None:
            cards = row
        else:
            pad_amount = cards.shape[1] - row.shape[1]
            assert pad_amount >= 0
            row = np.pad(
                row,
                [[0, 0], [0, pad_amount], [0, 0]],
                "constant",
                constant_values=255,
            )
            cards = np.vstack((cards, row))
    return cards


def pack_img(im_list: Sequence[np.ndarray]) -> np.ndarray:
    """Generate an image of the cards in a pack"""
    return cards_img(im_list)


def rares_img(im_list: Sequence[np.ndarray]) -> np.ndarray:
    """Generate an image of the rares in a sealed pool"""
    return cards_img(im_list)


def arena_to_json(arena_list: str) -> Sequence[dict]:
    json_list = []
    for line in arena_list.split("\n"):
        count, card = line.split(" ", 1)
        card_name = card.split(" (")[0]
        json_list.append({"name": f"{card_name}", "count": int(count)})
    return json_list


def emoji(name: str, guild: Optional[discord.Guild] = None) -> str:
    """Returns an emoji if it exists on the server or empty string otherwise"""
    for e in guild.emojis if guild else client.emojis:
        if e.name == name:
            return str(e)
    return ""


def set_symbol_link(code: str, size: str = "large", rarity: str = "M") -> str:
    return (
        f"https://gatherer.wizards.com/Handlers/Image.ashx?"
        f"type=symbol&size={size}&rarity={rarity}&set={code.lower()}"
    )


@client.event
async def on_ready() -> None:
    print(f"{client.user} has connected to Discord!")


@client.event
async def on_message(message: discord.Message) -> None:
    if message.author == client.user:
        return
    if not message.content.startswith(prefix):
        return

    argv = message.content.removeprefix(prefix).split()
    assert len(argv)
    command = argv[0].lower()
    if len(message.mentions):
        member = message.mentions[0]
    else:
        member = message.author

    p = p_list = None
    em = ""
    if command == "random":
        p = generator.get_random_packs(log=log)[0]
    elif command == "historic":
        p = generator.get_random_packs(historic_sets, log=log)[0]
    elif command == "standard":
        p = generator.get_random_packs(standard_sets, log=log)[0]
    elif command == "jmp":
        if jmp is not None:
            p = generator.get_random_jmp_decks(log=log)[0]
    elif command in all_sets:
        p = generator.get_pack(command, log=log)
    elif command == "chaossealed":
        em = emoji("CHAOS", message.guild) + " "
        p_list = generator.get_random_packs(historic_sets, n=6, log=log)
    elif command.removesuffix("sealed") in all_sets:
        em = emoji(command.removesuffix("sealed").upper(), message.guild) + " "
        p_list = generator.get_packs(
            command.removesuffix("sealed"), n=6, log=log
        )
    elif command == "jmpsealed":
        if jmp is not None:
            em = emoji("JMP", message.guild)
            p_list = generator.get_random_jmp_decks(n=3, log=log)
    elif command == "help":
        await message.channel.send(
            f"You can give me one of the following commands:\n"
            f"> `{prefix}random`: generates a random pack from the whole "
            f"history of Magic\n"
            f"> `{prefix}historic`: generates a random historic pack\n"
            f"> `{prefix}standard`: generates a random standard pack\n"
            f"> `{prefix}{{setcode}}`: generates a pack from the indicated "
            f"set (e.g., `{prefix}znr` generates a *Zendikar Rising* pack)\n"
            f"> `{prefix}{{setcode}}sealed`: generates 6 packs from the "
            f"indicated set (e.g., `{prefix}znrsealed` generates 6 *Zendikar "
            f"Rising* packs)\n"
            f"> `{prefix}chaossealed`: generates 6 random historic packs\n"
            f"> `{prefix}addpack xyz123`: if issued replying to a pack I have "
            f"generated, adds that pack to the previously generated "
            f"sealeddeck.tech pool with ID `xyz123`\n"
            f"> `{prefix}help`: shows this message\n"
            f"While replying to any command, I will mention the user who "
            f"issued it, unless the command is followed by a mention, in "
            f"which case I will mention that user instead. For example, "
            f"`{prefix}znr @user` has me mention *user* (instead of you) in "
            f"my reply."
        )
    elif command == "addpack":
        if len(argv) != 2 or not message.reference:
            await message.channel.send(
                f"{message.author.mention}\n"
                "To add a pack to the sealeddeck.tech pool `xyz123`, reply to "
                "my message with the pack content with the command "
                f"`{prefix}addpack xyz123`"
            )
        else:
            ref = await message.channel.fetch_message(
                message.reference.message_id
            )
            if ref.author != client.user or len(ref.content.split("```")) < 2:
                await message.channel.send(
                    f"{message.author.mention}\n"
                    "The message you are replying to does not contain a pack "
                    "I have generated"
                )
            else:
                ref_pack = ref.content.split("```")[1].strip()

                sealeddeck_id = argv[1].strip()

                pack_json = arena_to_json(ref_pack)
                m = await message.channel.send(
                    f"{message.author.mention}\n"
                    f":hourglass: Adding pack to pool..."
                )
                try:
                    new_id = await pool_to_sealeddeck(pack_json, sealeddeck_id)
                except aiohttp.ClientResponseError as e:
                    print(f"Sealeddeck error: {e}")
                    content = (
                        f"{message.author.mention}\n"
                        f"The pack could not be added to sealeddeck.tech pool "
                        f"with ID `{sealeddeck_id}`. Please, verify the ID.\n"
                        f"If the ID is correct, sealeddeck.tech might be "
                        f"having some issues right now, try again later."
                    )

                else:
                    content = (
                        f"{message.author.mention}\n"
                        f"The pack has been added to the pool.\n\n"
                        f"**Updated sealeddeck.tech pool**\n"
                        f"link: https://sealeddeck.tech/{new_id}\n"
                        f"ID: `{new_id}`"
                    )
                await m.edit(content=content)

    if p:
        # First send the booster text with a loading message for the image
        embed = discord.Embed(
            description=":hourglass: Summoning a vision of your booster from "
            "the aether...",
            color=discord.Color.orange(),
        )
        em = emoji(p.set.code.upper(), message.guild) + " "

        m = await message.channel.send(
            f"**{em.lstrip()}{p.name}**\n"
            f"{member.mention}\n"
            f"```\n{p.get_arena_format()}\n```",
            embed=embed,
        )

        try:
            # Then generate the image of the booster content (takes a while)
            img_list = await p.get_images(size="normal")
            p_img = pack_img(img_list)
            img_file = BytesIO()
            imageio.imwrite(img_file, p_img, format="jpeg")

            # Upload it to imgur.com
            link = await upload_img(img_file)
        except aiohttp.ClientResponseError:
            # Send an error message if the upload failed...
            embed = discord.Embed(
                description=":x: Sorry, it seems your booster is lost in the "
                "Blind Eternities...",
                color=discord.Color.red(),
            )
        else:
            # ...or edit the message by embedding the link
            embed = discord.Embed(
                color=discord.Color.dark_green(), description=link
            )
            embed.set_image(url=link)

        await m.edit(embed=embed)
    elif p_list:
        pool = ""
        sets = ""
        json_pool: list[dict] = []
        for p in p_list:
            sets += f"{p.set.code}, "
            pool += f"{p.get_arena_format()}\n"
            json_pool += p.get_json()
        sets = sets + ""
        pool_file = StringIO(pool.replace("\n", "\r\n"))

        # First send the pool content with a loading message for the image
        embed = discord.Embed(
            description=":hourglass: Summoning a vision of your rares from "
            "the aether...",
            color=discord.Color.orange(),
        )
        m = await message.channel.send(
            f"**{em.lstrip()}Sealed pool**\n"
            f"{member.mention}\n"
            f"Content: [{sets.rstrip(', ')}]",
            embed=embed,
            file=discord.File(pool_file, filename=f"{member.nick}_pool.txt"),
        )

        content = m.content
        try:
            sealeddeck_id = await pool_to_sealeddeck(json_pool)
        except aiohttp.ClientResponseError as e:
            print(f"Sealeddeck error: {e}")
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
            # Then generate the image of the rares in the pool (takes a while)
            img_list = []
            for p in p_list:
                for c in p.cards:
                    if c.card.rarity in ["rare", "mythic"]:
                        img_list.append(await c.get_image(size="normal"))
            r_img = rares_img(img_list)
            r_file = BytesIO()
            imageio.imwrite(r_file, r_img, format="jpeg")

            # Upload it to imgur.com
            link = await upload_img(r_file)
        except aiohttp.ClientResponseError:
            # Send an error message if the upload failed...
            embed = discord.Embed(
                description=":x: Sorry, it seems your rares are lost in the "
                "Blind Eternities...",
                color=discord.Color.red(),
            )
        else:
            # ...or edit the message by embedding the link
            embed = discord.Embed(
                color=discord.Color.dark_green(), description=link
            )
            embed.set_image(url=link)

        await m.edit(embed=embed)
