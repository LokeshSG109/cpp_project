import datetime

def calculate_priority(issue: str, preferred_time: str):
    """
    Returns High / Normal / Low priority based on issue text and timing.
    """
    issue = issue.lower()

    if any(word in issue for word in ["leak", "fire", "no power", "gas smell", "urgent"]):
        return "HIGH"
    if "maintenance" in issue or "checkup" in issue:
        return "LOW"

    try:
        appt_time = datetime.datetime.strptime(preferred_time, "%Y-%m-%d %H:%M")
        if (appt_time - datetime.datetime.now()).total_seconds() < 86400:
            return "HIGH"
    except Exception:
        pass

    return "NORMAL"
