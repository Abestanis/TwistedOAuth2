""" Test for the Client class. """

from tests import TwistedTestCase
from txoauth2 import GrantTypes
from txoauth2.util import isAnyStr
from txoauth2.clients import Client, PasswordClient


class ClientTest(TwistedTestCase):
    """ Tests the functionality of the Client object. """

    def testClientAttributeTypes(self):
        """ Ensure that all attributes of the client are of the expected type. """
        client = PasswordClient('clientId', ['https://valid.nonexistent'], ['password'], 'secret')
        self.assertTrue(isAnyStr(client.id), msg='The client id must be a string.')
        self.assertIsInstance(client.secret, str, message='The client secret must be a string.')
        self.assertIsInstance(client.redirectUris, list,
                              message='The redirect uris must be a list.')
        for uri in client.redirectUris:
            self.assertIsInstance(uri, str, message='All redirect uris must be strings.')
        self.assertIsInstance(client.authorizedGrantTypes, list,
                              message='The authorized grant types must be a list.')
        for grantType in client.authorizedGrantTypes:
            self.assertIsInstance(grantType, str, message='All grant types must be strings.')
        client = PasswordClient(u'clientId', ['https://valid.nonexistent'], ['password'], 'secret')
        self.assertTrue(isAnyStr(client.id), msg='The client id must be a string.')

    def testAcceptsValidUri(self):
        """ Check that the client does not reject valid redirect uris. """
        # noinspection HttpUrlsUsage
        validUris = [
            'https://valid.nonexistent',
            'http://valid.nonexistent',
            'https://valid.nonexistent/path/subpath',
            'https://valid.nonexistent/path/subpath?querry=1',
            'custom://callback',
        ]
        for uri in validUris:
            self.assertEqual(uri, Client('clientId', [uri], []).redirectUris[0],
                             msg='Expected the client to accept the valid redirect uri ' + uri)

    def testRejectsRedirectUrisWithFragment(self):
        """ Test that the Client rejects redirect uris with fragments. """
        self.assertRaises(ValueError, Client, 'clientId',
                          ['https://example.nonexistent/test#fragment'], [])
        self.assertRaises(ValueError, Client, 'clientId',
                          ['https://v.nonexistent', 'https://sth.nonexistent/test#fragment'], [])

    def testRejectsRelativeRedirectUris(self):
        """ Test that the client rejects relative redirect uris. """
        self.assertRaises(ValueError, Client, 'clientId', ['/relative'], [])
        self.assertRaises(ValueError, Client, 'clientId',
                          ['https://valid.nonexistent', '/test?q=1'], [])

    def testValidatesClientId(self):
        """ Test that the client only accepts client ids that are a string. """
        for clientId in ['clientId', u'clientId']:
            try:
                Client('clientId', [], [])
            except ValueError:
                self.fail('Expected Client to accept a client id of type ' + str(type(clientId)))
        for clientId in [1, None, True, [], {}, object()]:
            self.assertRaises(ValueError, Client, clientId, [], [])
        if not isinstance(b'', str):
            self.assertRaises(ValueError, Client, b'clientId', [], [])

    def testValidatesUris(self):
        """ Test that the client only accepts list of strings as uris. """
        # noinspection HttpUrlsUsage
        for urls in [['https://valid.nonexistent'],
                     ['https://valid.nonexistent', 'http://valid.nonexistent']]:
            try:
                Client('clientId', urls, [])
            except ValueError:
                self.fail('Expected Client to accept these urls: ' + str(urls))
        notString = b'https://valid.nonexistent' if isinstance(u'', str) \
            else u'https://valid.nonexistent'
        for urls in ['x', 1, None, True, object(), [notString], [None], [True], [object()],
                     [notString, 'https://valid.nonexistent'], [None, 'https://valid.nonexistent'],
                     [True, 'https://valid.nonexistent'], [object(), 'https://valid.nonexistent']]:
            self.assertRaises(ValueError, Client, 'clientId', urls, [])

    def testValidatesGrantTypes(self):
        """ Test that the client only accepts list of strings as grant types. """
        for grantType in GrantTypes:
            try:
                Client('clientId', [], [grantType.value])
                Client('clientId', [], [GrantTypes.AUTHORIZATION_CODE.value, grantType.value])
            except ValueError as error:
                self.fail('Expected Client to accept a string grant type: ' + str(error))
            try:
                Client('clientId', [], [grantType])
                Client('clientId', [], [GrantTypes.AUTHORIZATION_CODE, grantType])
            except ValueError as error:
                self.fail('Expected Client to accept a GrantType object: ' + str(error))
        notString = b'Test' if isinstance(u'', str) else u'Test'
        for grantTypes in ['x', 1, None, True, object(), [notString], [None], [True], [object()],
                           [notString, GrantTypes.AUTHORIZATION_CODE],
                           [None, GrantTypes.AUTHORIZATION_CODE],
                           [True, GrantTypes.AUTHORIZATION_CODE],
                           [object(), GrantTypes.AUTHORIZATION_CODE]]:
            self.assertRaises(ValueError, Client, 'clientId', [], grantTypes)
