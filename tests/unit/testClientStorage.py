import os

from tempfile import NamedTemporaryFile

from txoauth2.clients import Client, ClientAuthType
from txoauth2.imp import ConfigParserClientStorage

from tests import TwistedTestCase, getDummyClient, assertClientEquals


class AbstractClientStorageTest(TwistedTestCase):
    """
    An abstract test case for ClientStorage implementations. A subclass must set __test__
    to True and call setupClientStorage with an instance of the client storage to test.
    """
    _CLIENT_STORAGE = None
    _VALID_CLIENT = getDummyClient()

    @classmethod
    def setupClientStorage(cls, clientStorage):
        """
        Set the client storage implementation to use for the tests.
        The client storage should contain the _VALID_CLIENT.
        :param clientStorage: The token factory implementation to test.
        """
        cls._CLIENT_STORAGE = clientStorage

    def testGetClient(self):
        """ Test the retrieval of a client from the client storage. """
        client = self._CLIENT_STORAGE.getClient(self._VALID_CLIENT.id)
        self.assertIsInstance(
            client, Client, message='Expected the client storage to return a client object.')
        assertClientEquals(self, client, self._VALID_CLIENT,
                           msg='Expected the client storage to return a client '
                               'with the same attributes as the one stored')
        self.assertIsInstance(client.id, str,
                              message='Expected the client id of the client returned '
                                      'by the client storage to be a string.')
        self.assertIsInstance(client.redirectUris, list,
                              message='Expected the redirect uris of the client returned '
                                      'by the client storage to be a list.')
        for uri in client.redirectUris:
            self.assertIsInstance(uri, str,
                                  message='Expected all redirect uris of the client returned '
                                          'by the client storage to be a string.')
        self.assertIsInstance(client.authType, ClientAuthType,
                              message='Expected the authentication type of the client returned by '
                                      'the client storage to be member of the ClientAuthType enum.')
        self.assertIsInstance(client.authToken, str,
                              message='Expected the authentication token of the client '
                                      'returned by the client storage to be a string.')
        self.assertRaises(KeyError, self._CLIENT_STORAGE.getClient, 'invalidClientId')


class ConfigParserClientStorageTest(AbstractClientStorageTest):
    """ Test the ConfigParserClientStorage. """

    @classmethod
    def setUpClass(cls):
        with NamedTemporaryFile(prefix='.ini', delete=False) as tempFile:
            cls.clientStoragePath = tempFile.name
        clientStorage = ConfigParserClientStorage(cls.clientStoragePath)
        cls.setupClientStorage(clientStorage)
        clientStorage.addClient(cls._VALID_CLIENT)

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.clientStoragePath)

    def testAddClient(self):
        """ Test if a client can be added to the client storage. """
        client = Client(
            'newClientId', ['https://return.nonexistent', 'https://return2.nonexistent'],
            ClientAuthType.SECRET, 'newClientSecret')
        self._CLIENT_STORAGE.addClient(client)
        self.assertEquals(
            self._CLIENT_STORAGE.getClient(client.id).authToken, client.authToken,
            msg='Expected the client storage to contain a client after adding him.')