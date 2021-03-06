# Booster Tutor

A Discord bot to generate *Magic: the Gathering* (MTG) boosters

![screenshot](screenshot.jpg)

## Usage

The bot responds to the following commands:

* `!random`: generates a random pack from the whole history of Magic
* `!historic`: generates a random historic pack
* `!standard`: generates a random standard pack
* `!{setcode}`: generates a pack from the indicated set (e.g., `!znr` generates
  a *Zendikar Rising* pack)
* `!{setcode}sealed`: generates 6 packs from the indicated set (e.g.,
  `!znrsealed` generates 6 *Zendikar Rising* packs)
* `!chaossealed`: generates 6 random historic packs
* `!help`: shows usage message

While replying to any command, the bot will mention the user who issued it,
unless the command is followed by a mention, in which case the bot will mention
that user instead. For example, `!znr @user#1234` has the bot mention
*user#1234* (instead of you) in its reply.

## Under the hood

### Booster data source

All booster data comes from [mtgjson](https://mtgjson.com), an open-source
project that catalogs all MTG cards.

### Color balancing

MTG boosters are not purely random, mathematically speaking. They are generated
by collating together cards from print sheets in specific orders, this is what
is kind of known in the limited world as "print run". How this is performed is
not publicly disclosed by Wizards, but in practice the process generates
boosters which enforce some desirable properties for limited play (like color
balancing and no duplicates).

To try to produce boosters which *feel* similar to real MTG boosters, Booster
Tutor uses what is known as *Reuben's algorithm*.

> *Reuben's algorithm*
>
> First, generate a booster using a pure random algorithm, then check against
> the following rules, and if any of the rules aren't met, generate a new
> booster. Repeat until a booster that conforms to the rules is generated. The
> rules are:
>
> * A pack must never have more than 4 commons of the same color
> * A pack must have at least 1 common card of each color
> * A pack must have at least 1 common creature
> * A pack must never have more than 2 uncommons of the same color
> * A pack must never have repeated cards

To avoid infinite loops in presence of corner cases, Booster Tutor attempts at
balancing packs with *Reuben's algorithm* up to a maximum number of iterations
(default: 100).

Some packs (for example *Mystery Boosters*) are not balanced. Information on
whether a pack should be balanced or not is obtained from the metadata by
[mtgjson](https://mtgjson.com).

## Credits

* Of course, huge thanks to [mtgjson](https://mtgjson.com)
* Card images are taken from [Scryfall](https://scryfall.com)
* Part of my data reading implementation is borrowed from
  [pymtgjson](https://pythonhosted.org/mtgjson)
* An [interesting
  discussion](https://gist.github.com/fenhl/8d163733ab92ed718d89975127aac152#simulated-collation)
  over a few approaches on color balancing in MTG boosters from where I took
  *Reuben's algorithm*
* *Wizards of the Coast*, *Magic: The Gathering*, and their logos are
  trademarks of Wizards of the Coast LLC in the United States and other
  countries. © 1993-2021 Wizards. All Rights Reserved. Booster Tutor may use
  the trademarks and other intellectual property of Wizards of the Coast LLC,
  which is permitted under Wizards' Fan Site Policy. For more information about
  Wizards of the Coast or any of Wizards' trademarks or other intellectual
  property, please visit their [website](https://company.wizards.com/).
