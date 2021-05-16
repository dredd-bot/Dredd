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
import aiohttp
import asyncio
import random
import typing

from discord.ext import commands
from discord.utils import escape_markdown

from datetime import datetime, timezone
from utils.paginator import Pages
from utils import default, btime, checks
from db.cache import CacheManager as CM
from db.cache import LoadCache as LC


def to_add_reaction(c):
    return '\N{KEYCAP TEN}' if c == 10 else str(c) + '\u20e3'


class Misc(commands.Cog, name='Miscellaneous', aliases=['Misc']):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:etaa:747192603757248544>"
        self.big_icon = "https://cdn.discordapp.com/emojis/747192603757248544.png?v=1"

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"

    MAX_FILE_SIZE = 1024 * 1024 * 20
    TIMEOUT = 20
    NO_IMG = "http://i.imgur.com/62di8EB.jpg"
    CHUNK_SIZE = 512 * 1024

    async def create_reminder(self, ctx, content: str, time):
        await self.bot.db.execute("INSERT INTO reminders(user_id, channel_id, message_id, time, reminder) VALUES($1, $2, $3, $4, $5)", ctx.author.id, ctx.channel.id, ctx.message.id, time, content)

        check_reminders = CM.get(self.bot, 'reminders', ctx.author.id)

        if not check_reminders:
            self.bot.reminders[ctx.author.id] = {'1': {'time': time, 'content': content, 'channel': ctx.channel.id, 'message': ctx.message.id}}
        else:
            self.bot.reminders[ctx.author.id][str(len(check_reminders) + 1)] = {'time': time, 'content': content, 'channel': ctx.channel.id, 'message': ctx.message.id}

    @commands.command(brief="Search the urban dictionary")
    @commands.guild_only()
    @commands.is_nsfw()
    async def urban(self, ctx, *, urban: str):
        """ Search for a term in the urban dictionary """

        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'http://api.urbandictionary.com/v0/define?term={urban}') as r:
                url = await r.json()

        if url is None:
            return await ctx.send("No URL found")

        count = len(url['list'])
        if count == 0:
            return await ctx.send("No results were found.")
        result = url['list'][random.randint(0, count - 1)]

        definition = result['definition']
        example = result['example']
        if len(definition) >= 1000:
            definition = definition[:1000]
            definition = definition.rsplit(' ', 1)[0]
            definition += '...'

        text = _("**Search:** {0}\n**Author:** {1}\n"
                 "{2} {3} | {4} {5}\n**Definition:**\n{6}\n"
                 "**Example:**\n{7}").format(result['word'], result['author'], self.bot.settings['emojis']['misc']['upvote'],
                                             result['thumbs_up'], self.bot.settings['emojis']['misc']['downvote'], result['thumbs_down'],
                                             definition, example)
        await ctx.send(text)

    @commands.command(brief="Suggest anything", aliases=['idea'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def suggest(self, ctx, *, suggestion: commands.clean_content):
        """ Suggest anything you want to see in the server/bot!
        Suggestion will be sent to support server for people to vote.

        Please write your suggestion in English"""

        if ctx.guild:
            check = CM.get(self.bot, 'blacklist', ctx.guild.id)

            if check and check['type'] == 0:
                return await ctx.send(_("{0} Sorry, but this server is blacklisted from submitting suggestions. "
                                        "If you want to submit a suggestion, please do so in my DMs. Spamming them will result in a blacklist.").format(
                                          self.bot.settings['emojis']['misc']['warn']
                                      ))

        logchannel = self.bot.get_channel(self.bot.settings['channels']['suggestions'])

        if len(suggestion) > 1000:
            num = len(suggestion) - 1000
            chars = _('characters') if num != 1 else _('character')
            return await ctx.send(_("{0} Suggestions can only be 1000 characters long. You're {1} {2} over the limit.").format(
                                        self.bot.settings['emojis']['misc']['warn'], num, chars
                                    ))
        elif len(suggestion) < 1000:
            try:
                await ctx.message.delete()
            except Exception:
                pass
            ids = await self.bot.db.fetch("SELECT suggestion_id FROM suggestions")
            e = discord.Embed(color=self.bot.settings['colors']['embed_color'],
                              title=f"New suggestion from {ctx.author.name} #{len(ids) + 1}",
                              description=f"> {suggestion}", timestamp=datetime.now(timezone.utc))
            e.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
            msg = await logchannel.send(embed=e)
            await msg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
            await msg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
            await self.bot.db.execute("INSERT into suggestions(suggestion, suggestion_id, user_id, msg_id) VALUES($1, $2, $3, $4)", suggestion, len(ids) + 1, ctx.author.id, msg.id)
            await self.bot.db.execute("INSERT INTO track_suggestions VALUES($1, $2)", ctx.author.id, len(ids) + 1)
            e = discord.Embed(color=self.bot.settings['colors']['approve_color'], description=_("Your suggestion was successfully submitted in [my support server!]({0}) "
                                                                                                "You'll get notified in your DMs when the suggestion will be approved or denied."
                                                                                                "People can also follow this suggestion using `{1}suggestion track {2}`\n"
                                                                                                "**Suggestion:**\n>>> {3} ").format(self.bot.support, ctx.prefix, len(ids) + 1, suggestion), timestamp=datetime.now(timezone.utc))
            e.set_author(name=_("Suggestion sent as #{0}").format(len(ids) + 1), icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=e)

    @commands.group(brief='Track and untrack suggestions', aliases=['ideas'], invoke_without_command=True)
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def suggestion(self, ctx):
        """ Base command for tracking suggestions """
        await ctx.send_help(ctx.command)

    @suggestion.command(name='track', aliases=['t'], brief='Track a suggestion')
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def suggestion_track(self, ctx, id: int):
        """ Start tracking a suggestion """
        check = await self.bot.db.fetchval("SELECT * FROM track_suggestions WHERE user_id = $1 AND _id = $2", ctx.author.id, id)
        suggestions = await self.bot.db.fetchval("SELECT * FROM suggestions WHERE suggestion_id = $1", id)

        if suggestions is None:
            return await ctx.send(_("{0} Suggestion **#{1}** doesn't exist.").format(self.bot.settings['emojis']['misc']['warn'], id))
        elif check is not None:
            return await ctx.send(_("{0} You're already following that suggestion.").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO track_suggestions VALUES($1, $2)", ctx.author.id, id)
            await ctx.send(_("{0} | Started following suggestion **#{1}**. I'll DM you when the suggestion's status has been updated.").format(
                self.bot.settings['emojis']['misc']['white-mark'], id
            ))

    @suggestion.command(name='untrack', aliases=['u'], brief='Untrack a suggestion')
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def suggestion_untrack(self, ctx, id: int):
        """ Stop tracking a suggestion """
        check = await self.bot.db.fetchval("SELECT * FROM track_suggestions WHERE user_id = $1 AND _id = $2", ctx.author.id, id)
        suggestions = await self.bot.db.fetchval("SELECT * FROM suggestions WHERE suggestion_id = $1", id)
        owner = await self.bot.db.fetchval("SELECT * FROM suggestions WHERE suggestion_id = $1 AND user_id = $2", id, ctx.author.id)

        if suggestions is None:
            return await ctx.send(_("{0} Suggestion **#{1}** doesn't exist.").format(self.bot.settings['emojis']['misc']['warn'], id))
        elif check is None and owner is None:
            return await ctx.send(_("{0} You're not following that suggestion.").format(self.bot.settings['emojis']['misc']['warn']))
        elif owner is not None:
            return await ctx.send(_("{0} You cannot untrack that suggestion because you're the one who suggested it.").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("DELETE FROM track_suggestions WHERE user_id = $1 AND _id = $2", ctx.author.id, id)
            await ctx.send(_("{0} Stopped following suggestion **#{1}**. I won't DM you when the suggestion's status changes.").format(
                self.bot.settings['emojis']['misc']['white-mark'], id
            ))

    @commands.group(brief='Manage your todo list', invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def todo(self, ctx):
        """ Have anything to do later and you think you won't remember? You can manage your todo list with this command!"""
        await ctx.send_help(ctx.command)

    @todo.command(name='add', brief='Add a todo to your list', aliases=['a'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def todo_add(self, ctx, *, todo: commands.clean_content):
        """ Add a todo to your list """
        check = await self.bot.db.fetchval("SELECT * FROM todos WHERE user_id = $1 AND todo = $2", ctx.author.id, todo)

        if check is not None:
            return await ctx.send(_("{0} You already have that item in your todo list.").format(self.bot.settings['emojis']['misc']['warn']))
        else:
            await self.bot.db.execute("INSERT INTO todos(user_id, todo, jump_url, time) VALUES($1, $2, $3, $4)", ctx.author.id, todo, ctx.message.jump_url, datetime.now())
            if len(todo) > 200:
                todo = todo[:200]
                todo += '...'
            count = await self.bot.db.fetchval("SELECT count(*) FROM todos WHERE user_id = $1", ctx.author.id)
            await ctx.send(_("{0} Added **{1}** to your todo list. You now have **{2}** items in your list.").format(
                self.bot.settings['emojis']['misc']['white-mark'], escape_markdown(todo, as_needed=False), count
            ))

    @todo.command(name='edit', brief='Edit your todo', aliases=['e'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def todo_edit(self, ctx, pos: int, *, todo: commands.clean_content):
        """ Edit your todos """
        todos = await self.bot.db.fetch("SELECT DISTINCT todo, time, ROW_NUMBER () OVER (ORDER BY time) FROM todos WHERE user_id = $1 ORDER BY time", ctx.author.id)
        if not todos:
            return await ctx.send(_("{0} You don't have any items in your todo list.").format(self.bot.settings['emojis']['misc']['warn']))
        if pos not in [t['row_number'] for t in todos]:
            return await ctx.send(_("{0} There is no todo item with an id of **{1}** in your todo list.").format(
                self.bot.settings['emojis']['misc']['warn'], pos
            ))
        check = await self.bot.db.fetchval("SELECT * FROM todos WHERE user_id = $1 AND todo = $2", ctx.author.id, todo)
        if check:
            return await ctx.send(_("{0} You already have that item in your todo list.").format(self.bot.settings['emojis']['misc']['warn']))

        await self.bot.db.execute("UPDATE todos SET todo = $1 WHERE user_id = $2 AND time = $3", todo, ctx.author.id, todos[pos - 1]['time'])
        if len(todo) > 200:
            todo = todo[:200]
            todo += '...'
        await ctx.send(_("{0} Successfully edited the item in your todo list with an ID of **{1}** to: **{2}**").format(
            self.bot.settings['emojis']['misc']['white-mark'], pos, escape_markdown(todo, as_needed=False)
        ))

    @todo.command(name='swap', brief='Swap 2 todo\'s', aliases=['s'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def todo_swap(self, ctx, swap: int, to: int):
        """ Swap 2 todo's around. This will swap the time when todos have been added.
        Syntax: `todo swap 1, 5` -> this will swap 1 with 5 """
        todos = await self.bot.db.fetch("SELECT DISTINCT todo, time, ROW_NUMBER () OVER (ORDER BY time) FROM todos WHERE user_id = $1 ORDER BY time", ctx.author.id)
        if not todos:
            return await ctx.send(_("{0} You don't have any items in your todo list.").format(self.bot.settings['emojis']['misc']['warn']))

        if int(swap) not in [t['row_number'] for t in todos]:
            return await ctx.send(_("{0} There is no todo item with an id of **{1}** in your todo list.").format(
                self.bot.settings['emojis']['misc']['warn'], swap
            ))
        elif int(to) not in [t['row_number'] for t in todos]:
            return await ctx.send(_("{0} There is no todo item with an id of **{1}** in your todo list.").format(
                self.bot.settings['emojis']['misc']['warn'], to
            ))

        query = 'UPDATE todos SET time = $1 WHERE todo = $2 AND user_id = $3'
        entries = [(todos[swap - 1]['time'], todos[to - 1]['todo'], ctx.author.id), (todos[to - 1]['time'], todos[swap - 1]['todo'], ctx.author.id)]
        await self.bot.db.executemany(query, entries)

        await ctx.send(_("{0} Successfully swapped places of todo **#{1}** and **#{2}**.").format(
            self.bot.settings['emojis']['misc']['white-mark'], swap, to
        ))

    @todo.command(name='list', aliases=['l'], brief='Check your todo list')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def todo_list(self, ctx):
        """ Once you've added todos to your todo list you can use this command to check them. """
        todos = await self.bot.db.fetch("SELECT DISTINCT todo, time, ROW_NUMBER () OVER (ORDER BY time) FROM todos WHERE user_id = $1 ORDER BY time", ctx.author.id)
        if not todos:
            return await ctx.send(_("{0} You don't have any items in your todo list.").format(self.bot.settings['emojis']['misc']['warn']))
        todol = []
        for res in todos:
            if len(res['todo']) > 195:
                yourtodo = res['todo'][:190] + '...'
            elif len(res['todo']) < 195:
                yourtodo = res['todo']
            todol.append(f"`[{res['row_number']}]` {yourtodo}\n")

        paginator = Pages(ctx,
                          entries=todol,
                          thumbnail=None,
                          per_page=10,
                          embed_color=ctx.bot.settings['colors']['embed_color'],
                          embed_author=_("{0}'s Todo List").format(ctx.author),
                          show_entry_count=True)
        await paginator.paginate()

    @todo.command(name='info', aliases=['i'], brief='Information about your todo item')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def todo_info(self, ctx, pos: int):
        """ Get more information about your todo item """
        todo = await self.bot.db.fetch("SELECT DISTINCT todo, time, jump_url, ROW_NUMBER () OVER (ORDER BY time) FROM todos WHERE user_id = $1 ORDER BY time", ctx.author.id)

        if not todo:
            return await ctx.send(_("{0} You don't have any items in your todo list.").format(self.bot.settings['emojis']['misc']['warn']))

        if pos not in [t['row_number'] for t in todo]:
            return await ctx.send(_("{0} There is no todo item with an id of **{1}** in your todo list.").format(self.bot.settings['emojis']['misc']['warn'], pos))

        e = discord.Embed(color=self.bot.settings['colors']['embed_color'])
        e.set_author(name=_("Information about your todo item"), icon_url=ctx.author.avatar_url)
        dots = '...'
        e.description = _("""**Todo:** {0}\n\n**Todo position:** {1}/{2}\n**Todo added:** {3}\n**Jump url:** [click here to jump]({4})""").format(
            f"{todo[pos-1]['todo']}" if len(todo[pos - 1]['todo']) < 1800 else f"{escape_markdown(todo[pos - 1]['todo'][:1800] + dots, as_needed=False)}",
            pos, len(todo), btime.human_timedelta(todo[pos - 1]['time']), todo[pos - 1]['jump_url']
        )
        await ctx.send(embed=e)

    @todo.command(name='remove', aliases=['r'], brief='Remove a todo from your list')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def todo_remove(self, ctx, *, pos: str):
        """ Remove a todo from your list """
        todos = await self.bot.db.fetch("SELECT DISTINCT todo, time, ROW_NUMBER () OVER (ORDER BY time) FROM todos WHERE user_id = $1 ORDER BY time", ctx.author.id)
        if not todos:
            return await ctx.send(_("{0} You don't have any items in your todo list.").format(self.bot.settings['emojis']['misc']['warn']))
        todo_ids = pos.split(' ')
        to_remove = []
        for tid in todo_ids:
            if not tid.isdigit():
                return await ctx.send(_("{0} That is not a valid id.").format(self.bot.settings['emojis']['misc']['warn']))
            elif int(tid) not in [t['row_number'] for t in todos]:
                return await ctx.send(_("{0} There is no todo item with an id of **{1}** in your todo list.").format(
                    self.bot.settings['emojis']['misc']['warn'], pos
                ))
            to_remove.append(int(tid))
        query = 'DELETE FROM todos WHERE user_id = $1 and time = $2'
        entries = [(ctx.author.id, todos[todo_id - 1]['time']) for todo_id in to_remove]
        await self.bot.db.executemany(query, entries)
        dots = '...'
        contents = '\n• '.join([f"""{f'{escape_markdown(todos[todo_id-1]["todo"], as_needed=False)}' if len(todos[todo_id-1]['todo']) < 150 else f'{escape_markdown(todos[todo_id-1]["todo"][:150] + dots, as_needed=False)}'} """ for todo_id in to_remove])
        return await ctx.send(_("{0} Removed **{1}** todo from your todo list:\n• {2}").format(
            self.bot.settings['emojis']['misc']['white-mark'], len(todo_ids), contents
        ))

    @todo.command(aliases=['c'], brief='Clear your todos')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def clear(self, ctx):
        """ Clear your todo list """

        todos = await self.bot.db.fetch('SELECT * FROM todos WHERE user_id = $1 ORDER BY time', ctx.author.id)
        if not todos:
            return await ctx.send(_("{0} There's nothing to clear. Your todo list is already empty.").format(self.bot.settings['emojis']['misc']['warn']))

        def check(r, u):
            return u.id == ctx.author.id and r.message.id == checkmsg.id

        try:
            checkmsg = await ctx.send(_("Are you sure you want to clear **{0}** items from your todo list?").format(len(todos)))
            await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
            await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
            react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30)

            if str(react) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                try:
                    await checkmsg.clear_reactions()
                except Exception:
                    pass
                await checkmsg.edit(content=_("{0} Deleted {1} items from your todo list").format(
                    self.bot.settings['emojis']['misc']['white-mark'], len(todos)
                ))
                await self.bot.db.execute("DELETE FROM todos WHERE user_id = $1", ctx.author.id)

            if str(react) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                try:
                    await checkmsg.clear_reactions()
                except Exception:
                    pass
                await checkmsg.edit(content=_("{0} I'm not deleting any items from your todo list.").format(self.bot.settings['emojis']['misc']['white-mark']))

        except asyncio.TimeoutError:
            try:
                await checkmsg.clear_reactions()
            except Exception:
                pass
            await checkmsg.edit(content=_("Canceling..."), delete_after=15)

    @commands.command(brief='Set your AFK status in the current server', aliases=['afk'])
    @commands.guild_only()
    @checks.has_voted()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def setafk(self, ctx, *, note: commands.clean_content = "I'm currently AFK"):
        """ Set your AFK status in the current server so users who mention you would know that you're AFK """
        check = CM.get(self.bot, 'afk', f"{str(ctx.guild.id)}, {str(ctx.author.id)}")
        check1 = CM.get(self.bot, 'afk', f"{str(ctx.author.id)}")

        if check1:
            return await ctx.send(_("{0} You've set your AFK status globally already.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        if len(note) > 500:
            note = note[:500]
            note += '...'

        if check is not None:
            await self.bot.db.execute("UPDATE afk SET message = $1 WHERE user_id = $2 AND guild_id = $3", note, ctx.author.id, ctx.guild.id)
            self.bot.afk[f"{str(ctx.guild.id)}, {str(ctx.author.id)}"]['note'] = note
            await ctx.send(_("{0} **Changed your AFK state to:** {1}").format(
                self.bot.settings['emojis']['misc']['white-mark'], escape_markdown(note, as_needed=False)
            ))
        elif check is None:
            await self.bot.db.execute("INSERT INTO afk(user_id, guild_id, message, time) VALUES($1, $2, $3, $4)", ctx.author.id, ctx.guild.id, note, datetime.now())
            self.bot.afk[f"{str(ctx.guild.id)}, {str(ctx.author.id)}"] = {'note': note, 'time': datetime.now()}
            await ctx.send(_("{0} ** Set your AFK state to:** {1}").format(
                self.bot.settings['emojis']['misc']['white-mark'], escape_markdown(note, as_needed=False)
            ))

    @commands.command(brief='Set your AFK status globally', aliases=['globalafk', 'gafk'])
    @commands.guild_only()
    @checks.has_voted()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def setglobalafk(self, ctx, *, note: commands.clean_content = "I'm currently AFK"):
        """ Set your AFK status in all the shared servers with the bot so users who mention you would know that you're AFK """

        check = CM.get(self.bot, 'afk', f"{str(ctx.author.id)}")
        check1 = await self.bot.db.fetchval("SELECT count(*) FROM afk WHERE user_id = $1", ctx.author.id)

        if check1 > 0:
            return await ctx.send(_("{0} You first need to unafk yourself in **{1}** servers!").format(
                self.bot.settings['emojis']['misc']['warn'], check1
            ))

        if len(note) > 500:
            note = note[:500]
            note += '...'

        if check is not None:
            await self.bot.db.execute("UPDATE afk SET message = $1 WHERE user_id = $2", note, ctx.author.id)
            self.bot.afk[f"{str(ctx.author.id)}"]['note'] = note
            await ctx.send(_("{0} **Changed your global AFK state to:** {1}").format(
                self.bot.settings['emojis']['misc']['white-mark'], escape_markdown(note, as_needed=False)
            ))
        elif check is None:
            await self.bot.db.execute("INSERT INTO afk(user_id, message, time) VALUES($1, $2, $3)", ctx.author.id, note, datetime.now())
            self.bot.afk[f"{str(ctx.author.id)}"] = {'note': note, 'time': datetime.now()}
            await ctx.send(_("{0} ** Set your global AFK state to:** {1}").format(
                self.bot.settings['emojis']['misc']['white-mark'], escape_markdown(note, as_needed=False)
            ))

    @commands.command(brief='See the latest deleted message in a channel.')
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def snipe(self, ctx, *, channel: discord.TextChannel = None):
        channel = channel or ctx.channel

        snipe = CM.get(self.bot, 'snipes', channel.id)
        if snipe is None:
            return await ctx.send(_("{0} I haven't yet logged any messages from {1}.").format(
                self.bot.settings['emojis']['misc']['warn'], channel.mention if channel != ctx.channel else _('this channel')
            ))
        if snipe['nsfw'] and not ctx.channel.is_nsfw():
            return await ctx.send(_("{0} I can't let you snipe messages from an NSFW channel!").format(self.bot.settings['emojis']['logs']['nsfw']))

        else:
            try:
                user = await self.bot.fetch_user(snipe['author'])
                name = user
            except discord.errors.NotFound:
                try:
                    user = await self.bot.fetch_webhook(snipe['author'])
                    name = user.name
                except discord.errors.NotFound:
                    return await ctx.send(_("{0} Looks like I can't fetch the user that sent the snipped message.").format(self.bot.settings['emojis']['logs']['nsfw']))
                except discord.errors.Forbidden:
                    return await ctx.send(_("{0} That message looks like it was a webhook, and I'm missing permissions to look for more information.").format(self.bot.settings['emojis']['logs']['nsfw']))

            message = snipe['message'] or _("*[Couldn't get the sniped content]*")
            message = message.replace('[', '\[')
            e = discord.Embed(color=self.bot.settings['colors']['embed_color'], description=message)
            e.set_author(name=_("Deleted by {0}").format(name), icon_url=user.avatar_url)
            e.set_footer(text=_("Deleted {0} in #{1}").format(btime.human_timedelta(snipe['deleted_at']), channel.name))
            await ctx.send(embed=e)

    # toggle commands for activity and snipes
    @commands.group(brief='Toggle your data logging', invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def toggle(self, ctx):
        """ Toggle your data logging. This only applies to snipes, nicknames and statuses """
        await ctx.send_help(ctx.command)

    @toggle.command(brief='Toggle your snipes logging', aliases=['snipe'], name='snipes')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def toggle_snipes(self, ctx):
        """ Toggle your snipes (deleted messages)
        This applies to all the servers we share """
        check = CM.get(self.bot, 'snipes_op', ctx.author.id)

        def checks(r, u):
            return u.id == ctx.author.id and r.message.id == checkmsg.id

        if check is None:
            try:
                checkmsg = await ctx.send(_("Are you sure you want to opt-out? Once you'll do that, I won't log your deleted messages in my snipe command."))
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
                react, user = await self.bot.wait_for('reaction_add', check=checks, timeout=30.0)

                if str(react) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                    await self.bot.db.execute('INSERT INTO snipes_op(user_id, username) VALUES($1, $2)', ctx.author.id, ctx.author.display_name)
                    self.bot.snipes_op[ctx.author.id] = ctx.author.display_name
                    await ctx.channel.send(_("{0} Alright. I won't be logging your snipes anymore!").format(self.bot.settings['emojis']['misc']['white-mark']))
                    await checkmsg.delete()

                if str(react) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                    await checkmsg.delete()
                    await ctx.channel.send(_("Oh sweet! I'll continue logging your snipes."))
            except asyncio.TimeoutError:
                await checkmsg.clear_reactions()
                return
            except Exception as e:
                self.bot.dispatch('command_error', ctx, e)
                return

        elif check is not None:
            try:
                checkmsg = await ctx.send("Are you sure you want to opt-in? Once you'll do that I'll start logging your snipes to my cache.")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
                react, user = await self.bot.wait_for('reaction_add', check=checks, timeout=30.0)

                if str(react) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                    await self.bot.db.execute('DELETE FROM snipes_op WHERE user_id = $1', ctx.author.id)
                    self.bot.snipes_op.pop(ctx.author.id)
                    await ctx.channel.send(_("{0} You're now opted-in! From now on, I'll be logging your deleted messages in my snipe command!").format(
                        self.bot.settings['emojis']['misc']['white-mark']
                    ))
                    await checkmsg.delete()

                if str(react) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                    await checkmsg.delete()
                    await ctx.channel.send(_("Alright, not opting you in."))
            except asyncio.TimeoutError:
                await checkmsg.clear_reactions()
                return
            except Exception as e:
                self.bot.dispatch('command_error', ctx, e)
                return

    @toggle.command(brief='Toggle your nicknames logging', aliases=['nicks'], name='nicknames')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def toggle_nicknames(self, ctx):
        """ Toggle your nicknames logging
        This applies to all the servers we share """
        check = CM.get(self.bot, 'nicks_op', f'{ctx.author.id} - {ctx.guild.id}')

        def checks(r, u):
            return u.id == ctx.author.id and r.message.id == checkmsg.id

        if check is None:
            try:
                checkmsg = await ctx.send(_("Are you sure you want to opt-out? Once you'll do that, I won't be logging nickname changes from you in this server."))
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
                react, user = await self.bot.wait_for('reaction_add', check=checks, timeout=30.0)

                if str(react) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                    await self.bot.db.execute('INSERT INTO nicks_op(guild_id, user_id) VALUES($1, $2)', ctx.guild.id, ctx.author.id)
                    self.bot.nicks_op[f'{ctx.author.id} - {ctx.guild.id}'] = ctx.author.id
                    await self.bot.db.execute("DELETE FROM nicknames WHERE user_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
                    await ctx.channel.send(_("{0} Alright. I won't be logging your nicknames anymore in this server!").format(self.bot.settings['emojis']['misc']['white-mark']))
                    await checkmsg.delete()

                if str(react) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                    await checkmsg.delete()
                    await ctx.channel.send(_("Oh sweet! I'll continue logging your nicknames"))
            except asyncio.TimeoutError:
                await checkmsg.clear_reactions()
                return
            except Exception as e:
                self.bot.dispatch('command_error', ctx, e)
                return

        elif check is not None:
            try:
                checkmsg = await ctx.send(_("Are you sure you want to opt-in? Once you'll do that I'll start logging your nicknames again."))
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
                react, user = await self.bot.wait_for('reaction_add', check=checks, timeout=30.0)

                if str(react) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                    await self.bot.db.execute('DELETE FROM nicks_op WHERE guild_id = $1 AND user_id = $2', ctx.guild.id, ctx.author.id)
                    self.bot.nicks_op.pop(f'{ctx.author.id} - {ctx.guild.id}')
                    await ctx.channel.send(_("{0} You're now opted-in! I'll be logging your nicknames from now on in this server!").format(self.bot.settings['emojis']['misc']['white-mark']))
                    await checkmsg.delete()

                if str(react) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                    await checkmsg.delete()
                    await ctx.channel.send(_("Alright. Not opting you in"))
            except asyncio.TimeoutError:
                await checkmsg.clear_reactions()
                return
            except Exception as e:
                self.bot.dispatch('command_error', ctx, e)
                return

    @toggle.command(brief='Toggle your status logging', aliases=['activity', 'presence'], name='status')
    @commands.cooldown(1, 5, commands.BucketType.user)
    @checks.removed_command()
    async def toggle_status(self, ctx):
        """ Toggle your status logging """
        check = CM.get(self.bot, 'status_op', ctx.author.id)

        def checks(r, u):
            return u.id == ctx.author.id and r.message.id == checkmsg.id
        if check is not None:
            try:
                checkmsg = await ctx.send("Are you sure you want to opt-out? Once you'll do that I won't be logging your status to the database.")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
                react, user = await self.bot.wait_for('reaction_add', check=checks, timeout=30.0)
                if str(react) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                    await self.bot.db.execute('DELETE FROM status_op WHERE user_id = $1', ctx.author.id)
                    self.bot.status_op.pop(ctx.author.id)
                    await self.bot.db.execute("DELETE FROM status WHERE user_id = $1", ctx.author.id)
                    await ctx.channel.send(f"{self.bot.settings['emojis']['misc']['white-mark']} Alright. I won't be logging your statuses anymore!")
                    await checkmsg.delete()
                if str(react) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                    await checkmsg.delete()
                    await ctx.channel.send("Oh sweet! I'll continue logging your statuses")
            except asyncio.TimeoutError:
                await checkmsg.clear_reactions()
                return
            except Exception as e:
                self.bot.dispatch('command_error', ctx, e)
                return
        elif check is None:
            try:
                checkmsg = await ctx.send("Are you sure you want to opt-in? Once you'll do that I'll start logging your status to the database.")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
                react, user = await self.bot.wait_for('reaction_add', check=checks, timeout=30.0)
                if str(react) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                    await self.bot.db.execute('INSERT INTO status_op(user_id, username) VALUES($1, $2)', ctx.author.id, ctx.author.display_name)
                    self.bot.status_op[ctx.author.id] = ctx.author.display_name
                    await self.bot.db.execute("INSERT INTO status(user_id, status_type, since) VALUES($1, $2, $3)", ctx.author.id, ctx.author.status.name, datetime.now())
                    await ctx.channel.send(f"{self.bot.settings['emojis']['misc']['white-mark']} You're now opted-in! I'll be logging your statuses from now on!")
                    await checkmsg.delete()
                if str(react) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not opting you in")
            except asyncio.TimeoutError:
                await checkmsg.clear_reactions()
                return
            except Exception as e:
                self.bot.dispatch('command_error', ctx, e)
                return

    @commands.command(brief='Create a poll', aliases=['poll'])
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def createpoll(self, ctx, channel: typing.Optional[discord.TextChannel], *, questions_and_answers: str):
        """ Create a poll with upto 10 options.
        Separate the options with a `|` between them. """

        if "|" in questions_and_answers:
            next_question = "|"
        else:
            next_question = None

        if next_question:
            questions_and_choices = questions_and_answers.split(next_question)
        else:
            return await ctx.send(_("{0} You need to split options with `|` in between them.").format(self.bot.settings['emojis']['misc']['warn']))

        if len(questions_and_choices) < 3 or len(questions_and_choices) > 11:
            return await ctx.send(_("{0} Poll is either too short, or too long. You must have at least 3 options and up to 10").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        question = questions_and_choices[0]
        choices = []
        for e, v in enumerate(questions_and_choices[1:], start=1):
            if '  ' in v or v == '' or v == ' ':
                return await ctx.send(_("{0} Option {1} is empty when it can't be empty.").format(self.bot.settings['emojis']['misc']['warn'], e))
            choices.append((f"`{e}.`", v))
        reactions = [(to_add_reaction(e), v) for e, v in enumerate(questions_and_choices[1:], 1)]
        answer = '\n'.join('%s %s' % t for t in choices)

        if len(question) > 125:
            return await ctx.send(_("{0} Your question is over the limit by {1} characters. Max is 125 characters.").format(
                self.bot.settings['emojis']['misc']['warn'], len(question) - 125
            ))

        embed = discord.Embed(color=self.bot.settings['colors']['embed_color'],
                              title=question,
                              description=answer)
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

        channel = channel or ctx.channel
        msg = await channel.send(embed=embed, content=_('New poll created by **{0}**').format(ctx.author))
        for reaction, x in reactions:
            await msg.add_reaction(reaction)

        await ctx.send(_("{0} Successfully created poll in {1}!").format(
            self.bot.settings['emojis']['misc']['white-mark'], _('this channel') if channel == ctx.channel else channel.mention
        ))

    @commands.command(brief='Get lyrics of a song.', aliases=['song'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def lyrics(self, ctx, *, song: str):
        """"""
        try:
            await ctx.send(_("{0} Searching for song lyrics - {1}").format(
                self.bot.settings['emojis']['misc']['loading'], song
            ))
            song = await self.bot.sr_api.get_lyrics(song)
        except Exception as e:
            return await ctx.send(_("{0} Failed to find lyrics for that song. {1}").format(self.bot.settings['emojis']['misc']['warn'], e))

        embed = discord.Embed(color=self.bot.settings['colors']['embed_color'],
                              title=_("{0} - {1} lyrics").format(song.author, song.title),
                              url=song.link,
                              description=song.lyrics[:1800] + '...' if len(song.lyrics) > 1800 else song.lyrics)
        embed.set_thumbnail(url=song.thumbnail)
        await ctx.send(embed=embed)

    @commands.command(brief='Setup your status logging', aliases=['activity', 'presence'])
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @checks.removed_command()
    async def status(self, ctx, *, member: discord.Member = None):
        member = member or ctx.author

        if member.bot:
            return await ctx.send(_("{0} I do not track bot's activity...").format(self.bot.settings['emojis']['misc']['warn']))

        member_check = CM.get(self.bot, 'status_op', member.id)
        author_check = CM.get(self.bot, 'status_op', ctx.author.id)
        afks = CM.get(self.bot, 'afk', f'{str(ctx.guild.id)}, {str(ctx.author.id)}')

        if member_check is None:
            return await ctx.send(_("{0} {1} has opted-out of status logging."
                                  "{2}").format(
                                      self.bot.settings['emojis']['misc']['warn'],
                                      member,
                                      _("You can opt-in to status logging by using `{0}toggle status`").format(ctx.prefix) if member == ctx.author else ''
                                  ))

        elif member_check is not None and author_check is None:
            return await ctx.send(_("{0} you cannot view **{1}**'s activity because you've opted out of status logging!"
                                    "You can opt back in using `{2}toggle status`").format(
                self.bot.settings['emojis']['misc']['warn'], member, ctx.prefix
            ))

        elif member_check is not None and author_check is not None:
            status = await self.bot.db.fetch("SELECT * FROM status WHERE user_id = $1", member.id)
            if status is None:
                return await ctx.send(_("{0} I don't have {1}").format(
                    self.bot.settings['emojis']['misc']['warn'],
                    _("{0}'s status logged.").format(member) if member != ctx.author else _("your status logged.")
                ))
            elif status is not None:
                bslash = '\n'
                the_status = default.member_status(ctx, member)
                afk = _("They've been AFK for **{0}**{1}").format(btime.human_timedelta(afks['time'], suffix=None), bslash) if afks else ''
                s = status[0]['status_type']
                s = "**{0}**".format(_("idle") if s == 'idle' else _("online") if s == 'online' else _('do not disturb') if s == 'dnd' else _("offline"))
                presence = _("**{0}** has been{1} {2} **{3}** for {4}.\n{5}\n".format(
                    ctx.guild.get_member(status[0]['user_id']), _(' on') if status[0]['status_type'] == 'dnd' else '',
                    the_status, s, btime.human_timedelta(status[0]['since'], suffix=None), afk
                ))
                activity = default.member_presence(ctx, member)
                e = discord.Embed(color=self.bot.settings['colors']['embed_color'])
                e.set_author(name=_("{0}'s Activity").format(member), icon_url=member.avatar_url)
                b = '\n'
                e.description = _("""{0}{1}""").format(
                    presence, _("**They've also been:**{0}").format(activity) if activity != f"{b}" else ''
                )
                return await ctx.send(embed=e)

    @commands.group(brief='Manage your reminders', aliases=['reminds', 'rm', 'reminder', 'remindme'], invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def remind(self, ctx, *, remind: btime.UserFriendlyTime(commands.context, default="\u2026")):
        """ Create a reminder for yourself.
        Example usage: `remind 1h do homework`"""
        try:
            await self.create_reminder(ctx, remind.arg, remind.dt)
            time = btime.human_timedelta(remind.dt, source=ctx.message.created_at)
            await ctx.send(_("Alright, reminding you in {0}: {1}").format(time, remind.arg))
        except AttributeError:
            return

    @remind.command(brief='A list with your reminders', name='list')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def remind_list(self, ctx):
        """ Check your reminders list """
        check_reminders = CM.get(self.bot, 'reminders', ctx.author.id)

        if not check_reminders:
            return await ctx.send(_("{0} You have no reminders.").format(self.bot.settings['emojis']['misc']['warn']))

        reminders = []
        for result in check_reminders:
            when = btime.human_timedelta(check_reminders[result]['time'], source=ctx.message.created_at)
            content = check_reminders[result]['content']
            reminders.append(_("`[{0}]` Reminding in **{1}**\n{2}\n").format(result, when, content[:150] + '...' if len(content) > 150 else content))

        paginator = Pages(ctx,
                          entries=reminders,
                          thumbnail=None,
                          per_page=10,
                          embed_color=ctx.bot.settings['colors']['embed_color'],
                          embed_author=_("{0}'s Reminders").format(ctx.author),
                          show_entry_count=True)
        await paginator.paginate()

    @remind.command(brief='Remove a reminder', name='remove')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def reminder_remove(self, ctx, reminder: str):
        """ Remove an unwanted reminder """
        check_reminders = CM.get(self.bot, 'reminders', ctx.author.id)

        if not check_reminders:
            return await ctx.send(_("{0} You have no reminders.").format(self.bot.settings['emojis']['misc']['warn']))

        if not reminder.isdigit():
            return await ctx.send(_("{0} That is not a valid id.").format(self.bot.settings['emojis']['misc']['warn']))
        elif reminder not in [t for t in check_reminders]:
            return await ctx.send(_("{0} There is no reminder with an id of **{1}** in your reminders list.").format(
                self.bot.settings['emojis']['misc']['warn'], reminder
            ))

        else:
            the_reminder = check_reminders[reminder]['content']
            the_time = check_reminders[reminder]['time']
            self.bot.reminders[ctx.author.id].pop(reminder)
            await self.bot.db.execute("DELETE FROM reminders WHERE user_id = $1 AND reminder = $2 AND time = $3", ctx.author.id, the_reminder, the_time)
            await LC.reminders(self.bot)
            await ctx.send(_("{0} Removed reminder from your reminders list: {1}").format(self.bot.settings['emojis']['misc']['white-mark'], the_reminder))


def setup(bot):
    bot.add_cog(Misc(bot))
