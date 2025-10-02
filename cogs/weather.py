
import discord
from discord.ext import commands
import aiohttp

API_KEY = is.getinv("WEATHER")  # Replace with your actual key

class Weather(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="weather")
    async def weather(self, ctx, *, city: str):
        """Get current weather for a city."""
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await ctx.send(f"❌ Couldn't fetch weather for `{city}`.")
                    return
                data = await resp.json()

        weather = data["weather"][0]["description"].title()
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]

        # 🌈 Determine embed color based on temperature
        if temp >= 30:
            color = discord.Color.red()
        elif temp >= 15:
            color = discord.Color.gold()
        else:
            color = discord.Color.blue()

        embed = discord.Embed(
            title=f"Weather in {city.title()}",
            description=f"{weather}",
            color=color
        )
        embed.add_field(name="🌡️ Temperature", value=f"{temp}°C (feels like {feels_like}°C)", inline=False)
        embed.add_field(name="💧 Humidity", value=f"{humidity}%", inline=True)
        embed.add_field(name="🌬️ Wind Speed", value=f"{wind} m/s", inline=True)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Weather(bot))