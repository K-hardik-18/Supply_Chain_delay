import requests
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")

def get_weather(city):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
        
        response = requests.get(url)
        data = response.json()

        weather_main = data["weather"][0]["main"]
        temperature = data["main"]["temp"]

        return weather_main, temperature

    except Exception as e:
        print("Weather API Error:", e)
        return "Clear", 25  # fallback