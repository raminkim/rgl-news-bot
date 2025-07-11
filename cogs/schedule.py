from discord.ext import commands
from crawlers.schedule_crawling import fetch_lol_league_schedule_months, fetch_monthly_league_schedule, parse_lol_month_days
from datetime import datetime, timezone
import discord
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont
import asyncio

LEAGUE_TYPE = {
    "LCK": "lck",
    "LPL": "lpl",
    "LEC": "lec",
    "LCS": "lcs",
    "MSI": "msi",
    "WORLDS": "wrl",
    "LJL": "ljl",
}

class ScheduleCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name='롤리그', help='LoL 경기 일정 확인 (곧 시작할 4경기). 예) /롤리그 LCK')
    async def show_schedule(self, ctx: commands.Context, league_str: str):
        """다가오는 4경기 일정을 임베드로 표시합니다."""
        
        try:
            league_key = league_str.upper()
            if league_key not in LEAGUE_TYPE:
                print(f"지원하지 않는 리그: {league_key}")
                return

            league_code = LEAGUE_TYPE[league_key]
            now_dt = datetime.now(timezone.utc)
            today_iso = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            now_ym = now_dt.strftime("%Y-%m")

            print(f"롤리그 검색 시작: {league_key}")

            # 월 목록 조회
            year_str = now_dt.strftime("%Y")
            months_resp = await fetch_lol_league_schedule_months(year_str, league_code)
            months_list: list[str] = (months_resp or {}).get("content", [])
            months_list = [m for m in months_list if m >= now_ym]

            upcoming: list[dict] = []

            # 월별 일정 수집 (1초 간격으로 단축)
            for i, ym in enumerate(months_list):
                if i > 0:
                    await asyncio.sleep(1)
                    
                print(f"월 일정 조회: {ym}")
                month_resp = await fetch_monthly_league_schedule(ym, league_code)
                if not month_resp:
                    continue
                for match in parse_lol_month_days(month_resp):
                    if match["startDate"] and match["startDate"] >= today_iso:
                        upcoming.append(match)
                if len(upcoming) >= 4:
                    break

            if not upcoming:
                print("예정된 경기를 찾지 못함")
                return

            upcoming.sort(key=lambda m: m["startDate"])
            upcoming = upcoming[:4]

            print(f"경기 {len(upcoming)}개 발견, 임베드 생성 시작")
            
        except Exception as e:
            print(f"롤리그 명령어 실행 중 오류: {e}")
            return

        # 이미지 배너 생성 및 Embed 전송
        async def build_scoreboard(team1: dict, team2: dict, score1, score2):
            """팀 로고와 점수를 조합한 PNG BytesIO 반환"""
            async with aiohttp.ClientSession() as session:
                async def fetch_img(url):
                    await asyncio.sleep(0.2)
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            return Image.open(io.BytesIO(data)).convert("RGBA")
                        raise ValueError("img dl fail")

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

        for m in upcoming:
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
                file = discord.File(buf, filename="score.png")
                embed.set_image(url="attachment://score.png")
                await ctx.send(file=file, embed=embed)
            else:
                await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ScheduleCommand(bot))