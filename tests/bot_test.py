import discord.ext.test as dpytest
import pytest

from boostertutor.bot import MAX_NUM_PACKS, DiscordBot, process_num_packs


@pytest.mark.parametrize(
    ["num", "expected"],
    [
        (-1, 1),
        (0, 1),
        (1, 1),
        (MAX_NUM_PACKS - 1, MAX_NUM_PACKS - 1),
        (MAX_NUM_PACKS, MAX_NUM_PACKS),
        (MAX_NUM_PACKS + 1, MAX_NUM_PACKS),
    ],
)
async def test_process_num_packs(num: int, expected: int):
    assert process_num_packs(num) == expected


def test_bot_sets(bot: DiscordBot):
    assert set(bot.standard_sets).issubset(set(bot.explorer_sets))
    assert set(bot.explorer_sets).issubset(set(bot.historic_sets))
    assert set(bot.historic_sets).issubset(set(bot.all_sets))


@pytest.mark.asyncio
async def test_donate(bot: DiscordBot):
    await dpytest.message("!donate")
    assert (
        dpytest.verify()
        .message()
        .contains()
        .content("https://ko-fi.com/boostertutor")
    )


async def test_send_pack_msg(bot: DiscordBot, mocked_aioresponses):
    await dpytest.message("!set znr")
    assert dpytest.verify().message().contains().content("Zendikar Rising")


async def test_send_pool_msg(bot: DiscordBot, mocked_aioresponses):
    await dpytest.message("!set znr 6")
    assert dpytest.verify().message().contains().content("Sealed pool")


async def test_send_pool_msg_non_sealed(bot: DiscordBot, mocked_aioresponses):
    await dpytest.message("!set znr 12")
    assert dpytest.verify().message().contains().content("12 packs")


async def test_send_pool_msg_above_max(bot: DiscordBot, mocked_aioresponses):
    await dpytest.message("!set znr 100")
    assert (
        dpytest.verify().message().contains().content(f"{MAX_NUM_PACKS} packs")
    )
