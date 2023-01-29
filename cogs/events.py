
import random
import enum
import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands import Context, Bot

from helpers import checks


class SingletonDecorator:
    def __init__(self,klass):
        self.klass = klass
        self.instance = None
    def __call__(self,*args,**kwds):
        if self.instance == None:
            self.instance = self.klass(*args,**kwds)
        return self.instance


class GameEvent(enum.Enum):
    CHAIN = ('0', 50, 'Чейн', 'Простой чейн боссов.')
    ONETIME = ('1', 25, 'Разовый', 'Чейн из 1 и более сложныйх боссов.')
    AWAKENED = ('2', 25, 'Пробужденный', 'Пробужденный босс.')

    def __init__(self, id, point, title, description):
        self.id = id
        self.point = point
        self.title = title
        self.description = description

    @classmethod
    def by_id(cls, id):
        for _, member in cls.__members__.items():
            if member.id == id:
                return member


class EventStatus(enum.IntEnum):
    IN_PROGRES = 0
    SUCCESS = 1
    CANCEL = 2


@SingletonDecorator
class EventManager:
    bot: Bot
    _data: dict = {}

    done_reactions = ['✅', ]
    late_reactions = ['⏲️', ]

    member_reactions = done_reactions + late_reactions
    limited_reactions = ['⚔️', ]

    reactions = member_reactions + limited_reactions

    COLOR_GREEN = 0x57F287
    COLOR_RED = 0xED4245
    COLOR_AQUA = 0x3498DB

    def __init__(self, bot: Bot):
        self.bot = bot

    def create_event_by_message(self, ctx: Context, message: discord.Message, event: GameEvent):
        self._data[message.id] = {
            'message': message,
            'event': event,
            'status': EventStatus.IN_PROGRES,
            'author': ctx.author,
            'users': {
                ctx.author: None
            },
            'extra': {'war': False}
        }

    def close_event_by_message(self, ctx: Context, message: discord.Message, status: EventStatus):
        data = self._data[message.id]
        data['status'] = status

    def check_limited_reaction(self, message: discord.Message, user: discord.User, reaction: discord.Reaction) -> bool:
        if reaction.emoji in self.limited_reactions:
            return True
        return False

    def check_user_reaction(self, message: discord.Message, user: discord.User, reaction: discord.Reaction) -> bool:
        if reaction.emoji in self.member_reactions:
            return True
        return False

    def check_user_reacted(self, message: discord.Message, user: discord.User, reaction: discord.Reaction) -> [discord.Reaction, None]:
        data = self._data[message.id]['users']
        user_reaction = data.get(user)
        return user_reaction

    def add_reaction(self, message: discord.Message, user: discord.User, reaction: discord.Reaction):
        data = self._data[message.id]
        users = data['users']
        users[user] = reaction

    def remove_reaction(self, message: discord.Message, user: discord.User, reaction: discord.Reaction):
        data = self._data[message.id]
        users = data['users']
        users[user] = None

    def get_reacted_users_for_message(self, message: discord.Message):
        data = self._data[message.id]['users']
        users_done = [user for user, reaction in data.items() if reaction.emoji in self.done_reactions]
        users_late = [user for user, reaction in data.items() if reaction.emoji in self.late_reactions]
        return users_done, users_late

    def get_extra_for_message(self, message: discord.Message):
        data = self._data[message.id]
        return data['extra']

    def event_description_embed_for_message(self, message: discord.Message) -> discord.Embed:
        data = self._data[message.id]
        author = data['author']
        event = data['event']
        status = data['status']
        color = self.COLOR_AQUA

        if status == EventStatus.SUCCESS:
            color = self.COLOR_GREEN
        elif status == EventStatus.CANCEL:
            color = self.COLOR_RED

        embed = discord.Embed(color=color)
        embed.set_author(name=f'РЛ: {author.display_name}', icon_url=f'{author.avatar.url}')
        embed.set_footer(text='✅ - присутствовал\n⏲ - опоздал\n⚔:️- вары (только для РЛ)')

        embed.description = f'**Созданно событие:** "{event.title}"\n' \
                            f'**Описание:** *{event.description}*\n' \
                            f'**Количество очков:** {event.point}'

        return embed

    def event_result_embed_for_message(self, message: discord.Message) -> discord.Embed:
        data = self._data[message.id]
        author = data['author']
        event = data['event']
        status = data['status']
        war = data["extra"]["war"]
        color = self.COLOR_AQUA
        users_done = [user for user, reaction in data['users'].items() if reaction and reaction.emoji in self.done_reactions]
        users_late = [user for user, reaction in data['users'].items() if reaction and reaction.emoji in self.late_reactions]

        if status == EventStatus.SUCCESS:
            color = self.COLOR_GREEN
        elif status == EventStatus.CANCEL:
            color = self.COLOR_RED

        embed = discord.Embed(color=color)
        embed.set_author(name=f'РЛ: {author.display_name}', icon_url=f'{author.avatar.url}')
        embed.set_footer(text='Дополнительное описание... Время или имя босса... ХЗ пока что...')

        embed.description = f'**Созданно событие:** "{event.title}"\n' \
                            f'**Описание:** *{event.description}*\n' \
                            f'**Количество очков:** {event.point}\n' \
                            f'**Вары:** {"Да" if war else "Нет"} (не активно)'

        if status == EventStatus.SUCCESS:
            embed.add_field(name=f'Присутствовали', value='\n'.join([user.display_name for user in users_done]), inline=True)
            embed.add_field(name=f'Опоздали', value='\n- '.join([user.display_name for user in users_late]), inline=True)

        elif status == EventStatus.CANCEL:
            embed.add_field(name='', value='**Событие было отменено.**')

        embed.add_field(name='', value='')
        return embed

