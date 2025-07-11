import discord
import pytz
from typing import List, Dict, Any, Callable

from discord.ext import commands, tasks
from datetime import date, datetime

from crawlers.news_crawling import lol_news_articles, valorant_news_articles, overwatch_news_articles

async def safe_send(ctx_or_channel, content=None, **kwargs):
    """Rate Limit 안전한 메시지 전송"""
    try:
        if hasattr(ctx_or_channel, 'send'):
            return await ctx_or_channel.send(content, **kwargs)
        else:
            return await ctx_or_channel.send(content, **kwargs)
    except Exception as e:
        print(f"메시지 전송 실패: {e}")
        return None

class NewsCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_games = {}

    async def cog_load(self):
        try:
            if not self.news_loop.is_running():
                self.news_loop.start()
                print("✅ 뉴스 자동 전송 루프 시작됨")
        except Exception as e:
            print(f"⚠️ 뉴스 루프 시작 실패: {e}")
            print("⚠️ 뉴스 자동 전송은 비활성화됩니다. 수동 명령어는 여전히 사용 가능합니다.")

    async def cog_unload(self):
        if self.news_loop.is_running():
            self.news_loop.cancel()
            print("❌ 뉴스 자동 전송 루프 중지됨")

    def create_news_embed(self, article: Dict[str, Any]):
        embed = discord.Embed(
            title=article.get('title'),
            description=article.get('subContent'),
            url=article.get('linkUrl'),
            timestamp=datetime.fromtimestamp(article["createdAt"] / 1000, tz=pytz.UTC),
            color=0x1E90FF
        )

        if article['thumbnail']:
            embed.set_thumbnail(url=article['thumbnail'])
        
        embed.add_field(
            name="🏆 순위", 
            value=f"#{article['rank']}", 
            inline=True
        )

        ts_seconds = article['createdAt'] / 1000
        kst = pytz.timezone("Asia/Seoul")
        dt = datetime.fromtimestamp(ts_seconds, tz=kst)

        formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        embed.add_field(
            name="⏰ 발행시간", 
            value=formatted,
            inline=False
        )

        return embed
    
    @tasks.loop(seconds=1200)
    async def news_loop(self):
        formatted_date = date.today().strftime('%Y-%m-%d')
        
        fetch_lol_articles = await self.safe_fetch_news(lol_news_articles, formatted_date, "롤")
        fetch_valorant_articles = await self.safe_fetch_news(valorant_news_articles, formatted_date, "발로란트")
        fetch_overwatch_articles = await self.safe_fetch_news(overwatch_news_articles, formatted_date, "오버워치")
            
        for channel_id, game in self.channel_games.items():
            articles_to_send = []
            
            if "lol" in game:
                articles_to_send.extend(fetch_lol_articles)
            if "valorant" in game:
                articles_to_send.extend(fetch_valorant_articles)
            if "overwatch" in game:
                articles_to_send.extend(fetch_overwatch_articles)

            if not articles_to_send:
                continue
            
            articles_to_send.sort(key=lambda x: x['createdAt'])

            channel = self.bot.get_channel(channel_id)
            if channel:
                for article in articles_to_send:
                    embed = self.create_news_embed(article)
                    await safe_send(channel, embed=embed)

        now_done = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
        print(f"✅ [{now_done}] 뉴스 전송 완료")

    @commands.command(name='뉴스확인', help='현재 채널에 설정된 게임의 최신 뉴스를 가져옵니다.')
    async def check_news_now(self, ctx: commands.Context):
        channel_games = self.channel_games.get(ctx.channel.id, [])

        if not channel_games:
            await safe_send(ctx, "❌ 이 채널은 뉴스 설정이 되어 있지 않습니다.\n`/뉴스채널설정 롤 발로란트 오버워치`로 설정해주세요!")
            return
        
        game_names = {"lol": "리그오브레전드", "valorant": "발로란트", "overwatch": "오버워치"}
        selected_names = [game_names[game] for game in channel_games]

        await safe_send(ctx, f"🔍 현재 채널에 설정된 뉴스 채널: {ctx.channel.name} -> {', '.join(selected_names)}")

        try:
            formatted_date = date.today().strftime('%Y-%m-%d')
            articles_to_send = []

            if "lol" in channel_games:
                articles_to_send.extend(await self.safe_fetch_news(lol_news_articles, formatted_date, "롤"))
            if "valorant" in channel_games:
                articles_to_send.extend(await self.safe_fetch_news(valorant_news_articles, formatted_date, "발로란트"))
            if "overwatch" in channel_games:
                articles_to_send.extend(await self.safe_fetch_news(overwatch_news_articles, formatted_date, "오버워치"))

            if not articles_to_send:
                await safe_send(ctx, "❌ 현재 새로운 뉴스가 없습니다.")
                return
            
            articles_to_send.sort(key=lambda x: x['createdAt'])

            await safe_send(ctx, f"📢 새로운 뉴스 {len(articles_to_send)}개를 발견했습니다!")
            for article in articles_to_send[:10]:
                try:
                    embed = self.create_news_embed(article)
                    await safe_send(ctx, embed=embed)

                except Exception as e:
                    await safe_send(ctx, f"❌ 뉴스 전송 중 오류: {e}")
                    continue
            
            if len(articles_to_send) > 10:
                await safe_send(ctx, f"📋 총 {len(articles_to_send)}개 중 최신 10개만 표시했습니다.")
            
        except Exception as e:
            await safe_send(ctx, f"❌ 뉴스 확인 중 오류가 발생했습니다: {e}")
            print(f"뉴스확인 명령어 오류: {e}")

    @commands.command(name='뉴스채널설정', help='채널별 게임 뉴스 설정. 매개변수 없이 입력하면 현재 설정 확인, 게임명 입력하면 설정 변경 (예: 롤 발로란트 오버워치)')
    @commands.has_guild_permissions(manage_channels=True)
    async def set_news_channel(self, ctx: commands.Context, *games: str):
        # 한국어 게임명 매칭
        game_mapping = {
            "롤": "lol",
            "리그오브레전드": "lol", 
            "lol": "lol",
            "발로란트": "valorant",
            "발로": "valorant",
            "valorant": "valorant",
            "오버워치": "overwatch", 
            "오버": "overwatch",
            "overwatch": "overwatch",
            "모든게임": ["lol", "valorant", "overwatch"],
            "전체": ["lol", "valorant", "overwatch"]
        }

        game_names = {"lol": "리그오브레전드", "valorant": "발로란트", "overwatch": "오버워치"}

        if not games:
            current_games = self.channel_games.get(ctx.channel.id, [])
            if current_games:
                current_names = [game_names[game] for game in current_games]
                await safe_send(ctx, f"현재 설정된 뉴스 채널: {ctx.channel.name} -> {', '.join(current_names)}")
            else:
                await safe_send(ctx, "현재 설정된 뉴스 채널이 없습니다.")
            return

        selected_games = []
        for game in games:
            mapped = game_mapping.get(game.lower())
            if mapped is None:
                await safe_send(ctx, f"❌ '{game}'는 지원하지 않는 게임명입니다.\n💡 **사용 가능한 게임:** 롤, 발로란트, 오버워치, 모든게임")
                return
            
            if isinstance(mapped, list):
                selected_games.extend(mapped)
            else:
                selected_games.append(mapped)

        selected_games = list(set(selected_games))
        self.channel_games[ctx.channel.id] = selected_games

        if selected_games:
            selected_names = [game_names[game] for game in selected_games]
            
            embed = discord.Embed(
                title="📰 뉴스 채널 설정 완료",
                description=f"**채널:** {ctx.channel.name}\n**게임:** {', '.join(selected_names)}\n\n🔄 20분마다 자동으로 새로운 뉴스를 확인합니다.",
                color=0x00ff00
            )
            embed.add_field(name="💡 팁", value="언제든지 `/뉴스확인` 명령어로 수동 확인이 가능합니다!", inline=False)
            
            await safe_send(ctx, embed=embed)

            try:
                formatted_date = date.today().strftime('%Y-%m-%d')
                articles_to_send = []

                if "lol" in selected_games:
                    articles_to_send.extend(await self.safe_fetch_news(lol_news_articles, formatted_date, "롤"))
                if "valorant" in selected_games:
                    articles_to_send.extend(await self.safe_fetch_news(valorant_news_articles, formatted_date, "발로란트"))
                if "overwatch" in selected_games:
                    articles_to_send.extend(await self.safe_fetch_news(overwatch_news_articles, formatted_date, "오버워치"))

                if articles_to_send:
                    await safe_send(ctx, f"📢 설정 완료! 최신 뉴스 {len(articles_to_send)}개를 확인했습니다:")
                    for article in articles_to_send[:3]:
                        embed = self.create_news_embed(article)
                        await safe_send(ctx, embed=embed)
                else:
                    await safe_send(ctx, "📰 현재 새로운 뉴스가 없습니다.")
            except Exception as e:
                print(f"초기 뉴스 확인 오류: {e}")

    async def safe_fetch_news(self, game_func: Callable, formatted_date: str, game_name: str):
        try:
            news_data = await game_func(formatted_date)
            if news_data and news_data.get("content"):
                return news_data["content"]
            return []
        except Exception as e:
            print(f"{game_name} 뉴스 크롤링 오류: {e}")
            return []

async def setup(bot: commands.Bot):
    await bot.add_cog(NewsCommand(bot))