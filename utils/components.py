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
import datetime
import re
import wavelink
import json
import spotify as spotify_client

from typing import List, Any, Union, Optional
from contextlib import suppress
from utils import i18n, default, publicflags, logger as logging, paginator
from utils.enums import PlaylistEnum

RURL = re.compile(r'https?://(?:www\.)?.+')
SPOTIFY_RURL = re.compile(r'https?://open.spotify.com/(?P<type>album|playlist|track)/(?P<id>[a-zA-Z0-9]+)')


# noinspection PyProtectedMember,PyUnboundLocalVariable,PyUnusedLocal
class Dropdown(discord.ui.Select):
    def __init__(self, ctx, placeholder: str, options: List[Any], max_values: int = 1, cls=None, **kwargs):

        if len(options) > 25:
            raise ValueError("Dropdowns can only have 25 options!")

        options = options
        self.ctx = ctx
        self.cls = cls
        self.kwargs = kwargs

        super().__init__(placeholder=placeholder, max_values=max_values, options=options)

    async def select_song(self, track, interaction):
        player = self.ctx.guild.voice_client
        if not player:
            return await interaction.message.edit(content=_("Seems like I was disconnected from the channel in the process."), view=None)
        track = self.ctx.bot.wavelink_track(track.id, track.info, requester=self.ctx.author)
        await interaction.message.edit(content=_('{0} Added **{1}** to the Queue! (`{2}`)').format('🎶', track.title, str(datetime.timedelta(seconds=int(track.length)))), delete_after=15, view=None)
        await player.queue.put(track)
        self.cls._last_command_channel[self.ctx.guild.id] = self.ctx.channel.id
        if not player.is_playing():
            await player.do_next()

    async def select_type(self, interaction: discord.Interaction):
        thing = self.kwargs.get("thing", None)
        reason = self.kwargs.get("reason")
        if not reason:
            return await interaction.message.edit("You must provide the reason!", view=None)  # type: ignore
        if isinstance(thing, discord.Guild):
            dropdown = DropdownView(self.ctx, "Select type...", [
                discord.SelectOption(label="Suggestions", value=0),  # type: ignore
                discord.SelectOption(label="Guild", value=3),  # type: ignore
                discord.SelectOption(label="Cancel", value=4)  # type: ignore
            ], cls=self.cls, thing=thing, reason=reason, timeout=30)
        elif isinstance(thing, discord.User):
            dropdown = DropdownView(self.ctx, "Select type...", [
                discord.SelectOption(label="Direct Messages", value=1),  # type: ignore
                discord.SelectOption(label="User", value=2),  # type: ignore
                discord.SelectOption(label="Cancel", value=4)  # type: ignore
            ], cls=self.cls, thing=thing, reason=reason, timeout=30)

        await interaction.message.edit(view=dropdown)

    async def perform_action(self, liftable: bool, interaction: discord.Interaction, **kwargs):
        liftable = 0 if liftable else 1
        await interaction.message.delete()
        return await self.cls.blacklist_(self.ctx, thing=self.kwargs.get("thing"), type=self.kwargs.get("type"), liftable=liftable,
                                         reason=self.kwargs.get("reason"))

    async def select_rank(self, interaction: discord.Interaction, instance: Union[discord.User, discord.Guild], append_badge: bool = True):
        badge_values = default.badge_values()
        current_badges = publicflags.BotFlags(instance.data.badges or 0)  # type: ignore
        ranks = self.ctx.bot.settings['emojis']['ranks']
        if append_badge:
            if isinstance(instance, discord.Guild):
                ranks = {
                    "bot_admin": '<:staff:706190137058525235>',
                    "server_partner": '<:p_s:848573752002347029>',
                    "verified": '<:v5:848573780090814484>',
                    "duck": '🦆'
                }
            options = [discord.SelectOption(
                label=rank.replace('_', ' ').title(), emoji=ranks[rank], value=badge_values[rank]
            ) for rank in ranks.keys() if rank not in current_badges]
        else:
            the_ranks = {rank: ranks[rank] for rank in ranks if rank in current_badges}
            options = [discord.SelectOption(
                label=rank.replace('_', ' ').title(), emoji=ranks[rank], value=badge_values[rank]
            ) for rank in the_ranks]
        options.append(discord.SelectOption(label="Cancel", value=-2, description="Cancel the dropdown."))  # type: ignore

        dropdown = DropdownView(self.ctx, "Select a badge", options, cls=self, thing=self.kwargs.get("thing"), add_badges=append_badge)
        return await interaction.message.edit(view=dropdown)

    async def callback(self, interaction: discord.Interaction):  # sourcery no-metrics

        if self.cls.__class__.__name__ == 'HelpCommand':
            if self.values[0].lower() != "stop":
                return await self.ctx.send_help(self.ctx.bot.get_cog(self.values[0]))
            return await self.cls.delete_original()

        elif self.cls.__class__.__name__ == 'ListPages':
            return await self.cls.checked_show_page(int(self.values[0]))

        elif self.cls.__class__.__name__ == 'Music':
            songs = self.kwargs.get("track_objects")[0]
            assert self.values[0].isdigit()
            return await self.select_song(songs[int(self.values[0]) - 1], interaction)

        elif self.cls.__class__.__name__ == 'staff':
            if int(self.values[0]) == 10:  # blacklist
                if isinstance(self.kwargs.get("thing"), int):
                    return await interaction.message.edit(content="Can't blacklist that!", view=None)
                return await self.select_type(interaction)
            elif int(self.values[0]) == 11:  # unblacklist
                if not self.kwargs.get("reason"):
                    return await interaction.message.edit("You must provide the reason!", view=None)  # type: ignore
                return await self.cls.unblacklist_(self.ctx, self.kwargs.get("thing"), self.kwargs.get("reason"))
            elif int(self.values[0]) == 12:
                return await self.select_rank(interaction, self.kwargs.get("thing"))
            elif int(self.values[0]) == 13:
                return await self.select_rank(interaction, self.kwargs.get("thing"), False)
            elif int(self.values[0]) == 4:  # Cancel command
                return await interaction.message.edit(content="Cancelled command.", view=None)
            elif int(self.values[0]) in range(4):  # blacklist
                self.kwargs["type"] = int(self.values[0])
                buttons = ConfirmationButtons(self.ctx.bot, self, self.ctx.author)
                return await interaction.message.edit("Blacklist is liftable?", view=buttons)  # type: ignore

        elif self.cls.__class__.__name__ == 'Dropdown':
            if int(self.values[0]) == -2:
                return await interaction.message.delete()
            add_badges = self.kwargs.get("add_badges")
            badge_value = publicflags.BotFlags(int(self.values[0]))
            badge = self.ctx.bot.settings['emojis']['ranks'][list(badge_value)[0]]
            instance: Union[discord.User, discord.Guild] = self.kwargs.get("thing")
            if add_badges:
                current_badges = publicflags.BotFlags(instance.data.badges or 0)  # type: ignore
                if list(badge_value)[0] in current_badges:
                    return await interaction.response.send_message(f"User already has {badge}", ephemeral=True)
                if current_badges.value != 0:
                    query = "UPDATE badges SET flags = flags + $1 WHERE _id = $2"
                    self.ctx.bot.badges[instance.id] += int(self.values[0])
                else:
                    query = "INSERT INTO badges VALUES($1, $2)"
                    self.ctx.bot.badges[instance.id] = int(self.values[0])
                await self.ctx.bot.db.execute(query, int(self.values[0]), instance.id)
                return await interaction.response.send_message(f"Added {badge} to {instance}", ephemeral=True)
            else:
                await self.ctx.bot.db.execute("UPDATE badges SET flags = flags - $1 WHERE _id = $2", int(self.values[0]), instance.id)
                self.ctx.bot.badges[instance.id] -= int(self.values[0])
                if self.ctx.bot.badges[instance.id] == 0:
                    await self.ctx.bot.db.execute("DELETE FROM badges WHERE _id = $1", instance.id)
                return await interaction.message.edit(f"Removed {badge} from {instance} badges", view=None)  # type: ignore

        return await interaction.response.send_message(f"You chose {self.values[0]}\n**Interaction data:** {interaction.data}\n**Class belongs:** {self.cls}\n**Kwargs** {self.kwargs}", ephemeral=True)


