import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
import pytz  # For time zone conversion


# Define the time range for today in UTC
now = datetime.now(timezone.utc)
start = now.replace(hour=0, minute=0, second=0, microsecond=0)  # Start of today
end = start + timedelta(days=1) - timedelta(seconds=1)          # End of today

# Format the start and end times for the API (truncate to seconds)
start_str = start.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
end_str = end.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

# API URL
api_url = f"https://dashboard.elering.ee/api/nps/price?start={start_str}&end={end_str}"

# Fetch data from the API
response = requests.get(api_url)

# Check if the request succeeded
if response.status_code != 200:
    print(f"Error: Received status code {response.status_code} from API")
    print("Response content:", response.text)
    exit()

data = response.json()

# Extract prices for Estonia ("ee")
if "data" in data and "ee" in data["data"]:
    estonia_data = data["data"]["ee"]  # Extract Estonia data
else:
    print("Error: 'ee' key not found in API response.")
    exit()

# Prepare data for plotting
timestamps = []
prices = []

# Define the target time zone (e.g., UTC+2)
local_tz = pytz.timezone("Europe/Tallinn")  # Adjust this to your local time zone

for entry in estonia_data:
    if "timestamp" in entry and "price" in entry:
        # Convert UNIX timestamp to a UTC datetime object
        utc_time = datetime.fromtimestamp(entry["timestamp"], tz=timezone.utc)
        # Convert to local time zone
        local_time = utc_time.astimezone(local_tz)
        price = entry["price"]
        timestamps.append(local_time)
        prices.append(price)

# Debug: Ensure data is being extracted correctly
print("Extracted Timestamps (Local):", timestamps)
print("Extracted Prices:", prices)

# Ensure there is data to plot
if not timestamps or not prices:
    print("No data available to plot.")
    exit()

# Create the bar chart
plt.figure(figsize=(12, 6))
plt.bar([ts.strftime("%H:%M") for ts in timestamps], prices, color='skyblue')
plt.xlabel("Hour of the Day (Local Time)")
plt.ylabel("Electricity Price (€/MWh)")
plt.title("Hourly Electricity Prices for Today (Estonia - Local Time)")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
