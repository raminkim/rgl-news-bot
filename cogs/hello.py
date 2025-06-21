from discord.ext import commands

class HelloCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='hello', help='인사해 줌')
    async def hello(self, ctx):
        await ctx.send('안녕, 나는 롤/발로란트 이스포츠 뉴스 봇이야!')

async def setup(bot):
    await bot.add_cog(HelloCommand(bot))