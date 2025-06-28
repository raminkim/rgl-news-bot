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

        # Cog 이름을 한국어로 매핑
        cog_name_mapping = {
            "NewsCommand": "📰 뉴스 기능",
            "HelloCommand": "🎮 일반 기능",
            "GeneralHelp": "❓ 도움말"
        }

        # Cog별로 명령어 그룹화
        for cog_name, cog in self.bot.cogs.items():
            # 해당 Cog의 명령어 목록 가져오기
            cog_commands = []
            
            for command in cog.get_commands():
                # 표시 제외 조건: 숨김 처리된 명령어나 내부용
                if command.hidden:
                    continue

                # 내부적으로 제거했지만 혹시 남아있을 수 있는 기본 help 제외
                if command.name == 'help':
                    continue

                # /도움 자신은 목록에 포함하지 않음 (별도 처리)
                if command.name == '도움':
                    continue

                cog_commands.append(command)

            # 해당 Cog에 표시할 명령어가 있을 때만 카테고리 추가
            if cog_commands:
                category_name = cog_name_mapping.get(cog_name, f"📂 {cog_name}")
                
                # 명령어를 알파벳순으로 정렬
                cog_commands.sort(key=lambda c: c.name)
                
                # 카테고리별 명령어 목록 생성
                command_list = []
                for command in cog_commands:
                    signature = f" {command.signature}" if command.signature else ""
                    help_text = command.help or '설명이 등록되지 않았습니다.'
                    command_list.append(f"**/{command.name}{signature}**\n{help_text}")

                embed.add_field(
                    name=category_name, 
                    value="\n\n".join(command_list), 
                    inline=False
                )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """봇이 Cog를 로드할 때 호출됩니다."""
    await bot.add_cog(GeneralHelp(bot)) 