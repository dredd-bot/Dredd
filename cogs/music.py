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
import wavelink
import re
import asyncio
import itertools
import humanize
import datetime
import async_timeout
import math
import random
import json
import spotify as spotify_client

from time import time
from discord.ext import commands
from wavelink.ext import spotify
from utils.checks import check_music, is_admin, has_voted
from utils.paginator import Pages
from contextlib import suppress
from typing import Optional
from utils.i18n import locale_doc
from utils.default import background_error, spotify_support
from utils import logger as logging, components

RURL = re.compile(r'https?://(?:www\.)?.+')
SOUNDCLOUD = re.compile(r'http[s]?://(?:www\.)?soundcloud.com/(?P<author>[a-zA-Z0-9\-.]+)/(?P<song>[a-zA-Z0-9\-.]+)')
SPOTIFY_RURL = re.compile(r'https?://open.spotify.com/(?P<type>album|playlist|track)/(?P<id>[a-zA-Z0-9]+)')


class Track(wavelink.Track):
    """Wavelink Track object with a requester attribute."""

    __slots__ = ('requester', 'identified', )

    def __init__(self, *args, **kwargs):
        super().__init__(*args)  # type: ignore

        self.requester = kwargs.get('requester')
        self.identified = kwargs.get('identified')

    @property
    def thumbnail(self) -> str:
        """The URL to the thumbnail of this video."""
        return f"https://img.youtube.com/vi/{self.identifier}/maxresdefault.jpg"

    thumb = thumbnail


