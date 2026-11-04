"""Reference solution for the conditionals review."""


def rain_level(rain_mm):
    if rain_mm >= 20.0:
        return "heavy"
    elif rain_mm >= 5.0:
        return "moderate"
    elif rain_mm > 0:
        return "light"
    else:
        return "none"
