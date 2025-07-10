from discord.ext import commands

class HelloCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name='안녕', help='봇이 인사를 합니다.')
    async def hello(self, ctx: commands.Context):
        await ctx.send(f'안녕하세요 {ctx.author.mention}님! 🎮\n롤, 발로란트의 이스포츠 뉴스를 알려드릴게요!')
    
    @commands.command(name='핑', help='봇의 응답 속도를 확인합니다.')
    async def ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000, 2)
        await ctx.send(f'🏓 퐁! 응답속도: **{latency}ms**')

async def setup(bot: commands.Bot):
    await bot.add_cog(HelloCommand(bot))