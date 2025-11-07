from smartnotifier.priority import calculate_priority

def test_priority_keywords():
    assert calculate_priority("gas leak", "2025-11-06 10:00") == "HIGH"
    assert calculate_priority("maintenance", "2025-11-06 10:00") == "LOW"
