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

from discord.ext import commands
from discord.interactions import Interaction
from datetime import timedelta
from contextlib import suppress
from typing import Optional


class EditingContext(commands.Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    interaction: Optional[Interaction] = None

    async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None, allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False, replied_user=True),
                   view=None, ephemeral=False, return_message=None, reference=None, edit=True):
        # sourcery no-metrics

        reply = None
        with suppress(KeyError):
            reply = self.bot.cmd_edits[self.message.id]

        if self.interaction is None or (self.interaction.response.responded_at is not None and discord.utils.utcnow() - self.interaction.response.responded_at >= timedelta(minutes=15)):
            if file or files:
                return await super().send(content=content, tts=tts, embed=embed, file=file, files=files, delete_after=delete_after, nonce=nonce, allowed_mentions=allowed_mentions, view=view, reference=reference)
            if reply and edit is True:
                try:
                    return await reply.edit(content=content, embed=embed, delete_after=delete_after, allowed_mentions=allowed_mentions, view=view)
                except discord.errors.NotFound:
                    pass
            if self.message.reference and isinstance(self.message.reference.resolved, discord.Message):
                msg = await self.message.reference.resolved.reply(content=content, tts=tts, embed=embed, file=file, files=files, delete_after=delete_after, nonce=nonce, allowed_mentions=allowed_mentions, view=view)
            else:
                msg = await super().send(content=content, tts=tts, embed=embed, file=file, files=files, delete_after=delete_after, nonce=nonce, allowed_mentions=allowed_mentions, view=view, reference=reference)
        else:
            if return_message or self.interaction.response.is_done() or file or files or allowed_mentions:
                if not self.interaction.response.is_done():
                    await self.interaction.response.defer(ephemeral=ephemeral)

                send = self.interaction.followup.send
            elif not reply:
                send = self.interaction.response.send_message
            else:
                send = self.interaction.response.edit_message
            msg = await send(content, ephemeral=ephemeral, **kwargs)  # type: ignore
        self.bot.cmd_edits[self.message.id] = msg
        return msg
