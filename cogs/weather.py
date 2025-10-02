import discord
from discord.ext import commands
import aiohttp
import os

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

LABELS = {
    "en": {
        "weather_in": "Weather in",
        "temperature": "Temperature",
        "feels_like": "Feels like",
        "humidity": "Humidity",
        "wind": "Wind Speed",
        "unit": "m/s"
    },
    "fr": {
        "weather_in": "Météo à",
        "temperature": "Température",
        "feels_like": "Ressenti",
        "humidity": "Humidité",
        "wind": "Vitesse du vent",
        "unit": "m/s"
    },
    "ar": {
        "weather_in": "الطقس في",
        "temperature": "درجة الحرارة",
        "feels_like": "تشعر وكأنها",
        "humidity": "الرطوبة",
        "wind": "سرعة الرياح",
        "unit": "م/ث"
    },
    # Add more languages here as needed
}

class Weather(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def detect_language(self, text: str) -> str:
        if "--lang" in text:
            parts = text.split("--lang")
            return parts[1].strip().lower()
        elif any(c in text for c in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"):
            return "ar"
        else:
            return "en"

    def normalize_city(self, raw: str) -> str:
        raw = raw.split("--lang")[0]
        raw = raw.lower().replace("algeria", "").replace("الجزائر", "").strip()
        return raw.title()

    def get_weather_emoji(self, condition: str) -> str:
        condition = condition.lower()
        for key in WEATHER_EMOJIS:
            if key in condition:
                return WEATHER_EMOJIS[key]
        return "🌈"

    @commands.command(name="weather")
    async def weather(self, ctx, *, city: str):
        """Get current weather with emoji and full language support."""
        lang = self.detect_language(city)
        normalized_city = self.normalize_city(city)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={normalized_city}&appid={API_KEY}&units=metric&lang={lang}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await ctx.send(f"❌ Couldn't fetch weather for `{normalized_city}`.")
                    return
                data = await resp.json()

        weather_desc = data["weather"][0]["description"].title()
        emoji = self.get_weather_emoji(weather_desc)
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind = data["wind"]["speed"]

        # Embed color based on temperature
        if temp >= 30:
            color = discord.Color.red()
        elif temp >= 15:
            color = discord.Color.gold()
        else:
            color = discord.Color.blue()

        labels = LABELS.get(lang, LABELS["en"])

        embed = discord.Embed(
            title=f"{emoji} {labels['weather_in']} {normalized_city}",
            description=f"{weather_desc}",
            color=color
        )
        embed.add_field(
            name=f"🌡️ {labels['temperature']}",
            value=f"{temp}°C ({labels['feels_like']} {feels_like}°C)",
            inline=False
        )
        embed.add_field(name=f"💧 {labels['humidity']}", value=f"{humidity}%", inline=True)
        embed.add_field(name=f"🌬️ {labels['wind']}", value=f"{wind} {labels['unit']}", inline=True)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Weather(bot))