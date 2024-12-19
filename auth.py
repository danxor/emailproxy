#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import time

from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Protocol

from config import Config

class AccessToken:
    """Represents an access token"""
    access_token: str
    token_type: str
    scope: str
    not_after: datetime
    
    def __init__(self, access_token: str, token_type: str, scope: str, not_after: datetime):
        self.access_token = access_token
        self.token_type = token_type
        self.scope = scope
        self.not_after = not_after

    def is_valid(self) -> bool:
        if datetime.now() < self.not_after:
            return True
        
        return False
    
    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'{self.token_type} {self.access_token} [not_after={self.not_after.isoformat()}, scope={self.scope}]'

class _AccessTokenAndRefreshToken:
    """Represents an access token coupled with a refresh token"""
    access_token: str
    refresh_token: str
    token_type: str
    scope: str
    not_after: datetime
    ext_not_after: datetime
    
    def __init__(self, data: any):
        self.access_token = data['access_token']
        self.refresh_token = data.get('refresh_token')
        self.token_type = data.get('token_type')
        if not self.token_type:
            self.token_type = 'Bearer'

        self.scope = data.get('scope')

        not_after = data.get('not_after')
        if not_after:
            self.not_after = datetime.fromisoformat(not_after)
        else:
            expires_in = data.get('expires_in')
            if not expires_in:
                expires_in = '300'

            self.not_after = datetime.now() + timedelta(0, float(expires_in))

        ext_not_after = data.get('ext_not_after')
        if ext_not_after:
            self.ext_not_after = datetime.fromisoformat(ext_not_after)
        else:
            ext_expires_in = data.get('ext_expires_in')
            if not ext_expires_in:
                ext_expires_in = '300'
        
            self.ext_not_after = datetime.now() + timedelta(0, float(ext_expires_in))

    def is_valid(self) -> bool:
        if datetime.now() < self.ext_not_after:
            return True
        
        return False
    
    def as_dict(self) -> dict[str, any]:
        return {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': self.token_type,
            'scope': self.scope,
            'not_after': self.not_after.isoformat(),
            'ext_not_after': self.ext_not_after.isoformat()
        }
    
    def get_access_token(self) -> AccessToken:
        if self.is_valid():
                return AccessToken(self.access_token, self.token_type, self.scope, self.not_after)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'{self.token_type} {self.access_token} [not_after={self.ext_expires_in.isoformat()}, scope={self.scope}]'


class _DeviceToken:
    """Represents an device token"""
    device_code: str
    user_code: str
    verification_uri: str
    poll_interval: float
    expires_in: float
    not_after: datetime
    
    def __init__(self, response: any):
        self.device_code = response['device_code']
        self.user_code = response['user_code']
        self.verification_uri = response['verification_uri']

        expires_in = response.get('expires_in')
        if not expires_in:
            expires_in = '300'

        self.expires_in = float(expires_in)

        poll_interval = response.get('interval')
        if not poll_interval:
            poll_interval = '5'

        self.poll_interval = float(poll_interval)
        self.not_after = datetime.now() + timedelta(0, self.expires_in)

    def is_valid(self):
        if datetime.now() < self.not_after:
            return True

        return False

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f'DeviceToken(device_code={self.device_code}, user_code={self.user_code}, verification_uri={self.verification_uri}, not_after={self.not_after})'

