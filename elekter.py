import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
import pytz
from matplotlib.widgets import TextBox, Button
from matplotlib.patches import Rectangle
import numpy as np


# Define the time range from today to tomorrow midnight in UTC
now = datetime.now(timezone.utc)
start = now.replace(hour=0, minute=0, second=0, microsecond=0)
# End at tomorrow's midnight
end = start + timedelta(days=2) - timedelta(seconds=1)

# Format the start and end times for the API
start_str = start.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
end_str = end.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

# API URL
api_url = f"https://dashboard.elering.ee/api/nps/price?start={start_str}&end={end_str}"

# Fetch data from the API
response = requests.get(api_url)

if response.status_code != 200:
    print(f"Error: Received status code {response.status_code} from API")
    print("Response content:", response.text)
    exit()

data = response.json()

# Extract prices for Estonia
if "data" in data and "ee" in data["data"]:
    estonia_data = data["data"]["ee"]
else:
    print("Error: 'ee' key not found in API response.")
    exit()

# Prepare data for plotting
timestamps = []
prices = []
local_tz = pytz.timezone("Europe/Tallinn")

# Get today's date in local timezone for comparison
today_local = datetime.now(local_tz).date()
tomorrow_local = today_local + timedelta(days=1)

# Track if we have valid tomorrow prices
tomorrow_has_data = False

for entry in estonia_data:
    if "timestamp" in entry and "price" in entry:
        utc_time = datetime.fromtimestamp(entry["timestamp"], tz=timezone.utc)
        local_time = utc_time.astimezone(local_tz)
        local_date = local_time.date()

        # Convert price from €/MWh to cents/kWh
        price = entry["price"] / 10

        # Check if this is tomorrow's data
        if local_date == tomorrow_local:
            # Only add tomorrow's data if price is valid (not None, not 0)
            if price is not None and price != 0:
                tomorrow_has_data = True
                timestamps.append(local_time)
                prices.append(price)
        else:
            # Always add today's data
            timestamps.append(local_time)
            prices.append(price)

print("Extracted Timestamps (Local):", timestamps)
print("Extracted Prices:", prices)
print(f"Tomorrow's data available: {tomorrow_has_data}")

if not timestamps or not prices:
    print("No data available to plot.")
    exit()

# Store original prices
original_prices = prices.copy()

# Initial price rows configuration
price_rows = [
    {'start': 22, 'end': 6, 'price': 3.03},
    {'start': 7, 'end': 8, 'price': 5.29},
    {'start': 9, 'end': 11, 'price': 8.18},
    {'start': 12, 'end': 15, 'price': 5.29},
    {'start': 16, 'end': 19, 'price': 8.18},
    {'start': 20, 'end': 21, 'price': 5.29},
]

# Store UI widgets
ui_widgets = {'rows': []}

def calculate_adjusted_prices():
    """Calculate adjusted prices based on all price rows"""
    adjusted = original_prices.copy()
    for i, ts in enumerate(timestamps):
        hour = ts.hour
        for row in price_rows:
            if is_hour_in_range(hour, row['start'], row['end']):
                adjusted[i] += row['price']
    return adjusted

def is_hour_in_range(hour, start, end):
    """Check if hour is in range, handling overnight periods"""
    if start <= end:
        return start <= hour <= end
    else:  # Overnight range (e.g., 22:00 to 6:00)
        return hour >= start or hour <= end

def find_cheapest_5h_window():
    """Find the cheapest 5 consecutive full hours starting from current time"""
    current_time = datetime.now(local_tz)

    # Get indices of all full hours (minute == 0)
    full_hour_indices = [i for i, ts in enumerate(timestamps) if ts.minute == 0]

    if len(full_hour_indices) < 5:
        return set()  # Not enough full hours

    # Find the first full hour index at or after current time
    current_full_hour_idx = None
    for idx in full_hour_indices:
        if timestamps[idx] >= current_time:
            current_full_hour_idx = idx
            break

    if current_full_hour_idx is None:
        return set()  # No future full hours

    adjusted_prices = calculate_adjusted_prices()

    # Find cheapest 5-hour window using only full hours from current time onwards
    min_sum = float('inf')
    min_start_idx = None

    for i in range(len(full_hour_indices) - 4):
        start_idx = full_hour_indices[i]

        # Skip if this window starts before current time
        if start_idx < current_full_hour_idx:
            continue

        # Check if next 4 indices are consecutive full hours (hourly gaps)
        window_indices = [full_hour_indices[i + j] for j in range(5)]

        # Verify these are 5 consecutive full hours (each 1 hour apart)
        is_consecutive = True
        for j in range(4):
            hour_diff = (timestamps[window_indices[j+1]] - timestamps[window_indices[j]]).total_seconds() / 3600
            if abs(hour_diff - 1.0) > 0.1:  # Allow small tolerance
                is_consecutive = False
                break

        if not is_consecutive:
            continue

        # Calculate sum of 5 consecutive full hours
        window_sum = sum(adjusted_prices[idx] for idx in window_indices)
        if window_sum < min_sum:
            min_sum = window_sum
            min_start_idx = i

    if min_start_idx is None:
        return set()

    # Return set of indices for the cheapest 5 full-hour window
    return set([full_hour_indices[min_start_idx + j] for j in range(5)])

