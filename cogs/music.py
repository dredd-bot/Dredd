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
import typing
import datetime
import async_timeout
import math
import random

from discord.ext import commands
from utils.checks import check_music
from utils.paginator import Pages
from contextlib import suppress

RURL = re.compile(r'https?://(?:www\.)?.+')


class Track(wavelink.Track):
    """Wavelink Track object with a requester attribute."""

    __slots__ = ('requester', )

    def __init__(self, *args, **kwargs):
        super().__init__(*args)

        self.requester = kwargs.get('requester')


class Player(wavelink.Player):
    """Custom wavelink Player class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.context = kwargs.get('context', None)
        if self.context:
            self.dj: discord.Member = self.context.author

        self.queue = asyncio.Queue()
        self.controller = None
        self.loop = 0
        self.volume = 50

        self.waiting = False
        self.updating = False

        self.mode247 = False

        self.pause_votes = set()
        self.resume_votes = set()
        self.skip_votes = set()
        self.shuffle_votes = set()
        self.stop_votes = set()
        self.loop_votes = set()

    async def do_next(self) -> None:
        if self.is_playing or self.waiting:
            return

        # Clear the votes for a new song...
        self.pause_votes.clear()
        self.resume_votes.clear()
        self.skip_votes.clear()
        self.shuffle_votes.clear()
        self.stop_votes.clear()
        self.loop_votes.clear()

        if isinstance(self.context.guild.me.voice.channel, discord.StageChannel):
            if self.context.guild.me.voice.suppress:
                await self.context.guild.me.request_to_speak()
                await self.context.channel.send(_("{0} Please give me permissions to speak in a stage channel. I will check if I have permissions to speak again in 10 seconds,"
                                                  " if not, I will leave the stage channel.").format(self.context.bot.settings['emojis']['misc']['warn']), delete_after=10)
                await asyncio.sleep(10)
                if self.context.guild.me.voice.suppress:
                    await self.context.channel.send(_("Left because I was still suppressed."))
                    return await self.teardown()
                else:
                    pass

        if self.loop == 0:
            try:
                self.waiting = True
                with async_timeout.timeout(300):
                    track = await self.queue.get()
            except asyncio.TimeoutError:
                # No music has been played for 5 minutes, cleanup and disconnect...
                return await self.teardown()
        elif self.loop != 0:
            track = await self.queue.get()
            if self.loop == 1:
                self.queue._queue.appendleft(track)
            else:
                await self.queue.put(track)

        try:
            time = " (`{0}`)".format(str(datetime.timedelta(milliseconds=int(track.length))))
        except Exception:
            time = ''

        if track.length >= 20000:  # if video is shorter than 20 seconds don't send the "Started playing" message to 1) don't spam the chat 2) don't hit the ratelimit (5/5)
            await self.context.channel.send(_("{0} Started playing **{1}**{2}").format('🎶', track.title, time), delete_after=10)
        await self.set_volume(self.volume)
        await self.play(track)
        self.waiting = False

    def build_embed(self) -> typing.Optional[discord.Embed]:
        """Method which builds our players controller embed."""
        track = self.current
        if not track:
            return

        channel = self.bot.get_channel(int(self.channel_id))
        qsize = self.queue.qsize()
        if qsize != 0:
            upcoming = self.queue._queue[0]
            qsize -= 1
        else:
            upcoming = _('Queue End')

        embed = discord.Embed(color=self.bot.settings['colors']['embed_color'])
        if track.is_stream:
            embed.title = _("Live: {0}").format(track.title)
            embed.url = track.uri
            position = ''
        else:
            embed.title = track.title
            embed.url = track.uri
            position = str(datetime.timedelta(milliseconds=int(self.position)))
            position = str(position).split(".")[0]

        loop = _('None') if self.loop == 0 else _('Current') if self.loop == 1 else _('All') if self.loop == 2 else ''
        desc = _("**Now Playing:** {0}\n**Duration:** {1}\n**Volume:** {2}%\n**Requested by:** {3}\n**DJ:** {4}\n**Loop:** {5}\n**Upcoming:** {6} `(+{7})`\n**Filter:**\n{8}╠ **Pitch:** `{9}x`\n{8}╚ **Speed:** `{10}x`").format(
            track.title, f"{position}/{str(datetime.timedelta(milliseconds=int(track.length)))}" if not track.is_stream else _('Live Stream'), self.volume,
            track.requester, self.dj, loop, upcoming, qsize, '⠀', self.filter.pitch, self.filter.speed
        )
        embed.description = desc
        if track.thumb:
            embed.set_thumbnail(url=track.thumb)

        return embed

    async def teardown(self):
        """Clear internal states, remove player controller and disconnect."""
        try:
            await self.destroy()
        except KeyError:
            pass


class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.controllers = {}

        self.help_icon = '<:deafened:686251889519493250>'
        self.big_icon = ''
        self._last_command_channel = {}

        if not hasattr(bot, 'wavelink'):
            bot.wavelink = wavelink.Client(bot=self.bot)

        self.bot.loop.create_task(self.initialize_nodes())

    async def initialize_nodes(self):
        await self.bot.wait_until_ready()

        if self.bot.wavelink.nodes:
            previous = self.bot.wavelink.nodes.copy()

            for node in previous.values():
                await node.destroy()

        nodes = {
            'Dredd': {
                'host': '127.0.0.1',
                'port': self.bot.config.MUSIC_PORT,
                'rest_uri': 'http://127.0.0.1:{0}'.format(self.bot.config.MUSIC_PORT),
                'password': self.bot.config.MUSIC_PASSWORD,
                'identifier': self.bot.config.MUSIC_ID,
                'region': 'us_central'
            }}

        for n in nodes.values():
            await self.bot.wavelink.initiate_node(**n)

    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node: wavelink.Node):
        print(f'Node {node.identifier} is ready!')

    @wavelink.WavelinkMixin.listener('on_track_stuck')
    @wavelink.WavelinkMixin.listener('on_track_end')
    @wavelink.WavelinkMixin.listener('on_track_exception')
    async def on_player_stop(self, node: wavelink.Node, payload):
        await payload.player.do_next()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel and (not after.channel or after.channel != before.channel):
            if member.guild.me in before.channel.members:
                if member.bot:
                    return
                humans = [x for x in before.channel.members if not x.bot]
                if member.guild.me in before.channel.members and len(humans) == 0:
                    player = self.bot.wavelink.get_player(member.guild.id, cls=Player)
                    try:
                        channel = member.guild.get_channel(self._last_command_channel[member.guild.id])
                        await channel.send(_("Everyone left the voice channel, I will stop playing music"))
                    except Exception:
                        pass
                    await player.destroy()

    def is_dj(self, ctx) -> bool:
        player = self.bot.wavelink.get_player(guild_id=ctx.guild.id, cls=Player, context=ctx)
        if not getattr(player.dj, 'voice', None):
            player.dj = ctx.author

        return player.dj == ctx.author or ctx.author.guild_permissions.manage_messages

    def required_votes(self, ctx: commands.Context) -> int:
        player = self.bot.wavelink.get_player(guild_id=ctx.guild.id, cls=Player, context=ctx)
        channel = self.bot.get_channel(int(player.channel_id))
        required = math.ceil((len(channel.members) - 1) / 2.5)

        if required > 5:
            required = 5

        return required

    @commands.command()
    @check_music(author_channel=True, bot_channel=False, same_channel=True, verify_permissions=True, is_playing=False, is_paused=False)
    @commands.guild_only()
    async def connect(self, ctx):
        """ Connect bot to a voice channel """
        player = self.bot.wavelink.get_player(guild_id=ctx.guild.id, cls=Player, context=ctx)

        if not player.is_connected:
            channel = getattr(ctx.author.voice, 'channel')
            await player.connect(channel.id)
        elif player.is_connected:
            return await ctx.send(_("{0} Already connected to the voice channel.").format(self.bot.settings['emojis']['misc']['warn']))

        await ctx.send(_("{0} Connected to **{1}**!").format('🎶', channel.name))

    @commands.command()
    @check_music(author_channel=True, bot_channel=False, same_channel=True, verify_permissions=True, is_playing=False, is_paused=False)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def play(self, ctx, *, query: str):
        """Search for and add a song to the Queue."""

        player = self.bot.wavelink.get_player(guild_id=ctx.guild.id, cls=Player, context=ctx)

        if not player.is_connected:
            channel = getattr(ctx.author.voice, 'channel')
            await player.connect(channel.id)

        query = query.strip('<>')
        if not RURL.match(query):
            query = f'ytsearch:{query}'

        tracks = await self.bot.wavelink.get_tracks(query)
        if not tracks:
            return await ctx.send(_('No songs were found with that query. Please try again.'), delete_after=15)

        if isinstance(tracks, wavelink.TrackPlaylist):
            length = 0
            for track in tracks.tracks:
                track = Track(track.id, track.info, requester=ctx.author)
                await player.queue.put(track)
                length += track.length
            try:
                time = " (`{0}`)".format(str(datetime.timedelta(milliseconds=int(length))))
            except Exception:
                time = ''

            await ctx.send(_('{0} Added the playlist **{1}**'
                             ' with {2} songs to the queue!{3}').format('🎶', tracks.data["playlistInfo"]["name"], len(tracks.tracks), time), delete_after=15)
        else:
            track = Track(tracks[0].id, tracks[0].info, requester=ctx.author)
            try:
                time = " (`{0}`)".format(str(datetime.timedelta(milliseconds=int(track.length))))
            except Exception:
                time = ''
            await ctx.send(_('{0} Added **{1}** to the Queue!{2}').format('🎶', track.title, time), delete_after=15)
            await player.queue.put(track)

        self._last_command_channel[ctx.guild.id] = ctx.channel.id
        if not player.is_playing:
            await player.do_next()

    @commands.command()
    @check_music(author_channel=True, bot_channel=False, same_channel=True, verify_permissions=True, is_playing=False, is_paused=False)
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def search(self, ctx, *, query: str):
        """ Search for and add a song(s) to the Queue. """

        player = self.bot.wavelink.get_player(guild_id=ctx.guild.id, cls=Player, context=ctx)

        if not player.is_connected:
            channel = getattr(ctx.author.voice, 'channel')
            await player.connect(channel.id)

        query = query.strip('<>')
        if RURL.match(query):
            return await ctx.send(_("{0} If you have the URL of the song might as well use the `play` command.").format(self.bot.settings['emojis']['misc']['warn']))

        tracks = await self.bot.wavelink.get_tracks(f'ytsearch:{query}')
        if not tracks:
            return await ctx.send(_('No songs were found with that query. Please try again.'), delete_after=15)

        songs = []
        for num, track in enumerate(tracks[:5], start=1):
            songs.append("`[{0}]` {1} `({2})`\n".format(num, track.title, str(datetime.timedelta(milliseconds=int(track.length)))))

        prompt_msg = await ctx.send(_("{0} **I've found these songs:**\n\n{1}\n*Please choose a song you want me to queue*").format('🎶', ''.join(songs)))

        def check(m):
            return m.author == ctx.author and m.channel.id == ctx.channel.id

        select = True
        while select:
            try:
                song_request = await self.bot.wait_for('message', check=check, timeout=60.0)

                if song_request.content in ['1', '2', '3', '4', '5']:
                    channel = getattr(ctx.author.voice, 'channel', None)
                    if not channel:
                        select = False
                        return
                    track = Track(tracks[int(song_request.content) - 1].id, tracks[int(song_request.content) - 1].info, requester=ctx.author)
                    await prompt_msg.edit(content=_('{0} Added **{1}** to the Queue! (`{2}`)').format('🎶', track.title, str(datetime.timedelta(milliseconds=int(track.length)))), delete_after=15)
                    await player.queue.put(track)
                    select = False
                elif song_request.content.lower() == 'cancel':
                    select = False
                    return await prompt_msg.edit(content=_("Canceled the command."))
                else:
                    select = True
                    pass
            except asyncio.TimeoutError:
                channel = getattr(ctx.author.voice, 'channel', None)
                if not channel:
                    select = False
                    return
                track = Track(tracks[0].id, tracks[0].info, requester=ctx.author)
                await prompt_msg.edit(content=_('{0} Added **{1}** to the Queue! (`{2}`)').format('🎶', track.title, str(datetime.timedelta(milliseconds=int(track.length)))), delete_after=15)
                await player.queue.put(track)
                select = False

            except Exception as e:
                await ctx.channel.send(_("{0} Unknown error occured - {1}").format(self.bot.settings['emojis']['misc']['warn'], e))

            self._last_command_channel[ctx.guild.id] = ctx.channel.id

            if not player.is_playing:
                await player.do_next()

    @commands.command()
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def pause(self, ctx):
        """ Pause the currently playing song. """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if self.is_dj(ctx):
            await player.set_pause(True)
            return await ctx.send(_('{0} An admin or DJ has stopped the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)

        if not self.is_dj(ctx):
            player.pause_votes.add(ctx.author)
            if len(player.pause_votes) >= self.required_votes(ctx):
                await ctx.send(_('{0} Vote to pause passed. Pausing the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
                player.pause_votes.clear()
                return await player.set_pause(True)
            else:
                return await ctx.send(_('**{0}** has voted to pause the player, {1} more votes are needed to pause.').format(ctx.author, self.required_votes(ctx) - len(player.pause_votes)), delete_after=15)

    @commands.command()
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def resume(self, ctx):
        """ Resume the currently paused song. """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if self.is_dj(ctx):
            await ctx.send(_('{0} An admin or DJ has resumed the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)
            return await player.set_pause(False)

        if not self.is_dj(ctx):
            player.resume_votes.add(ctx.author)
            if len(player.resume_votes) >= self.required_votes(ctx):
                await ctx.send(_('{0} Vote to resume passed. Resuming the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
                player.resume_votes.clear()
                await player.set_pause(False)
            else:
                return await ctx.send(_('**{0}** has voted to resume the player, {1} more votes are needed to resume.').format(ctx.author, self.required_votes(ctx) - len(player.resume_votes)), delete_after=15)

    @commands.command()
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def skip(self, ctx):
        """Skip the currently playing song."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if player.queue.qsize() == 0 and not player.mode247:
            return await ctx.send(_("{0} There's nothing to skip to, the queue is empty..").format(self.bot.settings['emojis']['misc']['warn']))

        if self.is_dj(ctx):
            await ctx.send(_('{0} An admin or DJ has skipped the song.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)
            return await player.stop()

        elif ctx.author == player.current.requester:
            await ctx.send(_('The song requester has skipped the song.'), delete_after=10)
            player.skip_votes.clear()
            return await player.stop()

        elif not self.is_dj(ctx):
            player.skip_votes.add(ctx.author)
            if len(player.skip_votes) >= self.required_votes(ctx):
                await ctx.send(_('{0} Vote to skip passed. Skipping the song.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
                player.skip_votes.clear()
                return await player.stop()
            else:
                return await ctx.send(_('**{0}** has voted to skip the current song, {1} more votes are needed to skip.').format(ctx.author, self.required_votes(ctx) - len(player.skip_votes)), delete_after=15)

    @commands.command(aliases=['disconnect', 'dc'])
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=False, is_paused=False)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def stop(self, ctx):
        """Stop and disconnect the player and controller."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if self.is_dj(ctx):
            await player.teardown()
            return await ctx.send(_('{0} An admin or DJ has stopped the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)

        if not self.is_dj(ctx):
            player.stop_votes.add(ctx.author)
            if len(player.stop_votes) >= self.required_votes(ctx):
                await ctx.send(_('{0} Vote to stop passed. Stopping the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
                player.stop_votes.clear()
                await player.teardown()
            else:
                return await ctx.send(_('**{0}** has voted to stop the player, {1} more votes are needed to stop.').format(ctx.author, self.required_votes(ctx) - len(player.stop_votes)), delete_after=15)

    @commands.command(aliases=['vol'])
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def volume(self, ctx, *, vol: int):
        """Set the player volume."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if await self.bot.is_booster(ctx.author):  # another perk for boosters/donators
            vol = max(min(vol, 250), 0)
        else:
            vol = max(min(vol, 200), 0)

        await ctx.send(_('Setting the player volume to **{0}%**').format(vol))
        await player.set_volume(vol)

    @commands.command()
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def seek(self, ctx, seconds: int = None):
        """ Seek the current song """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if player.current.is_stream:
            return await ctx.send(_("{0} Can't do that on a stream.").format(self.bot.settings['emojis']['misc']['warn']))

        seconds = seconds or 0

        if not (player.current.length - (seconds * 1000)) < player.current.length:
            seconds = 0

        if seconds * 1000 > player.current.length:
            seconds = player.current.length / 1000

        await player.seek(seconds * 1000)
        await ctx.send(_("{0} Seeked the current song to `{1}/{2}`").format(self.bot.settings['emojis']['misc']['white-mark'], str(datetime.timedelta(milliseconds=seconds * 1000)), str(datetime.timedelta(milliseconds=int(player.current.length)))))

    @commands.command(aliases=['mix'])
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the players queue."""
        player = self.bot.wavelink.get_player(guild_id=ctx.guild.id, cls=Player, context=ctx)

        if player.queue.qsize() < 3:
            return await ctx.send(_('Add more songs to the queue before shuffling.'), delete_after=15)

        if self.is_dj(ctx):
            await ctx.send(_('{0} An admin or DJ has shuffled the player.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=20)
            player.shuffle_votes.clear()
            return random.shuffle(player.queue._queue)

        required = self.required(ctx)
        player.shuffle_votes.add(ctx.author)

        if len(player.shuffle_votes) >= self.required_votes(ctx):
            await ctx.send(_('{0} Vote to shuffle passed. Shuffling the playlist.').format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=10)
            player.shuffle_votes.clear()
            random.shuffle(player.queue._queue)
        else:
            return await ctx.send(_('**{0}** has voted to shuffle the playlist, {1} more votes are needed to shuffle.').format(ctx.author, self.required_votes(ctx) - len(player.shuffle_votes)), delete_after=15)

    @commands.command(aliases=['q'])
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def queue(self, ctx):
        """Retrieve information on the next 5 songs from the queue."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if not player.current or not player.queue._queue:
            return await ctx.send(_('There are no songs currently in the queue.'), delete_after=20)

        upcoming = []
        total_duration = 0
        for num, item in list(enumerate(itertools.islice(player.queue._queue, 0, player.queue.qsize()), start=1)):
            upcoming.append(f"`[{num}]` {item} ({str(datetime.timedelta(milliseconds=int(item.length)))})\n")
            total_duration += item.length

        paginator = Pages(ctx,
                          title=_("{0} Queue. Duration: {1}").format(ctx.guild.name, str(datetime.timedelta(milliseconds=int(total_duration)))),
                          entries=upcoming,
                          thumbnail=None,
                          per_page=10,
                          embed_color=self.bot.settings['colors']['embed_color'],
                          footertext=_("Total songs in the queue: {0}").format(player.queue.qsize()),
                          author=ctx.author)
        await paginator.paginate()

    @commands.command(aliases=['cq', 'clearqueue'], name='clear-queue')
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.bot_has_permissions(use_external_emojis=True)
    @commands.guild_only()
    async def clear_queue(self, ctx):
        """ Clear all the songs from the queue """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if not player.queue._queue:
            return await ctx.send(_('There are no songs in the queue.'), delete_after=20)

        tot_songs = player.queue.qsize()
        loop = True
        while loop:
            try:
                msg = await ctx.channel.send(_("{0} You're about to delete all the songs from the queue. Are you sure you want to do that?").format(self.bot.settings['emojis']['misc']['warn']), delete_after=60)
                await msg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
                await msg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
                verify_response, user = await self.bot.wait_for('reaction_add', check=lambda r, m: r.message.id == msg.id and m.id == ctx.author.id, timeout=60.0)

                if str(verify_response) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                    loop = False
                    pass
                elif str(verify_response) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                    loop = False
                    return await ctx.channel.send(_("Alright, I will not be clearing the queue."))
                else:
                    loop = True
            except asyncio.TimeoutError:
                loop = False
                return await ctx.send(_("{0} You've waited for too long, canceling the command.").format(self.bot.settings['emojis']['misc']['warn']))

        player.queue._queue.clear()
        await ctx.channel.send(_("{0} Successfully cleared {1} songs from the queue.").format(self.bot.settings['emojis']['misc']['white-mark'], tot_songs))

    @commands.command(aliases=['np', 'current'], name='now-playing')
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def now_playing(self, ctx):
        """ Retrieve currently playing song. """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        track = player.current
        if not track:
            return

        channel = self.bot.get_channel(int(player.channel_id))
        qsize = player.queue.qsize()

        embed = player.build_embed()

        await ctx.send(embed=embed)

    @commands.group(aliases=['setfilter'], name='filter', invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def _filter(self, ctx):
        """Change the players filter."""
        await ctx.send_help(ctx.command)

    @_filter.command(brief="Change the pitch of the song")
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def pitch(self, ctx, pitch: float):
        """ Set the players pitch."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if pitch < 0.1:
            return await ctx.send(_("The value you provided is invalid and will crash the player."))

        try:
            await player.set_filter(wavelink.Timescale(pitch=pitch, speed=player.filter.speed if hasattr(player.filter, 'speed') else 1.0))
        except Exception:
            raise commands.BadArgument(_("The value you provided can't be negative or above 2.0"))

        await ctx.send(_("{0} Changed the pitch to **{1}x**, give up to 10 seconds for player to take effect").format(self.bot.settings['emojis']['misc']['white-mark'], pitch))

    @_filter.command(brief="Change the speed of the song")
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def speed(self, ctx, speed: float):
        """ Set the players speed."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        if speed < 0.1:
            return await ctx.send(_("The value you provided is invalid and will crash the player."))

        try:
            await player.set_filter(wavelink.Timescale(speed=speed, pitch=player.filter.pitch if hasattr(player.filter, 'pitch') else 1.0))
        except Exception:
            raise commands.BadArgument(_("The value you provided can't be negative or above 2.0"))

        await ctx.send(_("{0} Changed the speed to **{1}x**, give up to 10 seconds for player to take effect").format(self.bot.settings['emojis']['misc']['white-mark'], speed))

    @_filter.command(brief="Reset the filter")
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def reset(self, ctx):
        """ Reset the players pitch and speed """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)

        await player.set_filter(wavelink.Timescale())

        await ctx.send(_("{0} Reset the players filter, give up to 10 seconds for player to take effect.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.command()
    @check_music(author_channel=True, bot_channel=True, same_channel=True, verify_permissions=True, is_playing=True, is_paused=False)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def loop(self, ctx):
        """ Switch the players loop """
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player, context=ctx)
        track = player.current

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

    @commands.command(hidden=True)
    @commands.is_owner()
    async def musicinfo(self, ctx):
        """Retrieve various Node/Server/Player information."""
        player = self.bot.wavelink.get_player(ctx.guild.id)
        node = player.node

        used = humanize.naturalsize(node.stats.memory_used)
        total = humanize.naturalsize(node.stats.memory_allocated)
        free = humanize.naturalsize(node.stats.memory_free)
        cpu = node.stats.cpu_cores

        fmt = f'**WaveLink:** `{wavelink.__version__}`\n\n' \
              f'Connected to `{len(self.bot.wavelink.nodes)}` nodes.\n' \
              f'Best available Node `{self.bot.wavelink.get_best_node().__repr__()}`\n' \
              f'`{len(self.bot.wavelink.players)}` players are distributed on nodes.\n' \
              f'`{node.stats.players}` players are distributed on server.\n' \
              f'`{node.stats.playing_players}` players are playing on server.\n\n' \
              f'Server Memory: `{used}/{total}` | `({free} free)`\n' \
              f'Server CPU: `{cpu}`\n\n' \
              f'Server Uptime: `{datetime.timedelta(milliseconds=node.stats.uptime)}`'
        await ctx.send(fmt)


def setup(bot):
    bot.add_cog(Music(bot))