class DropdownView(discord.ui.View):
    def __init__(self, ctx, placeholder: str, options: List[Any], max_values: int = 1, cls=None, **kwargs):
        super().__init__(timeout=kwargs.get("timeout", 300))  # defaults at 5 minutes

        self.cls = cls
        self.ctx = ctx

        self.add_item(Dropdown(ctx=ctx,
                               placeholder=placeholder,
                               options=options,
                               max_values=max_values,
                               cls=cls,
                               **kwargs))

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.ctx.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.ctx.author.id or await self.ctx.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        i18n.current_locale.set(self.ctx.bot.translations.get(interaction.guild.id, 'en_US'))
        print(default.traceback_maker(error))
        await interaction.message.edit(view=None)
        if isinstance(error, AssertionError):
            if error.args:
                await self.ctx.send(f"{self.ctx.bot.settings['emojis']['misc']['warn']} | {error}")
            return
        if interaction.response.is_done():
            await interaction.followup.send(_('An unknown error occurred, sorry'), ephemeral=True)
        else:
            await interaction.response.send_message(_('An unknown error occurred, sorry'), ephemeral=True)

    async def on_timeout(self) -> None:
        self.clear_items()
        with suppress(Exception):
            await self.cls.message.edit(view=self)


# noinspection PyUnusedLocal
class ConfirmationButtons(discord.ui.View):
    def __init__(self, bot, cls, author, **kwargs):
        super().__init__(timeout=kwargs.get("timeout", 120))  # defaults at 2 minutes

        self.bot = bot
        self.cls = cls
        self.author = author
        self.from_command = kwargs.get("command", None)

        self.kwargs = kwargs

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.author.id or await self.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        return

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        i18n.current_locale.set(self.bot.translations.get(interaction.guild.id, 'en_US'))
        print(default.traceback_maker(error))
        await interaction.message.edit(view=None)
        if interaction.response.is_done():
            await interaction.followup.send(_('An unknown error occurred, sorry'), ephemeral=True)
        else:
            await interaction.response.send_message(_('An unknown error occurred, sorry'), ephemeral=True)

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def button_yes(self, button, interaction) -> None:
        i18n.current_locale.set(self.bot.translations.get(interaction.guild.id, 'en_US'))
        await self.cls.perform_action(True, interaction, command=self.from_command or None)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def button_no(self, button, interaction) -> None:
        i18n.current_locale.set(self.bot.translations.get(interaction.guild.id, 'en_US'))
        await self.cls.perform_action(False, interaction, command=self.from_command or None)


