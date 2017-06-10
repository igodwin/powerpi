import re
import sqlite3
from time import sleep


class TextMsg(object):
    """
    Represents a text message with some meta data

    Args:
        phone_number: Example format format: +1223334444
        timestamp: Example format: 14/05/30,00:13:34-32
        message: Text message body with CRLF removed
    """

    def __init__(self, phone_number, timestamp, message):
        self.phone_number = phone_number
        self.timestamp = timestamp
        self.message = message.strip()

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
            and self.__dict__ == other.__dict__)

    def __str__(self):
        return ', '.join([self.phone_number, self.timestamp, self.message])


class Sim900(object):
    """
    Sends commands and read input from Sim900 shield.

    Note that if you are sending commands to an Arduino,
    then the Arduino needs to be loaded with a sketch that 
    proxies commands to the shield and also forwards the 
    response through serial.

    With the pcDuino, this class communicates directly
    with the shield.
    """
    
    CRLF = "\r\n"
    CTRL_Z = chr(26)

    DELAY_AFTER_READ = 0.1

    def __init__(self, serial, delay=0.1):
        self.serial = serial
        self.delay = delay
        self.send_cmd("AT")
        self.send_cmd("AT+CMGF=1")

    def send_cmd(self, cmd, delay=None):
        """
        Sends AT commands to Sim900 shield. A CRLF
        is automatically added to the command.

        Args:
            cmd: AT Command to send to shield
            delay: Custom delay after sending command. Default is 0.1s
        """
        self.serial.write(cmd)
        self.serial.write(Sim900.CRLF)

        sleep(delay if delay is not None else self.delay)

    def available(self):
        return self.serial.inWaiting()

    def read(self, num_chars=1):
        return self.serial.read(num_chars)

    def read_available(self):
        return self.serial.read(self.available())

    def read_all(self):
        """
        Attempts to read all incoming input even if the 
        baud rate is very slow (ie 4800 bps) and only returns
        if no change is encountered.
        """
        msg = ""
        prev_len = 0
        curr_len = 0
        while True:
            prev_len = curr_len
            while self.available() != 0:
                msg += self.read_available()
                curr_len = len(msg)
                sleep(self.DELAY_AFTER_READ)
            if prev_len == curr_len:
                break
        return msg

class SMSReader(object):
    """
    Listens for incoming SMS text message and extracts 
    header and message for further processing.

    Example format:
    +CMT: "+12223334444","","14/05/30,00:13:34-32"<CRLF>
    This is the text message body!<CRLF>

    Note that the GSM shield can be set to include other metadata 
    in the +CMT header.
    """

    DATA_BEGIN = "+CMT"
    DATA_DELIM = "\r\n"

    NOT_FOUND = -1
    
    MSG_FORMAT = "\+CMT: \"(\+\d{11})\",\"\",\"(\d{2}\/\d{2}\/\d{2},\d{2}:\d{2}:\d{2}\-\d{2})\"\r\n(.*)\r\n"

    def __init__(self, sim900):
        self.sim900 = sim900
        self.sms_regex = re.compile(self.MSG_FORMAT)

    def init_reader(self):
        """
        Makes sure Sim900 shield is set to listen
        for incoming SMS text message in text mode.

        For the PcDuino, make sure to set the baudrate to
Otherwise, data will be garbled.

        This step can be skipped if you are sure that the 
        shield is set correctly.

        For instance if you are proxying commands/responses 
        through an Arduino, the Arduino sketch may already do
        this.

        Returns:
            Sim900 response to commands.
        """
        self.sim900.send_cmd("AT+CMGF=1")
        self.sim900.send_cmd("AT+CNMI=2,2,0,0,0")
        resp = self.sim900.read_all()
        if resp == '':
            return 'No active connection'
        return resp

    def listen(self):
        """
        Listens for incoming SMS text message with +CMT response code.

        Returns:
            If SMS text message is found, TextMsg is returned

            If message not found, then None is returned
        """
        msg = self.sim900.read_all()
        return self.extract_sms(msg)

    def extract_sms(self, msg):
        """
        Extracts SMS text message just in case the message includes
        gibberish before or after.

        Returns:
            TextMsg object or None if content is not in the correct format
        """
        result = self.sms_regex.search(msg)
        return TextMsg(*result.groups()) if result else None
