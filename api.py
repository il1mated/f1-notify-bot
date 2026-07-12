import requests

def get_race_data(year):
    try:
        res = requests.get(f"https://api.jolpi.ca/ergast/f1/{year}/races")
        if res.status_code == 200:
            data = res.json()
            return data
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred: {e}")
print(get_race_data(2026))