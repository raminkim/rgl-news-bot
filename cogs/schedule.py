import ssl
from typing import List
from zoneinfo import ZoneInfo
import certifi
from discord.ext import commands, tasks
from crawlers.schedule_crawling import fetch_lol_league_schedule_months, fetch_monthly_lol_league_schedule, fetch_valorant_league_schedule, parse_lol_month_days
from datetime import datetime, timezone
import discord
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont
import asyncio
import traceback

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

LOL_LEAGUE_TYPE = {
    "LCK": "lck",
    "LPL": "lpl",
    "LEC": "lec",
    "LCS": "lcs",
    "MSI": "msi",
    "WORLDS": "wrl",
    "LJL": "ljl",
    "EWC": "ewc_lol"
}

VALORANT_LEAGUE_TYPE = {
    "VCT BR": "brazil",
    "VCT JP": "japan",
    "VCT NA": "na",
    "VCT Pacific": "pacific",
    "VCT Americas": "americas",
    "VCT EMEA": "emea",
    "Valorant Masters":  "masters",
}

class LeagueButton(discord.ui.Button):
    def __init__(self, game_name: str, league_name: str, league_code: str, cog: "ScheduleCommand"):
        super().__init__(label=league_name, style=discord.ButtonStyle.primary)
        self.game_name = game_name
        self.league_name = league_name
        self.league_code = league_code
        self.cog = cog
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"{self.game_name} {self.league_name} 리그 정보를 가져오는 중입니다... ⏳")

        if self.game_name == "LOL":
            try:
                upcoming = await self.cog.get_lol_league_schedule(interaction.channel, self.league_code)
                if not upcoming:
                    await safe_send(interaction.channel, f"❌ 예정된 {self.game_name} {self.league_name} 경기를 찾을 수 없습니다.")
                    return
                
                # 임베드 생성 및 전송
                await self.cog.send_upcoming_embeds(interaction.channel, upcoming)

            except Exception as e:
                print(f"{self.game_name} {self.league_name} 리그 명령어 실행 중 오류: {e}")
                traceback.print_exc()
                await safe_send(interaction.channel, f"❌ {self.game_name} {self.league_name} 경기 일정을 가져오는 중 오류가 발생했습니다.")
                return
            
        elif self.game_name == "VALORANT":
            try:
                upcoming = await self.cog.get_valorant_league_schedule(interaction.channel, self.league_code)
                if not upcoming:
                    await safe_send(interaction.channel, f"❌ 예정된 {self.game_name} {self.league_name} 경기를 찾을 수 없습니다.")
                    return
                
                await self.cog.send_upcoming_embeds(interaction.channel, upcoming)

            except Exception as e:
                print(f"{self.game_name} {self.league_name} 리그 명령어 실행 중 오류: {e}")
                traceback.print_exc()
                await safe_send(interaction.channel, f"❌ {self.game_name} {self.league_name} 경기 일정을 가져오는 중 오류가 발생했습니다.")
                return


class LeagueView(discord.ui.View):
    def __init__(self, game_name: str, cog: "ScheduleCommand"):
        super().__init__(timeout=300)

        if game_name == "LOL":

            for league_name, league_code in LOL_LEAGUE_TYPE.items():
                self.add_item(
                    LeagueButton(
                        game_name,
                        league_name,
                        league_code,
                        cog
                    )
                )
        elif game_name == "VALORANT":
            for league_name, league_code in VALORANT_LEAGUE_TYPE.items():
                self.add_item(
                    LeagueButton(
                        game_name,
                        league_name,
                        league_code,
                        cog
                    )
                )


class ScheduleCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.load_verify_locations(certifi.where())
        self.connector = aiohttp.TCPConnector(
            ssl=self.ssl_context,
            limit=4,
            ttl_dns_cache=300,
            force_close=True
        )
        self.timeout = aiohttp.ClientTimeout(total=15)
        self.session = None
    
    async def cog_load(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Whale/4.32.315.22 Safari/537.36",
                    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"
                }
            )

    async def cog_unload(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def send_upcoming_embeds(self, channel: discord.TextChannel, upcoming: List[dict]):
        # 이미지 배너 생성 및 Embed 전송
        async def build_scoreboard(team1: dict, team2: dict, score1, score2):
            """팀 로고와 점수를 조합한 PNG BytesIO 반환"""
            try:
                async def fetch_img(url):
                    for attempt in range(3):
                        try:
                            await asyncio.sleep(0.3 * attempt)
                            async with self.session.get(url) as resp:
                                if resp.status == 200:
                                    data = await resp.read()
                                    return Image.open(io.BytesIO(data)).convert("RGBA")
                                raise ValueError(f"HTTP {resp.status}")
                        except Exception as e:
                            if attempt == 2:
                                raise e
                            print(f"이미지 다운로드 재시도 {attempt + 1}/3: {e}")

                img1 = await fetch_img(team1["img"])
                await asyncio.sleep(0.2)
                img2 = await fetch_img(team2["img"])

                # 로고 사이즈 조정
                size = (70, 70)
                img1.thumbnail(size, Image.LANCZOS)
                img2.thumbnail(size, Image.LANCZOS)

                # 캔버스 생성
                W, H = 460, 90
                canvas = Image.new("RGBA", (W, H), (255, 255, 255, 0))
                draw = ImageDraw.Draw(canvas)

                y = (H - img1.height)//2
                canvas.paste(img1, (10, y), img1)
                canvas.paste(img2, (W - img2.width - 10, y), img2)

                try:
                    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
                except Exception:
                    try:
                        # 시스템 폰트 경로들을 시도
                        font_paths = [
                            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
                            "/System/Library/Fonts/Arial.ttf",  # macOS
                            "C:/Windows/Fonts/arial.ttf",  # Windows
                            "/usr/share/fonts/TTF/arial.ttf",  # Some Linux distributions
                        ]
                        font = None
                        for font_path in font_paths:
                            try:
                                font = ImageFont.truetype(font_path, 32)
                                break
                            except:
                                continue
                        if font is None:
                            raise Exception("No suitable font found")
                    except Exception:
                        font = ImageFont.load_default()

                if score1 is None and score2 is None:
                    score_text = "- : -"
                else:
                    left_score = 0 if score1 is None else score1
                    right_score = 0 if score2 is None else score2
                    score_text = f"{left_score} : {right_score}"
                
                try:
                    tw, th = draw.textsize(score_text, font=font)
                except AttributeError:
                    bbox = draw.textbbox((0, 0), score_text, font=font)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                
                draw.text(((W - tw)//2, (H - th)//2), score_text, fill="white", font=font, stroke_width=2, stroke_fill="black")

                buf = io.BytesIO()
                canvas.save(buf, format="PNG")
                buf.seek(0)
                return buf
            except Exception as e:
                print(f"이미지 생성 실패: {e}")
                return None

        # Discord 메시지 전송 (safe_send 사용)
        for i, m in enumerate(upcoming):
            try:
                start_epoch = int(datetime.fromisoformat(m["startDate"]).timestamp())
                date_abs = f"<t:{start_epoch}:F>"

                title = f"{m['team1']} vs {m['team2']}"

                if m["status"] == "BEFORE":
                    desc_lines = [date_abs]
                    colour = discord.Colour.blue()
                elif m["status"] == "STARTED":
                    desc_lines = [f"{date_abs} | 진행중"]
                    colour = discord.Colour.orange()
                else:
                    desc_lines = [f"{date_abs} | 종료"]
                    colour = discord.Colour.green()

                embed = discord.Embed(title=title, description="\n".join(desc_lines), colour=colour)

                if m.get("team1Img") and m.get("team2Img"):
                    buf = await build_scoreboard({"img": m["team1Img"]}, {"img": m["team2Img"]}, m.get("score1"), m.get("score2"))
                    if buf:
                        file = discord.File(buf, filename="score.png")
                        embed.set_image(url="attachment://score.png")
                        await safe_send(channel, file=file, embed=embed)
                    else:
                        await safe_send(channel, embed=embed)
                else:
                    await safe_send(channel, embed=embed)

                # 메시지 전송 간격 (Discord Rate Limit 방지)
                if i < len(upcoming) - 1:
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"임베드 생성/전송 실패: {e}")
                print(f"[ERROR] 예외 발생 시 경기 데이터: {m}")
                traceback.print_exc()
                continue

    async def get_lol_league_schedule(self, ctx: commands.Context, league_code: str) -> List[dict]:
        now_dt = datetime.now(timezone.utc)
        today_iso = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        today_kst = now_dt.astimezone(ZoneInfo("Asia/Seoul")).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        now_ym = now_dt.strftime("%Y-%m")

        # 월 목록 조회
        year_str = now_dt.strftime("%Y")
        months_resp = await fetch_lol_league_schedule_months(year_str, league_code)
        months_list: list[str] = (months_resp or {}).get("content", [])
        months_list = [m for m in months_list if m >= now_ym]

        upcoming: list[dict] = []

        # 월별 일정 수집
        for i, ym in enumerate(months_list):
            if i > 0:
                await asyncio.sleep(1)
                
            print(f"월 일정 조회: {ym}")
            month_resp = await fetch_monthly_lol_league_schedule(ym, league_code)
            if not month_resp:
                continue
            for match in parse_lol_month_days(month_resp):
                if match["startDate"] and match["startDate"] >= today_iso:
                    upcoming.append(match)
            if len(upcoming) >= 4:
                break

        if not upcoming:
            await safe_send(ctx, "❌ 예정된 롤 경기를 찾을 수 없습니다.")
            return

        upcoming.sort(key=lambda m: m["startDate"])
        upcoming = upcoming[:4]

        print(f"경기 {len(upcoming)}개 발견, 임베드 생성 시작")

        return upcoming
    
    async def get_valorant_league_schedule(self, ctx: commands.Context, league_code: str) -> List[dict]:
        upcoming = await fetch_valorant_league_schedule(league_code)
        if not upcoming:
            await safe_send(ctx, "❌ 예정된 발로란트 경기를 찾을 수 없습니다.")
            return
        
        upcoming.sort(key=lambda m: m["startDate"])
        upcoming = upcoming[:4]

        print(f"경기 {len(upcoming)}개 발견, 임베드 생성 시작")
        
        return upcoming
        
    
    @commands.command(name='리그', help="""LoL 및 발로란트 경기 일정 확인 (곧 시작할 4경기).
    예시: /리그 롤, /리그 발로란트

    지원 게임: 롤(LOL, 롤, 리그오브레전드), 발로란트(VALORANT, 발로란트)
    롤 지원 리그: LCK, LPL, LEC, LCS, MSI, WORLDS, LJL, EWC
    발로란트 지원 리그: 퍼시픽, 마스터스, EMEA, 아메리카 등""")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def show_schedule(self, ctx: commands.Context, game_name: str):
        """다가오는 4경기 일정을 임베드로 표시합니다."""
        GAME_TYPE = {
            "LOL": "lol",
            "lol": "lol",
            "롤": "lol",
            "리그오브레전드": "lol",
            "VALORANT": "valorant",
            "valorant": "valorant",
            "발로란트": "valorant",
            "발로": "valorant",
        }

        game_type = GAME_TYPE.get(game_name.lower())
        if not game_type:
            await safe_send(ctx, f"❌ 지원하지 않는 게임: {game_name}\n\n 지원하는 게임 키워드: {', '.join(GAME_TYPE.keys())}")
            return
        
        embed = discord.Embed(
            title=f"지원 리그 선택",
            description="아래 버튼을 클릭하여 일정을 검색하고자 하는 리그를 선택해주세요.",
            colour=discord.Colour.blue()
        )
        
        if game_type == "lol":
            try:
                await safe_send(ctx, embed=embed, view=LeagueView("LOL", self))
                
            except Exception as e:
                print(f"롤 리그 명령어 실행 중 오류: {e}")
                await safe_send(ctx, "❌ 롤 경기 일정을 가져오는 중 오류가 발생했습니다.")
                return
        
        elif game_type == "valorant":
            try:
                await safe_send(ctx, embed=embed, view=LeagueView("VALORANT", self))
            except Exception as e:
                print(f"발로란트 리그 명령어 실행 중 오류: {e}")
                await safe_send(ctx, "❌ 발로란트 경기 일정을 가져오는 중 오류가 발생했습니다.")
                return

    @show_schedule.error
    async def schedule_error(self, ctx, error):
        """롤리그 명령어 에러 처리"""
        if isinstance(error, commands.CommandOnCooldown):
            remaining = int(error.retry_after)
            await safe_send(ctx, f"⏰ 잠시만요! {remaining}초 후에 다시 시도해주세요.")
        else:
            print(f"롤리그 명령어 에러: {error}")
            await safe_send(ctx, "❌ 명령어 실행 중 오류가 발생했습니다.")

async def setup(bot: commands.Bot):
    cog = ScheduleCommand(bot)
    await bot.add_cog(cog)
    if hasattr(cog, 'cog_load'):
        await cog.cog_load()