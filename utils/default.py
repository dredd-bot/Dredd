import timeago as timesince
import discord
import codecs
import os
import pathlib
import random
import time
import traceback

from discord.ext import commands
from utils.Nullify import clean
from datetime import datetime
from db import emotes

def timeago(target):
    return timesince.format(target)

def timetext(name):
    return f"{name}_{int(time.time())}.txt"

def date(target, clock=True):
    if clock is False:
        return target.strftime("%d %B %Y")
    return target.strftime("%d %B %Y, %H:%M")

def responsible(target, reason):
    responsible = f"[ Mod: {target} ]"
    if reason is None:
        return f"{responsible} no reason."
    return f"{responsible} {reason}"

def traceback_maker(err, advance: bool = True):
    _traceback = ''.join(traceback.format_tb(err.__traceback__))
    error = ('```py\n{1}{0}: {2}\n```').format(type(err).__name__, _traceback, err)
    return error if advance else f"{type(err).__name__}: {err}"

def next_level(ctx):
    if str(ctx.guild.premium_tier) == "0":
        count = int(2 - ctx.guild.premium_subscription_count)
        txt = f'Next level in **{count}** boosts'
        return txt

    if str(ctx.guild.premium_tier) == "1":
        count = int(15 - ctx.guild.premium_subscription_count)
        txt = f'Next level in **{count}** boosts'
        return txt

    if str(ctx.guild.premium_tier) == "2":
        count = int(30 - ctx.guild.premium_subscription_count)
        txt = f'Next level in **{count}** boosts'
        return txt

    if str(ctx.guild.premium_tier) == "3":
        txt = 'Guild is boosted to its max level'
        return txt


def member_activity(member):

    if not member.activity or not member.activities:
        return "N/A"

    message = "\n"

    for activity in member.activities:

        if activity.type == discord.ActivityType.custom:
            message += f"• "
            if activity.emoji:
                if activity.emoji.is_custom_emoji():
                    message += f'(Emoji) '
                else:
                    message += f"{activity.emoji} "
            if activity.name:
                message += f"{clean(activity.name)}"
            message += "\n"

        elif activity.type == discord.ActivityType.playing:


            message += f"{emotes.rich_presence} Playing **{clean(activity.name)}** "
            if not isinstance(activity, discord.Game):
                
                if activity.details:
                    message += f"**| {activity.details}** "
                if activity.state:
                    message += f"**| {activity.state}** "
                message += "\n"
            else:
                message += "\n"

        elif activity.type == discord.ActivityType.streaming:
            try:
                message += f"{emotes.stream_presence} Streaming **[{activity.name}]({activity.url})** on **{activity.platform}**\n"
            except AttributeError:
                message += f"{emotes.stream_presence} Shit broke while trying to figure out streaming details."

        elif activity.type == discord.ActivityType.watching:
            message += f"{emotes.rich_presence} Watching **{clean(activity.name)}**\n"

        elif activity.type == discord.ActivityType.listening:

            if isinstance(activity, discord.Spotify):
                url = f"https://open.spotify.com/track/{activity.track_id}"
                message += f"{emotes.music_presence} Listening to **[{activity.title}]({url})** by **{', '.join(activity.artists)}** "
                if activity.album and not activity.album == activity.title:
                    message += f", album — **{activity.album}** "
                message += "\n"
            else:
                message += f"{emotes.music_presence} Listening to **{clean(activity.name)}**\n"

    return message

