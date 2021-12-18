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
from utils import i18n, default, publicflags, paginator
from utils.enums import PlaylistEnum, SelfRoles, ReactionRolesComponentDisplay, ReactionRolesEmbed, ReactionRolesMessageType
from db.cache import ReactionRoles

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

        elif self.cls.__class__.__name__ == "Manage":
            await interaction.message.delete()
            if int(self.values[0]) == 2:
                return await interaction.response.send_message(_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
            return await self.cls.interactive_reaction_roles(self.ctx, self.values[0])

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
        self.reaction_roles = kwargs.get("current_setup", None)
        self.ctx = kwargs.get("ctx", None)

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
        self.stop()
        if self.reaction_roles:
            await interaction.message.delete()
            return await self.cls.perform_action(True, interaction, current_setup=self.reaction_roles, ctx=self.ctx)
        await self.cls.perform_action(True, interaction, command=self.from_command or None)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def button_no(self, button, interaction) -> None:
        i18n.current_locale.set(self.bot.translations.get(interaction.guild.id, 'en_US'))
        self.stop()
        if self.reaction_roles:
            await interaction.message.delete()
            return await self.cls.perform_action(False, interaction, current_setup=self.reaction_roles, ctx=self.ctx)
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
    def __init__(self, ctx, **kwargs):  # noqa
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


class ReactionRolesView(discord.ui.View):
    def __init__(self, cls, ctx, **kwargs):  # noqa
        self.cls = cls
        self.ctx = ctx

        self.author = ctx.author
        self.bot = ctx.bot

        super().__init__(timeout=kwargs.get("timeout", 120))

        self.add_item(Dropdown(ctx, kwargs.get("placeholder"), kwargs.get("options"), cls=cls))

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.author.id or await self.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        print(error)


class ReactionRolesConfirmComponents(discord.ui.View):
    def __init__(self, cls, ctx, timeout, current_setup):
        self.cls = cls
        self.ctx = ctx

        self.current_setup = current_setup

        super().__init__(timeout=timeout or 60)

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.ctx.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.ctx.author.id or await self.ctx.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        return

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        print(error)

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_setup["use_components"] = True
        self.stop()
        await interaction.message.delete()
        buttons = ReactionRolesComponentsStyle(self.cls, self.ctx, 60, self.current_setup)
        e = discord.Embed(title="Reaction Roles Setup", color=self.ctx.bot.settings['colors']['embed_color'])
        e.description = _("Should buttons display label only, emoji only or both? This action is irreversible!")
        e.image = self.ctx.bot.rr_image
        return await interaction.response.send_message(embed=e, view=buttons)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def deny(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_setup["use_components"] = False
        self.stop()
        await interaction.message.delete()
        return await self.cls.interactive_reaction_roles_2(self.ctx, self.current_setup)


class ReactionRolesComponentsStyle(discord.ui.View):
    def __init__(self, cls, ctx, timeout, current_setup):
        self.cls = cls
        self.ctx = ctx

        self.current_setup = current_setup

        super().__init__(timeout=timeout or 60)

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.ctx.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.ctx.author.id or await self.ctx.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        return

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        print(error)

    @discord.ui.button(label="Label only", style=discord.ButtonStyle.primary)
    async def labelonly(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_setup["components_style"] = ReactionRolesComponentDisplay.label_only
        self.stop()
        await interaction.message.delete()
        return await self.cls.interactive_reaction_roles_2(self.ctx, self.current_setup)

    @discord.ui.button(label="Emoji only", style=discord.ButtonStyle.primary)
    async def emojionly(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_setup["components_style"] = ReactionRolesComponentDisplay.emoji_only
        self.stop()
        await interaction.message.delete()
        return await self.cls.interactive_reaction_roles_2(self.ctx, self.current_setup)

    @discord.ui.button(label="Label & Emoji", style=discord.ButtonStyle.primary)
    async def useboth(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_setup["components_style"] = ReactionRolesComponentDisplay.all
        self.stop()
        await interaction.message.delete()
        return await self.cls.interactive_reaction_roles_2(self.ctx, self.current_setup)


class ReactionRolesEmbedDropdown(discord.ui.Select):
    def __init__(self, cls, ctx, current_setup):
        self.cls = cls
        self.ctx = ctx
        self.current_setup = current_setup

        options = [
            discord.SelectOption(label=_("Title of the embed."), description=_("Let's you change the title of the embed."), value=0),  # type: ignore
            discord.SelectOption(label=_("Description of the embed."), description=_("Let's you change the description of the embed."), value=1),  # type: ignore
            discord.SelectOption(label=_("Footer of the embed."), description=_("Let's you change the footer of the embed."), value=2),  # type: ignore
            discord.SelectOption(label=_("None of the above."), description=_("Let's you customize the whole embed, this requires you to send a whole payload."), value=3)  # type: ignore
        ]
        super().__init__(placeholder=_("Select an option..."), options=options, max_values=3)

    async def get_response(self, message, char_limit, validate_payload=False) -> Optional[Union[str, dict]]:

        try:
            def check(m):
                return m.author == self.ctx.author and m.channel.id == self.ctx.channel.id

            while True:
                value = await self.ctx.channel.send(message)
                get_value = await self.ctx.bot.wait_for('message', check=check, timeout=60.0)

                if get_value.content.lower() == "cancel":
                    break
                elif len(get_value.content) > char_limit:
                    await value.edit(content=_("You've hit the characters limit: {0}/{1}").format(len(get_value.content), char_limit))
                else:
                    if not validate_payload:
                        return get_value.content
                    try:
                        payload = json.loads(get_value.content)
                        return payload
                    except Exception:
                        await self.ctx.channel.send(_("{0} Your sent dict is invalid. Please "
                                                      "use <https://embedbuilder.nadekobot.me/> to create an embed dict, then paste the code here.").format(self.ctx.bot.settings['emojis']['misc']['warn']))
        except Exception:
            return None

    async def callback(self, interaction: discord.Interaction):
        # sourcery no-metrics
        await interaction.response.defer()
        await interaction.message.delete()

        title = description = footer = payload = None
        if str(int(ReactionRolesEmbed.custom)) in self.values:
            while True:
                payload = await self.get_response(_("What should the embed look like? Embed builder: <https://embedbuilder.nadekobot.me/>"), 6000, True)
                if not payload:
                    break
                try:
                    embed = await self.ctx.channel.send(embed=discord.Embed.from_dict(payload))
                    response = await self.get_response(_("This is how your embed will look like, are you ok with it? `y` or `n`"), 1)
                    if response.lower() != 'n':
                        self.current_setup["message_style"]["payload"] = payload
                        message, values = await self.cls.execute_message(self.ctx, current_setup=self.current_setup)
                        return await self.ctx.channel.send(_("{0} Successfully created reaction roles setup!").format(self.ctx.bot.settings['emojis']['misc']['white-mark']), delete_after=15)
                    elif response.lower() == 'cancel':
                        break
                    await embed.delete()
                    await self.ctx.channel.send(_("Okay, let's try again."), delete_after=5)
                except Exception as e:
                    await self.ctx.channel.send(_("It seems like the embed was not built correctly, let's retry that."), delete_after=5)

            return await self.ctx.channel.send(_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
        else:
            for value in self.values:
                if int(value) == int(ReactionRolesEmbed.title):
                    title = await self.get_response(_("What should the title of the embed be?"), 256)
                    if not title:
                        return await self.ctx.channel.send(_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                    self.current_setup["message_style"]["payload"]["title"] = title
                elif int(value) == int(ReactionRolesEmbed.description):
                    description = await self.get_response(_("What should the description of the embed be?"), 4000)
                    if not description:
                        return await self.ctx.channel.send(_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                    self.current_setup["message_style"]["payload"]["description"] = description
                elif int(value) == int(ReactionRolesEmbed.footer):
                    footer = await self.get_response(_("What should the footer of the embed be?"), 2048)
                    if not footer:
                        return await self.ctx.channel.send(_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                    self.current_setup["message_style"]["payload"]["footer"]["text"] = footer

            message, values = await self.cls.execute_message(self.ctx, current_setup=self.current_setup)
            return await self.ctx.channel.send(_("{0} Successfully created reaction roles setup!").format(self.ctx.bot.settings['emojis']['misc']['white-mark']), delete_after=15)


class ReactionRolesEmbedView(discord.ui.View):
    def __init__(self, cls, ctx, timeout, current_setup):
        self.cls = cls
        self.ctx = ctx

        self.current_setup = current_setup

        super().__init__(timeout=timeout or 60)

        self.add_item(ReactionRolesEmbedDropdown(cls, self.ctx, current_setup))

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.ctx.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.ctx.author.id or await self.ctx.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        return


class ReactionRolesMessage(discord.ui.View):
    def __init__(self, cls, ctx, timeout, current_setup):
        self.cls = cls
        self.ctx = ctx

        self.current_setup = current_setup

        super().__init__(timeout=timeout or 60)

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.ctx.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.ctx.author.id or await self.ctx.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        return

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        print(error)

    def setup_embed_payload(self, payload) -> dict:
        roles = []
        for value in payload["payload"]:
            for emoji in value:
                roles.append((emoji, value[emoji]))
        list_of_roles = [f"{emoji} - <@&{role}>\n" for emoji, role in roles]
        return {
            "title": "Reaction Roles",
            "description": f"Interact with the reactions below to get the corresponding role(s).\n{''.join(list_of_roles)}",
            "color": self.ctx.bot.settings['colors']['embed_color'],
            "footer": {
                "text": "Powered by Dredd"
            }
        }

    @discord.ui.button(label="Embedded", style=discord.ButtonStyle.primary)
    async def embedded(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_setup["message_style"]["type"] = ReactionRolesMessageType.embed
        self.current_setup["message_style"]["payload"] = self.setup_embed_payload(self.current_setup)
        self.stop()
        await interaction.message.delete()
        confirm_buttons = ConfirmationButtons(self.ctx.bot, self.cls, self.ctx.author, current_setup=self.current_setup, ctx=self.ctx)
        return await interaction.response.send_message(_("Would you like to customize the message?"), view=confirm_buttons)

    @discord.ui.button(label="Normal", style=discord.ButtonStyle.primary)
    async def normal(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.current_setup["message_style"]["type"] = ReactionRolesMessageType.normal
        self.current_setup["message_style"]["payload"] = self.setup_embed_payload(self.current_setup)["description"]
        self.stop()
        await interaction.message.delete()
        confirm_buttons = ConfirmationButtons(self.ctx.bot, self.cls, self.ctx.author, current_setup=self.current_setup, ctx=self.ctx)
        return await interaction.response.send_message(_("Would you like to customize the message?"), view=confirm_buttons)


async def selfroles_callback(interaction: discord.Interaction):
    data: ReactionRoles = interaction.message.rr
    if not data:
        return

    button_pressed = data.payload.get(interaction.data["custom_id"])  # type: ignore
    user = interaction.user
    author_roles = user._roles  # noqa

    if not author_roles.has(button_pressed):  # type: ignore
        if data.required_role and not author_roles.has(data.required_role) and interaction.guild.get_role(data.required_role):
            role = interaction.guild.get_role(data.required_role)
            return await interaction.response.send_message(_("You must have {role.mention} role in order to access this reaction roles setup.").format(role=role), ephemeral=True)

        if data.max_roles != len(data.payload):
            total_roles = int(sum(1 for role_id in data.payload.values() if author_roles.has(role_id)))
            if total_roles >= data.max_roles:
                return await interaction.response.send_message(_("This reaction roles setup is configured to give a total of {total_available} roles, which you already have.").format(total_available=data.max_roles),
                                                               ephemeral=True)

        role = interaction.guild.get_role(button_pressed)  # type: ignore
        if role:
            await interaction.user.add_roles(role)
            return await interaction.response.send_message(_("Successfully added {role.mention} to your roles!").format(role=role), ephemeral=True)
    elif author_roles.has(button_pressed):  # type: ignore
        role = interaction.guild.get_role(button_pressed)  # type: ignore
        if role:
            await interaction.user.remove_roles(role)
            return await interaction.response.send_message(_("Successfully removed {role.mention} from your roles!").format(role=role), ephemeral=True)

    return await interaction.response.send_message(_("That role doesn't seem to exist anymore!"), ephemeral=True)


def create_self_roles(guild: Optional[discord.Guild] = None, button_display: Optional[ReactionRolesComponentDisplay] = None, roles: Optional[Union[List[SelfRoles], Any]] = None):
    # not the best way, but it works
    selfrole = {}

    class View(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

            if not roles:
                for num, time in enumerate(range(25), start=1):
                    custom_id = f"dredd_selfrole:role_{num}"
                    button = discord.ui.Button(style=discord.ButtonStyle.primary, label='ok', custom_id=custom_id)
                    button.callback = selfroles_callback

                    self.add_item(button)
            else:
                for item in roles:
                    for num, reaction in enumerate(item, start=1):
                        if reaction.__contains__("dredd_selfrole"):  # don't mess up already existing ones
                            selfrole[reaction] = item[reaction]  # type: ignore
                            continue
                        label: discord.Role = guild.get_role(item[reaction])  # type: ignore
                        emoji: Optional[Union[discord.Emoji, discord.PartialEmoji]] = reaction if button_display != button_display.label_only else None  # type: ignore
                        custom_id = f"dredd_selfrole:role_{num}"
                        selfrole[custom_id] = label.id if label else None

                        button = discord.ui.Button(style=discord.ButtonStyle.primary,
                                                   label=label.name if button_display != button_display.emoji_only else None,
                                                   emoji=emoji if emoji else None,
                                                   custom_id=custom_id)
                        button.callback = selfroles_callback

                        self.add_item(button)

    return View(), selfrole


class AutomodTimeSelect(discord.ui.Select):
    def __init__(self, ctx, options):
        self.ctx = ctx

        super().__init__(placeholder=_("Select an option..."), options=options, max_values=len(options))

    async def callback(self, interaction: discord.Interaction):
        self.view.children[0].disabled = True  # type: ignore
        await interaction.message.edit(view=self.view)
        duration = self.ctx.bot.automod_time[(interaction.user.id, interaction.channel.id)]["time"]
        guild_id = interaction.guild.id
        for value in self.values:
            if int(value) == 1:
                await self.ctx.bot.db.execute("UPDATE antispam SET time = $1 WHERE guild_id = $2", duration, guild_id)
                self.ctx.bot.spam[guild_id]["time"] = duration
            elif int(value) == 2:
                await self.ctx.bot.db.execute("UPDATE masscaps SET time = $1 WHERE guild_id = $2", duration, guild_id)
                self.ctx.bot.masscaps[guild_id]["time"] = duration
            elif int(value) == 3:
                await self.ctx.bot.db.execute("UPDATE invites SET time = $1 WHERE guild_id = $2", duration, guild_id)
                self.ctx.bot.invites[guild_id]["time"] = duration
            elif int(value) == 4:
                await self.ctx.bot.db.execute("UPDATE massmention SET time = $1 WHERE guild_id = $2", duration, guild_id)
                self.ctx.bot.massmention[guild_id]["time"] = duration
            elif int(value) == 5:
                await self.ctx.bot.db.execute("UPDATE links SET time = $1 WHERE guild_id = $2", duration, guild_id)
                self.ctx.bot.links[guild_id]["time"] = duration

        return await interaction.response.send_message(_("{0} Successfully set the duration to {duration}.").format(self.ctx.bot.settings['emojis']['misc']['white-mark'], duration=duration))


class AutomodTimeView(discord.ui.View):
    def __init__(self, ctx, options):
        self.ctx = ctx

        super().__init__()

        self.add_item(AutomodTimeSelect(ctx, options))

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.ctx.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.ctx.author.id or await self.ctx.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        return


class AutomodTime(discord.ui.View):
    def __init__(self, ctx, options):
        self.ctx = ctx
        self.options = options

        super().__init__()

    async def interaction_check(self, interaction):
        i18n.current_locale.set(self.ctx.bot.translations.get(interaction.guild.id, 'en_US'))
        if interaction.user and interaction.user.id == self.ctx.author.id or await self.ctx.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        return

    async def send_message(self, interaction: discord.Interaction, time: str):
        view = AutomodTimeView(self.ctx, self.options)
        await interaction.response.send_message(_("What actions should temporary mute or ban member for {time}?").format(time=time), view=view)
        await interaction.message.delete()

    @discord.ui.button(label="12 Hours", style=discord.ButtonStyle.primary)
    async def twelf_hours(self, button: discord.Button, interaction: discord.Interaction):
        self.ctx.bot.automod_time[(self.ctx.author.id, self.ctx.channel.id)]["time"] = "12h"
        self.stop()
        await self.send_message(interaction, "12h")

    @discord.ui.button(label="24 Hours", style=discord.ButtonStyle.primary)
    async def tf_hours(self, button: discord.Button, interaction: discord.Interaction):
        self.ctx.bot.automod_time[(self.ctx.author.id, self.ctx.channel.id)]["time"] = "24h"
        self.stop()
        await self.send_message(interaction, "24h")

    @discord.ui.button(label="48 Hours", style=discord.ButtonStyle.primary)
    async def fe_hours(self, button: discord.Button, interaction: discord.Interaction):
        self.ctx.bot.automod_time[(self.ctx.author.id, self.ctx.channel.id)]["time"] = "48h"
        self.stop()
        await self.send_message(interaction, "48h")

    @discord.ui.button(label="7 Days", style=discord.ButtonStyle.primary)
    async def sd_hours(self, button: discord.Button, interaction: discord.Interaction):
        self.ctx.bot.automod_time[(self.ctx.author.id, self.ctx.channel.id)]["time"] = "7d"
        self.stop()
        await self.send_message(interaction, "7d")

    @discord.ui.button(label="30 Days", style=discord.ButtonStyle.primary)
    async def t_hours(self, button: discord.Button, interaction: discord.Interaction):
        self.ctx.bot.automod_time[(self.ctx.author.id, self.ctx.channel.id)]["time"] = "30d"
        self.stop()
        await self.send_message(interaction, "30d")