class TokenHandler(Protocol):
    """Protocol for all token handlers"""
    @abstractmethod
    def get_access_token(self, silently: bool = False) -> AccessToken:
        raise NotImplementedError

    @abstractmethod
    def load_credentials(self, file: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_credentials(self, file: str) -> None:
        raise NotImplementedError

class DeviceCodeHandler:
    """"Handler that takes care of the OAuth 2 Device Code flow"""
    client_id: str
    authorize_url: str
    token_url: str
    __device_tokens: dict[str, _DeviceToken]
    __credentials: list[_AccessTokenAndRefreshToken]

    def __init__(self, config: Config):
        if not config.client_id:
            raise KeyError('client_id')

        self.client_id = config.client_id
        self.authorize_url = config.authorize_url
        self.token_url = config.token_url
        self.__device_tokens = {}
        self.__credentials = []

    def get_access_token(self, silently: bool = False):
        tokens = self.__get_active_credentials()

        if len(tokens) > 0:
            token = tokens[0]
            access = token.get_access_token()
            if not access.is_valid():
                token = self.__get_refresh_token(token)
                if not token and silently:
                    return None
            else:
                return token.get_access_token()
        elif silently:
            return None

        device_code, user_code, verification_uri = self.__get_device_code()

        print(f'Please navigate to {verification_uri} and enter the code {user_code} to authenticate.')

        return self.__get_access_token_for_device_code(device_code)

    def load_credentials(self, file: str) -> None:
        # TODO: Decrypt the contents using some kind of machine key
        if os.path.isfile(file):
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                client_id = data.get('client_id')

                assert client_id

                if client_id != self.client_id:
                    return

                tokens = data.get('tokens')
                if not tokens:
                    return

                self.__credentials = []
                credentials = [ _AccessTokenAndRefreshToken(data) for data in tokens ]
                for token in credentials:
                    if token.is_valid():
                        self.__credentials.append(token)
                    else:
                        self.__get_refresh_token(token)


    def save_credentials(self, file: str) -> None:
        dirname = os.path.dirname(file)
        os.makedirs(dirname, exist_ok=True)

        data = json.dumps({
            'client_id': self.client_id,
            'tokens': [ x.as_dict() for x in self.__get_active_credentials() ]
        })

        # TODO: Encrypt the contents using some kind of machine key
        with open(file, 'w', encoding='utf-8') as f:
            f.write(data)

    def __get_active_credentials(self) -> list[_AccessTokenAndRefreshToken]:
        return sorted([ token for token in self.__credentials if token.is_valid() ], key=lambda t: t.not_after, reverse=True)

    def __get_device_code(self) -> tuple[str, str, str]:
        headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
        data = { 'client_id': self.client_id, 'scope': 'https://graph.microsoft.com/Mail.Send offline_access' }
        token = _DeviceToken(requests.post(self.authorize_url, headers=headers, data=data).json())

        self.__device_tokens[token.device_code] = token

        return (token.device_code, token.user_code, token.verification_uri)
    
    def __get_access_token_for_device_code(self, device_code: str) -> AccessToken | None:
        if device_code not in self.__device_tokens:
            return None

        headers={ 'Content-Type': 'application/x-www-form-urlencoded' }
        data = { 'grant_type': 'urn:ietf:params:oauth:grant-type:device_code', 'device_code': device_code, 'client_id': self.client_id }

        deviceToken = self.__device_tokens[device_code]
        del self.__device_tokens[device_code]

        while deviceToken.is_valid():
            print('Waiting ...')

            time.sleep(deviceToken.poll_interval)

            response = requests.post(self.token_url, headers=headers, data=data).json()

            if response.get('access_token'):
                token = _AccessTokenAndRefreshToken(response)

                self.__credentials = self.__get_active_credentials() + [ token ]

                return token.get_access_token()
            elif response.get('error') == 'authorization_pending':
                pass
            else:
                print(response['error'])
                break

        return None

    def __get_refresh_token(self, token: _AccessTokenAndRefreshToken) -> _AccessTokenAndRefreshToken:
        if not token.is_valid():
            return None
        
        headers={ 'Content-Type': 'application/x-www-form-urlencoded' }
        data = { 'grant_type': 'refresh_token', 'refresh_token': token.refresh_token, 'client_id': self.client_id }

        response = requests.post(self.token_url, headers=headers, data=data).json()

        if response.get('access_token'):
            token = _AccessTokenAndRefreshToken(response)
            if token.is_valid():
                self.__credentials = self.__get_active_credentials() + [ token ]
                return token

        return None
            




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

    token = handler.get_access_token(silently=False)
    print(f'Access token: {token.access_token[0:3]}...{token.access_token[-4:-1]}')

    token = handler.get_access_token(silently=True)
    print(f'Access token: {token.access_token[0:3]}...{token.access_token[-4:-1]}')

    handler.save_credentials(config.credentials_file)

if __name__ == '__main__':
    main()
