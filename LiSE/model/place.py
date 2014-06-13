# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013 Zachary Spector,  zacharyspector@gmail.com
from LiSE.orm import SaveableMetaclass
from container import Contents
from stats import Stats


class Place(object):
    """Places where things may be.

    Places are vertices in a character's graph where things can be,
    and where portals can lead. A place's name must be unique within
    its character.

    You don't need to create a bone for each and every place you
    use--link to it with a portal, or put a thing there, and it will
    exist. Place bones are only for when a place needs stats.

    """
    __metaclass__ = SaveableMetaclass
    tables = [
        (
            "place_stat",
            {
                "columns":
                [
                    {
                        'name': 'character',
                        'type': 'text'
                    }, {
                        'name': 'name',
                        'type': 'text'
                    }, {
                        'name': 'key',
                        'type': 'text',
                        'default': 'exists'
                    }, {
                        'name': 'branch',
                        'type': 'integer',
                        'default': 0
                    }, {
                        'name': 'tick',
                        'type': 'integer',
                        'default': 0
                    }, {
                        'name': 'value',
                        'type': 'text',
                        'nullable': True
                    }, {
                        'name': 'type',
                        'type': 'text',
                        'default': 'text'
                    }
                ],
                "primary_key":
                ("character", "name", "key", "branch", "tick"),
                "checks":
                ["type in ('text', 'real', 'boolean', 'integer')"]
            }
        )
    ]

    def __init__(self, character, name):
        """Initialize a place in a character by a name"""
        def make_stat_bone(branch, tick, key, value):
            return Place.bonetypes['place_stat'](
                character=character.name,
                name=name,
                branch=branch,
                tick=tick,
                key=key,
                value=value,
                type={
                    str: 'text',
                    unicode: 'text',
                    int: 'integer',
                    float: 'real',
                    bool: 'boolean'
                }[type(value)]
            )
        self.stats = Stats(
            character.closet,
            ['place_stat', character.name, name],
            make_stat_bone
        )
        self.contents = Contents(character, name)
        self.character = character
        self.name = name

    def __contains__(self, that):
        """Is that here?"""
        return that in self.contents

    def __str__(self):
        return str(self.name)

    def __unicode__(self):
        return unicode(self.name)

    def __eq__(self, other):
        return (
            hasattr(other, 'character') and
            hasattr(other, 'name') and 
            self.character == other.character and
            self.name == other.name
        )

    def __hash__(self):
        return hash((self.character, self.name))

    def __getitem__(self, key):
        return self.stats[key]
