import requests

def get_traffic_delay(src_lat, src_lon, dst_lat, dst_lon, api_key):
    try:
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{src_lat},{src_lon}:{dst_lat},{dst_lon}/json?key={api_key}&traffic=true"

        res = requests.get(url, timeout=3).json()

        route = res["routes"][0]["summary"]

        travel_time = route["travelTimeInSeconds"]
        traffic_delay = route["trafficDelayInSeconds"]

        normal_time = travel_time - traffic_delay

        if normal_time <= 0:
            return 1.0

        delay_ratio = travel_time / normal_time

        return delay_ratio

    except Exception as e:
        print("❌ Traffic API Error:", e)
        return 1.0


def convert_traffic(delay_ratio):
    if delay_ratio < 1.2:
        return 0   # low
    elif delay_ratio < 1.5:
        return 1   # medium
    else:
        return 2   # high