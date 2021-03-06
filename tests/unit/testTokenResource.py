""" Tests for the token resource. """

import json
import warnings

from twisted.web import error
from twisted.web.server import NOT_DONE_YET

from txoauth2 import GrantTypes
from txoauth2.clients import PublicClient
from txoauth2.errors import InsecureConnectionError, UnsupportedGrantTypeError, \
    MalformedRequestError, NoClientAuthenticationError, MultipleClientAuthenticationError, \
    MultipleClientCredentialsError, InvalidClientIdError, InvalidClientAuthenticationError, \
    MalformedParameterError, MultipleParameterError, MissingParameterError, InvalidParameterError
from txoauth2.imp import DictTokenStorage
from txoauth2.token import TokenResource

from tests import TwistedTestCase, TestTokenFactory, getTestPasswordClient, TestClientStorage, \
    MockRequest, TestPasswordManager, TestPersistentStorage


class Abstract(object):
    """ Wrapper for the abstract TokenResourceTest to hide it during test discovery. """

    class TokenResourceTest(TwistedTestCase):
        """ Abstract base class for test targeting the token resource. """
        _VALID_REFRESH_TOKEN = 'refreshToken'
        _VALID_SCOPE = ['All', 'scope']
        _VALID_CLIENT = getTestPasswordClient()

        @classmethod
        def setUpClass(cls):
            super(Abstract.TokenResourceTest, cls).setUpClass()
            cls._AUTH_TOKEN_STORAGE = DictTokenStorage()
            cls._REFRESH_TOKEN_STORAGE = DictTokenStorage()
            cls._TOKEN_FACTORY = TestTokenFactory()
            cls._PERSISTENT_STORAGE = TestPersistentStorage()
            cls._CLIENT_STORAGE = TestClientStorage()
            cls._REFRESH_TOKEN_STORAGE.store(
                cls._VALID_REFRESH_TOKEN, cls._VALID_CLIENT, cls._VALID_SCOPE)
            cls._CLIENT_STORAGE.addClient(cls._VALID_CLIENT)
            cls._PASSWORD_MANAGER = TestPasswordManager()
            cls._TOKEN_RESOURCE = TokenResource(
                cls._TOKEN_FACTORY, cls._PERSISTENT_STORAGE, cls._REFRESH_TOKEN_STORAGE,
                cls._AUTH_TOKEN_STORAGE, cls._CLIENT_STORAGE, passwordManager=cls._PASSWORD_MANAGER)

        @classmethod
        def tearDownClass(cls):
            setattr(TokenResource, '_OAuthTokenStorage', None)

        def setUp(self):
            self._TOKEN_FACTORY.reset(self)

        @staticmethod
        def _addAuthenticationToRequestHeader(request, client):
            """ Add authentication with the clients credentials to the header of the request. """
            request.addAuthorization(client.id, client.secret)

        @classmethod
        def generateValidTokenRequest(cls, url='token', urlQuery='', authentication=None, **kwargs):
            """
            :param url: The request url.
            :param urlQuery: An optional query part of the request url.
            :param authentication: An optional client to use for header-authentication.
            :param kwargs: Optional arguments to the the request.
            :return: A valid request to the token resource.
            """
            if urlQuery:
                url = '?'.join((url, urlQuery))
            request = MockRequest('POST', url, **kwargs)
            request.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded')
            if authentication is not None:
                cls._addAuthenticationToRequestHeader(request, authentication)
            return request

        def assertValidTokenResponse(self, request, result, expectedAccessToken,
                                     expectedExpireTime=None, expectedTokenType='Bearer',
                                     expectedRefreshToken=None, expectedScope=None,
                                     expectedAdditionalData=None):
            """
            Assert that the request succeeded and the token resource returned a correct response.
            :param request: The request.
            :param result: The return value of the render_POST function of the token resource.
            :param expectedAccessToken: The new token that the token resource should have created.
            :param expectedExpireTime: The expire time of the new token.
            :param expectedTokenType: The expected type of the token.
            :param expectedRefreshToken: The expected optional refresh token that
                                         the token resource should have created.
            :param expectedScope: The expected scope of all new created tokens.
            :param expectedAdditionalData: The optional additional data of the new tokens.
            """
            self.assertEqual(
                'application/json;charset=UTF-8', request.getResponseHeader('Content-Type'),
                msg='Expected the token resource to return the token in the json format.')
            self.assertEqual('no-store', request.getResponseHeader('Cache-Control'),
                             msg='Expected the token resource to set Cache-Control to "no-store".')
            self.assertEqual('no-cache', request.getResponseHeader('Pragma'),
                             msg='Expected the token resource to set Pragma to "no-cache".')
            self.assertEqual(200, request.responseCode,
                             msg='Expected the token resource to return '
                                 'a new token with the HTTP code 200 OK.')
            jsonResult = json.loads(result.decode('utf-8'))
            self.assertIn('access_token', jsonResult,
                          msg='Expected the result from the token resource '
                              'to contain an access_token parameter.')
            self.assertEqual(
                expectedAccessToken, jsonResult['access_token'],
                msg='The token resource returned a different access token than expected.')
            self.assertIn('token_type', jsonResult,
                          msg='Expected the result from the token resource '
                              'to contain a token_type parameter.')
            self.assertEqual(
                expectedTokenType.lower(), jsonResult['token_type'].lower(),
                msg='The token resource returned a different access token type than expected.')
            if expectedExpireTime is None:
                self.assertNotIn('expires_in', jsonResult,
                                 msg='Expected the result from the token resource '
                                     'to not contain an expires_in parameter.')
            else:
                self.assertIn('expires_in', jsonResult,
                              msg='Expected the result from the token resource '
                                  'to contain an expires_in parameter.')
                self.assertEqual(expectedExpireTime, jsonResult['expires_in'],
                                 msg='The token resource returned a different '
                                     'access token expire time than expected.')
            if expectedRefreshToken is None:
                self.assertNotIn('refresh_token', jsonResult,
                                 msg='Expected the result from the token resource '
                                     'to not contain a refresh_token parameter.')
            else:
                self.assertIn('refresh_token', jsonResult,
                              msg='Expected the result from the token resource '
                                  'to contain a refresh_token parameter.')
                self.assertEqual(expectedRefreshToken, jsonResult['refresh_token'],
                                 msg='The token resource returned a different '
                                     'refresh token than expected.')
            if expectedScope is None:
                self.assertNotIn('scope', jsonResult,
                                 msg='Expected the result from the token resource '
                                     'to not contain a scope parameter.')
                expectedScope = self._VALID_SCOPE
            else:
                self.assertIn('scope', jsonResult,
                              msg='Expected the result from the token resource '
                                  'to contain a scope parameter.')
                self.assertListEqual(jsonResult['scope'].split(), expectedScope,
                                     msg='The token resource returned a different '
                                         'scope than expected.')
            self.assertTrue(self._AUTH_TOKEN_STORAGE.contains(expectedAccessToken),
                            msg='Expected the token storage to contain the new access token.')
            self.assertTrue(
                self._AUTH_TOKEN_STORAGE.hasAccess(expectedAccessToken, expectedScope),
                msg='Expected the new access token to have access to the expected scope.')
            self.assertEqual(
                expectedAdditionalData,
                self._AUTH_TOKEN_STORAGE.getTokenAdditionalData(expectedAccessToken),
                msg='Expected the new access token to have the expected additional data.')
            if expectedRefreshToken is not None:
                self.assertTrue(self._REFRESH_TOKEN_STORAGE.contains(expectedRefreshToken),
                                msg='Expected the token storage to contain the refresh token.')
                self.assertTrue(
                    self._REFRESH_TOKEN_STORAGE.hasAccess(expectedRefreshToken, expectedScope),
                    msg='Expected the refresh token to have access to the expected scope.')
                self.assertEqual(
                    expectedAdditionalData,
                    self._REFRESH_TOKEN_STORAGE.getTokenAdditionalData(expectedAccessToken),
                    msg='Expected the new refresh token to have the expected additional data.')

        def assertFailedTokenRequest(self, request, result, expectedError, msg):
            """
            Assert that the request did not succeed and that
            the token resource returned an appropriate error response.
            :param request: The request.
            :param result: The return value of the render_POST function of the token resource.
            :param expectedError: The expected error.
            :param msg: The assertion error message.
            """
            if result == NOT_DONE_YET:
                result = request.getResponse()
            if msg.endswith('.'):
                msg = msg[:-1]
            self.assertEqual(
                'application/json;charset=UTF-8', request.getResponseHeader('Content-Type'),
                msg='Expected the token resource to return an error in the json format.')
            self.assertEqual('no-store', request.getResponseHeader('Cache-Control'),
                             msg='Expected the token resource to set Cache-Control to "no-store".')
            self.assertEqual('no-cache', request.getResponseHeader('Pragma'),
                             msg='Expected the token resource to set Pragma to "no-cache".')
            self.assertEqual(expectedError.code, request.responseCode,
                             msg='Expected the token resource to return a response '
                                 'with the HTTP code {code}.'.format(code=expectedError.code))
            errorResult = json.loads(result.decode('utf-8'))
            self.assertIn('error', errorResult, msg=msg + ': Missing error parameter in response.')
            self.assertEqual(expectedError.name, errorResult['error'],
                             msg=msg + ': Result contained a different error than expected.')
            self.assertIn('error_description', errorResult,
                          msg=msg + ': Missing error_description parameter in response.')
            self.assertEqual(
                expectedError.description, errorResult['error_description'],
                msg=msg + ': Result contained a different error description than expected.')
            if expectedError.errorUri is not None:
                self.assertIn('error_uri', errorResult,
                              msg=msg + ': Missing error_uri parameter in response.')
                self.assertEqual(expectedError.errorUri, errorResult['error_uri'],
                                 msg=msg + ': Result contained an unexpected error_uri.')
            if expectedError.name == 'invalid_client':
                self.assertEqual(
                    401, request.responseCode,
                    msg='Expected the token resource to return UNAUTHORIZED as the response code.')
                authenticateResponse = request.getResponseHeader('WWW-Authenticate')
                self.assertIsNotNone(
                    authenticateResponse,
                    msg='If the request has authentication via the "Authorization" header field, '
                        'the result must include the "WWW-Authenticate" response header field.')
                authType, _ = authenticateResponse.split(' ', 1)
                self.assertEqual(
                    'Bearer', authType,
                    msg='Expected an WWW-Authenticate response to use the Bearer scheme.')
                expectedHeaderValue = 'realm="' + request.prePathURL().decode('utf-8') + '"'
                self.assertIn(expectedHeaderValue, authenticateResponse,
                              msg='The "realm" auth-parameter does not contain the '
                                  'expected value: ' + expectedHeaderValue)


