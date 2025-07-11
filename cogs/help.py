import discord
from discord.ext import commands

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

class HelpCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='도움', help='봇의 모든 명령어를 확인할 수 있습니다.')
    async def help(self, ctx: commands.Context, command_name: str = None):
        if command_name:
            command = self.bot.get_command(command_name)
            if command:
                embed = discord.Embed(
                    title=f"📋 '{command_name}' 명령어 도움말",
                    description=command.help or "설명이 제공되지 않았습니다.",
                    color=0x00ff56
                )
                
                if command.aliases:
                    embed.add_field(
                        name="📎 별칭",
                        value=', '.join([f"`/{alias}`" for alias in command.aliases]),
                        inline=False
                    )
                
                if hasattr(command, 'signature') and command.signature:
                    embed.add_field(
                        name="📝 사용법",
                        value=f"`/{command.name} {command.signature}`",
                        inline=False
                    )
                
                embed.set_footer(text="💡 <필수> [선택] 형태로 표시됩니다.")
            else:
                embed = discord.Embed(
                    title="❌ 명령어를 찾을 수 없습니다",
                    description=f"'{command_name}' 명령어가 존재하지 않습니다.\n`/도움`으로 전체 명령어를 확인해보세요!",
                    color=0xff0000
                )
        else:
            embed = discord.Embed(
                title="🤖 이스포츠 뉴스 봇 도움말",
                description="아래는 사용 가능한 모든 명령어입니다.",
                color=0x00ff56
            )
            
            commands_dict = {}
            for command in self.bot.commands:
                cog_name = command.cog.qualified_name if command.cog else "기타"
                
                if cog_name not in commands_dict:
                    commands_dict[cog_name] = []
                commands_dict[cog_name].append(command)
            
            cog_emojis = {
                "HelloCommand": "👋",
                "HelpCommand": "📋", 
                "NewsCommand": "📰",
                "ScheduleCommand": "📅",
                "PlayerCommand": "🎮",
                "기타": "🔧"
            }
            
            for cog_name, commands_list in commands_dict.items():
                emoji = cog_emojis.get(cog_name, "🔧")
                commands_text = []
                
                for cmd in commands_list:
                    cmd_help = cmd.help or "설명 없음"
                    commands_text.append(f"`/{cmd.name}` - {cmd_help}")
                
                embed.add_field(
                    name=f"{emoji} {cog_name}",
                    value="\n".join(commands_text),
                    inline=False
                )
            
            embed.add_field(
                name="📌 사용 팁",
                value="• 특정 명령어의 자세한 정보: `/도움 명령어이름`\n• 예시: `/도움 뉴스확인`",
                inline=False
            )
            
            embed.set_footer(text="문의사항이 있으시면 관리자에게 연락해주세요! 🛠️")

        await safe_send(ctx, embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommand(bot))