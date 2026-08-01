import datetime

COUNTRY_FLAGS = {
    "Australia": "🇦🇺",
    "China": "🇨🇳",
    "Japan": "🇯🇵",
    "Bahrain": "🇧🇭",
    "Saudi Arabia": "🇸🇦",
    "USA": "🇺🇸",
    "Italy": "🇮🇹",
    "Monaco": "🇲🇨",
    "Canada": "🇨🇦",
    "Spain": "🇪🇸",
    "Austria": "🇦🇹",
    "UK": "🇬🇧",
    "Belgium": "🇧🇪",
    "Hungary": "🇭🇺",
    "Netherlands": "🇳🇱",
    "Azerbaijan": "🇦🇿",
    "Singapore": "🇸🇬",
    "Mexico": "🇲🇽",
    "Brazil": "🇧🇷",
    "Qatar": "🇶🇦",
    "UAE": "🇦🇪",
}

MSK = datetime.timezone(datetime.timedelta(hours=3))

SESSION_TITLES = {
    "FirstPractice": "🟢 Практика 1 (FP1)",
    "SecondPractice": "🟡 Практика 2 (FP2)",
    "ThirdPractice": "🟠 Практика 3 (FP3)",
    "SprintQualifying": "🔴 Спринт-квалификация",
    "Sprint": "🏎 Спринт",
    "Qualifying": "🔵 Квалификация",
    "Race": "🏁 Гонка",
}

TIMING_LABELS = {
    "1h": "За 1 час",
    "15m": "За 15 минут",
    "both": "За 1 час и за 15 минут",
}

SESSIONS_LABELS = {
    "main": "Только квалификации, спринты и гонки",
    "all": "Все сессии (включая практики)",
}

ALLOWED_TIMINGS = {"1h", "15m", "both"}
ALLOWED_SESSIONS = {"main", "all"}
