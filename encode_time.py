MINUTES_UNITS = 0
MINUTES_TENS  = 10
HOURS_UNITS   = 20
HOURS_TENS    = 29      # digit 1 -> 30, digit 2 -> 31


def encode_time(timestr):
    try:
        hh, mm = timestr.split(":")

        if len(mm) != 2:
            raise ValueError("minutes must be two digits")

        out = []

        if len(hh) == 2:
            out.append(HOURS_TENS + int(hh[0]))
            out.append(HOURS_UNITS + int(hh[1]))
        else:
            out.append(HOURS_UNITS + int(hh))

        out.append(MINUTES_TENS + int(mm[0]))
        out.append(MINUTES_UNITS + int(mm[1]))

        return tuple(out)

    except (ValueError, IndexError):
        raise ValueError(
            "invalid time format '{}', expected H:MM or HH:MM".format(timestr)
        )