""" Tests for the implicit code grant flow. """

from txoauth2 import GrantTypes

from tests import MockRequest
from tests.unit.testGrant import Abstract


class TestImplicitCodeGrant(Abstract.SharedGrantTest):
    """
    Test the Implicit Code Grant.
    See https://tools.ietf.org/html/rfc6749#section-4.2
    """
    _RESPONSE_TYPE = 'token'

    # pylint: disable=arguments-differ
    def assertValidCodeResponse(self, request, result, data, msg, expectedAdditionalData=None,
                                expectedScope=None, parameterInFragment=True,
                                expectedAccessTokenLifetime=None):
        """
        Validate the parameters of the uri that the authorization endpoint redirected to.

        :param request: The request.
        :param result: The result of the grantAccess call.
        :param data: The data that was stored in the persistent storage.
        :param msg: The assertion message.
        :param expectedAdditionalData: Expected additional data stored alongside the token.
        :param expectedScope: The expected scope of the token.
        :param parameterInFragment: Whether or not the return parameters
                                    are in the query or fragment of the redirect uri.
        :param expectedAccessTokenLifetime: The expected lifetime of the auth token.
        :return: The redirect parameters extracted from the redirect url.
        """
        if msg.endswith('.'):
            msg = msg[:-1]
        redirectParameter = super(TestImplicitCodeGrant, self).assertValidCodeResponse(
            request, result, data, msg, parameterInFragment)
        if expectedScope is None:
            expectedScope = data['scope']
        self.assertIn(
            'scope', redirectParameter, msg=msg + ': Expected the authorization resource send the '
                                                  'scope of the access token to the redirect uri.')
        self.assertEqual(' '.join(expectedScope), redirectParameter['scope'],
                         msg=msg + ': Expected the authorization resource to send '
                                   'the expected scope to the redirect uri.')
        self.assertNotIn(
            'refresh_token', redirectParameter,
            msg=msg + ': Expected the authorization resource to not send a refresh token.')
        self.assertIn('access_token', redirectParameter,
                      msg=msg + ': Expected the authorization resource to send '
                                'an access token to the redirect uri.')
        self.assertIn('token_type', redirectParameter,
                      msg=msg + ': Expected the authorization resource to send '
                                'the token type to the redirect uri.')
        self.assertEqual('Bearer', redirectParameter['token_type'],
                         msg=msg + ': Expected the authorization resource to send the '
                                   'correct token type to the redirect uri.')
        self.assertIn('expires_in', redirectParameter,
                      msg=msg + ': Expected the authorization resource to send '
                                'the token lifetime to the redirect uri.')
        if expectedAccessTokenLifetime is None:
            expectedAccessTokenLifetime = self._AUTH_RESOURCE.authTokenLifeTime
        self.assertEqual(str(expectedAccessTokenLifetime), redirectParameter['expires_in'],
                         msg=msg + ': Expected the authorization resource to send the '
                                   'correct token lifetime to the redirect uri.')
        accessToken = redirectParameter['access_token']
        self.assertTrue(self._TOKEN_STORAGE.contains(accessToken),
                        msg=msg + ': Expected the authorization resource to store the '
                                  'auth token in the token storage.')
        self.assertTrue(self._TOKEN_STORAGE.hasAccess(accessToken, expectedScope),
                        msg=msg + ': Expected the authorization resource to give the '
                                  'auth token access to the expected scope.')
        self.assertEqual(
            expectedAdditionalData, self._TOKEN_STORAGE.getTokenAdditionalData(accessToken),
            msg=msg + ': Expected the authorization resource to store '
                      'the expected additional data with the token.')
        expectedToken = self._TOKEN_FACTORY.expectedTokenRequest(
            expectedAccessTokenLifetime, self._VALID_CLIENT, expectedScope, expectedAdditionalData)
        self._TOKEN_FACTORY.assertAllTokensRequested()
        self.assertEqual(
            expectedToken, accessToken, msg=msg + ': Expected the authorization resource to return '
                                                  'the expected token to the redirect uri.')

    def testAccessTokenLifetime(self):
        """ Ensure that the token lifetime is controlled by the authTokenLifeTime parameter. """
        dataKey = 'implicitGrantDataKeySubsetLifetime'
        redirectUri = self._VALID_CLIENT.redirectUris[0]
        request = MockRequest('GET', 'some/path')
        lifetime = 10
        scope = ['All']
        data = {
            'response_type': GrantTypes.IMPLICIT.value,
            'redirect_uri': redirectUri,
            'client_id': self._VALID_CLIENT.id,
            'scope': scope,
            'state': b'state\xFF\xFF'
        }
        self._PERSISTENT_STORAGE.put(dataKey, data)
        authResource = self.TestOAuth2Resource(
            self._TOKEN_FACTORY, self._PERSISTENT_STORAGE, self._CLIENT_STORAGE,
            authTokenLifeTime=lifetime, authTokenStorage=self._TOKEN_STORAGE)
        result = authResource.grantAccess(request, dataKey, scope=scope)
        self.assertValidCodeResponse(
            request, result, data, expectedScope=scope, expectedAccessTokenLifetime=lifetime,
            msg='Expected the auth resource to correctly handle a valid accepted {type} grant '
                'with a subset of the scope original requested.'.format(type=self._RESPONSE_TYPE))

    def testGrantAccessAdditionalData(self):
        """ Ensure that the expected additional data is stored alongside the auth token. """
        self._testGrantAccessAdditionalData(
            dataKey='implicitGrantDataKeyAdditionalData',
            responseType=GrantTypes.IMPLICIT.value,
            msg='Expected the auth resource to correctly handle a valid accepted implicit grant '
                'and store the token with the given additional data.')
