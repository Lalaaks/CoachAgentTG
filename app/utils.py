from datetime import datetime, timedelta, timezone
import pytz

def week_start_utc_iso(tz_name: str) -> str:
    tz = pytz.timezone(tz_name)
    now_local = datetime.now(tz)
    # Monday = 0
    monday = now_local - timedelta(days=now_local.weekday())
    start_local = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_local.astimezone(timezone.utc)
    return start_utc.isoformat()
