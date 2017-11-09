# Copyright (c) Sebastian Scholz
# See LICENSE for details.

import os
import time

from uuid import uuid4
try:
    from ConfigParser import RawConfigParser
except ImportError:
    from configparser import RawConfigParser

from txoauth2.clients import ClientStorage, Client, ClientAuthType
from txoauth2.token import TokenFactory, TokenStorage


class UUIDTokenFactory(TokenFactory):
    """ A TokenFactory that generates UUID tokens. """
    def generateToken(self, lifetime, client, scope, additionalData=None):
        """
        Generate an UUID toke.
        :param lifetime: Unused.
        :param client: Unused.
        :param scope: Unused.
        :param additionalData: Unused.
        :return: An UUID token.
        """
        return str(uuid4())


class ConfigParserClientStorage(ClientStorage):
    """ A ClientStorage using a ConfigParser. """
    _configParser = None
    path = None

    def __init__(self, path):
        """
        Initialize a new SimpleClientStorage which loads and stores
        it's clients from the given path.
        :param path: Path to a config file to load and store clients.
        """
        super(ConfigParserClientStorage, self).__init__()
        self._configParser = RawConfigParser()
        self.path = path
        self._configParser.read(path)

    def getClient(self, clientId):
        """
        Return a client object which represents the client
        with the given client id.
        :raises KeyError: If no client with the given client id exists.
        :param clientId: The id of the client.
        :return: A client object.
        """
        sectionName = 'client_' + clientId
        if not self._configParser.has_section(sectionName):
            raise KeyError('No client with id "{id}" exists'.format(id=clientId))
        redirectUris = self._configParser.get(sectionName, 'redirect_uris').split()
        authType = ClientAuthType(self._configParser.getint(sectionName, 'auth_type'))
        authToken = self._configParser.get(sectionName, 'auth_token')
        return Client(clientId, redirectUris, authType, authToken)

    def addClient(self, client):
        """
        Add a new or update an existing client to the list
        and save it to the config file.
        :raises ValueError: If the data in the client is not valid.
        :param client: The client to update or add.
        """
        sectionName = 'client_' + client.id
        if not self._configParser.has_section(sectionName):
            self._configParser.add_section(sectionName)
        self._configParser.set(sectionName, 'auth_type', client.authType.value)
        self._configParser.set(sectionName, 'auth_token', client.authToken)
        self._configParser.set(sectionName, 'redirect_uris', ' '.join(client.redirectUris))
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))
        with open(self.path, 'w') as configFile:
            self._configParser.write(configFile)


class DictTokenStorage(TokenStorage):
    """
    This token storage does not implement any type of persistence and tokens will therefore
    not survive a server restart. This implementation should probably only be used for testing.
    """
    _tokens = {}

    def contains(self, token):
        if token not in self._tokens:
            return False
        return not self._checkExpire(token)

    def hasAccess(self, token, scope):
        if self._checkExpire(token):
            raise KeyError('Token expired')
        for scopeItem in scope:
            if scopeItem not in self._tokens[token]['scope']:
                return False
        return True

    def getTokenData(self, token):
        self._checkExpire(token)
        return self._tokens[token]['scope'], self._tokens[token]['data']

    def store(self, token, client, scope, additionalData=None, expireTime=None):
        if not isinstance(token, str):
            raise ValueError('Token parameter is not a string')
        if not isinstance(scope, list):
            scope = [scope]
        if expireTime is not None and expireTime <= time.time():
            return
        self._tokens[token] = {
            'data': additionalData,
            'expireTime': expireTime,
            'scope': scope
        }

    def _checkExpire(self, token):
        """
        Check if a token has expired and remove it if necessary.
        :param token: The token to check.
        :return: True if the token has expired.
        :raises KeyError: If the token is not in the token storage.
        """
        expireTime = self._tokens[token]['expireTime']
        if expireTime is not None and time.time() > expireTime:
            del self._tokens[token]
            return True
        return False