# noinspection PyProtectedMember
class Player(wavelink.Player):
    """Custom wavelink Player class."""

    def __init__(self, ctx, dj: Optional[discord.Member], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.context = ctx
        self.dj: Optional[discord.Member] = dj

        self.queue = asyncio.Queue()
        self.controller = None
        self.loop = 0
        self.volume = 15

        self.waiting = False
        self.updating = False

        self.pause_votes = set()
        self.resume_votes = set()
        self.skip_votes = set()
        self.shuffle_votes = set()
        self.stop_votes = set()
        self.loop_votes = set()

    async def do_next(self) -> None:  # sourcery no-metrics
        try:
            if self.is_playing() or self.waiting:
                return

            # Clear the votes for a new song...
            self.pause_votes.clear()
            self.resume_votes.clear()
            self.skip_votes.clear()
            self.shuffle_votes.clear()
            self.stop_votes.clear()
            self.loop_votes.clear()

            if not self.context.guild.me.voice and not await self.context.bot.is_owner(self.dj):
                await self.teardown()
                return await self.context.channel.send(_("Looks like you've encountered bug that we're unaware how to fix, we've gone ahead and destroyed "
                                                         "your music player for this guild, if you still encounter these bugs, please join the support server here: {0}").format(
                                                             self.context.bot.support
                                                         ))

            if isinstance(self.context.guild.me.voice.channel, discord.StageChannel):
                if self.context.guild.me.voice.suppress and self.context.guild.me.voice.channel.permissions_for(self.context.guild.me).request_to_speak:
                    await self.context.guild.me.request_to_speak()
                    await self.context.channel.send(_("{0} Please give me permissions to speak in a stage channel. I will check if I have permissions to speak again in 10 seconds,"
                                                      " if not, I will leave the stage channel.").format(self.context.bot.settings['emojis']['misc']['warn']), delete_after=10)
                await asyncio.sleep(10)
                if self.context.guild.me.voice and self.context.guild.me.voice.suppress:
                    await self.context.channel.send(_("Left because I was still suppressed."))
                    return await self.teardown()

            mode247 = self.context.bot.cache.get(self.context.bot, 'mode247', self.context.guild.id)
            if self.loop == 0:
                try:
                    self.waiting = True
                    with async_timeout.timeout(300):
                        track = await self.queue.get()
                        if track.id == "spotify":
                            spotify_track = await self.context.bot.wavelink.get_tracks(query=f"ytsearch:{track.title} {track.author} audio")
                            track = Track(spotify_track[0].id, spotify_track[0].info, requester=track.requester)
                except asyncio.TimeoutError:
                    # No music has been played for 5 minutes, cleanup and disconnect...
                    if not mode247:
                        return await self.teardown()
            else:
                track = self.queue.get_nowait()
                if self.loop == 1:
                    self.queue._queue.appendleft(track)  # type: ignore
                else:
                    if track.id == "spotify":
                        spotify_track = await self.context.bot.wavelink.get_tracks(query=f"ytsearch:{track.title} {track.author} audio")
                        track = Track(spotify_track[0].id, spotify_track[0].info, requester=track.requester)
                    await self.queue.put(track)

            try:
                times = " (`{0}`)".format(str(datetime.timedelta(seconds=int(track.length))))
            except Exception:
                times = ''

            if track.length >= 20:  # if video is shorter than 20 seconds don't send the "Started playing" message to 1) don't spam the chat 2) don't hit the ratelimit (5/5)
                await self.context.channel.send(_("{0} Started playing **{1}**{2}").format('🎶', track.title, times), delete_after=10)
            await self.set_volume(self.volume)
            await self.play(track)
            self.waiting = False
            await logging.new_log(self.context.bot, time(), 3, 1)
        except Exception as e:
            print(e)

    def build_embed(self) -> Optional[discord.Embed]:
        """Method which builds our players controller embed."""
        track = self.source
        if not track:
            return

        qsize = self.queue.qsize()
        if qsize != 0:
            upcoming = self.queue._queue[0]  # type: ignore
            qsize -= 1
        else:
            upcoming = _('Queue End')

        embed = discord.Embed(color=self.context.bot.settings['colors']['embed_color'])
        if track.is_stream():  # type: ignore
            embed.title = _("Live: {0}").format(track.title)  # type: ignore
            embed.url = track.uri  # type: ignore
            position = ''
        else:
            embed.title = track.title  # type: ignore
            embed.url = track.uri  # type: ignore
            position = str(datetime.timedelta(seconds=int(self.position)))
            position = str(position).split(".")[0]

        loop = _('None') if self.loop == 0 else _('Current') if self.loop == 1 else _('All') if self.loop == 2 else ''
        desc = _(
            "**Now Playing:** {0}\n**Duration:** {1}\n**Volume:** {2}%\n**Requested by:** {3}\n**DJ:** {4}\n**Loop:** {5}\n**Upcoming:** {6} `(+{7})`\n**Filter:**\n{8}╠ **Pitch:** `{9}x`\n{8}╚ **Speed:** `{10}x`"
        ).format(
            track.title, f'{position}/{datetime.timedelta(seconds=int(track.length))}' if not track.is_stream() else _('Live Stream'), self.volume, track.requester,  # type: ignore
            self.dj, loop, upcoming, qsize, '⠀', self._filter.pitch, self._filter.speed,  # type: ignore
        )

        embed.description = desc
        if track.thumb:  # type: ignore
            embed.set_thumbnail(url=track.thumb)  # type: ignore

        return embed

    async def teardown(self):
        """Clear internal states, remove player controller and disconnect."""
        try:
            await self.stop()
            await self.disconnect(force=True)
        except KeyError:
            pass


# noinspection PyProtectedMember,PyUnboundLocalVariable
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.controllers = {}

        self.help_icon = '<:deafened:686251889519493250>'
        self.big_icon = ''
        self._last_command_channel = {}

        self.bot.loop.create_task(self.initialize_nodes())

    async def initialize_nodes(self):
        await self.bot.wait_until_ready()

        with suppress(Exception):
            current_node = wavelink.NodePool.get_node()
            if current_node:
                await current_node.disconnect(force=True)

        await wavelink.NodePool.create_node(bot=self.bot,
                                            host=self.bot.config.MUSIC_IP,
                                            port=self.bot.config.MUSIC_PORT,
                                            password=self.bot.config.MUSIC_PASSWORD,
                                            spotify_client=spotify.SpotifyClient(client_id=self.bot.config.SPOTIFY_CLIENT, client_secret=self.bot.config.SPOTIFY_SECRET))

        # if not hasattr(self.bot, 'wavelink'):
        self.bot.wavelink = wavelink.NodePool.get_node()
        self.bot.wavelink_player = Player
        self.bot.wavelink_track = Track

    @staticmethod
    def chop_microseconds(delta):
        return delta - datetime.timedelta(microseconds=delta.microseconds)

    async def perform_action(self, action: bool, interaction: discord.Interaction, **kwargs):
        if not action:
            return await interaction.message.edit(content=_("Alright, I will not be clearing the queue."), view=None)
        player = interaction.guild.voice_client
        player.queue._queue.clear()  # type: ignore
        tot_songs = kwargs.get("tot_songs")
        return await interaction.message.edit(content=_("{0} Successfully cleared {1} songs from the queue.").format(self.bot.settings['emojis']['misc']['white-mark'], tot_songs), view=None)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        print(f'Node {node.identifier} is ready!')

    @commands.Cog.listener('on_wavelink_track_stuck')
    @commands.Cog.listener('on_wavelink_track_end')
    @commands.Cog.listener('on_wavelink_track_exception')
    async def on_player_stop(self, player, track, **kwargs):
        await player.stop()
        await player.do_next()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.errors.CommandInvokeError) and not self.bot.wavelink.is_connected():
            return await ctx.send(_("{0} Music nodes decided to die at the moment, please try again later.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # sourcery no-metrics
        try:
            mode247 = self.bot.cache.get(self.bot, 'mode247', member.guild.id)
            if before.channel and (not after.channel or after.channel != before.channel) and not mode247 and member.guild.me in before.channel.members:
                if member.bot:
                    return
                humans = [x for x in before.channel.members if not x.bot]
                if not humans:
                    player = member.guild.voice_client
                    with suppress(Exception):
                        channel = member.guild.get_channel(self._last_command_channel[member.guild.id])
                        await channel.send(_("Everyone left the voice channel, I will stop playing music"), delete_after=5)
                    await player.teardown()

            if before.channel and (not after.channel or after.channel != before.channel) and mode247:
                if member.bot:
                    return
                humans = [x for x in before.channel.members if not x.bot]
                if member.guild.me in before.channel.members and not humans:
                    player = member.guild.voice_client
                    self.bot.mode247[member.guild.id]['last_connection'] = datetime.datetime.utcnow()
                    if not player.source.is_stream():
                        await player.set_pause(True)
                        with suppress(Exception):
                            channel = member.guild.get_channel(self._last_command_channel[member.guild.id])
                            await channel.send(_("Everyone left the voice channel, I will pause the current track"), delete_after=5)

            elif mode247 and after.channel.id == mode247['channel'] and not member.bot:
                player = member.guild.voice_client
                if player.is_paused:
                    await player.set_pause(False)
                elif not player.is_playing:
                    with suppress(Exception):
                        channel = member.guild.get_channel(self._last_command_channel[member.guild.id])
                        await channel.send(_("The queue is empty, please add songs to the queue so I could play them."))
                self.bot.mode247[member.guild.id]['last_connection'] = datetime.datetime.utcnow()

            if member.id == self.bot.user.id and not after.channel:
                player = member.guild.voice_client
                self.bot.mode247.pop(member.guild.id, None)
                if player:
                    await player.teardown()
        except Exception as exc:
            await background_error(self, err_type='Music error', err_msg=exc, guild=member.guild, channel=after.channel or before.channel)

    @staticmethod
    def is_dj(ctx) -> bool:
        player = ctx.guild.voice_client
        if not getattr(player.dj, 'voice', None):
            player.dj = ctx.author

        return player.dj == ctx.author or ctx.author.guild_permissions.manage_messages

    def required_votes(self, ctx: commands.Context) -> int:
        player = ctx.guild.voice_client
        channel = self.bot.get_channel(int(player.channel.id))  # type: ignore
        required = math.ceil((len(channel.members) - 1) / 2.5)

        required = min(required, 5)
        return required

    @commands.command(brief=_("Connect bot to a voice channel"))
    @check_music(author_channel=True, same_channel=True, verify_permissions=True)
    @commands.guild_only()
    @locale_doc
    async def connect(self, ctx):
        _(""" Connect bot to a voice channel """)

        player = ctx.guild.voice_client

        if player:
            return await ctx.send(_("{0} Already connected to the voice channel.").format(self.bot.settings['emojis']['misc']['warn']))

        channel = getattr(ctx.author.voice, 'channel')
        await channel.connect(cls=Player(ctx=ctx, dj=ctx.author))
        await asyncio.sleep(0.5)
        if channel.permissions_for(ctx.guild.me).deafen_members and ctx.guild.me.voice and not ctx.guild.me.voice.deaf:
            await ctx.guild.me.edit(deafen=True)
        await ctx.send(_("{0} Connected to **{1}**!").format('🎶', channel.name))

    @commands.command(aliases=['p'], brief=_("Search for and add song(s) to the Queue"))
    @check_music(author_channel=True, same_channel=True, verify_permissions=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    @locale_doc
    async def play(self, ctx, *, query: str):
        _(""" Search for and add song(s) to the Queue """)

        player = ctx.voice_client

        if not player:
            channel = getattr(ctx.author.voice, 'channel')
            player = await channel.connect(cls=self.bot.wavelink_player(ctx, dj=ctx.author))
            await asyncio.sleep(0.5)
            if channel.permissions_for(ctx.guild.me).deafen_members and ctx.guild.me.voice and not ctx.guild.me.voice.deaf:
                await ctx.guild.me.edit(deafen=True)

        query = query.strip('<>')
        if not RURL.match(query) and not SPOTIFY_RURL.match(query):
            query = f'ytsearch:{query}'
        elif SPOTIFY_RURL.match(query):
            url_check = SPOTIFY_RURL.match(query)
            search_type = url_check.group('type')
            search_id = url_check.group('id')

            self._last_command_channel[ctx.guild.id] = ctx.channel.id
            return await spotify_support(ctx, spotify=spotify_client, search_type=search_type, spotify_id=search_id, Track=Track)
        tracks = await self.bot.wavelink.get_tracks(query=query)
        if not tracks:
            return await ctx.send(_('No songs were found with that query. Please try again.'), delete_after=15)

        if isinstance(tracks, wavelink.abc.Playlist):
            length = 0
            for track in tracks.data["tracks"]:  # type: ignore
                await logging.new_log(self.bot, time(), 4, 1)
                await player.queue.put(Track(track["track"], track["info"], requester=ctx.author))
                length += track["info"]["length"]
            try:
                times = " (`{0}`)".format(str(datetime.timedelta(milliseconds=int(length))))
            except Exception:
                times = ''

            await ctx.send(_('{0} Added the playlist **{1}**'
                             ' with {2} songs to the queue!{3}').format('🎶', tracks.data["playlistInfo"]["name"], len(tracks.data["tracks"]), times), delete_after=15)  # type: ignore
        else:
            track = Track(tracks[0].id, tracks[0].info, requester=ctx.author)
            try:
                times = " (`{0}`)".format(str(datetime.timedelta(seconds=int(track.length))))
            except Exception:
                times = ''
            await ctx.send(_('{0} Added **{1}** to the Queue!{2}').format('🎶', track.title, times), delete_after=15)
            await player.queue.put(track)
            await logging.new_log(self.bot, time(), 4, 1)

        self._last_command_channel[ctx.guild.id] = ctx.channel.id
        if not player.is_playing():
            await player.do_next()

    @commands.command(brief=_("Search for and add song(s) to the Queue"))
    @check_music(author_channel=True, same_channel=True, verify_permissions=True)
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    @locale_doc
    async def search(self, ctx, *, query: str):
        _(""" Search for and add song(s) to the Queue """)

        player = ctx.guild.voice_client

        if not player:
            channel = getattr(ctx.author.voice, 'channel')
            await channel.connect(cls=self.bot.wavelink_player(ctx, dj=ctx.author))
            await asyncio.sleep(0.5)
            if channel.permissions_for(ctx.guild.me).deafen_members and not ctx.guild.me.voice.deaf:
                await ctx.guild.me.edit(deafen=True)

        query = query.strip('<>')
        if RURL.match(query):
            return await ctx.send(_("{0} If you have the URL of the song might as well use the `play` command.").format(self.bot.settings['emojis']['misc']['warn']))

        tracks = await self.bot.wavelink.get_tracks(query=f"ytsearch:{query}")
        if not tracks:
            return await ctx.send(_('No songs were found with that query. Please try again.'), delete_after=15)

        songs, options = [], []
        for num, track in enumerate(tracks[:10], start=1):
            songs.append("`[{0}]` {1} `({2})`\n".format(num, track.info["title"], str(datetime.timedelta(seconds=int(track.length)))))
            options.append(discord.SelectOption(label=f"{track.info['title']}", value=num))  # type: ignore

        options.append(discord.SelectOption(label=_("Cancel Search")))

        dropdown = components.DropdownView(ctx, _("Select one of the songs..."), options, cls=self, track_objects=[tracks[:10]])

        return await ctx.send(_("{0} **I've found these songs:**\n\n{1}\n*Please choose a song you want me to queue*").format('🎶', ''.join(songs)), view=dropdown)

    @commands.command(brief=_("Enqueue the radio station"))
    @check_music(author_channel=True, same_channel=True, verify_permissions=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def radio(self, ctx, *, radio: str = None):
        _(""" Plays the selected radio station, if you have suggestions for radio stations, feel free to suggest them in the support server""")

        player = ctx.voice_client

        if not player:
            channel = getattr(ctx.author.voice, 'channel')
            player = await channel.connect(cls=self.bot.wavelink_player(ctx, dj=ctx.author))
            await asyncio.sleep(0.5)
            if channel.permissions_for(ctx.guild.me).deafen_members and not ctx.guild.me.voice.deaf:
                await ctx.guild.me.edit(deafen=True)

        if not radio or radio.title() not in self.bot.radio_stations:
            return await ctx.send(_("You may choose from one of these radio stations:\n• {0}").format('\n• '.join(self.bot.radio_stations)))

        tracks = await self.bot.wavelink.get_tracks(query=f"{self.bot.radio_stations[f'{radio.title()}']}", cls=wavelink.abc.Playable)

        if not tracks:
            return await ctx.send(_("Uh oh, looks like that radio station broke down."))

        tracks[0].info['title'] = radio.title()
        track = Track(tracks[0].id, tracks[0].info, requester=ctx.author)
        await ctx.send(_('{0} Added **{1}** to the Queue!').format('🎶', track.title), delete_after=15)
        await player.queue.put(track)

        self._last_command_channel[ctx.guild.id] = ctx.channel.id
        if not player.is_playing():
            await player.do_next()

    @commands.command(brief=_("Toggle player's 24/7 mode"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def mode247(self, ctx):
        _(""" Enable or disable the player's 24/7 mode """)

        mode247 = self.bot.cache.get(self.bot, 'mode247', ctx.guild.id)

        if self.is_dj(ctx) and not mode247:
            self.bot.mode247[ctx.guild.id] = {"last_connection": datetime.datetime.utcnow(), 'channel': ctx.guild.me.voice.channel.id, 'text': ctx.channel.id}
            return await ctx.send(_("{0} Successfuly enabled 24/7 mode, I will stay in the voice channel when everyone leaves.").format(
                self.bot.settings['emojis']['misc']['white-mark']
            ))
        elif self.is_dj(ctx) and mode247:
            self.bot.mode247.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled 24/7 mode, I will leave the voice channel when everyone leaves.").format(
                self.bot.settings['emojis']['misc']['white-mark']
            ))
        else:
            return await ctx.send(_("{0} I'm sorry, but only the DJ and people with manage messages permission can toggle the 24/7 mode."))

    @commands.command(brief=_("Pause the currently playing song"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def pause(self, ctx):
        _(""" Pause the currently playing song. """)

        player = ctx.voice_client

        if player.source.is_stream():
            return await ctx.send(_("{0} You cannot pause live streams.").format(self.bot.settings['emojis']['misc']['warn']))

        if self.is_dj(ctx):
            await player.set_pause(True)
            return await ctx.send(_('{0} An admin or DJ has stopped the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)

        if not self.is_dj(ctx):
            player.pause_votes.add(ctx.author)
            if len(player.pause_votes) < self.required_votes(ctx):
                return await ctx.send(_('**{0}** has voted to pause the player, {1} more votes are needed to pause.').format(ctx.author, self.required_votes(ctx) - len(player.pause_votes)), delete_after=15)
            await ctx.send(_('{0} Vote to pause passed. Pausing the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
            player.pause_votes.clear()
            return await player.set_pause(True)

    @commands.command(brief=_("Resume the currently paused song."))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def resume(self, ctx):
        _(""" Resume the currently paused song. """)

        player = ctx.voice_client

        if self.is_dj(ctx):
            await ctx.send(_('{0} An admin or DJ has resumed the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)
            return await player.set_pause(False)

        if not self.is_dj(ctx):
            player.resume_votes.add(ctx.author)
            if len(player.resume_votes) < self.required_votes(ctx):
                return await ctx.send(_('**{0}** has voted to resume the player, {1} more votes are needed to resume.').format(ctx.author, self.required_votes(ctx) - len(player.resume_votes)), delete_after=15)
            await ctx.send(_('{0} Vote to resume passed. Resuming the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
            player.resume_votes.clear()
            await player.set_pause(False)

    @commands.command(brief=_("Skip the currently playing song."))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def skip(self, ctx):
        _(""" Skip the currently playing song. """)

        player = ctx.voice_client

        if player.queue.qsize() == 0:
            return await ctx.send(_("{0} There's nothing to skip to, the queue is empty..").format(self.bot.settings['emojis']['misc']['warn']))

        if self.is_dj(ctx):
            await ctx.send(_('{0} An admin or DJ has skipped the song.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)
            return await player.stop()

        elif ctx.author == player.source.requester:
            await ctx.send(_('The song requester has skipped the song.'), delete_after=10)
            player.skip_votes.clear()
            return await player.stop()

        elif not self.is_dj(ctx):
            player.skip_votes.add(ctx.author)
            if len(player.skip_votes) < self.required_votes(ctx):
                return await ctx.send(_('**{0}** has voted to skip the current song, {1} more votes are needed to skip.').format(ctx.author, self.required_votes(ctx) - len(player.skip_votes)), delete_after=15)
            await ctx.send(_('{0} Vote to skip passed. Skipping the song.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
            player.skip_votes.clear()
            return await player.stop()

    @commands.command(aliases=['disconnect', 'dc'], brief=_("Disconnect the player and controller"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def stop(self, ctx):
        _(""" Stop and disconnect the player and controller. """)
        player = ctx.voice_client

        if self.is_dj(ctx):
            await player.teardown()
            return await ctx.send(_('{0} An admin or DJ has stopped the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)

        if not self.is_dj(ctx):
            player.stop_votes.add(ctx.author)
            if len(player.stop_votes) < self.required_votes(ctx):
                return await ctx.send(_('**{0}** has voted to stop the player, {1} more votes are needed to stop.').format(ctx.author, self.required_votes(ctx) - len(player.stop_votes)), delete_after=15)
            await ctx.send(_('{0} Vote to stop passed. Stopping the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
            player.stop_votes.clear()
            await player.teardown()

    @commands.command(aliases=['vol'], brief=_("Change the player's volume"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @has_voted()
    @locale_doc
    async def volume(self, ctx, *, vol: int):
        _(""" Change the player's volume """)

        player = ctx.voice_client

        if await self.bot.is_booster(ctx.author):  # another perk for boosters/donators
            vol = max(min(vol, 250), 0)
        else:
            vol = max(min(vol, 200), 0)

        await ctx.send(_('Setting the player volume to **{0}%**').format(vol))
        await player.set_volume(vol)

    @commands.command(brief=_("Seek the currently playing song"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def seek(self, ctx, seconds: str):
        _(""" Seek the currently playing song """)
        player = ctx.voice_client

        if player.source.is_stream():
            return await ctx.send(_("{0} Can't do that on a stream.").format(self.bot.settings['emojis']['misc']['warn']))

        if seconds.isdigit():
            seconds = int(seconds)
            if 0 < (player.position + seconds) < player.source.length:  # should be 0 < x < end
                seek = player.position + seconds
            elif player.source.length - seconds >= player.source.length:
                seek = 0
            elif (player.position + seconds) > player.source.length:  # past the end
                return await ctx.send(_("{0} You can't seek past the song.").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            seconds = seconds.split(':')
            if len(seconds) > 3 or len(seconds) == 1:
                return await ctx.send(_("{0} Time format doesn't seem to be correct, make sure it's `x:xx:xx` for hours, `x:xx` for minutes and `xx` for seconds.").format(
                    self.bot.settings['emojis']['misc']['warn']
                ))
            if len(seconds) == 3:
                hours, minutes, secs = seconds[0], seconds[1], seconds[2]
            elif len(seconds) == 2:
                hours, minutes, secs = '0', seconds[0], seconds[1]
            if not hours.isdigit() or not minutes.isdigit() or not secs.isdigit():
                return await ctx.send(_("{0} The time you've provided contains letters, please make sure you only use numbers").format(
                    self.bot.settings['emojis']['misc']['warn']
                ))
            hours, minutes, secs = int(hours) * 60 * 60, int(minutes) * 60, int(secs)
            seconds = hours + minutes + secs
            seek = seconds
            if seek > player.source.length:  # past the end
                return await ctx.send(_("{0} You can't seek past the song.").format(self.bot.settings['emojis']['misc']['warn']))
        await player.seek(seek * 1000)  # type: ignore
        await ctx.send(_("{0} Seeked the current song to `{1}/{2}`").format(self.bot.settings['emojis']['misc']['white-mark'], self.chop_microseconds(datetime.timedelta(milliseconds=int(round(seek * 1000)))), str(datetime.timedelta(seconds=int(player.source.length)))))

    @commands.command(aliases=['mix'], brief=_("Shuffle the queue"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def shuffle(self, ctx: commands.Context):
        _("""Shuffle the queue.""")

        player: Optional[Player] = ctx.voice_client

        if player.queue.qsize() < 3:
            return await ctx.send(_('Add more songs to the queue before shuffling.'), delete_after=15)

        if self.is_dj(ctx):
            await ctx.send(_('{0} An admin or DJ has shuffled the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)
            player.shuffle_votes.clear()
            return random.shuffle(player.queue._queue)  # type: ignore

        player.shuffle_votes.add(ctx.author)  # type: ignore

        if len(player.shuffle_votes) < self.required_votes(ctx):
            return await ctx.send(_('**{0}** has voted to shuffle the playlist, {1} more votes are needed to shuffle.').format(ctx.author, self.required_votes(ctx) - len(player.shuffle_votes)), delete_after=15)
        await ctx.send(_('{0} Vote to shuffle passed. Shuffling the playlist.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
        player.shuffle_votes.clear()
        random.shuffle(player.queue._queue)  # type: ignore

    @commands.command(aliases=['q'], brief=_("See the player's Queue"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def queue(self, ctx):
        _(""" Retrieve information on the next songs in the queue. """)
        player = ctx.voice_client

        if not player.source or not player.queue._queue:
            return await ctx.send(_('There are no songs currently in the queue.'), delete_after=20)

        upcoming = []
        total_duration = 0
        for num, item in list(enumerate(itertools.islice(player.queue._queue, 0, player.queue.qsize()), start=1)):
            if not item.is_stream():
                upcoming.append(f"`[{num}]` {item} ({self.chop_microseconds(datetime.timedelta(seconds=int(item.length)))})\n")
                total_duration += item.length
            else:
                upcoming.append(f"`[{num}]` {item} (Live Stream)\n")

        if total_duration != 0:
            footer = _("Total songs in the queue: {0} | Duration: {1}").format(player.queue.qsize(), str(self.chop_microseconds(datetime.timedelta(seconds=int(total_duration)))))
        else:
            footer = _("Total songs in the queue: {0}").format(player.queue.qsize())

        paginator = Pages(ctx,
                          title=_("{0} Queue").format(ctx.guild.name),
                          entries=upcoming,
                          per_page=10,
                          embed_color=self.bot.settings['colors']['embed_color'],
                          footertext=footer,
                          author=ctx.author)
        await paginator.paginate()

    @commands.command(aliases=['rq', 'removequeue', 'remqueue'], name='remove-queue',
                      brief=_("Remove a song from the queue"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.bot_has_permissions(use_external_emojis=True)
    @commands.guild_only()
    @locale_doc
    async def remove_queue(self, ctx, song_pos: int):
        _(""" Remove a song from the queue """)
        player = ctx.voice_client

        if not player.queue._queue:
            return await ctx.send(_('There are no songs in the queue.'), delete_after=20)

        total_songs = player.queue.qsize()
        if song_pos > total_songs:
            return await ctx.send(_("{0} There are only {1} songs in the queue").format(self.bot.settings['emojis']['misc']['warn'], total_songs))

        song_name = player.queue._queue[song_pos - 1].title
        del player.queue._queue[song_pos - 1]
        return await ctx.send(_("{0} Removed song {1} from the queue, there are now {2} songs left in the queue.").format(
            self.bot.settings['emojis']['misc']['white-mark'], song_name, player.queue.qsize()
        ))

    @commands.command(aliases=['cq', 'clearqueue'], name='clear-queue',
                      brief=_("Clear all the songs from the queue"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.bot_has_permissions(use_external_emojis=True)
    @commands.guild_only()
    @locale_doc
    async def clear_queue(self, ctx):
        _(""" Clear all the songs from the queue """)
        player = ctx.voice_client

        if not player.queue._queue:
            return await ctx.send(_('There are no songs in the queue.'), delete_after=20)

        tot_songs = player.queue.qsize()
        buttons = components.ConfirmationButtons(self.bot, self, ctx.author, tot_songs=tot_songs)
        return await ctx.channel.send(_("{0} You're about to delete all the songs from the queue. Are you sure you want to do that?").format(self.bot.settings['emojis']['misc']['warn']), delete_after=60, view=buttons)

    @commands.command(aliases=['np', 'current'], name='now-playing',
                      brief=_("See currently playing song"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def now_playing(self, ctx):
        _(""" Retrieve currently playing song. """)
        player = ctx.voice_client

        track = player.source
        if not track:
            return

        embed = player.build_embed()
        await ctx.send(embed=embed)

    @commands.group(aliases=['setfilter'], name='filter', invoke_without_command=True,
                    brief=_("Manage the player's filter"))
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def _filter(self, ctx):
        _(""" Base command for managing player's filter """)
        await ctx.send_help(ctx.command)

    @_filter.command(brief=_("Change the pitch of the song"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def pitch(self, ctx, pitch: float):
        _(""" Modify the players pitch. """)
        player = ctx.voice_client

        if pitch < 0.1:
            return await ctx.send(_("The value you provided is invalid and will crash the player."))

        try:
            await player.set_filter(wavelink.Timescale(pitch=pitch, speed=player._filter.speed if hasattr(player._filter, 'speed') else 1.0))  # type: ignore
        except Exception:
            raise commands.BadArgument(_("The value you provided can't be negative or above 2.0"))

        await ctx.send(_("{0} Changed the pitch to **{1}x**, give up to 10 seconds for player to take effect").format(self.bot.settings['emojis']['misc']['white-mark'], pitch))

    @_filter.command(brief=_("Change the speed of the song"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def speed(self, ctx, speed: float):
        _(""" Set the players speed.""")

        player = ctx.voice_client

        if speed < 0.1:
            return await ctx.send(_("The value you provided is invalid and will crash the player."))

        if player.source.is_stream():
            return await ctx.send(_("{0} Can't do that on a stream.").format(self.bot.settings['emojis']['misc']['warn']))

        try:
            await player.set_filter(wavelink.Timescale(speed=speed, pitch=player._filter.pitch if hasattr(player._filter, 'pitch') else 1.0))  # type: ignore
        except Exception as e:
            print(e)
            raise commands.BadArgument(_("The value you provided can't be negative or above 2.0"))

        await ctx.send(_("{0} Changed the speed to **{1}x**, give up to 10 seconds for player to take effect").format(self.bot.settings['emojis']['misc']['white-mark'], speed))

    @_filter.command(brief=_("Reset the player's filter"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def reset(self, ctx):
        _(""" Reset the players pitch and speed """)

        player = ctx.voice_client

        await player.set_filter(wavelink.Timescale())  # type: ignore

        await ctx.send(_("{0} Reset the players filter, give up to 10 seconds for player to take effect.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.command(brief=_("Switch the player's loop"))
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def loop(self, ctx):
        _(""" Switch the players loop """)

        player = ctx.voice_client
        track = player.source

        if not self.is_dj(ctx):
            player.loop_votes.add(ctx.author)
            if len(player.loop_votes) >= self.required_votes(ctx):
                player.loop_votes.clear()
            else:
                return await ctx.send(_('**{0}** has voted to loop the player, {1} more votes are needed to loop.').format(ctx.author, self.required_votes(ctx) - len(player.loop_votes)), delete_after=15)

        if player.loop == 0:
            player.loop = 1
            await ctx.send(_("{0} Now looping **{1}**").format(self.bot.settings['emojis']['misc']['white-mark'], track.title))
            player.queue._queue.appendleft(track)
        elif player.loop == 1:
            player.loop = 2
            await ctx.send(_("{0} Now looping all the songs").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif player.loop == 2:
            player.loop = 0
            await ctx.send(_("{0} Songs will no longer loop").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.group(brief=_("Shows your playlist(s)"), invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def playlist(self, ctx, *, member: discord.Member = None):
        _(""" A base command for managing your playlists. If user is provided, you can see that user's playlist and queue it. """)
        user = member or ctx.author
        playlist = await self.bot.db.fetch("SELECT playlist_name, playlist FROM playlist WHERE user_id = $1", user.id)
        if not playlist:
            return await ctx.send(_("{0} You do not have any playlists!").format(self.bot.settings['emojis']['misc']['warn']) if user == ctx.author else _("{0} {1} does not have any playlists!").format(
                self.bot.settings['emojis']['misc']['warn'], user
            ))

        e = discord.Embed(color=self.bot.settings['colors']['embed_color'], title=_("{user}'s playlists").format(user=user.name) if user != ctx.author else _("Your playlists"))
        e.description = "\n".join(_("`[{0}]` **{1}** `({2} songs)`").format(num, pl['playlist_name'], len(pl.get('playlist', ''))) for num, pl in enumerate(playlist, start=1))
        await ctx.send(embed=e)

    @playlist.command(brief=_("Manage your playlist(s)"), name="manage")
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    @locale_doc
    async def manage_playlist(self, ctx, *, playlist_name: str = None):
        """ Manage your playlist(s)
         If playlist isn't provided you can create another playlist using this command. You can have up to 15 playlists. """
        if not playlist_name:
            options = [discord.SelectOption(label=_("Create playlist"), value=0)]  # type: ignore
        else:
            options = [
                discord.SelectOption(label=_("Delete playlist"), value=1),  # type: ignore
                discord.SelectOption(label=_("Add song(s)"), value=2),  # type: ignore
                discord.SelectOption(label=_("Delete song(s)"), value=3),  # type: ignore
                discord.SelectOption(label=_("Rename playlist"), value=4),  # type: ignore
                discord.SelectOption(label=_("Show playlist"), value=5)  # type: ignore
            ]
        options.append(discord.SelectOption(label=_("Cancel Command"), value=6))  # type: ignore
        dropdown = components.PlaylistView(ctx, user=ctx.author, options=options, playlist_name=playlist_name)
        message = _("Managing your playlists") if not playlist_name else _("Managing playlist - **{0}**").format(playlist_name)
        await ctx.send(message, view=dropdown)

    @playlist.command(brief=_("Enqueue your or someone else's playlist"), name="play")
    @commands.cooldown(1, 5, commands.BucketType.member)
    @check_music(author_channel=True, same_channel=True, verify_permissions=True)
    @commands.guild_only()
    @locale_doc
    async def play_playlist(self, ctx, member: Optional[discord.Member], *, playlist_name: str):
        _(""" A command that lets you enqueue yours or another member's playlist """)

        user = member or ctx.author
        playlist = await self.bot.db.fetchval("SELECT playlist FROM playlist WHERE user_id = $1 AND playlist_name = $2", user.id, playlist_name)
        if not playlist:
            return await ctx.send(_("{0} Playlist either has no songs or was not found.").format(self.bot.settings['emojis']['misc']['warn']))

        player = ctx.voice_client

        if not player:
            channel = getattr(ctx.author.voice, 'channel')
            player = await channel.connect(cls=self.bot.wavelink_player(ctx, dj=ctx.author))
            await asyncio.sleep(0.5)
            if channel.permissions_for(ctx.guild.me).deafen_members and ctx.guild.me.voice and not ctx.guild.me.voice.deaf:
                await ctx.guild.me.edit(deafen=True)

        length = 0
        for track in playlist:
            track = json.loads(track)
            track = Track(track["track"], track["info"])
            length += track.length
            await player.queue.put(track)

        try:
            times = " (`{0}`)".format(str(datetime.timedelta(seconds=int(length))))
        except Exception:
            times = ''

        await logging.new_log(self.bot, time(), 4, len(playlist))
        await ctx.send(_('{0} Added the playlist **{1}**'
                         ' with {2} songs to the queue!{3}').format('🎶', playlist_name, len(playlist), times), delete_after=15)  # type: ignore

        if not ctx.voice_client.is_playing():
            await ctx.voice_client.do_next()

    @commands.command(hidden=True)
    @is_admin()
    async def musicinfo(self, ctx):
        """Retrieve various Node/Server/Player information."""
        node = self.bot.wavelink

        used = humanize.naturalsize(node.stats.memory_used)
        total = humanize.naturalsize(node.stats.memory_allocated)
        free = humanize.naturalsize(node.stats.memory_free)
        cpu = node.stats.cpu_cores

        fmt = f'**WaveLink:** `{wavelink.__version__}`\n\n' \
              f'`{len(self.bot.wavelink.players)}` players are distributed on nodes.\n' \
              f'`{node.stats.players}` players are distributed on server.\n' \
              f'`{node.stats.playing_players}` players are playing on server.\n\n' \
              f'Server Memory: `{used}/{total}` | `({free} free)`\n' \
              f'Server CPU: `{cpu}`\n\n' \
              f'Server Uptime: `{datetime.timedelta(milliseconds=node.stats.uptime)}`'
        # f'Connected to `{len(self.bot.wavelink.node)}` nodes.\n' \
        # f'Best available Node `{self.bot.wavelink.get_best_node().__repr__()}`\n' \
        await ctx.send(fmt)


def setup(bot):
    bot.add_cog(Music(bot))
