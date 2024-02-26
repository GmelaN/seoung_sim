def microseconds(time):
    '''
    us -> s
    :param time:
    :return:
    '''
    return 0.0 if (time == 0) else (time / 1000000.0)


def milliseconds(time):
    '''
    ms -> s
    :param time:
    :return:
    '''
    return 0.0 if (time == 0) else (time / 1000.0)


def seconds(time):
    return time
