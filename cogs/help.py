from discord.ext import commands
import discord
from datetime import datetime


class GeneralHelp(commands.Cog):
    """모든 Cog의 명령어를 한눈에 보여주는 도움말 Cog입니다."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='도움', help='모든 명령어를 보여줍니다.')
    async def show_help(self, ctx: commands.Context):
        """'/도움' 명령어 실행 시 호출되어, 봇에 등록된 모든 명령어를 Embed로 출력합니다."""

        embed = discord.Embed(
            title='📚 전체 명령어 가이드',
            description='아래에서 사용 가능한 모든 명령어를 확인해보세요!',
            color=0x5865F2,
            timestamp=datetime.now()
        )

        if ctx.guild and ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        embed.set_author(name=ctx.bot.user.name, icon_url=ctx.bot.user.avatar.url)
        embed.set_footer(
            text=f"요청자: {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )

        cog_mapping = {
            "NewsCommand": ("📰 뉴스 & 정보", [
                "• `/뉴스확인` - 설정된 게임의 최신 뉴스를 확인합니다.",
                "• `/뉴스채널설정 [게임명]` - 채널별로 게임 뉴스 알림을 설정합니다.",
                "📌 예시: `/뉴스채널설정 발로란트`"
            ]),
            "HelloCommand": ("🎮 일반 기능", [
                "• `/안녕` - 봇이 인사를 합니다.",
                "• `/핑` - 봇의 응답 속도를 확인합니다."
            ]),
            "GeneralHelp": ("❓ 도움말 센터", [
                "• `/도움` - 모든 명령어를 보여줍니다.",
                "📌 예시: `/도움`"
            ]),
            "ScheduleCommand": ("🗓️ 롤 리그 일정", [
                "• `/롤리그 [리그명]` - LoL 경기 일정을 확인합니다.",
                "📌 예시: `/롤리그 LCK`"
            ]),
            "PlayerCommand": ("👤 선수 검색", [
                "• `/선수 [게임명] [선수명]` - 특정 선수의 정보를 조회합니다.",
                "📌 예시: `/선수 발로란트 k1ng`"
            ])
        }

        total_commands = 0

        for cog_name, cog in self.bot.cogs.items():
            cog_display, commands_list = cog_mapping.get(cog_name, (f"📂 {cog_name}", []))

            if commands_list:
                embed.add_field(
                    name=f"{cog_display}",
                    value="\n".join(commands_list),
                    inline=False
                )

                total_commands += len(commands_list)
                embed.add_field(name="", value="", inline=False)

        embed.add_field(name="━" * 20, value="", inline=False)

        embed.add_field(
            name="🔗 추가 정보",
            value=f"• 서버: **{ctx.guild.name if ctx.guild else '개인 메시지'}**\n"
                  f"• 총 명령어 수: **{total_commands}개**\n"
                  f"• 활성화된 모듈: **{len(self.bot.cogs)}개**\n\n"
                  "📮 문의 사항은 관리자에게 연락주세요!",
            inline=False
        )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralHelp(bot))