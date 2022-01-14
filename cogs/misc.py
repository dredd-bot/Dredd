"""
Dredd, discord bot
Copyright (C) 2022 Moksej
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

from discord.ext import commands
from discord.utils import escape_markdown

from typing import Optional
from datetime import datetime, timezone
from utils.paginator import Pages, ListPages
from utils import btime, checks, components
from db.cache import CacheManager as CM
from db.cache import LoadCache as LC
from utils.i18n import locale_doc


def to_add_reaction(c):
    return '\N{KEYCAP TEN}' if c == 10 else str(c) + '\u20e3'


# noinspection PyUnboundLocalVariable,PyTypeHints
class Misc(commands.Cog, name='Miscellaneous'):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:etaa:747192603757248544>"
        self.big_icon = "https://cdn.discordapp.com/emojis/747192603757248544.png?v=1"

        self.to_delete = {}

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

    async def perform_action(self, value: bool, interaction: discord.Interaction, command: Optional[str]) -> None:  # sourcery no-metrics
        if command:
            if command == "snipes":
                cache = CM.get(self.bot, 'snipes_op', interaction.user.id)
                if value:
                    if cache is None:
                        await self.bot.db.execute('INSERT INTO snipes_op(user_id, username) VALUES($1, $2)', interaction.user.id, interaction.user.display_name)
                        self.bot.snipes_op[interaction.user.id] = interaction.user.display_name
                        return await interaction.message.edit(content=_("{0} Alright. I won't be logging your snipes anymore!").format(self.bot.settings['emojis']['misc']['white-mark']), view=None)  # type: ignore
                    else:
                        await self.bot.db.execute('DELETE FROM snipes_op WHERE user_id = $1', interaction.user.id)
                        self.bot.snipes_op.pop(interaction.user.id)
                        return await interaction.message.edit(  # type: ignore
                            content=_("{0} You're now opted-in! From now on, I'll be logging your deleted messages in my snipe command!").format(self.bot.settings['emojis']['misc']['white-mark']), view=None)
                elif cache is not None:
                    return await interaction.message.edit(content=_("Alright, not opting you in."), view=None)  # type: ignore
                else:
                    return await interaction.message.edit(content=_("Oh sweet! I'll continue logging your snipes."), view=None)  # type: ignore
            elif command == "todos":
                if not value:
                    return await interaction.message.edit(content=_("{0} I'm not deleting any items from your todo list.").format(self.bot.settings['emojis']['misc']['white-mark']), view=None)  # type: ignore
                todos = await self.bot.db.fetch('SELECT * FROM todos WHERE user_id = $1 ORDER BY time', interaction.user.id)
                await interaction.message.edit(content=_("{0} Deleted {1} items from your todo list").format(
                    self.bot.settings['emojis']['misc']['white-mark'], len(todos)
                ), view=None)
                return await self.bot.db.execute("DELETE FROM todos WHERE user_id = $1", interaction.user.id)
            elif command == "nicknames":
                cache = CM.get(self.bot, 'nicks_op', f'{interaction.user.id} - {interaction.guild.id}')  # type: ignore
                if value:
                    if cache is None:
                        await self.bot.db.execute('INSERT INTO nicks_op(guild_id, user_id) VALUES($1, $2)', interaction.guild.id, interaction.user.id)
                        self.bot.nicks_op[f'{interaction.user.id} - {interaction.guild.id}'] = interaction.user.id
                        await self.bot.db.execute("DELETE FROM nicknames WHERE user_id = $1 AND guild_id = $2", interaction.user.id, interaction.guild.id)
                        return await interaction.message.edit(content=_("{0} Alright. I won't be logging your nicknames anymore in this server!").format(self.bot.settings['emojis']['misc']['white-mark']),  # type: ignore
                                                              view=None)
                    else:
                        await self.bot.db.execute('DELETE FROM nicks_op WHERE guild_id = $1 AND user_id = $2', interaction.guild.id, interaction.user.id)
                        self.bot.nicks_op.pop(f'{interaction.user.id} - {interaction.guild.id}')
                        return await interaction.message.edit(content=_("{0} You're now opted-in! I'll be logging your nicknames from now on in this server!").format(  # type: ignore
                            self.bot.settings['emojis']['misc']['white-mark']), view=None)
                elif cache is not None:
                    return await interaction.message.edit(content=_("Alright. Not opting you in"), view=None)  # type: ignore
                else:
                    return await interaction.message.edit(content=_("Oh sweet! I'll continue logging your nicknames"), view=None)  # type: ignore
        return await interaction.message.edit(view=None)  # type: ignore

    @commands.command(brief=_("Search the urban dictionary"))
    @commands.guild_only()
    @commands.is_nsfw()
    @locale_doc
    async def urban(self, ctx, *, urban: str):
        _(""" Search for a term in the urban dictionary """)

        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'http://api.urbandictionary.com/v0/define?term={urban}') as r:
                url = await r.json()

        if url is None:
            return await ctx.send(_("No URL found"))

        count = len(url.get('list', []))
        if count == 0:
            return await ctx.send(_("No results were found."))
        options, text_to_send = [], []
        for result in url['list']:
            options.append(f"{result['author']}")
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
            text_to_send.append(text)

        pages = ListPages(ctx, items=text_to_send, options=options)
        await pages.paginate()

    @commands.command(brief=_("Suggest a feature that you'd like to see implemented"), aliases=['idea'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @locale_doc
    async def suggest(self, ctx, *, suggestion: commands.clean_content):
        _(""" Suggest anything you want to see in the server/bot!
        Suggestion will be sent to support server for people to vote.

        *Make sure the suggestion is in English*""")

        if ctx.guild:
            check = CM.get(self.bot, 'blacklist', ctx.guild.id)

            if check and check['type'] == 0:
                return await ctx.send(_("{0} Sorry, but this server is blacklisted from submitting suggestions. "
                                        "If you want to submit a suggestion, please do so in my DMs. Spamming them will result in a blacklist.").format(
                                          self.bot.settings['emojis']['misc']['warn']
                                      ))

        logchannel = self.bot.get_channel(self.bot.settings['channels']['suggestions'])

        if len(suggestion) > 1000:  # type: ignore
            num = len(suggestion) - 1000  # type: ignore
            chars = _('characters') if num != 1 else _('character')
            return await ctx.send(_("{0} Suggestions can only be 1000 characters long. You're {1} {2} over the limit.").format(
                                        self.bot.settings['emojis']['misc']['warn'], num, chars
                                    ))
        elif len(suggestion) < 1000:  # type: ignore
            try:
                await ctx.message.delete()
            except Exception:
                pass
            ids = await self.bot.db.fetch("SELECT suggestion_id FROM suggestions")
            e = discord.Embed(color=self.bot.settings['colors']['embed_color'],
                              title=f"New suggestion from {ctx.author.name} #{len(ids) + 1}",
                              description=f"> {suggestion}", timestamp=discord.utils.utcnow())
            e.set_author(name=ctx.author, icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.display_avatar.url)
            msg = await logchannel.send(embed=e)
            await msg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
            await msg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
            await self.bot.db.execute("INSERT into suggestions(suggestion, suggestion_id, user_id, msg_id) VALUES($1, $2, $3, $4)", suggestion, len(ids) + 1, ctx.author.id, msg.id)
            await self.bot.db.execute("INSERT INTO track_suggestions VALUES($1, $2)", ctx.author.id, len(ids) + 1)
            e = discord.Embed(color=self.bot.settings['colors']['approve_color'], description=_("Your suggestion was successfully submitted in [my support server!]({0}) "
                                                                                                "You'll get notified in your DMs when the suggestion will be approved or denied."
                                                                                                "People can also follow this suggestion using `{1}suggestion track {2}`\n"
                                                                                                "**Suggestion:**\n>>> {3} ").format(self.bot.support, ctx.prefix, len(ids) + 1, suggestion), timestamp=datetime.now(timezone.utc))
            e.set_author(name=_("Suggestion sent as #{0}").format(len(ids) + 1), icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.display_avatar.url)
            return await ctx.send(embed=e)

    @commands.group(brief=_("Track and untrack suggestions"), aliases=['ideas'], invoke_without_command=True)
    @commands.cooldown(1, 15, commands.BucketType.user)
    @locale_doc
    async def suggestion(self, ctx):
        _(""" Base command for tracking suggestions """)
        await ctx.send_help(ctx.command)

    @suggestion.command(name='track', aliases=['t'], brief=_("Track a suggestion"))
    @commands.cooldown(1, 15, commands.BucketType.user)
    @locale_doc
    async def suggestion_track(self, ctx, id: int):
        _(""" Start tracking a suggestion """)

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

    @suggestion.command(name='untrack', aliases=['u'], brief=_("Untrack a suggestion"))
    @commands.cooldown(1, 15, commands.BucketType.user)
    @locale_doc
    async def suggestion_untrack(self, ctx, id: int):
        _(""" Stop tracking a suggestion """)

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

    @commands.group(brief=_("Manage your todo list"), invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def todo(self, ctx):
        _(""" Base command for managing your todo list """)
        await ctx.send_help(ctx.command)

    @todo.command(name='add', brief=_("Add a todo to your list"), aliases=['a'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def todo_add(self, ctx, *, todo: commands.clean_content):
        _(""" Add a todo to your list """)
        check = await self.bot.db.fetchval("SELECT * FROM todos WHERE user_id = $1 AND todo = $2", ctx.author.id, todo)

        if check is not None:
            return await ctx.send(_("{0} You already have that item in your todo list.").format(self.bot.settings['emojis']['misc']['warn']))
        await self.bot.db.execute("INSERT INTO todos(user_id, todo, jump_url, time) VALUES($1, $2, $3, $4)", ctx.author.id, todo, ctx.message.jump_url, datetime.now())
        if len(todo) > 200:  # type: ignore
            todo = todo[:200]
            todo += '...'
        count = await self.bot.db.fetchval("SELECT count(*) FROM todos WHERE user_id = $1", ctx.author.id)
        await ctx.send(_("{0} Added **{1}** to your todo list. You now have **{2}** items in your list.").format(
            self.bot.settings['emojis']['misc']['white-mark'], escape_markdown(todo, as_needed=True), count  # type: ignore
        ))

    @todo.command(name='edit', brief=_("Edit your todo"), aliases=['e'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def todo_edit(self, ctx, pos: int, *, todo: commands.clean_content):
        _(""" Edit your todos """)

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
        if len(todo) > 200:  # type: ignore
            todo = todo[:200]
            todo += '...'
        await ctx.send(_("{0} Successfully edited the item in your todo list with an ID of **{1}** to: **{2}**").format(
            self.bot.settings['emojis']['misc']['white-mark'], pos, escape_markdown(todo, as_needed=True)  # type: ignore
        ))

    @todo.command(name='swap', brief=_("Swap 2 todo's in places"), aliases=['s'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def todo_swap(self, ctx, swap: int, to: int):
        _(""" Swap 2 todo's around. This will swap the time when todos have been added. """)

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

    @todo.command(name='list', aliases=['l'], brief=_("Check your todo list"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def todo_list(self, ctx):
        _(""" Check your todo list """)

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
                          per_page=10,
                          embed_color=ctx.bot.settings['colors']['embed_color'],
                          embed_author=_("{0}'s Todo List").format(ctx.author))
        await paginator.paginate()

    @todo.command(name='info', aliases=['i'], brief=_("Information about your todo item"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def todo_info(self, ctx, pos: int):
        _(""" Get more information about your todo item """)
        todo = await self.bot.db.fetch("SELECT DISTINCT todo, time, jump_url, ROW_NUMBER () OVER (ORDER BY time) FROM todos WHERE user_id = $1 ORDER BY time", ctx.author.id)

        if not todo:
            return await ctx.send(_("{0} You don't have any items in your todo list.").format(self.bot.settings['emojis']['misc']['warn']))

        if pos not in [t['row_number'] for t in todo]:
            return await ctx.send(_("{0} There is no todo item with an id of **{1}** in your todo list.").format(self.bot.settings['emojis']['misc']['warn'], pos))

        e = discord.Embed(color=self.bot.settings['colors']['embed_color'])
        e.set_author(name=_("Information about your todo item"), icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.display_avatar.url)
        dots = '...'
        e.description = _("""**Todo:** {0}\n\n**Todo position:** {1}/{2}\n**Todo added:** {3}\n**Jump url:** [click here to jump]({4})""").format(
            f"{todo[pos-1]['todo']}" if len(todo[pos - 1]['todo']) < 1800 else f"{escape_markdown(todo[pos - 1]['todo'][:1800] + dots)}",
            pos, len(todo), btime.discord_time_format(todo[pos - 1]['time'], 'R'), todo[pos - 1]['jump_url']
        )
        await ctx.send(embed=e)

    @todo.command(name='remove', aliases=['r'], brief=_("Remove a todo from your list"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def todo_remove(self, ctx, *, pos: str):
        _(""" Remove a todo from your list """)
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
        contents = '\n• '.join(f"""{f'{escape_markdown(todos[todo_id-1]["todo"])}' if len(todos[todo_id-1]['todo']) < 150 else f'{escape_markdown(todos[todo_id-1]["todo"][:150] + dots)}'} """ for todo_id in to_remove)
        return await ctx.send(_("{0} Removed **{1}** todo from your todo list:\n• {2}").format(
            self.bot.settings['emojis']['misc']['white-mark'], len(todo_ids), contents
        ))

    @todo.command(aliases=['c'], brief=_("Clear your todos"))
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def clear(self, ctx):
        _(""" Clear your todo list """)

        todos = await self.bot.db.fetch('SELECT * FROM todos WHERE user_id = $1 ORDER BY time', ctx.author.id)
        if not todos:
            return await ctx.send(_("{0} There's nothing to clear. Your todo list is already empty.").format(self.bot.settings['emojis']['misc']['warn']))

        buttons = components.ConfirmationButtons(self.bot, self, ctx.author, command="todos")
        return await ctx.send(_("Are you sure you want to clear **{0}** items from your todo list?").format(len(todos)), view=buttons)

    @commands.command(brief=_("Set your AFK status in the current server"), aliases=['afk'])
    @commands.guild_only()
    @checks.has_voted()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def setafk(self, ctx, *, note: commands.clean_content = "I'm currently AFK"):
        _(""" Set your AFK status in the current server so users who mention you would know that you're AFK """)
        check = CM.get(self.bot, 'afk', f'{ctx.guild.id}, {ctx.author.id}')  # type: ignore
        check1 = CM.get(self.bot, 'afk', f'{ctx.author.id}')  # type: ignore

        if check1:
            return await ctx.send(_("{0} You've set your AFK status globally already.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        if len(note) > 500:  # type: ignore
            note = note[:500]
            note += '...'

        if check is not None:
            await self.bot.db.execute("UPDATE afk SET message = $1 WHERE user_id = $2 AND guild_id = $3", note, ctx.author.id, ctx.guild.id)
            self.bot.afk[f'{ctx.guild.id}, {ctx.author.id}']['note'] = note
            await ctx.send(_("{0} **Changed your AFK state to:** {1}").format(
                self.bot.settings['emojis']['misc']['white-mark'], note
            ))
        else:
            await self.bot.db.execute("INSERT INTO afk(user_id, guild_id, message, time) VALUES($1, $2, $3, $4)", ctx.author.id, ctx.guild.id, note, datetime.utcnow())
            self.bot.afk[f'{ctx.guild.id}, {ctx.author.id}'] = {
                'note': note,
                'time': datetime.utcnow(),
            }

            await ctx.send(_("{0} ** Set your AFK state to:** {1}").format(
                self.bot.settings['emojis']['misc']['white-mark'], note
            ))

    @commands.command(brief=_("Set your AFK status globally"), aliases=['globalafk', 'gafk'])
    @commands.guild_only()
    @checks.has_voted()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def setglobalafk(self, ctx, *, note: commands.clean_content = "I'm currently AFK"):
        _(""" Set your AFK status in all the shared servers with the bot so users who mention you would know that you're AFK """)

        check = CM.get(self.bot, 'afk', f'{ctx.author.id}')  # type: ignore
        check1 = await self.bot.db.fetchval("SELECT count(*) FROM afk WHERE user_id = $1 AND guild_id IS NOT NULL", ctx.author.id)

        if check1 > 0:
            return await ctx.send(_("{0} You first need to unafk yourself in **{1}** servers!").format(
                self.bot.settings['emojis']['misc']['warn'], check1
            ))

        if len(note) > 500:  # type: ignore
            note = note[:500]
            note += '...'

        if check is not None:
            await self.bot.db.execute("UPDATE afk SET message = $1 WHERE user_id = $2", note, ctx.author.id)
            self.bot.afk[f"{str(ctx.author.id)}"]['note'] = note
            await ctx.send(_("{0} **Changed your global AFK state to:** {1}").format(
                self.bot.settings['emojis']['misc']['white-mark'], note
            ))
        else:
            await self.bot.db.execute("INSERT INTO afk(user_id, message, time) VALUES($1, $2, $3)", ctx.author.id, note, datetime.utcnow())
            self.bot.afk[f'{ctx.author.id}'] = {'note': note, 'time': datetime.utcnow()}
            await ctx.send(_("{0} ** Set your global AFK state to:** {1}").format(
                self.bot.settings['emojis']['misc']['white-mark'], note
            ))

    @commands.command(brief=_("See the latest deleted message in a channel."))
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def snipe(self, ctx, *, channel: discord.TextChannel = None):
        _(""" Snipe latest deleted message in the current or mentioned channel """)
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
            e.set_author(name=_("Deleted by {0}").format(name), icon_url=user.avatar.url if user.avatar else user.display_avatar.url)
            e.set_footer(text=_("Deleted {0} in #{1}").format(btime.human_timedelta(snipe['deleted_at']), channel.name))
            await ctx.send(embed=e)

    # toggle commands for nicknames and snipes
    @commands.group(brief=_("Toggle your data logging"), invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def toggle(self, ctx):
        _(""" Base command for toggling your data logging. This only applies to snipes, nicknames """)
        await ctx.send_help(ctx.command)

    @toggle.command(brief=_("Toggle your snipes logging"), aliases=['snipe'], name='snipes')
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def toggle_snipes(self, ctx):
        _(""" Toggle your snipes (deleted messages) logging
        This applies to all the servers we share """)
        check = CM.get(self.bot, 'snipes_op', ctx.author.id)

        buttons = components.ConfirmationButtons(self.bot, self, ctx.author, command="snipes")

        if check is None:
            return await ctx.send(_("Are you sure you want to opt-out? Once you'll do that, I won't log your deleted messages in my snipe command."), view=buttons)
        else:
            return await ctx.send(_("Are you sure you want to opt-in? Once you'll do that I'll start logging your snipes to my cache."), view=buttons)

    @toggle.command(brief=_("Toggle your nicknames logging"), aliases=['nicks'], name='nicknames')
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def toggle_nicknames(self, ctx):
        _(""" Toggle your nicknames logging
        This applies to all the servers we share """)
        check = CM.get(self.bot, 'nicks_op', f'{ctx.author.id} - {ctx.guild.id}')  # type: ignore

        buttons = components.ConfirmationButtons(self.bot, self, ctx.author, command="nicknames")

        if check is None:
            return await ctx.send(_("Are you sure you want to opt-out? Once you'll do that, I won't be logging nickname changes from you in this server."), view=buttons)
        else:
            return await ctx.send(_("Are you sure you want to opt-in? Once you'll do that I'll start logging your nicknames again."), view=buttons)

    @commands.command(brief=_("Create a poll"), aliases=['poll'])
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def createpoll(self, ctx, channel: Optional[discord.TextChannel], *, questions_and_answers: str):
        _(""" Create a poll with upto 10 options.
        Separate the options with a `|` between them """)

        next_question = "|" if "|" in questions_and_answers else None
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
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.display_avatar.url)

        channel = channel or ctx.channel
        msg = await channel.send(embed=embed, content=_('New poll created by **{0}**').format(ctx.author))
        for reaction, x in reactions:
            await msg.add_reaction(reaction)

        if channel == ctx.channel:
            await ctx.send(_("{0} Successfully created poll in this channel!").format(
                self.bot.settings['emojis']['misc']['white-mark']
            ))
        else:
            await ctx.send(_("{0} Successfully created poll in {1}!").format(
                self.bot.settings['emojis']['misc']['white-mark'], channel.mention
            ))

    @commands.command(brief=_("Get lyrics of a song."), aliases=['song'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def lyrics(self, ctx, *, song: str):
        _(""" Get a lyrics of a song """)

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

    @commands.group(brief=_("Manage your reminders"), aliases=['reminds', 'rm', 'reminder', 'remindme'], invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def remind(self, ctx, *, remind: btime.UserFriendlyTime(commands.context, default="\u2026")):
        _(""" Create a reminder for yourself. Example usage: `remind 1h do homework` """)

        try:
            await self.create_reminder(ctx, remind.arg, remind.dt)
            time = btime.human_timedelta(remind.dt, source=ctx.message.created_at)
            await ctx.send(_("Alright, reminding you in {0}: {1}").format(time, remind.arg))
        except AttributeError:
            return

    @remind.command(brief=_("A list with your reminders"), name='list')
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def remind_list(self, ctx):
        _(""" Check your reminders list """)
        check_reminders = CM.get(self.bot, 'reminders', ctx.author.id)

        if not check_reminders:
            return await ctx.send(_("{0} You have no reminders.").format(self.bot.settings['emojis']['misc']['warn']))

        reminders = []
        for result in check_reminders:
            when = btime.discord_time_format(check_reminders[result]['time'], source='R')
            content = check_reminders[result]['content']
            reminders.append(_("`[{0}]` Reminding **{1}**\n{2}\n").format(result, when, content[:150] + '...' if len(content) > 150 else content))

        paginator = Pages(ctx,
                          entries=reminders,
                          per_page=10,
                          embed_color=ctx.bot.settings['colors']['embed_color'],
                          embed_author=_("{0}'s Reminders").format(ctx.author))
        await paginator.paginate()

    @remind.command(brief=_("Remove a reminder"), name='remove')
    @commands.cooldown(1, 5, commands.BucketType.user)
    @locale_doc
    async def reminder_remove(self, ctx, reminder: str):
        _(""" Remove an unwanted reminder """)
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
