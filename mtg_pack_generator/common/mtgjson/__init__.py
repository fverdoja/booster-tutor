from collections import OrderedDict
from functools import total_ordering
import json
import io
from operator import itemgetter
import os
import re
import zipfile

import requests
import six

from .jsonproxy import JSONProxy

ALL_SETS_URL = 'https://mtgjson.com/json/All.json'

ALL_SETS_ZIP_URL = ALL_SETS_URL + '.zip'

ALL_SETS_PATH = os.path.join(os.path.dirname(__file__), 'AllSets.json')

_WS = re.compile('\s+')


@total_ordering
class CardProxy(JSONProxy):
    """A wrapper for a card dictionary.

    Provides additional methods and attributes onto the plain data from
    mtgjson.com.

    Cards support a total ordering that will use the set's release date
    or if cards are from the same set, the collector's number. Cards without
    a collectors number use the canonical ordering system based on
    color/type/card name.
    """

    @property
    def img_url(self):
        """`Gatherer <https://gatherer.wizards.com>` image link."""
        return ('https://gatherer.wizards.com/Handlers/Image.ashx'
                '?multiverseid={}&type=card').format(self.identifiers["multiverseId"])

    @property
    def gatherer_url(self):
        """`Gatherer <https://gatherer.wizards.com>` card details link."""
        return ('https://gatherer.wizards.com/Pages/Card/Details.aspx'
                '?multiverseid={}').format(self.identifiers["multiverseId"])

    @property
    def ascii_name(self):
        """Simplified name (ascii characters, lowercase) for card."""
        return getattr(self, 'asciiName', self.name.lower())

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        if self.set != other.set:
            return self.set < other.set

        try:
            mynum = int(getattr(self, 'number', None))
            othernum = int(getattr(other, 'number', None))
            return mynum < othernum
        except (TypeError, ValueError):
            pass  # not comparable, no valid integer number

        # try creating a pseudo collectors number
        def _getcol(c):
            if hasattr(c, 'colors') and len(c.colors) > 0:
                if len(c.colors) > 1:
                    return 'M'
                return c.colors[0]
            else:
                if 'L' in c.types:
                    return 'L'
                else:
                    return 'A'

        col_order = ['W', 'U', 'B', 'R', 'G', 'M', 'A', 'L']

        if col_order.index(_getcol(self)) < col_order.index(_getcol(other)):
            return True

        # go by name
        return self.name < other.name


@total_ordering
class SetProxy(JSONProxy):
    """Wraps set dictionary with additional methods and attributes. Also
    subject to total ordering based on release date.
    """

    def __lt__(self, other):
        return self.releaseDate < other.releaseDate

    def __eq__(self, other):
        return self.name == other.name

    def __init__(self, data):
        super(SetProxy, self).__init__(data)
        self.cards_by_name = {}
        self.cards_by_ascii_name = {}

        cards = []
        for c in self.cards:
            card = CardProxy(c)
            card.set = self

            self.cards_by_name[card.name] = card
            self.cards_by_ascii_name[card.ascii_name] = card
            cards.append(card)

        self.cards = sorted(cards)


class CardDb(object):
    """The central object of the library. Upon instantiation, reads card data
    into memory and creates various indices to allow easy card retrieval. The
    data passed in is kept in memory and wrapped in a friendly interface.

    Note that usually one of the factory method
    (:func:`~mtgjson.CardDb.from_file` or :func:`~mtgjson.CardDb.from_url`) is
    used to instantiate a db.

    :param db_dict: Deserializied mtgjson.com ``AllSets.json``."""

    def __init__(self, db_dict):
        self._card_db = db_dict["data"]

        self.cards_by_id = {}
        self.cards_by_name = {}
        self.cards_by_ascii_name = {}
        self.sets = OrderedDict()

        # sort sets by release date
        sets = sorted(
            six.itervalues(self._card_db),
            key=itemgetter('releaseDate'))
        for _set in sets:
            s = SetProxy(_set)
            self.sets[s.code] = s

            self.cards_by_name.update(s.cards_by_name)
            self.cards_by_ascii_name.update(s.cards_by_ascii_name)
            for card in s.cards:
                if not hasattr(card, 'uuid'):
                    continue

                self.cards_by_id[card.uuid] = card

        for card_id in self.cards_by_id:
            card = self.cards_by_id[card_id]
            if hasattr(card, "variations"):
                var_ids = card.variations
                card.variations = [self.cards_by_id[i] for i in var_ids]

    @classmethod
    def from_file(cls, db_file=ALL_SETS_PATH):
        """Reads card data from a JSON-file.

        :param db_file: A file-like object or a path.
        :return: A new :class:`~mtgjson.CardDb` instance.
        """
        if callable(getattr(db_file, 'read', None)):
            return cls(json.load(db_file))

        with io.open(db_file, encoding='utf8') as inp:
            return cls(json.load(inp))

    @classmethod
    def from_url(cls, db_url=ALL_SETS_ZIP_URL):
        """Load card data from a URL.

        Uses :func:`requests.get` to fetch card data. Also handles zipfiles.

        :param db_url: URL to fetch.
        :return: A new :class:`~mtgjson.CardDb` instance.
        """
        r = requests.get(db_url)
        r.raise_for_status()

        if r.headers['content-type'] == 'application/json':
            return cls(json.loads(r.text))

        if r.headers['content-type'] == 'application/zip':
            with zipfile.ZipFile(six.BytesIO(r.content), 'r') as zf:
                names = zf.namelist()
                assert len(names) == 1, 'One datafile in ZIP'
                return cls.from_file(io.TextIOWrapper(
                    zf.open(names[0]),
                    encoding='utf8'))
