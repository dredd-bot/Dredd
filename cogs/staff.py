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
import json

from discord.ext import commands

from utils import checks, default, components
from db.cache import CacheManager as CM, DreddUser, DreddGuild, Blacklist, BlacklistEnum
from datetime import datetime, timezone
from utils.checks import admin_only
from typing import Union, Optional, Literal


class staff(commands.Cog, name="Staff", command_attrs={"slash_command": False}):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:staff:706190137058525235>"
        self.big_icon = "https://cdn.discordapp.com/emojis/706190137058525235.png?v=1"
        self._last_result = None

    async def cog_check(self, ctx: commands.Context):
        if not await ctx.bot.is_admin(ctx.author):
            raise admin_only()
        return True

    async def verify_type(self, ctx, thing: Union[discord.User, discord.Guild, int]) -> Union[discord.User, discord.Guild, int]:
        if isinstance(thing, discord.User) or isinstance(thing, discord.Guild):
            return thing
        elif isinstance(thing, int):
            try:
                return await ctx.bot.fetch_user(thing)
            except Exception:
                g = self.bot.get_guild(thing)
                return g or thing 
        else:
            return thing

    def embed(self, color: int, blacklist: bool, type: int, liftable: int, reason: str, user: discord.User, guild: Optional[Union[discord.Guild, str]] = None) -> Optional[discord.Embed]:
        if type in {0, 1}:
            return None
        e = discord.Embed(color=color, title='Blacklist state updated!', timestamp=datetime.now(timezone.utc))
        if not user:  # server doesn't have an owner
            return
        e.set_author(name=user, icon_url=user.avatar.url if user.avatar else user.display_avatar.url)

        if blacklist:
            bslash = '\n\n'
            apply = f"{f'{bslash}If you wish to appeal, you can [join the support server]({self.bot.support})' if liftable == 0 else ''}"
            if type == 2:
                e.description = f"Hey!\nI'm sorry, but your blacklist state was updated and you won't be able to use my commands anymore!\n**Reason:** {reason}{apply}"
            elif type == 3:
                e.description = f"I'm sorry, but your server's ({guild.name}) blacklist state was updated and you won't be able to invite me to that server\n**Reason:** {reason}{apply}"
        elif type == 2:
            e.description = f"Hey!\nJust wanted to let you know that your blacklist state was updated and you'll be able to use my commands again!\n**Reason:** {reason}"
        elif type == 3:
            e.description = f"Hey!\nJust wanted to let you know that your server ({guild}) is now unblacklisted and you'll be able to invite me there!\n**Reason:** {reason}"

        return e

    async def blacklist_(self, ctx, thing: Union[discord.User, discord.Guild], type: Literal[0, 1, 2, 3], liftable: Literal[0, 1], reason: str):
        # sourcery no-metrics
        data: Union[DreddGuild, DreddUser] = thing.data  # type: ignore
        blacklist: Blacklist = data.blacklist
        owner_id = guild_name = guild = msg = None
        if isinstance(thing, discord.Guild):
            owner_id = thing.owner, thing.owner.id
            guild, guild_name = thing, thing.name
        if blacklist and int(blacklist.type) in [type, 2, 3]:
            return await ctx.send(f"Seems like **{thing}** is already blacklisted. Type: {BlacklistEnum(int(blacklist.type))}")
        if await self.bot.is_admin(thing) and not await self.bot.is_owner(ctx.author) or thing.id == 345457928972533773:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | You cannot blacklist {thing} because they're a part of bot staff team.")
        query = """INSERT INTO blacklist(_id, type, reason, dev, issued, liftable, owner_id, server_name) VALUES($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (_id) DO UPDATE SET type = $2, reason = $3 WHERE blacklist._id = $1"""
        await self.bot.db.execute(query, thing.id, type, reason, ctx.author.id, datetime.now(), liftable, owner_id, guild_name)
        self.bot.blacklist[thing.id] = {'type': type, 'reason': reason, 'dev': ctx.author.id, 'issued': datetime.now(), 'liftable': liftable, 'owner_id': owner_id, 'server_name': guild_name}
        await self.bot.db.execute("INSERT INTO badges(_id, flags) VALUES($1, $2)", thing.id, 2048)
        self.bot.badges[thing.id] = 2048
        await self.bot.db.execute("INSERT INTO bot_history(_id, action, dev, reason, issued, type, liftable) VALUES($1, $2, $3, $4, $5, $6, $7)", thing.id, 1, ctx.author.id, reason, datetime.now(), type, liftable)
        user = thing if isinstance(thing, discord.User) else thing.owner
        embed_to_send = self.embed(self.bot.settings['colors']['deny_color'], True, type, liftable, reason, user, thing if isinstance(thing, discord.Guild) else None)
        if embed_to_send is not None:
            try:
                await user.send(embed=embed_to_send)
                msg = ' and DMed the user'
            except Exception as e:
                print(e)
                msg = ', however, I was unable to DM the user.'
        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | I've successfully added **{thing}** to the blacklist{msg or ''}")
        if guild and type == 3:
            await guild.leave()
        return await default.blacklist_log(ctx, 0, 0 if type in [2, 3] else 1 if type == 0 else 2, thing, reason)

    async def unblacklist_(self, ctx, thing: Union[discord.User, discord.Guild, int], reason: str):
        msg = None
        data: Union[DreddGuild, DreddUser] = thing.data if isinstance(thing, (discord.User, discord.Guild)) else CM.get_guild(self.bot, thing)  # type: ignore
        blacklist: Blacklist = data.blacklist
        liftable = int(blacklist.liftable) if blacklist else None
        type = int(blacklist.type) if blacklist else None
        owner = thing.owner if isinstance(thing, discord.Guild) else thing if isinstance(thing, discord.User) else self.bot.get_user(blacklist.owner_id)
        guild_name = blacklist.server if blacklist else None

        if not blacklist:
            return await ctx.send(f"{thing} doesn't seem to be blacklisted.")
        if not liftable and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | This user cannot be unblacklisted!")

        await self.bot.db.execute("DELETE FROM blacklist WHERE _id = $1", data.id)
        self.bot.blacklist.pop(data.id)
        await self.bot.db.execute("DELETE FROM badges WHERE _id = $1", data.id)
        self.bot.badges.pop(data.id, None)
        embed_to_send = self.embed(self.bot.settings['colors']['approve_color'], False, type, 0, reason, owner, guild_name if isinstance(thing, int) else None)
        if embed_to_send:
            try:
                await owner.send(embed=embed_to_send)
                msg = ' and DMed the user'
            except Exception as e:
                print(e)
                msg = ', however, I was unable to DM the user.'
        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | I've successfully removed **{guild_name or thing}** from the blacklist{msg or ''}")
        return await default.blacklist_log(ctx, 1, 0 if type in [2, 3] else 1 if type == 0 else 2, thing, reason)

    @commands.group(brief="Main staff commands", invoke_without_command=True)
    async def admin(self, ctx):
        """ Bot staff commands.
        Used to manage bot stuff."""

        await ctx.send_help(ctx.command)

    @admin.command()
    async def manage(self, ctx, thing: Union[discord.User, discord.Guild, int], *, reason: str = None):
        thing: Union[discord.User, discord.Guild, int] = await self.verify_type(ctx, thing)

        blacklist_emoji = self.bot.settings['emojis']['ranks']['blocked']
        dropdown = components.DropdownView(ctx, "Select an option...", [discord.SelectOption(label="Blacklist", emoji=blacklist_emoji, value=10, description="Blacklist user or guild"),  # type: ignore
                                                                        discord.SelectOption(label="Unblacklist", emoji=blacklist_emoji, value=11, description="Unblacklist user or guild"),  # type: ignore
                                                                        discord.SelectOption(label="Add badge", emoji="➕", value=12, description="Add a badge to user or guild"),  # type: ignore
                                                                        discord.SelectOption(label="Remove badge", emoji="➖", value=13, description="Remove a badge from user or guild"),  # type: ignore
                                                                        discord.SelectOption(label="Cancel", emoji="🟥", value=4, description="Cancel command.")],  # type: ignore
                                           cls=self, reason=reason, thing=thing)
        return await ctx.channel.send(f"You're managing **{thing}**", view=dropdown)

    @admin.command(name='disable-command', aliases=['discmd', 'disablecmd'])
    async def admin_disable_command(self, ctx, command: str, *, reason: str):

        command = self.bot.get_command(command)
        cant_disable = ['jsk', 'dev', 'admin', 'theme', 'help']

        if not command:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` doesn\'t exist.")

        elif command in cant_disable or command.parent in cant_disable:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` can't be disabled.")

        else:
            if command.parent:
                if await checks.is_disabled(ctx, command):
                    return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` is already disabled.")
                else:
                    if not command.name:
                        self.bot.disabled_commands[str(command.parent)] = {'reason': reason, 'dev': ctx.author.id}
                        await self.bot.db.execute("INSERT INTO discmds(command, reason, dev) VALUES($1, $2, $3)", str(command.parent), reason, ctx.author.id)
                        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent}` and its corresponding subcommands were successfully disabled for {reason}")
                    elif command.name:
                        self.bot.disabled_commands[str(f"{command.parent} {command.name}")] = {'reason': reason, 'dev': ctx.author.id}
                        await self.bot.db.execute("INSERT INTO discmds(command, reason, dev) VALUES($1, $2, $3)", str(f"{command.parent} {command.name}"), reason, ctx.author.id)
                        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent} {command.name}` and its corresponding subcommands were successfully disabled for {reason}")
            elif not command.parent:
                if await checks.is_disabled(ctx, command):
                    return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` is already disabled.")
                else:
                    self.bot.disabled_commands[str(command)] = {'reason': reason, 'dev': ctx.author.id}
                    await self.bot.db.execute("INSERT INTO discmds(command, reason, dev) VALUES($1, $2, $3)", str(command), reason, ctx.author.id)
                    await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command}` was successfully disabled for {reason}")

    @admin.command(name='enable-command', aliases=['enbcmd', 'enablecmd'])
    async def enable_command(self, ctx, *, cmd: str):

        command = self.bot.get_command(cmd)

        if not command:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{cmd}` doesn\'t exist.")

        else:
            if command.parent:
                if not await checks.is_disabled(ctx, command):
                    return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` is not disabled.")
                else:
                    if not command.name:
                        self.bot.disabled_commands.pop(str(command.parent))
                        await self.bot.db.execute("DELETE FROM discmds WHERE command = $1", str(command.parent))
                        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent}` and its corresponding subcommands were successfully re-enabled")
                    elif command.name:
                        self.bot.disabled_commands.pop(str(f"{command.parent} {command.name}"))
                        await self.bot.db.execute("DELETE FROM discmds WHERE command = $1", str(f"{command.parent} {command.name}"))
                        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent} {command.name}` and its corresponding subcommands were successfully re-enabled")
            elif not command.parent:
                if not await checks.is_disabled(ctx, command):
                    return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` is not disabled.")
                else:
                    self.bot.disabled_commands.pop(str(command))
                    await self.bot.db.execute("DELETE FROM discmds WHERE command = $1", str(command))
                    await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command}` was successfully re-enabled")

    @commands.command(brief='Approve the suggestion', aliases=['approve'])
    @checks.is_guild(709521003759403063)
    async def suggestapprove(self, ctx, suggestion_id: str, *, reason: commands.clean_content):
        """ Approve the suggestion """
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not suggestion_id.isdigit():
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | You provided invalid suggestion id. It has to be a digit.")

        suggestion = await self.bot.db.fetch("SELECT * FROM suggestions WHERE suggestion_id = $1 AND status = $2", int(suggestion_id), 0)

        if not suggestion:
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | That suggestion doesn't seem to exist or is already approved/denied.")

        user = await self.bot.fetch_user(suggestion[0]['user_id'])
        suggestion_content = f"{suggestion[0]['suggestion']}"
        suggestion_message = suggestion[0]['msg_id']

        message = await self.bot.get_guild(self.bot.settings['servers']['main']).get_channel(self.bot.settings['channels']['suggestions']).fetch_message(suggestion_message)
        embed = message.embeds[0]

        await self.bot.db.execute("INSERT INTO todos(user_id, todo, time, jump_url) VALUES($1, $2, $3, $4)", 345457928972533773, suggestion_content, datetime.now(), message.jump_url)
        embed.color = self.bot.settings['colors']['approve_color']
        embed.add_field(name="Approval note:", value=reason, inline=False)
        embed.set_footer(text=f"Suggestion was approved by {ctx.author}")
        await message.clear_reactions()
        await message.edit(embed=embed)

        await self.bot.db.execute("UPDATE suggestions SET status = $1, reason = $2 WHERE user_id = $3 AND suggestion_id = $4", 1, reason, user.id, int(suggestion_id))
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggestions WHERE _id = $1", int(suggestion_id))
        for res in trackers:
            e = discord.Embed(color=self.bot.settings['colors']['approve_color'], description=f"The following suggestion was approved by {ctx.author}\n**Approval note:** {reason}\n\n**Suggestion:**\n>>> {suggestion_content}")
            e.set_author(name=f"Suggested by {user} | #{suggestion_id}", icon_url=user.avatar.url if user.avatar else user.display_avatar.url)
            e.set_footer(text="You're either an author of this suggestion or you're following this suggestion's status")
            user = self.bot.get_user(res['user_id'])
            try:
                # await self.bot.db.execute("DELETE FROM track_suggestions WHERE user_id = $1 AND _id = $2", user.id, int(suggestion_id))
                await user.send(embed=e)
            except Exception:
                pass

    @commands.command(brief='Deny the suggestion', aliases=['deny'])
    @checks.is_guild(709521003759403063)
    async def suggestdeny(self, ctx, suggestion_id: str, *, reason: commands.clean_content):
        """ Deny the suggestion """
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not suggestion_id.isdigit():
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | You provided invalid suggestion id. It has to be a digit.")

        suggestion = await self.bot.db.fetch("SELECT * FROM suggestions WHERE suggestion_id = $1 AND status = $2", int(suggestion_id), 0)

        if not suggestion:
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | That suggestion doesn't seem to exist or is already approved/denied.")

        user = await self.bot.fetch_user(suggestion[0]['user_id'])
        suggestion_content = f"{suggestion[0]['suggestion']}"
        suggestion_message = suggestion[0]['msg_id']

        message = await self.bot.get_guild(self.bot.settings['servers']['main']).get_channel(self.bot.settings['channels']['suggestions']).fetch_message(suggestion_message)
        embed = message.embeds[0]

        embed.color = self.bot.settings['colors']['deny_color']
        embed.add_field(name="Denial note:", value=reason, inline=False)
        embed.set_footer(text=f"Suggestion was denied by {ctx.author}")
        await message.clear_reactions()
        await message.edit(embed=embed)

        await self.bot.db.execute("UPDATE suggestions SET status = $1, reason = $2 WHERE user_id = $3 AND suggestion_id = $4", 1, reason, user.id, int(suggestion_id))
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggestions WHERE _id = $1", int(suggestion_id))
        for res in trackers:
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], description=f"The following suggestion was denied by {ctx.author}\n**Denial note:** {reason}\n\n**Suggestion:**\n>>> {suggestion_content}")
            e.set_author(name=f"Suggested by {user} | #{suggestion_id}", icon_url=user.avatar.url if user.avatar else user.display_avatar.url)
            e.set_footer(text="You're either an author of this suggestion or you're following this suggestion's status")
            user = self.bot.get_user(res['user_id'])
            try:
                await self.bot.db.execute("DELETE FROM track_suggestions WHERE user_id = $1 AND _id = $2", user.id, int(suggestion_id))
                await user.send(embed=e)
            except Exception:
                pass

    @commands.command(brief='Deny the suggestion', aliases=['sdelete'])
    @checks.is_guild(709521003759403063)
    async def suggestdelete(self, ctx, suggestion_id: str, *, reason: commands.clean_content):
        """ Deny the suggestion """
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not suggestion_id.isdigit():
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | You provided invalid suggestion id. It has to be a digit.")

        suggestion = await self.bot.db.fetch("SELECT * FROM suggestions WHERE suggestion_id = $1 AND status = $2", int(suggestion_id), 0)

        if not suggestion:
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | That suggestion doesn't seem to exist or is already approved/denied.")

        user = await self.bot.fetch_user(suggestion[0]['user_id'])
        suggestion_content = f"{suggestion[0]['suggestion']}"
        suggestion_message = suggestion[0]['msg_id']

        message = await self.bot.get_guild(self.bot.settings['servers']['main']).get_channel(self.bot.settings['channels']['suggestions']).fetch_message(suggestion_message)
        await message.delete()

        await self.bot.db.execute("DELETE FROM suggestions WHERE suggestion_id = $1", int(suggestion_id))
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggestions WHERE _id = $1", int(suggestion_id))
        for res in trackers:
            e = discord.Embed(color=self.bot.settings['colors']['error_color'], description=f"The following suggestion was deleted by {ctx.author}\n**Delete note:** {reason}\n\n**Suggestion:**\n>>> {suggestion_content}")
            e.set_author(name=f"Suggested by {user} | #{suggestion_id}", icon_url=user.avatar.url if user.avatar else user.display_avatar.url)
            e.set_footer(text="You're either an author of this suggestion or you're following this suggestion's status")
            user = self.bot.get_user(res['user_id'])
            try:
                await self.bot.db.execute("DELETE FROM track_suggestions WHERE user_id = $1 AND _id = $2", user.id, int(suggestion_id))
                await user.send(embed=e)
            except Exception:
                pass

    @commands.command(brief='Mark suggestion as done', aliases=['sdone'])
    @checks.is_guild(709521003759403063)
    async def suggestdone(self, ctx, suggestion_id: str, *, note: commands.clean_content = None):
        """ Mark suggestion as done. """

        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not suggestion_id.isdigit():
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | You provided invalid suggestion id. It has to be a digit.")

        suggestion = await self.bot.db.fetch("SELECT * FROM suggestions WHERE suggestion_id = $1 AND status != $2", int(suggestion_id), 2)

        if not suggestion:
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | That suggestion doesn't seem to exist or is already implemented")

        user = await self.bot.fetch_user(suggestion[0]['user_id'])
        suggestion_content = f"{suggestion[0]['suggestion']}"
        suggestion_message = suggestion[0]['msg_id']

        message = await self.bot.get_guild(self.bot.settings['servers']['main']).get_channel(self.bot.settings['channels']['suggestions']).fetch_message(suggestion_message)
        embed = message.embeds[0]

        await self.bot.db.execute("DELETE FROM todos WHERE user_id = $1 AND todo = $2", 345457928972533773, suggestion_content)
        embed.color = self.bot.settings['colors']['approve_color']
        if note:
            embed.add_field(name="Note left:", value=note, inline=False)
        embed.set_footer(text=f"Suggestion was marked as done by {ctx.author}")
        await message.clear_reactions()
        await message.edit(embed=embed)

        note = note or 'No note left.'
        await self.bot.db.execute("UPDATE suggestions SET status = $1, reason = $2 WHERE user_id = $3 AND suggestion_id = $4", 2, note, user.id, int(suggestion_id))
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggestions WHERE _id = $1", int(suggestion_id))
        for res in trackers:
            e = discord.Embed(color=self.bot.settings['colors']['approve_color'], description=f"The following suggestion was marked as done by {ctx.author}\n**Note:** {note}\n\n**Suggestion:**\n>>> {suggestion_content}")
            e.set_author(name=f"Suggested by {user} | #{suggestion_id}", icon_url=user.avatar.url if user.avatar else user.display_avatar.url)
            e.set_footer(text="You're either an author of this suggestion or you're following this suggestion's status")
            user = self.bot.get_user(res['user_id'])
            try:
                await self.bot.db.execute("DELETE FROM track_suggestions WHERE user_id = $1 AND _id = $2", user.id, int(suggestion_id))
                await user.send(embed=e)
            except Exception:
                pass

    @admin.command(brief="DM a user", description="Direct message an user")
    async def dm(self, ctx, id: int, msg_id: Optional[int], *, msg: str):
        """ Send a DM to an user """
        try:
            await ctx.message.delete()
        except Exception:
            pass
        try:
            num = len(self.bot.dm)
            try:
                user = self.bot.dm[id]
            except Exception:
                user = self.bot.dm[num + 1] = id
            user = self.bot.get_user(user)
            if not user:
                self.bot.dm.pop(num)
                return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['warn']} User not found")
            if msg_id:
                dm_channel = user.dm_channel
                try:
                    message = await dm_channel.fetch_message(msg_id)
                except Exception:
                    return await user.send(msg)
                await message.reply(msg)
                msg = f"**Reply to:** {message.content}\n\n{msg}"
            else:
                await user.send(msg)
            logchannel = self.bot.get_channel(self.bot.settings['channels']['dm'])
            logembed = discord.Embed(description=msg,
                                     color=0x81C969,
                                     timestamp=datetime.now(timezone.utc))
            logembed.set_author(name=f"I've sent a DM to {user} | #{id}", icon_url=user.avatar.url if user.avatar else user.display_avatar.url)
            logembed.set_footer(text=f"User ID: {user.id}")
            await logchannel.send(embed=logembed)
        except discord.errors.Forbidden:
            await ctx.author.send("Couldn't send message to that user. Maybe he's not in the same server with me?")
        except Exception as e:
            await ctx.author.send(e)

    @commands.command(aliases=['addtester', 'atester', 'rtester', 'removetester'])
    async def tester(self, ctx, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        is_tester = CM.get(self.bot, 'testers', guild_id)
        if not guild and not is_tester:
            return await ctx.send("I'm not in that guild thus I cannot add them to the testers list.")
        elif guild and not is_tester:
            self.bot.testers[guild_id] = guild.name
            return await ctx.send(f"Added {guild} ({guild_id}) to testers list, they'll be able to use beta commands now.")
        elif guild:
            self.bot.testers.pop(guild_id)
            return await ctx.send(f"Removed {guild} ({guild_id}) from testers list.")

    @commands.command(aliases=['radioadd', 'addradio'], brief="Add a radio station")
    async def addradiostation(self, ctx, url: str, *, name: str):

        with open("db/radio_stations.json", "r") as f:
            data = json.load(f)

        try:
            # noinspection PyUnusedLocal
            check = data[f"{name}"]
            return await ctx.send(f"Radio station {name} already exists.")
        except KeyError:
            data[f"{name}"] = url
            self.bot.radio_stations[f"{name}"] = url

        with open("db/radio_stations.json", "w") as f:
            json.dump(data, f, indent=4)
        await ctx.send(f"Added {name} to the list.")

    @commands.command(aliases=['radioremove', 'removeradio', 'remradio'], brief="Remove a radio station")
    async def removeradiostation(self, ctx, *, name: str):
        with open("db/radio_stations.json", "r") as f:
            data = json.load(f)

        try:
            data.pop(f"{name}")
            self.bot.radio_stations.pop(f"{name}")
        except KeyError:
            return await ctx.send(f"Radio station {name} doesn't exist.")

        with open("db/radio_stations.json", "w") as f:
            json.dump(data, f, indent=4)
        await ctx.send(f"Removed {name} from the list.")


def setup(bot):
    bot.add_cog(staff(bot))