# pylint: disable=too-many-public-methods
class TestTokenResource(Abstract.TokenResourceTest):
    """ Test the functionality of the token resource that is shared among the grant types. """

    def testInsecureConnection(self):
        """
        Test the rejection of a request via an insecure transport,
        except if allowInsecureRequestDebug is set to true.
        """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        }, authentication=self._VALID_CLIENT, isSecure=False)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, InsecureConnectionError(),
            msg='Expected the token resource to reject a request made via an insecure transport')
        debugTokenResource = TokenResource(
            self._TOKEN_FACTORY, self._PERSISTENT_STORAGE, self._REFRESH_TOKEN_STORAGE,
            self._AUTH_TOKEN_STORAGE, self._CLIENT_STORAGE, allowInsecureRequestDebug=True,
            passwordManager=self._PASSWORD_MANAGER)
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        }, authentication=self._VALID_CLIENT, isSecure=False)
        newAuthToken = 'tokenViaInsecureConnection'
        self._TOKEN_FACTORY.expectTokenRequest(
            newAuthToken, debugTokenResource.authTokenLifeTime,
            self._VALID_CLIENT, self._VALID_SCOPE)
        result = debugTokenResource.render_POST(request)
        self._TOKEN_FACTORY.assertAllTokensRequested()
        self.assertValidTokenResponse(
            request, result, newAuthToken, expectedExpireTime=debugTokenResource.authTokenLifeTime,
            expectedScope=self._VALID_SCOPE)

    def testRequiresPostMethod(self):
        """ Test the rejection of any request that is not a POST request. """
        self.assertListEqual([b'POST'], self._TOKEN_RESOURCE.allowedMethods,
                             msg='Expected the token resource to only accept POST requests.')
        methods = [name[7:] for name in dir(self._TOKEN_RESOURCE)
                   if name.startswith('render_') and callable(getattr(self._TOKEN_RESOURCE, name))]
        for method in methods:
            if method == 'POST':
                continue
            self.assertRaises(error.UnsupportedMethod, self._TOKEN_RESOURCE.render,
                              MockRequest(method, 'token'))
        try:
            self._TOKEN_RESOURCE.render(MockRequest('POST', 'token'))
        except error.UnsupportedMethod:
            self.fail('Expected the token resource to accept POST requests.')

    def testInvalidContentType(self):
        """ Test the rejection requests whose content is not "x-www-form-urlencoded". """
        request = MockRequest('POST', 'token', arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        request.setRequestHeader('Content-Type', 'application/not-x-www-form-urlencoded')
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result,
            MalformedRequestError('The Content-Type must be "application/x-www-form-urlencoded"'),
            msg='Expected the token resource to reject a request with an invalid content type.')

    def testIgnoresUnrecognizedArgs(self):
        """ Test that unrecognized parameter are ignored. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        }, urlQuery='unrecognized=1', authentication=self._VALID_CLIENT)
        newAuthToken = 'tokenWithUnrecognizedArgs'
        self._TOKEN_FACTORY.expectTokenRequest(newAuthToken, self._TOKEN_RESOURCE.authTokenLifeTime,
                                               self._VALID_CLIENT, self._VALID_SCOPE)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self._TOKEN_FACTORY.assertAllTokensRequested()
        self.assertValidTokenResponse(
            request, result, newAuthToken,
            self._TOKEN_RESOURCE.authTokenLifeTime, expectedScope=self._VALID_SCOPE)

    def testDuplicatedGrantType(self):
        """ Test the rejection of a request with multiple grant_type parameters. """
        validArguments = {'grant_type': 'refresh_token', 'refresh_token': self._VALID_REFRESH_TOKEN}
        request = self.generateValidTokenRequest(
            urlQuery='grant_type=' + validArguments['grant_type'],
            arguments=validArguments, authentication=self._VALID_CLIENT)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(request, result, MultipleParameterError('grant_type'),
                                      msg='Expected the token resource to reject a request '
                                          'with multiple grant_type parameters')
        request = self.generateValidTokenRequest(urlQuery='grant_type=1', arguments=validArguments,
                                                 authentication=self._VALID_CLIENT)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MultipleParameterError('grant_type'),
            msg='Expected the token resource to reject a request with multiple grant_type '
                'parameters, even if one parameter is an unknown grant type.')

    def testUnsupportedGrantType(self):
        """ Test the rejection of a request with an unsupported grant type. """
        grantType = 'extendedFunctionalityGrantType'
        request = self.generateValidTokenRequest(arguments={'grant_type': grantType},
                                                 authentication=self._VALID_CLIENT)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, UnsupportedGrantTypeError(grantType),
            msg='Expected the token resource to reject a request with an unknown grant type.')
        tokenResource = TokenResource(
            self._TOKEN_FACTORY, self._PERSISTENT_STORAGE, self._REFRESH_TOKEN_STORAGE,
            self._AUTH_TOKEN_STORAGE, self._CLIENT_STORAGE, grantTypes=[grantType])
        result = tokenResource.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, UnsupportedGrantTypeError(grantType),
            msg='Expected the token resource to reject a request with an unsupported grant type.')

    def testNoGrantType(self):
        """ Test the rejection of a request without a grant type. """
        request = self.generateValidTokenRequest(authentication=self._VALID_CLIENT)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MissingParameterError(name='grant_type'),
            msg='Expected the token resource to reject a request without a grant type.')

    def testInvalidGrantType(self):
        """ Test the rejection of a request with an invalid grant type. """
        request = self.generateValidTokenRequest(arguments={'grant_type': b'grantType\xFF\xFF'},
                                                 authentication=self._VALID_CLIENT)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, InvalidParameterError('grant_type'),
            msg='Expected the token resource to reject a request with an invalid grant type.')

    def testIsValidToken(self):
        """ Test that the isValidToken method rejects invalid tokens and accepts valid ones. """
        self.assertTrue(TokenResource.isValidToken('aValidToken'),
                        msg='Expected isValidToken to accept a valid token.')
        self.assertTrue(TokenResource.isValidToken(TokenResource.VALID_TOKEN_CHARS),
                        msg='Expected isValidToken to accept a valid token.')
        self.assertFalse(TokenResource.isValidToken('Token!'),
                         msg='Expected isValidToken to accept an invalid token.')
        self.assertFalse(TokenResource.isValidToken('an invalid Token'),
                         msg='Expected isValidToken to accept an invalid token.')

    def testAuthorizationWithoutClientAuth(self):
        """ Test the rejection of a request without client authentication. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, NoClientAuthenticationError(),
            msg='Expected the token resource to reject a request without any authentication.')
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN,
            'client_id': self._VALID_CLIENT.id,
        })
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, NoClientAuthenticationError(),
            msg='Expected the token resource to reject a request without client authentication.')

    def testAuthorizationClientAuthInHeader(self):
        """ Test that a request with valid client authentication in the header is accepted. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        self._addAuthenticationToRequestHeader(request, self._VALID_CLIENT)
        newAuthToken = 'tokenWithAuthInHeader'
        self._TOKEN_FACTORY.expectTokenRequest(newAuthToken, self._TOKEN_RESOURCE.authTokenLifeTime,
                                               self._VALID_CLIENT, self._VALID_SCOPE)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self._TOKEN_FACTORY.assertAllTokensRequested()
        self.assertValidTokenResponse(
            request, result, newAuthToken,
            self._TOKEN_RESOURCE.authTokenLifeTime, expectedScope=self._VALID_SCOPE)

    def testAuthorizationClientAuthInParams(self):
        """ Test that a request with valid client authentication in the parameters is accepted. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN,
            'client_id': self._VALID_CLIENT.id,
            'client_secret': self._VALID_CLIENT.secret
        })
        newAuthToken = 'tokenWithAuthInParameter'
        self._TOKEN_FACTORY.expectTokenRequest(newAuthToken, self._TOKEN_RESOURCE.authTokenLifeTime,
                                               self._VALID_CLIENT, self._VALID_SCOPE)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self._TOKEN_FACTORY.assertAllTokensRequested()
        self.assertValidTokenResponse(
            request, result, newAuthToken,
            self._TOKEN_RESOURCE.authTokenLifeTime, expectedScope=self._VALID_SCOPE)

    def testAuthorizationMultipleClientId(self):
        """ Test the rejection of a request with multiple client ids. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'client_id': [self._VALID_CLIENT.id] * 2,
            'client_secret': self._VALID_CLIENT.secret,
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MultipleClientCredentialsError(),
            msg='Expected the token resource to reject a request with multiple client ids.')

    def testAuthorizationMultipleClientSecret(self):
        """ Test the rejection of a request with multiple client secrets. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'client_id': self._VALID_CLIENT.id,
            'client_secret': [self._VALID_CLIENT.secret] * 2,
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MultipleParameterError('client_secret'),
            msg='Expected the token resource to reject a request with multiple client secrets.')

    def testAuthorizationWithClientAuthInHeaderAndParameter(self):
        """
        Test the rejection of a request with client authorization in the header and the parameters.
        """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN,
            'client_id': self._VALID_CLIENT.id,
            'client_secret': self._VALID_CLIENT.secret
        })
        self._addAuthenticationToRequestHeader(request, self._VALID_CLIENT)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MultipleClientAuthenticationError(),
            msg='Expected the token resource to reject a request which utilizes '
                'more than one mechanism for authenticating the client.')

    def testAuthorizationWithDifferentClientAuthInHeaderAndParameter(self):
        """
        Test the rejection of a request with different
        client authorization in the header and the parameters.
        """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN,
            'client_id': self._VALID_CLIENT.id,
            'client_secret': self._VALID_CLIENT.secret
        })
        request.addAuthorization('otherClientId', 'otherClientSecret')
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MultipleClientCredentialsError(),
            msg='Expected the token resource to reject a request with multiple client ids.')

    def testAuthorizationWithDifferentClientIdInHeaderAndParameter(self):
        """
        Test the rejection of a request with different client ids in the header and the parameters.
        """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'client_id': self._VALID_CLIENT.id,
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        request.addAuthorization('otherClientId', 'otherClientSecret')
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MultipleClientCredentialsError(),
            msg='Expected the token resource to reject a request with multiple client credentials.')

    def testAuthorizationMalformedClientIdInHeader(self):
        """ Test the rejection of a request with a malformed client id in the header. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        request.addAuthorization(b'malformedId\xFF\xFF', b'clientSecret')
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MalformedParameterError('client_id'),
            msg='Expected the token resource to reject a '
                'request with a malformed Authorization header.')

    def testAuthorizationMalformedClientSecretInHeader(self):
        """ Test the rejection of a request with a malformed client secret in the header. """
        client = getTestPasswordClient('malformedSecret')
        client.secret = b'malformedSecret\xFF\xFF'
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        self._addAuthenticationToRequestHeader(request, client)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MalformedParameterError('client_secret'),
            msg='Expected the token resource to reject a '
                'request with a malformed Authorization header.')

    def testAuthorizationInvalidClientId(self):
        """ Test the rejection of a request with an invalid client in the parameters. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'client_id': 'invalidClientId',
            'client_secret': self._VALID_CLIENT.secret,
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, InvalidClientIdError(),
            msg='Expected the token resource to reject a request with an invalid client id.')

    def testAuthorizationInvalidClientIdInHeader(self):
        """ Test the rejection of a request with an invalid client in the headers. """
        client = getTestPasswordClient('invalidClientId')
        client.secret = self._VALID_CLIENT.secret
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        self._addAuthenticationToRequestHeader(request, client)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, InvalidClientIdError(),
            msg='Expected the token resource to reject a request with an invalid client id.')

    def testAuthorizationMalformedClientId(self):
        """ Test the rejection of a request with a malformed client in the parameters. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'client_id': b'malformedClientId\xFF\xFF',
            'client_secret': self._VALID_CLIENT.secret,
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MalformedParameterError('client_id'),
            msg='Expected the token resource to reject a request with a malformed client id.')

    def testAuthorizationWrongClientSecret(self):
        """ Test the rejection of a request with an invalid client secret in the parameters. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'client_id': self._VALID_CLIENT.id,
            'client_secret': 'invalidSecret',
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, InvalidClientAuthenticationError(),
            msg='Expected the token resource to reject a request with an invalid client secret.')

    def testAuthorizationWrongClientSecretInHeader(self):
        """ Test the rejection of a request with an invalid client secret in the header. """
        client = getTestPasswordClient(self._VALID_CLIENT.id)
        client.secret = 'invalidSecret'
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        self._addAuthenticationToRequestHeader(request, client)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, InvalidClientAuthenticationError(),
            msg='Expected the token resource to reject a request with an invalid client secret.')

    def testAuthorizationMalformedClientSecret(self):
        """ Test the rejection of a request with an malformed client secret in the parameters. """
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'client_id': self._VALID_CLIENT.id,
            'client_secret': b'malformedSecret\xFF\xFF',
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        result = self._TOKEN_RESOURCE.render_POST(request)
        self.assertFailedTokenRequest(
            request, result, MalformedParameterError('client_secret'),
            msg='Expected the token resource to reject a request with a malformed client secret.')

    def testAuthorizationForPublicClient(self):
        """ Test that a request for a public client gets accepted without authentication. """
        client = PublicClient('publicClient', ['https://return.nonexistent'], ['refresh_token'])
        refreshToken = 'publicClientRefreshToken'
        request = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'client_id': client.id,
            'refresh_token': refreshToken
        })
        self._REFRESH_TOKEN_STORAGE.store(refreshToken, client, self._VALID_SCOPE)
        newAuthToken = 'tokenForPublicClient'
        self._CLIENT_STORAGE.addClient(client)
        self._TOKEN_FACTORY.expectTokenRequest(newAuthToken, self._TOKEN_RESOURCE.authTokenLifeTime,
                                               client, self._VALID_SCOPE)
        result = self._TOKEN_RESOURCE.render_POST(request)
        self._TOKEN_FACTORY.assertAllTokensRequested()
        self.assertValidTokenResponse(
            request, result, newAuthToken,
            self._TOKEN_RESOURCE.authTokenLifeTime, expectedScope=self._VALID_SCOPE)

    def testWarnsOnReturningErrorFromAuthenticateClient(self):
        """
        Test that the Token resource generates a warning if authenticateClient
        returns an error instead of raising it.
        """

        class ErrorTestClientStorage(TestClientStorage):
            """ A ClientStorage to test returning errors from authenticateClient. """

            def __init__(self, errorToReturn):
                super(ErrorTestClientStorage, self).__init__()
                self.error = errorToReturn

            def authenticateClient(self, client, request, secret=None):
                return self.error

        validRequest = self.generateValidTokenRequest(arguments={
            'grant_type': 'refresh_token',
            'client_id': self._VALID_CLIENT.id,
            'client_secret': self._VALID_CLIENT.secret,
            'refresh_token': self._VALID_REFRESH_TOKEN
        })
        tokenResource = TokenResource(
            self._TOKEN_FACTORY, self._PERSISTENT_STORAGE,
            self._REFRESH_TOKEN_STORAGE, self._AUTH_TOKEN_STORAGE,
            ErrorTestClientStorage(errorToReturn=MalformedParameterError('client_secret')),
            passwordManager=self._PASSWORD_MANAGER)
        with warnings.catch_warnings(record=True) as caughtWarnings:
            warnings.simplefilter('always')
            result = tokenResource.render_POST(validRequest)
            self.assertEqual(
                1, len(caughtWarnings),
                msg='Expected the token resource to generate a warning, if '
                    'authenticateClient returns an OAuth2Error instead of raising it')
            self.assertTrue(issubclass(caughtWarnings[0].category, DeprecationWarning),
                            msg='Expected the token resource to generate a DeprecationWarning')
            self.assertIn(
                'Returning an error from authenticateClient is deprecated',
                str(caughtWarnings[0].message),
                msg='Expected the token resource to generate a DeprecationWarning explaining that '
                    'returning an error from authenticateClient is deprecated.')
        self.assertFailedTokenRequest(
            validRequest, result, MalformedParameterError('client_secret'),
            msg='Expected the token resource to reject the request '
                'if authenticateClient returns an error.')

    def testWarnsOnOverwritingTokenStorage(self):
        """
        Test that a warning is emitted if a second token resource is created with a different
        token storage. This makes the new token storage the new global singleton,
        overwriting the old one, which might be unintended.
        """
        with warnings.catch_warnings(record=True) as caughtWarnings:
            warnings.simplefilter('always')
            TokenResource(
                self._TOKEN_FACTORY, self._PERSISTENT_STORAGE, self._REFRESH_TOKEN_STORAGE,
                self._AUTH_TOKEN_STORAGE, self._CLIENT_STORAGE,
                passwordManager=self._PASSWORD_MANAGER)
            self.assertEqual(0, len(caughtWarnings),
                             msg='Expected the token resource not to generate a warning, if it is '
                                 'created with the same token storage as the previous one')
        try:
            with warnings.catch_warnings(record=True) as caughtWarnings:
                warnings.simplefilter('always')
                differentTokenStorage = DictTokenStorage()
                TokenResource(
                    self._TOKEN_FACTORY, self._PERSISTENT_STORAGE, self._REFRESH_TOKEN_STORAGE,
                    differentTokenStorage, self._CLIENT_STORAGE,
                    passwordManager=self._PASSWORD_MANAGER)
                self.assertEqual(1, len(caughtWarnings),
                                 msg='Expected the token resource to generate a warning, if it is '
                                     'created with a different token storage as the previous one')
                self.assertTrue(issubclass(caughtWarnings[0].category, RuntimeWarning),
                                msg='Expected the token resource to generate a RuntimeWarning')
                self.assertIn(
                    'overwrites previously registered singleton', str(caughtWarnings[0].message),
                    msg='Expected the token resource to generate a RuntimeWarning explaining that '
                        'the previously registered token storage singleton will be overwritten.')
        finally:
            setattr(TokenResource, '_OAuthTokenStorage', self._AUTH_TOKEN_STORAGE)

    def testIgnoresImplicitCodeGrant(self):
        """ Test that the token resource ignores the implicit code grant. """
        tokenResource = TokenResource(
            self._TOKEN_FACTORY, self._PERSISTENT_STORAGE, self._REFRESH_TOKEN_STORAGE,
            self._AUTH_TOKEN_STORAGE, self._CLIENT_STORAGE, grantTypes=[
                GrantTypes.IMPLICIT, GrantTypes.AUTHORIZATION_CODE])
        self.assertListEqual(
            [GrantTypes.AUTHORIZATION_CODE.value], tokenResource.acceptedGrantTypes,
            msg='Expected the token resource to ignore the implicit grant.')

    def testRequiresPasswordManagerForPasswordGrant(self):
        """
        Test that the token resource requires a password manager
        if the password grant is enabled.
        """
        self.assertRaises(ValueError, TokenResource, self._TOKEN_FACTORY, self._PERSISTENT_STORAGE,
                          self._REFRESH_TOKEN_STORAGE, self._AUTH_TOKEN_STORAGE,
                          self._CLIENT_STORAGE, grantTypes=[GrantTypes.PASSWORD])

    def testGetTokenStorageSingletonRaisesErrorOnNoSingleton(self):
        """ Test that getTokenStorageSingleton raises an error if no singleton is registered. """
        oldTokenStorage = TokenResource.getTokenStorageSingleton()
        try:
            setattr(TokenResource, '_OAuthTokenStorage', None)
            self.assertRaises(RuntimeError, TokenResource.getTokenStorageSingleton)
        finally:
            setattr(TokenResource, '_OAuthTokenStorage', oldTokenStorage)
