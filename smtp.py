#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from queue import Queue, Empty
from aiosmtpd.handlers import AsyncMessage
from aiosmtpd.controller import Controller
from email.message import EmailMessage

class SmtpProxyHandler(AsyncMessage):
    """An SMTP proxy handler"""
    queue: Queue
    
    def __init__(self, queue: Queue):
       super()
       self.message_class = EmailMessage
       self.queue = queue

    async def handle_message(self, message):
        self.queue.put(message)

if __name__ == '__main__':
    try:
        mail_queue = Queue()

        controller = Controller(SmtpProxyHandler(mail_queue), hostname='127.0.0.1', port=1587)
        print(f'SMTP-server started on {controller.hostname}:{controller.port}')
        controller.start()

        while True:
            try:
                message: EmailMessage = mail_queue.get(True, timeout=60.0)
                print(message)
                with open('test.eml', 'wb') as f:
                    f.write(message.as_bytes())
            except Empty:
                print('Waiting ...')
    except KeyboardInterrupt:
        controller.stop()
