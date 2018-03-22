import datetime
import logging
import smtplib
import sys
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from serial import Serial

from daemon import Daemon
from ina219 import INA219
from sim900 import Sim900


class PowerPi(Daemon):
    _HOST = 'mail.example.com'  # mail server
    _USERNAME = 'powerpi@example.com'  # from email
    _FREQUENCY = 900  # notification frequency in seconds
    _NUMBER_LIST = ['15555555555']  # phone numbers of sms recipients
    _EMAIL_LIST = ['jdoe@example.com']  # email addresses of email recipients

    ################################################################################
    def run(self):

        ina = INA219()
        failure = False
        last_notify = datetime.datetime.now() - datetime.timedelta(days=1)
        event_timestamp = None
        logger = logging.getLogger('power_pi')
        handler = logging.FileHandler('power_pi.log')
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        while True:
            load = ina.getCurrent_mA()

            if load < 10:
                logger.debug(str(load))

                if not failure:
                    logger.error('power outage has occurred')
                    failure = True
                    event_timestamp = datetime.datetime.now()

                if (datetime.datetime.now() - last_notify).total_seconds() > self._FREQUENCY:
                    notify_thread1 = threading.Thread(target=self.notify_email, args=('lost', event_timestamp))
                    notify_thread1.start()

                    notify_thread2 = threading.Thread(target=self.notify_sms, args=('lost', event_timestamp))
                    notify_thread2.start()

                    last_notify = datetime.datetime.now()

            elif failure:
                logger.info('power has been restored')

                notify_thread1 = threading.Thread(target=self.notify_email, args=('restored', event_timestamp))
                notify_thread1.start()

                notify_thread2 = threading.Thread(target=self.notify_sms, args=('restored', event_timestamp))
                notify_thread2.start()

                failure = False
                event_timestamp = None
                last_notify = datetime.datetime.now() - datetime.timedelta(days=1)

            time.sleep(1)

    ################################################################################
    def notify_email(self, state, timestamp):
        server = smtplib.SMTP(self._HOST)
        current_timestamp = datetime.datetime.now()
        current_date = str(current_timestamp).split('.')[0].split(' ')[0]
        current_time = str(current_timestamp).split('.')[0].split(' ')[1]
        event_date = str(timestamp).split('.')[0].split(' ')[0]
        event_time = str(timestamp).split('.')[0].split(' ')[1]
        duration = str((current_timestamp - timestamp)).split('.')[0]
        text = ''

        msg = MIMEMultipart()
        msg['From'] = formataddr(('powerpi', self._USERNAME))
        msg['To'] = ", ".join(self._EMAIL_LIST)

        if state == 'lost':
            msg['Subject'] = 'ALERT: Power Failure Detected'
            text = 'A loss of power occurred on {} at {}. Outage duration has been {}.'.format(event_date,
                                                                                               event_time,
                                                                                               duration)
        elif state == 'restored':
            msg['Subject'] = 'ALERT: Power has been Restored'
            text = 'Power has been restored. Outage began on {} at {} and ended on {} at {}. \
            Total outage duration was {}.'.format(event_date,
                                                  event_time,
                                                  current_date,
                                                  current_time,
                                                  duration)
        elif state == 'depleted':
            msg['Subject'] = 'ALERT: Backup Battery Depleted'
            text = 'A loss of power occurred on {} at {}. Outage duration has been {} . \
            Backup battery of power monitor has been depleted and the system will now shutdown.'.format(event_date,
                                                                                                        event_time,
                                                                                                        duration)

        body = MIMEText(text, 'plain')

        msg.attach(body)

        # send email
        server.sendmail(self._USERNAME, self._EMAIL_LIST, msg.as_string())

        server.quit()

    ###############################################################################
    def notify_sms(self, state, timestamp):
        gprs = Sim900(Serial("/dev/ttyAMA0", baudrate=115200, timeout=0), delay=0.5)
        current_timestamp = datetime.datetime.now()
        current_date = str(current_timestamp).split('.')[0].split(' ')[0]
        current_time = str(current_timestamp).split('.')[0].split(' ')[1]
        event_date = str(timestamp).split('.')[0].split(' ')[0]
        event_time = str(timestamp).split('.')[0].split(' ')[1]
        duration = str((current_timestamp - timestamp)).split('.')[0]
        text = ''

        if state == 'lost':
            text = 'A loss of power occurred on {} at {}. Outage duration has been {}.'.format(event_date,
                                                                                               event_time,
                                                                                               duration)
        elif state == 'restored':
            text = 'Power has been restored. Outage began on {} at {} and ended on {} at {}. \
            Total outage duration was {}.'.format(event_date,
                                                  event_time,
                                                  current_date,
                                                  current_time,
                                                  duration)
        elif state == 'depleted':
            text = 'A loss of power occurred on {} at {}. Outage duration has been {} . \
            Backup battery of power monitor has been depleted and the system will now shutdown.'.format(event_date,
                                                                                                        event_time,
                                                                                                        duration)

        for number in self._NUMBER_LIST:
            gprs.send_cmd('AT+CMGS="{}"'.format(number))
            gprs.send_cmd(text)
            gprs.send_cmd(Sim900.CTRL_Z)

            time.sleep(3)  # sim900 was not able to keep up if faster than this


################################################################################
if "__main__" == __name__:
    daemon = PowerPi('power_pi.pid')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print('Unknown command')
            sys.exit(2)
        sys.exit(0)
    else:
        print('usage: {} start|stop|restart'.format(sys.argv[0]))
        sys.exit(2)