def create_stacked_bars():
    """Create stacked bars with color coding"""
    ax.clear()
    x_positions = np.arange(len(timestamps))

    adjusted_prices = calculate_adjusted_prices()
    cheapest_hours = find_cheapest_5h_window()

    # Get current time to identify current hour
    current_time = datetime.now(local_tz)

    # For each hour, create stacked bars
    for i, (ts, base_price) in enumerate(zip(timestamps, original_prices)):
        hour = ts.hour
        total_adjustment = 0

        # Check if this is the current hour
        is_current_hour = (ts.hour == current_time.hour and ts.date() == current_time.date())

        # Calculate total adjustment for this hour
        for row in price_rows:
            if is_hour_in_range(hour, row['start'], row['end']):
                total_adjustment += row['price']

        # Determine base color
        if i in cheapest_hours:
            # Golden color for cheapest 5-hour window
            base_color = 'gold' if not is_current_hour else 'darkgoldenrod'
        elif base_price < total_adjustment:
            base_color = 'blue' if not is_current_hour else 'darkblue'
        else:
            base_color = 'green' if not is_current_hour else 'darkgreen'

        # Determine adjustment color (darker red for current hour)
        adjustment_color = 'darkred' if is_current_hour else 'red'

        # Draw base price bar
        ax.bar(i, base_price, width=0.8, color=base_color, edgecolor='black', linewidth=0.5)

        # Draw adjustment bar (red) on top
        if total_adjustment > 0:
            ax.bar(i, total_adjustment, width=0.8, bottom=base_price,
                   color=adjustment_color, edgecolor='black', linewidth=0.5)

    # Show only full hour marks on x-axis
    # Keep all bars but only label full hours
    full_hour_positions = []
    full_hour_labels = []
    for i, ts in enumerate(timestamps):
        if ts.minute == 0:  # Only full hours
            full_hour_positions.append(i)
            full_hour_labels.append(ts.strftime("%H"))

    ax.set_xticks(full_hour_positions)
    ax.set_xticklabels(full_hour_labels, rotation=90)
    ax.set_xlim(-0.5, len(timestamps) - 0.5)  # Ensure all bars are visible
    ax.set_xlabel("Hour of the Day (Local Time)")
    ax.set_ylabel("Electricity Price (cents/kWh)")
    ax.set_title("Hourly Electricity Prices for Today (Estonia - Local Time)")

    fig.canvas.draw_idle()

