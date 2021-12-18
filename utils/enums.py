"""
Dredd, discord bot
Copyright (C) 2021 Moksej
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.
You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import discord

from enum import Enum
from typing import TypedDict, Union, Optional


class LogType(Enum):
    unknown = -1
    guild_add = 1
    guild_remove = 2
    music_played = 3  # actually played
    music_queued = 4  # queued
    command_invoked = 5
    error_occured = 6
    logs_sent = 7  # all logs in cogs/events/logs.py
    automod_action = 8
    message_sent = 9  # might get changed
    backup_created = 10

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class BlacklistEnum(Enum):
    unknown = -1
    suggestions = 0
    dm = 1
    user = 2
    guild = 3

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class Liftable(Enum):
    unknown = -1
    liftable = 0
    notliftable = 1

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class AutomodActions(Enum):
    unknown = -1
    disable = 0
    mute = 1
    temp_mute = 2
    kick = 3
    ban = 4
    temp_ban = 5

    def __str(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class RaidModeActions(Enum):
    unknown = -1
    kick = 1
    ban = 2
    kick_all = 3
    ban_all = 4

    def __str(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class PlaylistEnum(Enum):
    unknown = -1
    create = 0
    delete = 1
    add_song = 2
    remove_song = 3
    rename = 4
    show = 5
    cancel = 6

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class ReactionRolesAuthor(Enum):
    unknown = -1
    bot = 0
    user = 1

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class ReactionRolesType(Enum):
    unknown = -1
    new_message = 0
    existing_message = 1

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class ReactionRolesMessageType(Enum):
    unknown = -1
    embed = 0
    normal = 1

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class ReactionRolesComponentDisplay(Enum):
    unknown = -1
    all = 0
    label_only = 1
    emoji_only = 2

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class ReactionRolesEmbed(Enum):
    unknown = -1
    title = 0
    description = 1
    footer = 2
    custom = 3

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class SelfRoles(TypedDict):
    reaction: Union[discord.Emoji, discord.PartialEmoji]
    role: int
