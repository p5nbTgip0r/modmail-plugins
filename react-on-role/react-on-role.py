import datetime

import discord
from discord.ext import commands
import motor.motor_asyncio

from core import checks
from core.models import PermissionLevel


class ReactOnRole(commands.Cog):
    db: motor.motor_asyncio.AsyncIOMotorCollection

    def __init__(self, bot: commands.bot):
        self.bot = bot
        self.db = bot.api.get_plugin_partition(self)

    async def get_introduction_emote(self):
        config = await self.db.find_one({'_id': 'config'}) or {}
        emote = config.get('introduction_emote')
        if emote is not None:
            return str(emote)

    async def get_introduction_channel(self):
        config = await self.db.find_one({'_id': 'config'}) or {}
        channel = config.get('introduction_channel')
        if channel is not None:
            return int(channel)

    async def get_monitored_roles(self):
        config = await self.db.find_one({'_id': 'config'}) or {}
        return config.get('monitored_roles', [])

    async def is_monitored_role(self, role: int):
        config = await self.db.find_one({'_id': 'config'}) or {}
        monitored_roles = config.get('monitored_roles', [])
        return str(role) in monitored_roles

    async def find_introduction_message(self, member: discord.Member):
        channel = await self.get_introduction_channel()
        if channel is None:
            print("Could not get introduction channel. Make sure it is set")
            return None
        channel = member.guild.get_channel(channel)
        last_message: discord.Message = await channel.history(limit=200).get(author__id=member.id)
        return last_message

    @checks.has_permissions(PermissionLevel.MODERATOR)
    @commands.command()
    async def introemote(self, ctx, emoji: str):
        """Sets the introduction emote to react with"""
        await self.db.find_one_and_update(
            {'_id': 'config'},
            {'$set': {'introduction_emote': emoji}},
            upsert=True
        )
        await ctx.send('Changed introduction emote to \'' + emoji + '\'')

    @checks.has_permissions(PermissionLevel.MODERATOR)
    @commands.command()
    async def introchannel(self, ctx, channel: discord.TextChannel):
        """Sets the introduction channel"""
        await self.db.find_one_and_update(
            {'_id': 'config'},
            {'$set': {'introduction_channel': str(channel.id)}},
            upsert=True
        )
        await ctx.send('Changed introduction channel to ' + channel.mention.__str__())

    @checks.has_permissions(PermissionLevel.MODERATOR)
    @commands.command()
    async def baserole(self, ctx, role: int):
        """Toggles whether a role is considered a base role"""
        role_obj = ctx.guild.get_role(role)
        is_monitored = await self.is_monitored_role(role)
        suffix = "role `{}` (id: `{}`)".format(role_obj.name, role)

        if is_monitored:
            await self.db.find_one_and_update(
                {'_id': 'config'},
                {'$pull': {'monitored_roles': str(role)}},
                upsert=True
            )
            await ctx.send('Monitoring disabled for ' + suffix)
        else:
            await self.db.find_one_and_update(
                {'_id': 'config'},
                {'$addToSet': {'monitored_roles': str(role)}},
                upsert=True
            )
            await ctx.send('Monitoring enabled for ' + suffix)

    @checks.has_permissions(PermissionLevel.MODERATOR)
    @commands.command()
    async def clearbaseroles(self, ctx):
        """Clears the list of base roles"""
        await self.db.find_one_and_update(
            {'_id': 'config'},
            {'$set': {'monitored_roles': []}},
            upsert=True
        )
        await ctx.send('Cleared all base/monitored roles')

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        role_to_id = lambda role: str(role.id)
        before_roles = list(map(role_to_id, before.roles))
        after_roles = list(map(role_to_id, after.roles))
        # find newly added roles
        added_roles = list(filter(lambda role: role not in before_roles, after_roles))
        monitored_roles = await self.get_monitored_roles()
        if any(item in added_roles for item in monitored_roles):
            # monitored role was added to this user
            message = await self.find_introduction_message(after)
            if message is None:
                print("Could not find introduction message for user " + after.id.__str__())
                return
            emote = await self.get_introduction_emote()
            if emote is None:
                print("Could not find introduction emote. Make sure it is set")
                return
            await message.add_reaction(emote)


def setup(bot):
    bot.add_cog(ReactOnRole(bot))
