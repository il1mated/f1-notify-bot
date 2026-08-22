import datetime
from constants import MSK, ALL_TIMINGS, TIMING_LABELS



def parse_notify_timings(raw: str | None) -> list[str]:
    if not raw:
        return ["1h"]
    if raw == "both":
        return ["1h", "15m"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    valid = [t for t in ALL_TIMINGS if t in parts]
    return valid if valid else ["1h"]


def serialize_notify_timings(timings: list[str] | set[str]) -> str:
    ordered = [t for t in ALL_TIMINGS if t in timings]
    return ",".join(ordered) if ordered else "1h"


def format_timings_display(timings: list[str] | set[str] | str) -> str:
    if isinstance(timings, str):
        timings = parse_notify_timings(timings)
    ordered = [t for t in ALL_TIMINGS if t in timings]
    if not ordered:
        return "Не выбрано"
    return ", ".join(TIMING_LABELS.get(t, t) for t in ordered)


def parse_session_datetime(date_str: str, time_str: str | None) -> datetime.datetime | None:
    if not time_str:
        return None
    try:
        dt_str = f"{date_str}T{time_str.replace('Z', '+00:00')}"
        return datetime.datetime.fromisoformat(dt_str)
    except Exception:
        return None


def format_msk_time(dt: datetime.datetime) -> str:
    msk_dt = dt.astimezone(MSK)
    return msk_dt.strftime("%d.%m.%Y, %H:%M МСК")


def format_session_datetime(date_str: str, time_str: str | None) -> str:
    if not time_str:
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except Exception:
            return date_str

    dt = parse_session_datetime(date_str, time_str)
    if dt:
        return format_msk_time(dt)
    return f"{date_str} {time_str}"


def check_race_status(date: str, time: str | None) -> str:
    if time:
        dt_str = f"{date}T{time.replace('Z', '+00:00')}"
        event_dt = datetime.datetime.fromisoformat(dt_str)
    else:
        # только дата — считаем полночь UTC
        event_dt = datetime.datetime.fromisoformat(date).replace(tzinfo=datetime.timezone.utc)
    delta = datetime.datetime.now(datetime.timezone.utc) - event_dt

    if delta.total_seconds() < 0:
        return ""
    elif delta < datetime.timedelta(hours=2):
        return "🟢"
    else:
        return "🏁"


def extract_race_sessions(race: dict) -> list[tuple[str, datetime.datetime]]:
    sessions = []

    sub_sessions = [
        ("FirstPractice", race.get("FirstPractice")),
        ("SecondPractice", race.get("SecondPractice")),
        ("ThirdPractice", race.get("ThirdPractice")),
        ("SprintQualifying", race.get("SprintQualifying")),
        ("Sprint", race.get("Sprint")),
        ("Qualifying", race.get("Qualifying")),
    ]

    for key, session_data in sub_sessions:
        if session_data:
            dt = parse_session_datetime(session_data.get("date"), session_data.get("time"))
            if dt:
                sessions.append((key, dt))

    # Main Race
    race_dt = parse_session_datetime(race.get("date"), race.get("time"))
    if race_dt:
        sessions.append(("Race", race_dt))

    return sessions
