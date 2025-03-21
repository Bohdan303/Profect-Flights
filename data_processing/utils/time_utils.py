import datetime

def convert_time_hour_to_utc(ts):
    """Converts a Unix timestamp (in seconds) to a UTC-aware datetime."""
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)

def clock_to_minutes(val):
    """Converts a HHMM clock value to minutes since midnight."""
    try:
        val_int = int(val)
    except Exception:
        return None
    s = f"{val_int:04d}"
    hours = int(s[:2])
    minutes = int(s[2:])
    return hours * 60 + minutes

def minutes_to_clock(minutes):
    """Converts minutes since midnight back to HHMM clock format."""
    minutes = int(round(minutes))
    hours = minutes // 60
    mins = minutes % 60
    return int(f"{hours:02d}{mins:02d}")

def ensure_datetime(val):
    """Ensures the input value is a UTC-aware datetime object."""
    if isinstance(val, datetime.datetime):
        return val
    if isinstance(val, (float, int)):
        return convert_time_hour_to_utc(val)
    if isinstance(val, str):
        try:
            val_iso = val.replace(" ", "T")
            return datetime.datetime.fromisoformat(val_iso)
        except Exception:
            try:
                return convert_time_hour_to_utc(float(val))
            except Exception:
                return None
    return None
