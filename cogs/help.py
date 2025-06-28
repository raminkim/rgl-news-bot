from discord.ext import commands
import discord

class GeneralHelp(commands.Cog):
    """모든 Cog의 명령어를 한눈에 보여주는 도움말 Cog입니다."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='도움', help='모든 명령어를 보여줍니다.')
    async def show_help(self, ctx: commands.Context):
        """'/도움' 명령어 실행 시 호출되어, 봇에 등록된 모든 명령어를 Embed로 출력합니다."""

        embed = discord.Embed(
            title='📚 명령어 목록',
            description='아래는 사용 가능한 명령어와 간단한 설명입니다.',
            color=0x1E90FF
        )

        # 명령어를 알파벳순으로 정렬해 가독성 향상
        for command in sorted(self.bot.commands, key=lambda c: c.name):
            # 표시 제외 조건: 숨김 처리된 명령어나 내부용
            if command.hidden:
                continue

            # 내부적으로 제거했지만 혹시 남아있을 수 있는 기본 help 제외
            if command.name == 'help':
                continue

            # /도움 자신은 목록에 포함하지 않음
            if command.name == '도움':
                continue

            # 명령어 시그니처(필수·옵션 인자) 포함해 가독성 향상
            signature = f" {command.signature}" if command.signature else ""

            help_text = command.help or '설명이 등록되지 않았습니다.'
            embed.add_field(name=f'/{command.name}{signature}', value=help_text, inline=False)

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """봇이 Cog를 로드할 때 호출됩니다."""
    await bot.add_cog(GeneralHelp(bot)) 