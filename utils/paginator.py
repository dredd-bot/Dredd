"""Dredd, discord bot
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

import asyncio

import discord
from discord.ext.commands import Paginator as CommandPaginator
from discord.ext import commands
from utils.checks import buttons_disable
from contextlib import suppress
from utils import i18n


class CannotPaginate(Exception):
    pass


# noinspection PyUnusedLocal
class ButtonPaginator(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=300)
        self.value = None
        self.pages = pages

    async def interaction_check(self, interaction) -> bool:
        if interaction.user and interaction.user.id == self.pages.author.id or await self.pages.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message(_('This pagination menu cannot be controlled by you, sorry!'), ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        with suppress(Exception):
            await self.pages.message.edit(view=self)

    @discord.ui.button(label="First", style=discord.ButtonStyle.green, disabled=True, row=0)
    async def to_first(self, button, interaction):
        i18n.current_locale.set(self.pages.bot.translations.get(interaction.guild.id, 'en_US'))
        self.children = buttons_disable(current_page=self.pages.current_page, max_pages=self.pages.maximum_pages, buttons=self)
        await self.pages.first_page()

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.green, row=0)
    async def one_back(self, button, interaction):
        i18n.current_locale.set(self.pages.bot.translations.get(interaction.guild.id, 'en_US'))
        self.children = buttons_disable(current_page=self.pages.current_page, max_pages=self.pages.maximum_pages, buttons=self)
        await self.pages.previous_page()

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, row=0)
    async def stop(self, button, interaction):
        await self.pages.stop_pages()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.green, row=0)
    async def one_forward(self, button, interaction):
        i18n.current_locale.set(self.pages.bot.translations.get(interaction.guild.id, 'en_US'))
        self.children = buttons_disable(current_page=self.pages.current_page, max_pages=self.pages.maximum_pages, buttons=self)
        await self.pages.next_page()

    @discord.ui.button(label="Last", style=discord.ButtonStyle.green, disabled=True, row=0)
    async def to_last(self, button, interaction):
        i18n.current_locale.set(self.pages.bot.translations.get(interaction.guild.id, 'en_US'))
        self.children = buttons_disable(current_page=self.pages.current_page, max_pages=self.pages.maximum_pages, buttons=self)
        await self.pages.last_page()

    @discord.ui.button(label="Home", style=discord.ButtonStyle.blurple)
    async def show_help(self, button, interaction):
        i18n.current_locale.set(self.pages.bot.translations.get(interaction.guild.id, 'en_US'))
        await self.pages.help_command.send_bot_help(self.pages.help_command.get_bot_mapping())


class Pages:
    """Implements a paginator that queries the user for the
    pagination interface.
    Pages are 1-index based, not 0-index based.
    If the user does not reply within 1 minute then the pagination
    interface exits automatically.
    Parameters
    ------------
    ctx: Context
        The context of the command.
    entries: List[str]
        A list of entries to paginate.
    per_page: int
        How many entries show up per page.
    show_entry_count: bool
        Whether to show an entry count in the footer.
    Attributes
    -----------
    embed: discord.Embed
        The embed object that is being used to send pagination info.
        Feel free to modify this externally. Only the description,
        footer fields, and colour are internally modified.
    permissions: discord.Permissions
        Our permissions for the channel.
    """
    def __init__(self, ctx, *, entries, per_page=12, show_entry_count=True, embed_color=discord.Color.blurple(), title=None, thumbnail=None, footericon=None, footertext=None, author=None, delete_after=None, embed_author=None,
                 home=None, use_dropdown=None, options=None, **kwargs):
        self.bot = ctx.bot
        self.entries = entries
        self.message = ctx.message
        self.channel = ctx.channel
        self.context = ctx
        self.use_dropdown = use_dropdown
        self.options = options
        self.author = author or ctx.author
        self.thumbnail = thumbnail
        self.footericon = footericon
        self.footertext = footertext
        self.home = home
        self.title = title
        self.embed_author = embed_author
        self.delete_after = delete_after or 300
        self.per_page = per_page
        pages, left_over = divmod(len(self.entries), self.per_page)
        if left_over:
            pages += 1
        self.maximum_pages = pages
        self.embed = discord.Embed(colour=embed_color)
        self.paginating = True
        self.show_entry_count = show_entry_count
        self.children = None
        self.help_command = kwargs.get("help_command", None)

        if ctx.guild is not None:
            self.permissions = self.channel.permissions_for(ctx.guild.me)
        else:
            self.permissions = self.channel.permissions_for(ctx.bot.user)

        if not self.permissions.embed_links:
            raise commands.BotMissingPermissions(['embed_links'])

        if not self.permissions.send_messages:
            return

    def get_page(self, page):
        base = (page - 1) * self.per_page
        return self.entries[base:base + self.per_page]

    def get_content(self, entries, page, *, first=False):
        return None

    def get_embed(self, entries, page, *, first=False):
        self.prepare_embed(entries, page, first=first)
        return self.embed

    def prepare_embed(self, entries, page, *, first=False):
        p = [f'{entry}' for index, entry in enumerate(entries, 1 + ((page - 1) * self.per_page))]

        if self.maximum_pages > 1 and not self.footertext:
            if self.show_entry_count:
                text = _('Showing page {page}/{maximum_pages} ({entries} entries)').format(page=page, maximum_pages=self.maximum_pages, entries=len(self.entries))
            else:
                text = _('Showing page {page}/{maximum_pages}').format(page=page, maximum_pages=self.maximum_pages)

            self.embed.set_footer(text=text)

        if self.footertext:
            self.embed.set_footer(text=self.footertext)

        if self.paginating and first:
            p.append('')

        self.embed.description = ''.join(p)
        self.embed.title = self.title or discord.Embed.Empty
        if self.thumbnail:
            self.embed.set_thumbnail(url=self.thumbnail)
        if self.embed_author:
            self.embed.set_author(icon_url=self.author.avatar.url if self.author.avatar else self.author.display_avatar.url, name=self.embed_author)

    async def show_page(self, page, *, first=False):
        self.current_page = page
        entries = self.get_page(page)
        content = self.get_content(entries, page, first=first)
        embed = self.get_embed(entries, page, first=first)
        if not self.use_dropdown or len(self.options) > 25:
            buttons = ButtonPaginator(self)
            buttons.children = buttons_disable(current_page=page, max_pages=self.maximum_pages, buttons=buttons)
            if not self.home:
                buttons.remove_item(buttons.show_help)  # type: ignore
            if self.maximum_pages <= 2:
                buttons.remove_item(buttons.to_first)  # type: ignore
                buttons.remove_item(buttons.to_last)  # type: ignore
            if self.maximum_pages == 1:
                buttons.remove_item(buttons.one_back)  # type: ignore
                buttons.remove_item(buttons.one_forward)  # type: ignore
        else:
            from utils import components
            buttons = components.DropdownView(self.context,
                                              _("Please choose an option..."),
                                              [discord.SelectOption(label=e, value=x) for x, e in enumerate(self.options, start=1)],  # type: ignore
                                              cls=self)

        if not first:
            return await self.message.edit(content=content, embed=embed, view=buttons)
        self.message = await self.context.send(content=content, embed=embed, view=buttons)

    async def checked_show_page(self, page):
        if page != 0 and page <= self.maximum_pages:
            await self.show_page(page)

    async def first_page(self):
        """goes to the first page"""
        await self.show_page(1)

    async def last_page(self):
        """goes to the last page"""
        await self.show_page(self.maximum_pages)

    async def next_page(self):
        """goes to the next page"""
        await self.checked_show_page(self.current_page + 1)

    async def previous_page(self):
        """goes to the previous page"""
        await self.checked_show_page(self.current_page - 1)

    async def show_current_page(self):
        if self.paginating:
            await self.show_page(self.current_page)

    async def main_help(self):
        """ Goes to the main page of help """
        await self.stop_pages()
        await self.context.send_help()

    async def numbered_page(self):
        """lets you type a page number to go to"""
        to_delete = [await self.channel.send('What page do you want to go to?')]

        def message_check(m):
            return m.author == self.author and \
                self.channel == m.channel and \
                m.content.isdigit()

        try:
            msg = await self.bot.wait_for('message', check=message_check, timeout=30.0)
        except asyncio.exceptions.TimeoutError:
            to_delete.append(await self.channel.send('Took too long.'))
            await asyncio.sleep(5)
        else:
            page = int(msg.content)
            to_delete.append(msg)
            if page != 0 and page <= self.maximum_pages:
                await self.show_page(page)
            else:
                to_delete.append(await self.channel.send(f'Invalid page given. ({page}/{self.maximum_pages})'))
                await asyncio.sleep(5)

        try:
            await self.channel.delete_messages(to_delete)
        except Exception:
            pass

    async def show_help(self):
        """shows this message"""
        messages = ['Welcome to the interactive paginator!\n', 'This interactively allows you to see pages of text by navigating with '
                                                               'reactions. They are as follows:\n']

        embed = self.embed.copy()
        embed.clear_fields()
        embed.description = '\n'.join(messages)
        embed.set_footer(text='We were on page before this message.')
        await self.message.edit(content=None, embed=embed)

        async def go_back_to_current_page():
            await asyncio.sleep(60.0)
            await self.show_current_page()

        self.bot.loop.create_task(go_back_to_current_page())

    async def stop_pages(self):
        """stops the interactive pagination session"""
        with suppress(Exception):
            await self.message.delete()
        self.paginating = False

    async def paginate(self):
        """Actually paginate the entries and run the interactive loop if necessary."""
        await self.show_page(1, first=True)


class FieldPages(Pages):
    """Similar to Pages except entries should be a list of
    tuples having (key, value) to show as embed fields instead.
    """
    def __init__(self, ctx, *, entries, per_page=12, show_entry_count=True, title, thumbnail, footericon, footertext, embed_color=discord.Color.blurple()):
        super().__init__(ctx, entries=entries, per_page=per_page, show_entry_count=show_entry_count, title=title, thumbnail=thumbnail, footericon=footericon, footertext=footertext, embed_color=embed_color)

    def prepare_embed(self, entries, page, *, first=False):
        self.embed.clear_fields()

        for key, value in entries:
            self.embed.add_field(name=key, value=value, inline=False)

        self.embed.title = self.title

        if self.maximum_pages > 1:
            text = f' ({page}/{self.maximum_pages})'
            self.embed.title = self.title + text

        self.embed.set_footer(icon_url=self.footericon, text=self.footertext)
        self.embed.set_thumbnail(url=self.thumbnail)


class TextPages(Pages):
    """Uses a commands.Paginator internally to paginate some text."""

    def __init__(self, ctx, text, *, prefix='```ml', suffix='```', max_size=2000, **kwargs):
        paginator = CommandPaginator(prefix=prefix, suffix=suffix, max_size=max_size - 200)
        for line in text.split('\n'):
            paginator.add_line(line)

        super().__init__(ctx, entries=paginator.pages, per_page=1, show_entry_count=False, **kwargs)

    def get_page(self, page):
        return self.entries[page - 1]

    def get_embed(self, entries, page, *, first=False):
        return None

    def get_content(self, entry, page, *, first=False):
        if self.maximum_pages > 1:
            return f'{entry}\nPage {page}/{self.maximum_pages}'
        return entry


class ListPages(Pages):
    def __init__(self, ctx, items, use_dropdown=True, options=None):
        super().__init__(ctx, entries=items, use_dropdown=use_dropdown, options=options, per_page=1)

    def get_page(self, page):
        return self.entries[page - 1]

    def get_embed(self, entries, page, *, first=False):
        return None

    def get_content(self, entry, page, *, first=False):
        if self.maximum_pages > 1 and len(self.options) > 25:
            return _("{0}\n\nPage {1}/{2}").format(entry, page, self.maximum_pages)
        return entry
