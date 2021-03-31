#!/usr/bin/env python

import os
from io import BytesIO, StringIO

import aiohttp
import discord
import imageio
import numpy
import yaml

from mtg_pack_generator.mtg_pack_generator import MtgPackGenerator

dir_path = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(dir_path, "config.yaml")) as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

client = discord.Client()
generator = MtgPackGenerator(config["mtgjson_path"])
standard_sets = ["eld", "thb", "iko", "m21", "znr", "khm"]
historic_sets = ["klr", "akr", "xln", "rix", "dom", "m19", "grn", "rna",
                 "war", "m20", "eld", "thb", "iko", "m21", "znr", "khm"]
all_sets = []
for s in generator.sets_with_boosters:
    all_sets.append(s.lower())
prefix = config["command_prefix"]


async def upload_img(file):
    '''Upload an image file to imgur.com and returns the link'''
    url = "https://api.imgur.com/3/image"

    headers = {"Authorization": f"Client-ID {config['imgur_client_id']}"}
    payload = {'image': file.getvalue()}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=payload) as resp:
            resp.raise_for_status()
            resp_json = await resp.json()

    return resp_json["data"]["link"]


def pack_img(im_list):
    '''Generate an image of the cards in a pack over two rows'''
    assert(len(im_list))
    cards_per_row = int(numpy.ceil(len(im_list) / 2))
    row1 = im_list[0]
    row2 = im_list[cards_per_row]
    for i in range(1, len(im_list)):
        if i < cards_per_row:
            row1 = numpy.hstack((row1, im_list[i]))
        if i > cards_per_row:
            row2 = numpy.hstack((row2, im_list[i]))
    pad_amount = row1.shape[1]-row2.shape[1]
    row2 = numpy.pad(row2, [[0, 0], [0, pad_amount], [
                     0, 0]], 'constant', constant_values=255)
    return numpy.vstack((row1, row2))


def rares_img(im_list):
    '''Generate an image of the rares in a sealed pool in a row'''
    assert(len(im_list))
    row = im_list[0]
    for i in range(1, len(im_list)):
        row = numpy.hstack((row, im_list[i]))
    return row


def emoji(name, guild=None):
    '''Returns an emoji if it exists on the server or empty string otherwise'''
    for e in guild.emojis if guild else client.emojis:
        if e.name == name:
            return str(e)
    return ""


def set_symbol_link(code, size="large", rarity="M"):
    return f"https://gatherer.wizards.com/Handlers/Image.ashx?" \
           f"type=symbol&size={size}&rarity={rarity}&set={code.lower()}"


@client.event
async def on_ready():
    print(f"{client.user} has connected to Discord!")


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if not message.content.startswith(prefix):
        return

    argv = message.content.removeprefix(prefix).split()
    assert(len(argv))
    command = argv[0].lower()
    if len(message.mentions):
        member = message.mentions[0]
    else:
        member = message.author

    p = p_list = em = None
    if command == "random":
        p = generator.get_random_pack()
    elif command == "historic":
        p = generator.get_random_pack(historic_sets)
    elif command == "standard":
        p = generator.get_random_pack(standard_sets)
    elif command in all_sets:
        p = generator.get_pack(command)
    elif command == "chaossealed":
        em = emoji("CHAOS", message.guild) + " "
        p_list = generator.get_random_pack(historic_sets, n=6)
    elif command.removesuffix("sealed") in all_sets:
        em = emoji(command.removesuffix("sealed").upper(), message.guild) + " "
        p_list = generator.get_pack(command.removesuffix("sealed"), n=6)
    elif command == "help":
        await message.channel.send(
            "You can give me one of the following commands:\n"
            "> `!random`: generates a random pack from the whole history "
            "of Magic\n"
            "> `!historic`: generates a random historic pack\n"
            "> `!standard`: generates a random standard pack\n"
            "> `!{setcode}`: generates a pack from the indicated set "
            "(e.g., `!znr` generates a *Zendikar Rising* pack)\n"
            "> `!{setcode}sealed`: generates 6 packs from the indicated set "
            "(e.g., `!znrsealed` generates 6 *Zendikar Rising* packs)\n"
            "> `!chaossealed`: generates 6 random historic packs\n"
            "> `!help`: shows this message\n"
            "While replying to any command, I will mention the user who "
            "issued it, unless the command is followed by a mention, in which "
            "case I will mention that user instead. For example, `!znr @user` "
            "has me mention *user* (instead of you) in my reply."
        )

    if p:
        # First send the booster text with a loading message for the image
        embed = discord.Embed(
            description=u":hourglass: Summoning a vision of your booster from "
                        u"the aether...",
            color=discord.Color.orange()
        )
        em = emoji(p.set.code.upper(), message.guild) + " "

        m = await message.channel.send(f"**{em.lstrip()}{p.name}**\n"
                                       f"{member.mention}\n"
                                       f"```\n{p.get_arena_format()}\n```",
                                       embed=embed)

        try:
            # Then generate the image of the booster content (takes a while)
            img_list = await p.get_images(size="normal")
            p_img = pack_img(img_list)
            file = BytesIO()
            imageio.imwrite(file, p_img, format="jpeg")

            # Upload it to imgur.com
            link = await upload_img(file)
        except aiohttp.ClientResponseError:
            # Send an error message if the upload failed...
            embed = discord.Embed(
                description=u":x: Sorry, it seems your booster is lost in the "
                            u"Blind Eternities...",
                color=discord.Color.red()
            )
        else:
            # ...or edit the message by embedding the link
            embed = discord.Embed(
                color=discord.Color.dark_green(),
                description=link
            )
            embed.set_image(url=link)

        await m.edit(embed=embed)
    elif p_list:
        pool = ""
        sets = ""
        for p in p_list:
            sets = sets + f"{p.set.code}, "
            pool = pool + f"{p.get_arena_format()}\n"
        sets = sets + ""
        file = StringIO(pool)

        # First send the pool content with a loading message for the image
        embed = discord.Embed(
            description=u":hourglass: Summoning a vision of your rares from "
                        u"the aether...",
            color=discord.Color.orange()
        )
        m = await message.channel.send(f"**{em.lstrip()}Sealed pool**\n"
                                       f"{member.mention}\n"
                                       f"Content: [{sets.rstrip(', ')}]",
                                       embed=embed,
                                       file=discord.File(
                                           file,
                                           filename=f"{member.nick}_pool.txt"))

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
                description=u":x: Sorry, it seems your rares are lost in the "
                            u"Blind Eternities...",
                color=discord.Color.red()
            )
        else:
            # ...or edit the message by embedding the link
            embed = discord.Embed(
                color=discord.Color.dark_green(),
                description=link
            )
            embed.set_image(url=link)

        await m.edit(embed=embed)

if __name__ == "__main__":
    client.run(config["discord_token"])
