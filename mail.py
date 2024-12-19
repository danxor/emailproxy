import json
import re
import requests

from auth import TokenHandler, DeviceCodeHandler
from config import Config
from email.message import EmailMessage
from email.parser import BytesParser

class MailSender:
    """A class that enables sending mail using Microsoft Graph"""
    handler: TokenHandler

    def __init__(self, handler: TokenHandler):
        self.handler = handler

    def send(self, message: EmailMessage):
        token = self.handler.get_access_token(True)
        if not token:
            raise PermissionError
        
        headers = {
            'Authorization': f'{token.token_type} {token.access_token}',
            'Content-Type': 'application/json'
        }

        data = MailSender.__get_message_body(message)

        response = requests.post('https://graph.microsoft.com/v1.0/me/sendMail', headers=headers, data=data)
        response.raise_for_status()

        recipients = message.get('To')
        if not recipients:
            recipients = message.get('X-RcptTo')

        print(f'Mail sent to {recipients}')

    @staticmethod
    def __get_message_body(message: EmailMessage) -> dict[str, any]:
        plain_text_parts = list(filter(lambda part: part.get_content_type() == 'text/plain', message.walk()))
        assert len(plain_text_parts) > 0

        text = ''

        for part in plain_text_parts:
            text += part.get_payload(decode=True).decode('utf-8')

        body = {
            'message': {
                'subject': message.get('Subject'),
                'body': {
                    'contentType': 'Text',
                    'content': text
                },
                'toRecipients': MailSender.__get_recipients(message),
                'ccRecipients': []
            },
            'saveToSentItems': True
        }
        return json.dumps(body)

    @staticmethod
    def __get_plain_text(payload: str):
        return re.sub(r'(?<!\t)((?<!\r)(?=\n)|(?=\r\n))', '\t', payload, flags=re.MULTILINE)

    @staticmethod
    def __get_recipients(message: EmailMessage) -> list[str]:
        to = message.get('To')
        if to:
            res = []
            for addr in [ x.strip().replace('\n', '').replace('\r', '') for x in to.split(',') ]:
                m = re.match(r'^([^<]+)<([^>]+)>$', addr)
                if m:
                    res.append({ 'emailAddress': { 'name': m.group(1).strip(), 'address': m.group(2).strip() } })
                else:
                    res.append({ 'emailAddress': {'address': addr.strip() } })
            return res

        to = message.get('X-RcptTo')
        if to:
            return [ { 'emailAddress': { 'address': x.strip() } } for x in to.split(',') ]

        return []

def __main():
    config = Config()

    errors = config.get_validation_errors()
    if len(errors) > 0:
        print('The configuration file contains errors:')

        for error in errors:
            print(f'> {error}')

        return

    handler = DeviceCodeHandler(config)
    handler.load_credentials(config.credentials_file)

    _ = handler.get_access_token(silently=False)

    mail = MailSender(handler)

    with open('test.eml', 'rb') as f:
        message = BytesParser(EmailMessage).parse(f)
        mail.send(message)

    handler.save_credentials(config.credentials_file)

if __name__ == '__main__':
    __main()