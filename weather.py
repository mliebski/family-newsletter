"""Weather forecast for the newsletter (Open-Meteo: free, no API key).

The forecast is fetched as data and rendered by render.py; the model never writes it,
so the numbers cannot be invented.
"""

import requests

API = "https://api.open-meteo.com/v1/forecast"

# WMO weather code -> (kind used for the icon, label shown to readers)
_CODES = {
    0: ("sun", "Sunny"), 1: ("sun", "Mostly sunny"), 2: ("partly", "Partly cloudy"),
    3: ("cloud", "Cloudy"), 45: ("cloud", "Fog"), 48: ("cloud", "Freezing fog"),
    51: ("rain", "Light drizzle"), 53: ("rain", "Drizzle"), 55: ("rain", "Heavy drizzle"),
    56: ("rain", "Freezing drizzle"), 57: ("rain", "Freezing drizzle"),
    61: ("rain", "Light rain"), 63: ("rain", "Rain"), 65: ("rain", "Heavy rain"),
    66: ("rain", "Freezing rain"), 67: ("rain", "Freezing rain"),
    71: ("snow", "Light snow"), 73: ("snow", "Snow"), 75: ("snow", "Heavy snow"),
    77: ("snow", "Snow grains"),
    80: ("rain", "Rain showers"), 81: ("rain", "Rain showers"), 82: ("rain", "Heavy showers"),
    85: ("snow", "Snow showers"), 86: ("snow", "Heavy snow showers"),
    95: ("storm", "Thunderstorm"), 96: ("storm", "Thunderstorm, hail"), 99: ("storm", "Thunderstorm, hail"),
}


def describe(code):
    return _CODES.get(code, ("cloud", "Mixed conditions"))


def fetch_forecast(latitude, longitude, timezone="auto", days=6, timeout=20):
    """Return [{date, high, low, kind, label, precip}] for today plus the next days-1 days."""
    r = requests.get(API, timeout=timeout, params={
        "latitude": latitude, "longitude": longitude, "timezone": timezone,
        "forecast_days": days,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    })
    r.raise_for_status()
    d = r.json()["daily"]
    out = []
    for i, date in enumerate(d["time"]):
        high, low = d["temperature_2m_max"][i], d["temperature_2m_min"][i]
        if high is None or low is None:
            continue
        kind, label = describe(d["weather_code"][i])
        precip = d.get("precipitation_probability_max", [None] * len(d["time"]))[i]
        out.append({"date": date, "high": round(high), "low": round(low),
                    "kind": kind, "label": label, "precip": precip})
    return out