def redraw_controls():
    """Redraw the control panel with current price rows"""
    # Clear existing controls
    for widget_list in ui_widgets['rows']:
        for widget in widget_list:
            if hasattr(widget, 'disconnect_events'):
                widget.disconnect_events()
    ui_widgets['rows'].clear()

    # Clear axes (except main chart)
    for ax_widget in fig.get_axes()[1:]:
        ax_widget.remove()

    # Recreate control panel on the left side
    num_rows = len(price_rows)
    row_height = 0.04
    start_y = 0.85  # Start from top
    left_margin = 0.02
    col_width = 0.05

    for idx, row_data in enumerate(price_rows):
        y_pos = start_y - (idx * row_height)

        # Start time
        ax_start = plt.axes([left_margin, y_pos, col_width, 0.03])
        start_box = TextBox(ax_start, '', initial=str(row_data['start']))

        # End time
        ax_end = plt.axes([left_margin + col_width + 0.01, y_pos, col_width, 0.03])
        end_box = TextBox(ax_end, '', initial=str(row_data['end']))

        # Price
        ax_price = plt.axes([left_margin + 2 * (col_width + 0.01), y_pos, col_width + 0.02, 0.03])
        price_box = TextBox(ax_price, '', initial=f"{row_data['price']:.2f}")

        # Delete button
        ax_del = plt.axes([left_margin + 2 * (col_width + 0.01) + col_width + 0.03, y_pos, 0.025, 0.03])
        del_button = Button(ax_del, 'X')

        def make_update_handler(index):
            def handler(text):
                try:
                    price_rows[index]['start'] = int(ui_widgets['rows'][index][0].text)
                    price_rows[index]['end'] = int(ui_widgets['rows'][index][1].text)
                    price_rows[index]['price'] = round(float(ui_widgets['rows'][index][2].text), 2)
                    create_stacked_bars()
                except (ValueError, IndexError):
                    pass
            return handler

        def make_delete_handler(index):
            def handler(event):
                if len(price_rows) > 1:
                    price_rows.pop(index)
                    redraw_controls()
                    create_stacked_bars()
            return handler

        start_box.on_submit(make_update_handler(idx))
        end_box.on_submit(make_update_handler(idx))
        price_box.on_submit(make_update_handler(idx))
        del_button.on_clicked(make_delete_handler(idx))

        ui_widgets['rows'].append([start_box, end_box, price_box, del_button])

    # Add "Lisa rida" button
    add_y = start_y - (num_rows * row_height) - 0.01
    ax_add = plt.axes([left_margin, add_y, 0.10, 0.03])
    add_button = Button(ax_add, 'Lisa rida')

    def add_row(event):
        price_rows.append({'start': 0, 'end': 23, 'price': 0.0})
        redraw_controls()
        create_stacked_bars()

    add_button.on_clicked(add_row)
    ui_widgets['add_button'] = add_button

    # Add column headers
    header_y = start_y + 0.02
    fig.text(left_margin + 0.015, header_y, 'Start', fontsize=9, weight='bold')
    fig.text(left_margin + col_width + 0.015, header_y, 'End', fontsize=9, weight='bold')
    fig.text(left_margin + 2 * (col_width + 0.01) + 0.015, header_y, 'Price (cents)', fontsize=9, weight='bold')

    # Add price information section below "Lisa rida" button
    info_section_y = add_y - 0.18

    # Get current time and find current price
    current_time = datetime.now(local_tz)
    current_price = 0.0
    current_base = 0.0

    # Find the price at current hour
    for i, ts in enumerate(timestamps):
        if ts.hour == current_time.hour and ts.date() == current_time.date():
            current_base = original_prices[i]
            adjusted_prices = calculate_adjusted_prices()
            current_price = adjusted_prices[i]
            break

    # Display current price
    fig.text(left_margin, info_section_y + 0.14, 'Current Price:', fontsize=10, weight='bold')
    fig.text(left_margin, info_section_y + 0.12, f'Total: {current_price:.2f} cents/kWh', fontsize=9)

    # Calculate averages
    avg_base_price = sum(original_prices) / len(original_prices) if original_prices else 0
    adjusted_prices = calculate_adjusted_prices()
    avg_total_price = sum(adjusted_prices) / len(adjusted_prices) if adjusted_prices else 0

    # Calculate average for next 5 hours
    next_5h_avg = 0.0
    next_5h_count = 0
    for i, ts in enumerate(timestamps):
        if ts >= current_time and next_5h_count < 5:
            next_5h_avg += adjusted_prices[i]
            next_5h_count += 1
    next_5h_avg = next_5h_avg / next_5h_count if next_5h_count > 0 else 0.0

    # Calculate average for cheapest 5 hours
    cheapest_hours = find_cheapest_5h_window()
    cheapest_5h_avg = 0.0
    if cheapest_hours:
        cheapest_5h_avg = sum(adjusted_prices[i] for i in cheapest_hours) / len(cheapest_hours)

    # Display average prices
    fig.text(left_margin, info_section_y + 0.10, 'Average Prices:', fontsize=10, weight='bold')
    fig.text(left_margin, info_section_y + 0.08, f'Next 5h: {next_5h_avg:.2f} cents/kWh', fontsize=9)
    fig.text(left_margin, info_section_y + 0.06, f'Cheapest 5h: {cheapest_5h_avg:.2f} cents/kWh', fontsize=9)
    fig.text(left_margin, info_section_y + 0.04, f'Base: {avg_base_price:.2f} cents/kWh', fontsize=9)
    fig.text(left_margin, info_section_y + 0.02, f'Total: {avg_total_price:.2f} cents/kWh', fontsize=9)

    fig.canvas.draw_idle()

# Create figure with chart on the right
fig = plt.figure(figsize=(16, 10))
ax = fig.add_subplot(111)
# Position: [left, bottom, width, height]
ax.set_position([0.25, 0.10, 0.72, 0.85])

# Initial chart
create_stacked_bars()

# Add hover functionality
annot = ax.annotate("", xy=(0,0), xytext=(20,20), textcoords="offset points",
                    bbox=dict(boxstyle="round", fc="w", alpha=0.9),
                    arrowprops=dict(arrowstyle="->"))
annot.set_visible(False)

def on_hover(event):
    """Display time and price when hovering over a bar"""
    if event.inaxes == ax:
        for i, ts in enumerate(timestamps):
            # Check if mouse is over this bar
            if abs(event.xdata - i) < 0.4:
                time_str = ts.strftime("%H:00")
                base_price = original_prices[i]
                adjusted = calculate_adjusted_prices()[i]

                annot.xy = (i, adjusted)
                text = f"Time: {time_str}\nBase: {base_price:.2f} cents/kWh\nTotal: {adjusted:.2f} cents/kWh"
                annot.set_text(text)
                annot.set_visible(True)
                fig.canvas.draw_idle()
                return

        if annot.get_visible():
            annot.set_visible(False)
            fig.canvas.draw_idle()

fig.canvas.mpl_connect("motion_notify_event", on_hover)

# Draw controls
redraw_controls()

plt.show()
