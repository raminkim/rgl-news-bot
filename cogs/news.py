import discord
import pytz

from discord.ext import commands, tasks
from datetime import datetime

from crawlers.crawling import fetch_news_articles, update_state

class NewsCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.news_channel_id = None  # 설정될 채널 ID
        self.check_interval = 1200  # 20분 (1200초)
        self.news_loop.start()

    def create_news_embed(self, article: dict):
        """
        뉴스 기사를 위한 디스코드 Embed 객체를 생성합니다.

        Args:
            article (dict): 네이버 e스포츠 뉴스 API에서 가져온 기사 데이터.
                필수 키:
                    - title (str): 기사 제목
                    - subContent (str): 요약 내용
                    - linkUrl (str): 기사 URL
                    - thumbnail (str): 썸네일 이미지 URL
                    - createdAt (int): 생성 시각 (밀리초 단위 타임스탬프)
                    - officeName (str): 언론사 이름
                    - rank (int): 순위
                    - hitCount (int): 조회수

        Returns:
            discord.Embed: 제목, 설명, URL, 타임스탬프, 썸네일, 푸터(언론사·순위) 등이 설정된 Embed 객체
        """

        embed = discord.Embed(
            title = article.get('title'),
            description = article.get('subContent'),
            url = article.get('linkUrl'),
            timestamp=datetime.fromtimestamp(article["createdAt"] / 1000, tz=pytz.UTC),
            color=0x1E90FF
        )

        if article['thumbnail']:
            embed.set_thumbnail(url = article['thumbnail'])
        
        embed.add_field(
            name="🏆 순위", 
            value=f"#{article['rank']}", 
            inline=True
        )

        # 1) 원본 밀리초를 초 단위로 변환
        ts_seconds = article['createdAt'] / 1000
        # 2) KST 기준 datetime 객체 생성
        kst = pytz.timezone("Asia/Seoul")
        dt = datetime.fromtimestamp(ts_seconds, tz=kst)

        # 예: "2025-06-22 14:45:10"
        formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        embed.add_field(
            name="⏰ 발행시간", 
            value=formatted,
            inline=False
        )

        return embed
    

    @tasks.loop(seconds=1200)
    async def news_loop(self):
        """
        20분마다 자동으로 새로운 기사를 확인하고,
        설정된 채널로 Embed 메시지를 전송합니다.
        """
        if not self.news_channel_id:
            return

        channel = self.bot.get_channel(self.news_channel_id)
        if channel is None:
            return

        new_articles = await fetch_news_articles()
        if not new_articles:
            return
        
        for art in new_articles:
            embed = self.create_news_embed(art)
            await channel.send(embed=embed)

        update_state(new_articles)

    
    @commands.command(name='뉴스확인', help='즉시 새로운 뉴스를 확인합니다.')
    async def check_news_now(self, ctx):
        """수동으로 뉴스를 확인합니다."""
        await ctx.send("🔍 뉴스를 확인하고 있습니다...")

        try:
            new_articles = await fetch_news_articles()

            if not new_articles:
                await ctx.send("📰 새로운 뉴스가 없습니다.")
                return
        
            await ctx.send(f"📢 새로운 뉴스 {len(new_articles)}개를 발견했습니다!")

            for article in new_articles:
                try:
                    embed = self.create_news_embed(article)
                    await ctx.send(embed=embed)
        
                except Exception as e:
                    await ctx.send(f"❌ 뉴스 전송 중 오류: {e}")
                    continue
            
            update_state(new_articles)
        
        except Exception as e:
            await ctx.send(f"❌ 뉴스 확인 중 오류가 발생했습니다: {e}")


    @commands.command(name='뉴스채널', help='뉴스 알림을 받을 채널을 설정합니다.')
    @commands.has_guild_permissions(manage_channels=True)
    async def set_news_channel(self, ctx, channel: discord.TextChannel = None):
        """뉴스 알림 채널을 설정합니다."""
        if channel is None:
            channel = ctx.channel
        
        embed = discord.Embed(
            title="✅ 뉴스 채널 설정 완료",
            description=f"이제 {channel.mention}에서 뉴스 알림을 받을 수 있습니다!",
            color=0x00ff56,
            timestamp=datetime.now()
        )

        await ctx.send(embed=embed)
        print(f"📡 뉴스 알림 채널 설정: {channel.name} (ID: {channel.id})")

        # ➡️ 여기서 즉시 한번 실행
        new_articles = await fetch_news_articles()
        if new_articles:
            for art in new_articles:
                await ctx.send(embed=self.create_news_embed(art))
            update_state(new_articles)


    @commands.command(name='뉴스도움', help='뉴스 봇 명령어 도움말을 표시합니다.')
    async def news_help(self, ctx):
        embed = discord.Embed(
            title='📖 뉴스봇 명령어',
            color=0x00ff56,
            description="사용 가능한 뉴스 관련 명령어들입니다."
        )

        embed.add_field(
            name='/뉴스확인',
            value='즉시 오늘 날짜의 새로운 뉴스를 확인합니다.',
            inline=False
        )

        embed.add_field(
            name='/뉴스채널 [#채널]',
            value='뉴스 알림을 받을 채널을 설정합니다. (관리자 권한 필요)',
            inline=False
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(NewsCommand(bot))