from discord.ext import commands

class HelloCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='안녕', help='인사해 줌')
    async def hello(self, ctx):
        await ctx.send(f'안녕하세요 {ctx.author.mention}님! 🎮\n롤, 발로란트의 이스포츠 뉴스를 알려드릴게요!')

async def setup(bot):
    await bot.add_cog(HelloCommand(bot))