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


def test_set_lists(bot: DiscordBot):
    assert set(bot.standard_sets).issubset(set(bot.explorer_sets))
    assert set(bot.explorer_sets).issubset(set(bot.historic_sets))
    assert set(bot.historic_sets).issubset(set(bot.all_sets + ["a-mkm"]))


@pytest.mark.asyncio
async def test_donate(bot: DiscordBot):
    await dpytest.message("!donate")
    assert (
        dpytest.verify()
        .message()
        .contains()
        .content("https://ko-fi.com/boostertutor")
    )


@pytest.mark.skip(
    reason="adding files to messages not currently supported by dpytest"
)
async def test_send_pack_msg(bot: DiscordBot, mocked_aioresponses: None):
    await dpytest.message("!set znr")
    await dpytest.run_all_events()
    assert dpytest.verify().message().contains().content("Zendikar Rising")


@pytest.mark.skip(
    reason="adding files to messages not currently supported by dpytest"
)
@pytest.mark.parametrize(
    ["message", "title"],
    [
        ("!set znr 6", "Sealed pool"),
        ("!set znr 4", "4 packs"),
        (f"!set znr {MAX_NUM_PACKS}", f"{MAX_NUM_PACKS} packs"),
        (f"!set znr {MAX_NUM_PACKS+1}", f"{MAX_NUM_PACKS} packs"),
    ],
)
async def test_send_pool_msg(
    bot: DiscordBot, message: str, title: str, mocked_aioresponses: None
):
    await dpytest.message(message)
    await dpytest.run_all_events()
    assert dpytest.verify().message().contains().content(title)
