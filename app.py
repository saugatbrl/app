import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
import requests
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = "super_secret_key"

API_KEY = "36357bbee22b979b263638d4b0eb06a9"  # replace with your key

# Temporary user storage (use database later)
users = {}


# ---------------- AUTH ROUTES ---------------- #

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )

        user = cursor.fetchone()

        conn.close()

        if user:
            session["user"] = username
            return redirect(url_for("home"))
        else:
            return render_template(
                "login.html",
                error="Invalid username or password"
            )

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("users.db", timeout=30)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, password)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# ---------------- WEATHER LOGIC ---------------- #

def get_coordinates(location):
    cleaned = location.strip()

    if not cleaned:
        return None

    if cleaned.isdigit() and len(cleaned) == 4:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"zip": f"{cleaned},AU", "appid": API_KEY, "units": "metric"}

        data = requests.get(url, params=params).json()

        if str(data.get("cod")) != "200":
            return None

        return {
            "name": data["name"],
            "lat": data["coord"]["lat"],
            "lon": data["coord"]["lon"]
        }

    geo_url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": f"{cleaned},AU", "limit": 1, "appid": API_KEY}
    data = requests.get(geo_url, params=params).json()

    if data:
        return {
            "name": data[0]["name"],
            "lat": data[0]["lat"],
            "lon": data[0]["lon"]
        }

    return None


def get_weather_data(lat, lon):
    current_url = "https://api.openweathermap.org/data/2.5/weather"
    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {"lat": lat, "lon": lon, "appid": API_KEY, "units": "metric"}

    current = requests.get(current_url, params=params).json()
    forecast = requests.get(forecast_url, params=params).json()

    return current, forecast


def calculate_time_windows(sunrise, sunset):
    return {
        "golden_morning": (sunrise, sunrise + timedelta(hours=1)),
        "blue_morning": (sunrise - timedelta(minutes=30), sunrise),
        "golden_evening": (sunset - timedelta(hours=1), sunset),
        "blue_evening": (sunset, sunset + timedelta(minutes=30)),
    }


def build_report(current, forecast):
    timezone = current["timezone"]

    sunrise = datetime.utcfromtimestamp(current["sys"]["sunrise"] + timezone)
    sunset = datetime.utcfromtimestamp(current["sys"]["sunset"] + timezone)
    now = datetime.utcfromtimestamp(current["dt"] + timezone)

    theme = current["weather"][0]["main"].lower()
    if not (sunrise <= now <= sunset):
        theme = "night"

    windows = calculate_time_windows(sunrise, sunset)

    report = {
    "location": current["name"],
    "location_label": current["name"],

    "current_temp": current["main"]["temp"],
    "current_condition": current["weather"][0]["description"],
    "current_humidity": current["main"]["humidity"],
    "current_wind": current["wind"]["speed"],

    "sunrise": sunrise.strftime("%I:%M %p"),
    "sunset": sunset.strftime("%I:%M %p"),

    "blue_morning": f"{windows['blue_morning'][0].strftime('%I:%M')} - {windows['blue_morning'][1].strftime('%I:%M')}",

    "golden_morning": f"{windows['golden_morning'][0].strftime('%I:%M')} - {windows['golden_morning'][1].strftime('%I:%M')}",

    "golden_evening": f"{windows['golden_evening'][0].strftime('%I:%M')} - {windows['golden_evening'][1].strftime('%I:%M')}",

    "blue_evening": f"{windows['blue_evening'][0].strftime('%I:%M')} - {windows['blue_evening'][1].strftime('%I:%M')}",

    "overall_score": 85,
    "overall_rating": "Excellent",

    "summary": "Good photography conditions.",

    "why": "Comfortable weather, reasonable light and low wind.",

    "best_slots": [
        {
            "time": "Golden Hour",
            "score": 95,
            "rating": "Excellent",
            "condition": current["weather"][0]["description"],
            "temp": current["main"]["temp"],
            "cloud": current.get("clouds", {}).get("all", 0),
            "wind": current["wind"]["speed"],
            "explanation": "Best natural lighting for photography."
        }
    ],

    "forecast_items": [],

    "theme": theme
}
    for item in forecast["list"][:8]:

     report["forecast_items"].append({
        "time": item["dt_txt"],
        "condition": item["weather"][0]["description"],
        "temp": item["main"]["temp"],
        "cloud": item["clouds"]["all"],
        "wind": item["wind"]["speed"],
        "score": 80,
        "rating": "Good"
    })

    return report


# ---------------- MAIN PAGE ---------------- #

@app.route("/", methods=["GET", "POST"])
def home():
    if "user" not in session:
        return redirect(url_for("login"))

    report = None
    error = None

    if request.method == "POST":
        location = request.form.get("location")

        coords = get_coordinates(location)

        if not coords:
            error = "Invalid location"
        else:
            current, forecast = get_weather_data(coords["lat"], coords["lon"])
            report = build_report(current, forecast)

    return render_template("index.html", report=report, error=error)


if __name__ == "__main__":
    app.run(debug=True)