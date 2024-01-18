def microseconds(time):
    return 0.0 if (time == 0) else (time / 1000000.0)


def milliseconds(time):
    return 0.0 if (time == 0) else (time / 1000.0)


def seconds(time):
    return time
