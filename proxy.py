#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from queue import Queue, Empty
from datetime import datetime
from aiosmtpd.controller import Controller
from auth import DeviceCodeHandler
from config import Config
from smtp import SmtpProxyHandler
from mail import MailSender

def process_queue(queue: Queue):
    while not queue.empty():
        message = queue.get()
        print(message)

def main():
    config = Config()

    errors = config.get_validation_errors()
    if len(errors) > 0:
        print('The configuration file contains errors:')

        for error in errors:
            print(f'> {error}')

        return

    handler = DeviceCodeHandler(config)
    handler.load_credentials(config.credentials_file)
    mailer = MailSender(handler)

    mail_queue = Queue()

    try:
        controller = Controller(SmtpProxyHandler(mail_queue), hostname=config.bind, port=config.port)
        print(f'Starting SMTP-server on {controller.hostname}:{controller.port}')
        controller.start()

        while True:
            token = handler.get_access_token(silently=True)
            if not token:
                # Fallback on getting a new access token
                token = handler.get_access_token(silently=False)
                if token:
                    handler.save_credentials(config.credentials_file)
                else:
                    continue

            timedelta = token.not_after - datetime.now()
            seconds = (timedelta.days * 86400.0) + timedelta.seconds
            if seconds > 60.0:
                seconds -= 30.0

            try:
                message = mail_queue.get(True, timeout=seconds)
                mailer.send(message)
            except Empty:
                print('Refreshing access token ...')

    except KeyboardInterrupt:
        controller.stop()

    handler.save_credentials(config.credentials_file)

if __name__ == '__main__':
    main()