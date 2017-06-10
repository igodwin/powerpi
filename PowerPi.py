import threading
import sys
import smtplib
import time
import datetime
import logging

from email.mime.text      import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils          import formataddr
from ina219               import INA219
from serial               import Serial
from sim900               import Sim900
from daemon               import Daemon


class PowerPi(Daemon):
    kHost       = 'mail.example.com'    #mail server
    kUsername   = 'powerpi@example.com' #from email
    kFrequency  = 900                   #notification frequency in seconds
    kNumberList = ['15555555555']       #phone numbers of sms recipients
    kEmailList  = ['jdoe@example.com']  #email addresses of email recipients

    ################################################################################
    def run(self):

        ina            = INA219()
        failure        = False
        lastNotify     = datetime.datetime.now() - datetime.timedelta(days=1)
        eventTimestamp = None
        logger         = logging.getLogger('powerpi')
        handler        = logging.FileHandler('/srv/powerpi/powerpi.log')
        formatter      = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        while True:
            load = ina.getCurrent_mA()
            
            if load < 10:
                logger.debug(str(load))

                if not failure:
                    logger.error('power outage has occurred')
                    failure        = True
                    eventTimestamp = datetime.datetime.now()

                if (datetime.datetime.now() - lastNotify).total_seconds() > self.kFrequency:
                    notifyThread1 = threading.Thread(target=self.notifyEmail, args = ('lost', eventTimestamp))
                    notifyThread1.start()

                    notifyThread2 = threading.Thread(target=self.notifySms, args = ('lost', eventTimestamp))
                    notifyThread2.start()

                    lastNotify = datetime.datetime.now()

            elif failure:
                logger.info('power has been restored')

                notifyThread1 = threading.Thread(target=self.notifyEmail, args = ('restored', eventTimestamp))
                notifyThread1.start()

                notifyThread2 = threading.Thread(target=self.notifySms, args = ('restored', eventTimestamp))
                notifyThread2.start()

                failure        = False
                eventTimestamp = None
                lastNotify     = datetime.datetime.now() - datetime.timedelta(days=1)

            time.sleep(1)

    ################################################################################
    def notifyEmail(self, type, timestamp):
        server           = smtplib.SMTP( self.kHost )
        currentTimestamp = datetime.datetime.now()
        currentDate      = str(currentTimestamp).split('.')[0].split(' ')[0]
        currentTime      = str(currentTimestamp).split('.')[0].split(' ')[1]
        eventDate        = str(timestamp).split('.')[0].split(' ')[0]
        eventTime        = str(timestamp).split('.')[0].split(' ')[1]
        duration         = str((currentTimestamp - timestamp)).split('.')[0]
        
        msg         = MIMEMultipart()
        msg['From'] = formataddr( ( 'powerpi', self.kUsername ) )
        msg['To']   = ", ".join(self.kEmailList)

        if type == 'lost':
            msg['Subject'] = 'ALERT: Power Failure Detected'
            text  = 'A loss of power occurred on ' + eventDate + ' at ' + eventTime + '.'
            text += ' Outage duration has been ' + duration + '.'
        elif type == 'restored':
            msg['Subject'] = 'ALERT: Power has been Restored'
            text  = 'Power has been restored. Outage began on ' + eventDate + ' at ' + eventTime
            text += ' and ended on ' + currentDate + ' at ' + currentTime + '.'
            text += ' Total outage duration was ' + duration + '.'
        elif type == 'depleted':
            msg['Subject'] = 'ALERT: Backup Battery Depleted'
            text  = 'A loss of power occurred on ' + eventDate + ' at ' + eventTime + '.'
            text += ' Outage duration has been ' + duration + '.'
            text += ' Backup battery of power monitor has been depleted and the system will now shutdown.'

        body = MIMEText( text, 'plain' )

        msg.attach(body)

        # send email
        server.sendmail( self.kUsername, self.kEmailList, msg.as_string() )

        server.quit()
        


    ###############################################################################
    def notifySms(self, type, timestamp):
        msg              = ""
        gprs             = Sim900(Serial("/dev/ttyAMA0", baudrate=115200, timeout=0), delay=0.5)
        currentTimestamp = datetime.datetime.now()
        currentDate      = str(currentTimestamp).split('.')[0].split(' ')[0]
        currentTime      = str(currentTimestamp).split('.')[0].split(' ')[1]
        eventDate        = str(timestamp).split('.')[0].split(' ')[0]
        eventTime        = str(timestamp).split('.')[0].split(' ')[1]
        duration         = str((currentTimestamp - timestamp)).split('.')[0]

        if type == 'lost':
            msg  = 'A loss of power occurred on ' + eventDate + ' at ' + eventTime + '.'
            msg += ' Outage duration has been ' + duration + '.'
        elif type == 'restored':
            msg  = 'Power has been restored. Outage began on ' + eventDate + ' at ' + eventTime
            msg += ' and ended on ' + currentDate + ' at ' + currentTime + '.'
            msg += ' Total outage duration was ' + duration + '.'
        elif type == 'depleted':
            msg  = 'A loss of power occurred on ' + eventDate + ' at ' + eventTime + '.'
            msg += ' Outage duration has been ' + duration + '.'
            msg += ' Backup battery of power monitor has been depleted and the system will now shutdown.'

        for number in self.kNumberList:
            gprs.send_cmd('AT+CMGS="' + number + '"')
            gprs.send_cmd(msg)
            gprs.send_cmd(Sim900.CTRL_Z)

            time.sleep(3) #sim900 was not able to keep up if faster than this
            


################################################################################
if "__main__" == __name__:
    daemon = PowerPi('/srv/powerpi/powerpi.pid')
    if len(sys.argv) == 2:
            if 'start' == sys.argv[1]:
                    daemon.start()
            elif 'stop' == sys.argv[1]:
                    daemon.stop()
            elif 'restart' == sys.argv[1]:
                    daemon.restart()
            else:
                    print "Unknown command"
                    sys.exit(2)
            sys.exit(0)
    else:
            print "usage: %s start|stop|restart" % sys.argv[0]
            sys.exit(2)


# eof
