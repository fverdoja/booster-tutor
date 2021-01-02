#!/usr/bin/env python

class MtgCard:
    def __init__(self, card, foil=False):
        self.card = card
        self.foil = foil

    # def get_image(self, size="normal"):
    #    return image

    def get_arena_format(self):
        return f"1 {self.card.name} ({self.card.setCode}) {self.card.number}"

    def to_str(self):
        foil_str = " (foil)" if self.foil else ""
        return f"{self.card.name}{foil_str}"
