from src.utils.traffic_api import get_traffic_delay

API_KEY = "hc4u00mvaF3geBhPS1JrwoLxMQ5qtJF3"

delay = get_traffic_delay(
    26.9124, 75.7873,   # Jaipur
    28.6139, 77.2090,   # Delhi
    API_KEY
)

print("Delay ratio:", delay)