class EventButton(discord.ui.Button):
    SUCCESS = 0
    CANCEL = 1

    def __init__(self, action: int, *args, ctx: Context = None, em: EventManager = None, **kwargs):
        self.action = action
        super().__init__(*args, **kwargs)
        self.ctx = ctx
        self.em = em

    async def callback(self, interaction: discord.Interaction):
        message: discord.Message = interaction.message
        if self.action == self.SUCCESS:
            self.em.close_event_by_message(self.ctx, message, EventStatus.SUCCESS)
        elif self.action == self.CANCEL:
            self.em.close_event_by_message(self.ctx, message, EventStatus.CANCEL)

        await interaction.response.edit_message(content=None, view=None)
        self.view.stop()


class EventSelect(discord.ui.Select):
    def __init__(self, ctx: Context, em: EventManager):
        self.ctx = ctx
        self.em = em

        options = [discord.SelectOption(label=event.title, value=event.id, description=event.description)
                   for event in list(GameEvent)]

        super().__init__(
            placeholder="Выбор события...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        message: discord.Message = interaction.message

        user_choice = self.values[0]
        # event = list(filter(lambda x: x.value == user_choice, self.options))[0]
        game_event = GameEvent.by_id(user_choice)

        self.em.create_event_by_message(ctx=self.ctx, message=message, event=game_event)
        embed = self.em.event_description_embed_for_message(message=message)

        await interaction.response.edit_message(embed=embed, content=None, view=None)
        self.view.stop()


class EventAction(discord.ui.View):
    CANCEL = 0
    SUCCESS = 1

    def __init__(self, *args, em: EventManager = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.em = em
        self.value = None

    @discord.ui.button(label="Завершить", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = self.SUCCESS
        self.stop()

    @discord.ui.button(label="Остановить", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = self.CANCEL
        self.stop()


class Event(commands.Cog, name='event'):
    def __init__(self, bot):
        self.bot = bot
        self.em = EventManager(self.bot)

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
        choice_view = discord.ui.View(timeout=None)
        choice_view.add_item(EventSelect(ctx=context, em=self.em))

        message = await context.send(content=None, view=choice_view)

        await choice_view.wait()

        button_view = discord.ui.View(timeout=None)
        button_view.add_item(EventButton(action=EventButton.SUCCESS, ctx=context, em=self.em, label='Завершить', style=discord.ButtonStyle.green))
        button_view.add_item(EventButton(action=EventButton.CANCEL, ctx=context, em=self.em, label='Отменить', style=discord.ButtonStyle.red))

        await message.edit(view=button_view)

        for event_reaction in self.em.reactions:
            await message.add_reaction(event_reaction)

        await button_view.wait()

        embed = self.em.event_result_embed_for_message(message)
        await message.edit(embed=embed)

        await message.clear_reactions()


    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):

        message: discord.Message = reaction.message
        guild: discord.Guild = self.bot.get_guild(message.guild.id)

        if not guild:  # In DM, ignore
            return

        if user.bot:  # Ignore Bot reaction
            return

        user_reaction = self.em.check_user_reaction(message, user, reaction)

        user_reacted = self.em.check_user_reacted(message, user, reaction)

        if user_reaction and not user_reacted:
            self.em.add_reaction(message, user, reaction)
        elif user_reaction and user_reacted:  # Re-reacted
            self.em.remove_reaction(message, user, reaction)
            await message.remove_reaction(user_reacted.emoji, user)
            self.em.add_reaction(message, user, reaction)
        elif not user_reaction:
            limited_reaction = self.em.check_limited_reaction(message, user, reaction)
            await message.remove_reaction(reaction.emoji, user)

        # print(f'ADD REACT ({reaction.emoji}): {user.id} ({user.name} aka {user.nick}) for {message.id} | {user_reacted}')
        # print(f"\t{self.em._data[message.id]}")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.Member):
        emoji = str(reaction.emoji)
        message: discord.Message = reaction.message
        guild: discord.Guild = self.bot.get_guild(message.guild.id)

        if not guild:  # In DM, ignore
            return

        if user.bot:  # Ignore Bot reaction
            return

        user_reaction = self.em.check_user_reaction(message, user, reaction)
        if user_reaction:
            self.em.remove_reaction(message, user, reaction)
            await message.remove_reaction(emoji, user)

        # print(f'REMOVE REACT ({emoji}): {user.id} ({user.name} aka {user.nick}) for {message.id}')
        # print(f"\t{self.em._data[message.id]}")


async def setup(bot):
    await bot.add_cog(Event(bot))
