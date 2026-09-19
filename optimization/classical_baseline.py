"""
Fixed/rule-based classical baseline -- used as the comparison point
required by the problem statement ("Compare the hybrid quantum
solution with a basic method such as fixed signal timing or
rule-based traffic control").
"""

GREEN_OPTIONS = [20, 30, 40]


def congestion_score(queue, waiting_time):
    return (queue * 10) + waiting_time


def choose_green_time(queue, waiting_time):
    score = congestion_score(queue, waiting_time)
    if score >= 100:
        return 40
    elif score >= 30:
        return 30
    return 20


def optimize_all(intersection_data):
    decisions = {}
    for junction, data in intersection_data.items():
        green_time = choose_green_time(data["queue"], data["waiting_time"])
        decisions[junction] = {
            "green_time": green_time,
            "congestion_score": congestion_score(data["queue"], data["waiting_time"]),
        }
    return decisions
