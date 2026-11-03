# ==========================================================
# RA7203 Value Decoder
# ==========================================================
#
# IMPORTANT:
#
# No unverified Jotron enumerations are invented here.
# Values are decoded only where their meaning/scaling
# has already been established from the working dashboard
# and observed SNMP responses.
#
# ==========================================================


def safe_int(value, default=None):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# ==========================================================
# FREQUENCY
# ==========================================================


def decode_frequency(value):
    """
    RA7203 frequency.

    SNMP example:
        118500 -> 118.500 MHz
    """
    try:
        return int(value) / 1000.0
    except (ValueError, TypeError):
        return None


# ==========================================================
# TEMPERATURE
# ==========================================================


def decode_temperature(value):
    """
    Temperature is already returned in degrees C.

    Example:
        36 -> 36 °C
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ==========================================================
# VOLTAGE
# ==========================================================


def decode_voltage_mv(value):
    """
    Voltage values are in millivolts.

    Example:
        23934 -> 23.934 V
    """
    try:
        return int(value) / 1000.0
    except (ValueError, TypeError):
        return None


# ==========================================================
# POWER SOURCE
# ==========================================================


def decode_power_source(value):
    """
    Confirmed from observed receiver value:

        1 = AC
        2 = DC
    """
    try:
        value = int(value)

        if value == 1:
            return "AC"

        if value == 2:
            return "DC"

        return f"Unknown ({value})"

    except (ValueError, TypeError):
        return "--"


# ==========================================================
# RSSI
# ==========================================================


def decode_rssi(value):
    """
    RSSI is displayed directly in dBm.

    Example:
        -22 -> -22 dBm
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ==========================================================
# RF LO LOCK
# ==========================================================


def decode_lo_lock(value):
    """
    Confirmed from observed receiver value:

        1 = OK / locked

    Do not invent additional enumeration values.
    """
    try:
        value = int(value)

        if value == 1:
            return "OK"

        return f"Not Locked ({value})"

    except (ValueError, TypeError):
        return "--"


# ==========================================================
# CARRIER / NOISE
# ==========================================================


def decode_cn(value):
    """
    Carrier/Noise value is displayed exactly as received.

    No scaling or unit is invented because the exact
    MIB scaling has not yet been confirmed.
    """
    if value is None:
        return "--"

    return str(value)


# ==========================================================
# FREQUENCY OFFSET
# ==========================================================


def decode_offset(value):
    """
    Frequency offset is displayed as received in Hz.

    Example:
        0 -> 0 Hz
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ==========================================================
# ALARM
# ==========================================================


def decode_alarm(value):
    """
    Alarm:

        0 -> OK

    Other numeric values are deliberately preserved
    instead of assigning an unverified alarm meaning.
    """
    if value is None:
        return "--"

    try:
        value = int(value)
    except (ValueError, TypeError):
        return str(value)

    if value == 0:
        return "OK"

    return f"Alarm Code {value}"


# ==========================================================
# AGC
# ==========================================================


def decode_agc(value):
    """
    AGC is intentionally kept as a raw value.

    We have confirmed the receiver returns a value such as
    161, but we have NOT confirmed a physical unit from the
    MIB. Therefore no invented unit is attached.
    """
    if value is None:
        return "--"

    try:
        return str(int(value))
    except (ValueError, TypeError):
        return str(value)


# ==========================================================
# MODE
# ==========================================================


def decode_mode(value):
    """
    Decode receiver mode.

    IMPORTANT:
    No Jotron mode enumeration is currently confirmed.

    Therefore the raw received value is preserved rather
    than inventing meanings such as AM, FM, NORMAL, etc.

    Examples:
        1    -> "1"
        0    -> "0"
        "AM" -> "AM"
        None -> "--"
    """
    if value is None:
        return "--"

    try:
        return str(int(value))
    except (ValueError, TypeError):
        return str(value)