class Playlist(discord.ui.Select):
    def __init__(self, ctx, bot, author, **kwargs):
        self.ctx = ctx
        self.bot = bot
        self.author = author
        self.playlist_name = kwargs.get("playlist_name", None)
        self.user = kwargs.get("user", None)

        super().__init__(placeholder=_("Select an option..."), max_values=kwargs.get("max_values"), options=kwargs.get("options"))

    async def await_response(self, interaction: discord.Interaction, respond: str, action: PlaylistEnum) -> Optional[Union[discord.Message, str, int]]:  # sourcery no-metrics
        try:
            await interaction.message.edit(view=None)
            msg = await interaction.followup.send(respond)
            while True:
                message = await self.bot.wait_for("message", check=lambda m: m.channel.id == interaction.channel.id and m.author.id == interaction.user.id, timeout=60)

                if message.content == "cancel":
                    await msg.delete()
                    return await interaction.message.edit(content=_("Cancelled command."), view=None)

                if len(message.content) > 32 and not RURL.match(message.content) and int(action) in [0, 3, 4]:
                    await interaction.followup.send(_("The message should be under 32 characters. Make sure you're not messing anything up!"), ephemeral=True)
                elif RURL.match(message.content) and int(action) == 2 and not SPOTIFY_RURL.match(message.content):
                    await msg.delete()
                    return message.content.strip('<>')
                elif SPOTIFY_RURL.match(message.content) and int(action) == 2:
                    search_id, search_type = await self.verify_spotify(message, msg)
                    return await default.spotify_support(self.ctx, spotify=spotify_client, search_type=search_type, spotify_id=search_id, Track=self.bot.wavelink_track, queue=False)
                elif RURL.match(message.content) and int(action) in [0, 3, 4]:
                    await interaction.followup.send(_("You cannot provide a link, try again without a link."), ephemeral=True)
                elif not RURL.match(message.content) and int(action) == 2:
                    await interaction.followup.send(_("You can only provide links to song(s), try again with a link."), ephemeral=True)
                else:
                    await msg.delete()
                    return message.content
        except (discord.HTTPException, discord.Forbidden, discord.NotFound):
            pass
        except Exception as e:
            print(e)
            return await interaction.message.edit(content=_("The command has expired."), view=None)

    @staticmethod
    async def verify_spotify(message, msg):
        await msg.delete()
        url_check = SPOTIFY_RURL.match(message.content)
        search_type = url_check.group('type')
        search_id = url_check.group('id')
        return search_id, search_type

    @staticmethod
    def chop_microseconds(delta):
        return delta - datetime.timedelta(microseconds=delta.microseconds)

    async def callback(self, interaction: discord.Interaction):  # sourcery no-metrics
        value = PlaylistEnum(int(self.values[0]))

        if int(value) == -1:
            return await interaction.message.edit(content=_("{0} Interaction returned an unknown value, please report this to the developer(s) here: {support}").format(
                self.bot.settings['emojis']['misc']['warn'], self.bot.support
            ), view=None)
        elif int(value) == 0:
            count = await self.bot.db.fetchval("SELECT count(playlist_name) FROM playlist WHERE user_id = $1", interaction.user.id)
            if count > 15:
                return await interaction.message.edit(content=_("{0} You can only have up to 15 playlists.").format(self.bot.settings['emojis']['misc']['warn']), view=None)
            await interaction.response.defer()
            message = await self.await_response(interaction, _("Provide the playlist name you want to use. The playlist name can be up to 32 characters."), value)
            double = await self.bot.db.fetchval("SELECT * FROM playlist WHERE user_id = $1 AND playlist_name = $2", interaction.user.id, message)
            if not double:
                await self.bot.db.execute("INSERT INTO playlist(user_id, playlist_name) VALUES($1, $2)", interaction.user.id, message)
                return await interaction.message.edit(content=_("{0} Successfully created a playlist **{1}**").format(
                    self.bot.settings['emojis']['misc']['white-mark'], message
                ), view=None)
            return await interaction.message.edit(content=_("{0} You already have a playlist named **{1}**").format(
                self.bot.settings['emojis']['misc']['warn'], message
            ), view=None)
        elif int(value) == 1:
            await interaction.response.defer()
            double = await self.bot.db.fetchval("SELECT * FROM playlist WHERE user_id = $1 AND playlist_name = $2", interaction.user.id, self.playlist_name)
            if double:
                await self.bot.db.execute("DELETE FROM playlist WHERE user_id = $1 AND playlist_name = $2", interaction.user.id, self.playlist_name)
                return await interaction.message.edit(content=_("{0} Successfully deleted a playlist **{1}**").format(
                    self.bot.settings['emojis']['misc']['white-mark'], self.playlist_name
                ), view=None)
            return await interaction.message.edit(content=_("{0} You don't have a playlist named **{1}**").format(
                self.bot.settings['emojis']['misc']['warn'], self.playlist_name
            ), view=None)
        elif int(value) == 2:
            db_check = await self.bot.db.fetch("SELECT playlist_name, playlist FROM playlist WHERE user_id = $1 AND playlist_name = $2", interaction.user.id, self.playlist_name)
            if not db_check:
                return await interaction.message.edit(content=_("{0} You don't have a playlist named **{1}**").format(
                    self.bot.settings['emojis']['misc']['warn'], self.playlist_name
                ), view=None)
            if db_check[0]["playlist"] is not None and len(db_check[0]["playlist"]) > 1000:
                return await interaction.message.edit(content=_("{0} Your playlist already has over 1000 songs, I cannot let you add more.").format(self.bot.settings['emojis']['misc']['warn']), view=None)
            await interaction.response.defer()
            message = await self.await_response(interaction, _("Provide the URL of the song(s) you want to add the playlist."), value)
            if not self.bot.wavelink.is_connected():
                return await interaction.message.edit(content=_("No music nodes are currently active, please try again later."), view=None)
            query = "UPDATE playlist SET playlist = playlist || array[$1]::json[] WHERE playlist_name = $2 AND user_id = $3"
            total_songs = 0
            if isinstance(message, list):
                for track in message:
                    total_songs += 1
                    await self.bot.db.execute(query, json.dumps({"track": track.id, "info": track.info}), self.playlist_name, interaction.user.id)  # type: ignore
                return await interaction.followup.send(_("{0} Added **{1}** songs to the playlist.").format(
                    self.bot.settings['emojis']['misc']['white-mark'], total_songs
                ))
            tracks = await self.bot.wavelink.get_tracks(query=message)
            if not tracks:
                return await interaction.followup.send(content=_('No songs were found with that query. Please try again.'), ephemeral=True)
            if not isinstance(tracks, wavelink.abc.Playlist):
                await self.bot.db.execute(query, json.dumps({"track": tracks[0].id, "info": tracks[0].info}), self.playlist_name, interaction.user.id)
                return await interaction.followup.send(_("{0} Added **{1}** to the playlist.").format(
                    self.bot.settings['emojis']['misc']['white-mark'], tracks[0].info["title"]
                ))

            for track in tracks.data["tracks"]:  # type: ignore
                track = json.dumps(track)
                await self.bot.db.execute(query, track, self.playlist_name, interaction.user.id)
                total_songs += 1
            return await interaction.followup.send(_("{0} Added **{1}** songs to the playlist.").format(
                self.bot.settings['emojis']['misc']['white-mark'], total_songs
            ))
        elif int(value) == 3:
            db_check = await self.bot.db.fetch("SELECT playlist_name, playlist FROM playlist WHERE user_id = $1 AND playlist_name = $2", interaction.user.id, self.playlist_name)
            if not db_check:
                return await interaction.message.edit(content=_("{0} You don't have a playlist named **{1}**").format(
                    self.bot.settings['emojis']['misc']['warn'], self.playlist_name
                ), view=None)
            await interaction.response.defer()
            message = await self.await_response(interaction, _("Provide the number of the song you want to delete from the playlist."), value)
            item = None
            with suppress(Exception):
                if message.isdigit():
                    item = json.loads(db_check[0]["playlist"][int(message) - 1])
                    del db_check[0]["playlist"][int(message) - 1]
            if not item:
                return await interaction.followup.send(_("{0} The song was not found, please make sure you provide a number of the song.").format(self.bot.settings['emojis']['misc']['warn']))
            await self.bot.db.execute("UPDATE playlist SET playlist = $1::json[] WHERE user_id = $2 AND playlist_name = $3", db_check[0]["playlist"], interaction.user.id, self.playlist_name)
            return await interaction.followup.send(_("{0} Successfully removed **{1}** from your playlist - {2}").format(
                self.bot.settings['emojis']['misc']['white-mark'], item["info"]["title"], self.playlist_name
            ))
        elif int(value) == 4:
            playlist_exists = await self.bot.db.fetchval("SELECT playlist_name FROM playlist WHERE user_id = $1 AND playlist_name = $2", interaction.user.id, self.playlist_name)
            if not playlist_exists:
                return await interaction.message.edit(content=_("{0} You don't have a playlist named **{1}**").format(
                    self.bot.settings['emojis']['misc']['warn'], self.playlist_name
                ), view=None)
            await interaction.response.defer()
            message = await self.await_response(interaction, _("Provide the new playlist name you want to use. The playlist name can be up to 32 characters."), value)
            await self.bot.db.execute("UPDATE playlist SET playlist_name = $1 WHERE user_id = $2 AND playlist_name = $3", message, interaction.user.id, self.playlist_name)
            return await interaction.followup.send(_("{0} Renamed playlist **{1}** to **{2}**").format(
                self.bot.settings['emojis']['misc']['white-mark'], self.playlist_name, message
            ), ephemeral=True)
        elif int(value) == 5:
            playlist_exists = await self.bot.db.fetch("SELECT playlist_name, playlist FROM playlist WHERE user_id = $1 AND playlist_name = $2", interaction.user.id, self.playlist_name)
            if not playlist_exists:
                return await interaction.message.edit(content=_("{0} You don't have a playlist named **{1}**").format(
                    self.bot.settings['emojis']['misc']['warn'], self.playlist_name
                ), view=None)
            if not playlist_exists[0]["playlist"]:
                return await interaction.message.edit(content=_("{0} This playlist has no songs.").format(self.bot.settings['emojis']['misc']['warn']))

            total_duration, count, tracks = 0, 0, []
            for num, track in enumerate(playlist_exists[0]["playlist"], start=1):
                track = json.loads(track)
                total_duration += track["info"]["length"]
                count += 1
                tracks.append(f"`{num}` [{track['info']['title']}]({track['info']['uri']}) `({self.chop_microseconds(datetime.timedelta(milliseconds=int(track['info']['length'])))})`\n")

            if total_duration != 0:
                length = str(self.chop_microseconds(datetime.timedelta(milliseconds=int(total_duration))))
                footer = _("Total songs in the queue: {0} | Duration: {1}").format(count, length)
            else:
                footer = _("Total songs in the queue: {0}").format(count)
            pages = paginator.Pages(self.ctx,
                                    entries=tracks,
                                    title=_("Playlist: {0}").format(self.playlist_name),
                                    footertext=footer)

            await pages.paginate()

        elif int(value) == 6:
            return await interaction.message.edit(content=_("Canceled command."), view=None)


class PlaylistView(discord.ui.View):
    def __init__(self, ctx, **kwargs):
        super().__init__(timeout=kwargs.get("timeout", 120))  # defaults at 2 minutes

        self.ctx = ctx
        self.bot = ctx.bot
        self.author = ctx.author

        self.add_item(Playlist(ctx=self.ctx,
                               bot=ctx.bot,
                               author=ctx.author,
                               **kwargs))

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.author.id or await self.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        i18n.current_locale.set(self.bot.translations.get(interaction.guild.id, 'en_US'))
        print(default.traceback_maker(error))
        await interaction.message.edit(view=None)
        if isinstance(error, AssertionError):
            if error.args:
                await self.ctx.send(f"{self.ctx.bot.settings['emojis']['misc']['warn']} | {error}")
            return
        if interaction.response.is_done():
            await interaction.followup.send(_('An unknown error occurred, sorry'), ephemeral=True)
        else:
            await interaction.response.send_message(_('An unknown error occurred, sorry'), ephemeral=True)
