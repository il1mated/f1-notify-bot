import requests

def get_races_data(year):
    try:
        res = requests.get(f"https://api.jolpi.ca/ergast/f1/{year}/races")
        if res.status_code == 200:
            data = res.json()
            return data
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred: {e}")
print(get_races_data(2026))

def get_race_data(year, round):
    try:
        res = requests.get(f"https://api.jolpi.ca/ergast/f1/{year}/{round}")
        if res.status_code == 200:
            data = res.json()
            print(data)
            return data
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred: {e}")

def get_race_results(year, round):
    try:
        res = requests.get(
            f"https://api.jolpi.ca/ergast/f1/{year}/{round}/results.json"
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred: {e}")


def get_qualifying_results(year, round):
    try:
        res = requests.get(
            f"https://api.jolpi.ca/ergast/f1/{year}/{round}/qualifying.json"
        )
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred: {e}")
