import discord
from discord.ext import commands
import aiohttp
import os
from datetime import datetime

API_KEY = os.getenv("WEATHER")

WEATHER_EMOJIS = {
    "clear": "☀️",
    "clouds": "☁️",
    "rain": "🌧️",
    "drizzle": "🌦️",
    "thunderstorm": "⛈️",
    "snow": "❄️",
    "mist": "🌫️",
    "fog": "🌁",
    "haze": "🌤️",
    "smoke": "🚬",
    "dust": "🌪️",
    "sand": "🏜️",
}

class Weather(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_weather_emoji(self, condition: str) -> str:
        """Return emoji matching condition."""
        condition = condition.lower()
        for key in WEATHER_EMOJIS:
            if key in condition:
                return WEATHER_EMOJIS[key]
        return "🌈"

    async def fetch_weather(self, city: str):
        """Fetch weather data from OpenWeatherMap."""
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=en"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if resp.status != 200:
                    return None, data.get("message", "Unknown error")
                return data, None

    @commands.command(name="weather")
    async def weather(self, ctx, *, city: str):
        """Get current weather with emoji and extra info."""
        data, error = await self.fetch_weather(city)
        if not data:
            await ctx.send(f"❌ Couldn't fetch weather for `{city}`. Error: {error}")
            return

        weather_main = data["weather"][0]["main"].title()
        weather_desc = data["weather"][0]["description"].title()
        emoji = self.get_weather_emoji(weather_desc)
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]
        country = data["sys"].get("country", "")
        sunrise = datetime.utcfromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M UTC")
        sunset = datetime.utcfromtimestamp(data["sys"]["sunset"]).strftime("%H:%M UTC")

        # Embed color based on temperature
        if temp >= 30:
            color = discord.Color.red()
        elif temp >= 15:
            color = discord.Color.gold()
        else:
            color = discord.Color.blue()

        embed = discord.Embed(
            title=f"{emoji} Weather in {data['name']}, {country}",
            description=f"{weather_main} - {weather_desc}",
            color=color
        )
        embed.add_field(name="🌡️ Temperature", value=f"{temp}°C (Feels like {feels_like}°C)", inline=False)
        embed.add_field(name="💧 Humidity", value=f"{humidity}%", inline=True)
        embed.add_field(name="🌬️ Wind Speed", value=f"{wind} m/s", inline=True)
        embed.add_field(name="🌅 Sunrise", value=sunrise, inline=True)
        embed.add_field(name="🌇 Sunset", value=sunset, inline=True)
        embed.set_footer(text="Weather data provided by OpenWeatherMap")

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Weather(bot))