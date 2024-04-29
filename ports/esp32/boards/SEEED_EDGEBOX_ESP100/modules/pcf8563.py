from machine import I2C

STAT1_REG = const(0x00)
STAT2_REG = const(0x01)
SEC_REG = const(0x02)
#...
YEAR_REG = const(0x08)
SQW_REG = const(0x0D)
TIMER1_REG = const(0x0E)
TIMER2_REG = const(0x0F)

def _bcd2dec(bcd):
    return (((bcd & 0xF0) >> 4) * 10 + (bcd & 0x0F))

def _dec2bcd(dec):
    tens, units = divmod(dec, 10)
    return (tens << 4) + units

class PCF8563:
    def __init__(self, i2c:I2C, address=0x51):
        self.i2c = i2c
        self.addr = address

    def _write_byte(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def _read_byte(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def now(self):
        """Read all time registers in one transaction"""
        buf   = self.i2c.readfrom_mem(self.addr, SEC_REG, 7)
        secs  = _bcd2dec(buf[0] & 0x7F)
        mins  = _bcd2dec(buf[1] & 0x7F)
        hours = _bcd2dec(buf[2] & 0x3F)
        day   = _bcd2dec(buf[3] & 0x3F)
        wday  = _bcd2dec(buf[4] & 0x07)
        month = _bcd2dec(buf[5] & 0x1F)
        year  = _bcd2dec(buf[6]) + 2000
        return (year, month, day, wday, hours, mins, secs, 0)

    def datetime(self, dt=None):
        """Write all time registers in one transaction"""
        if dt is None:
            return self.now()
        year, month, day, wday, hours, mins, secs, _ = dt
        buf = bytearray([
            _dec2bcd(secs)  & 0x7F,
            _dec2bcd(mins)  & 0x7F,
            _dec2bcd(hours) & 0x3F,
            _dec2bcd(day)   & 0x3F,
            _dec2bcd(wday)  & 0x07,
            _dec2bcd(month) & 0x1F,
            _dec2bcd(year % 100)
        ])
        self.i2c.writeto_mem(self.addr, SEC_REG, buf)

    def write_now_utc(self):
        import time
        year, month, day, hours, mins, secs, wday, yday = time.gmtime()
        self.datetime((year, month, day, wday, hours, mins, secs, 0))
