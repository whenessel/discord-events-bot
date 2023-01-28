
import random
import enum
import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands import Context

from helpers import checks


class TimeFeedback(discord.ui.Modal, title='TimeFeedback'):
    minutes = discord.ui.TextInput(
        label='Сколько времени в минутах?',
        style=discord.TextStyle.short,
        placeholder='0',
        required=True,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f'Событие завершенно, {self.minutes.value} минут затраченно!', ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)


class EventAction(discord.ui.View):
    def __init__(self, event: int):
        super().__init__()
        self.value = None
        self.event = event

    @discord.ui.button(label='Завершить', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = 'Завершить'

        modal = TimeFeedback()

        await interaction.response.send_modal(modal)
        await modal.wait()

        self.stop()

    @discord.ui.button(label='Отменить', style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = 'Отменить'
        self.stop()


class EventSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label='Чейн', value='0', description='Простой чейн боссов.'),
            discord.SelectOption(label='Сложный чейн', value='1', description='Чейн из 1 и более сложныйх боссов.'),
            discord.SelectOption(label='Пробужденный босс', value='2', description='Пробужденный босс.'),
        ]
        super().__init__(
            placeholder="Выбор события...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):

        result_embed = discord.Embed(color=0x9C84EF)
        # result_embed.set_author(
        #     name=interaction.user.name,
        #     icon_url=interaction.user.avatar.url
        # )

        user_choice = self.values[0]
        event = list(filter(lambda x: x.value == user_choice, self.options))[0]


        result_embed.set_author(name=f'Открыто событие: "{event.label}"',
                                icon_url=interaction.user.avatar.url)

        result_embed.description = f'**Лидер:** {interaction.user.nick}\n' \
                                   f'**Описание:** {event.description}\n'

        # result_embed.set_footer(text='----- FOTER HERE -------')
        result_embed.set_footer(text='✅ - присутствовал\n'
                                     '⏲ - опоздал\n'
                                     '⚔:️- вары (только для РЛ)')

        buttons = EventAction(event=event)

        await interaction.response.edit_message(embed=result_embed, content=None, view=buttons)
        await interaction.message.add_reaction('✅')
        await interaction.message.add_reaction('⏲️')
        await interaction.message.add_reaction('⚔️')



class EventSelectView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(EventSelect())


class Event(commands.Cog, name='event'):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name='event',
        description='Создание события для получения ДКП очков.'
    )
    @checks.not_blacklisted()
    async def do_event(self, context: Context) -> None:
        """
        Play the rock paper scissors game against the bot.

        :param context: The hybrid command context.
        """
        view = EventSelectView()
        await context.send('Выберите тип события...', view=view)


async def setup(bot):
    await bot.add_cog(Event(bot))
