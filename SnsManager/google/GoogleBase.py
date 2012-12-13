import httplib2
from apiclient.discovery import build
from oauth2client.client import OAuth2Credentials, AccessTokenRefreshError
from SnsManager.SnsBase import SnsBase
from SnsManager import ErrorCode

class GoogleBase(SnsBase):
    def __init__(self, *args, **kwargs):
        super(GoogleBase, self).__init__(*args, **kwargs)
        for k in ['refreshToken', 'clientId', 'clientSecret']:
            if k not in kwargs:
                raise ValueError('Invalid parameters.')
            setattr(self, '_' + k, kwargs[k])

        self.myId = self.getMyId()
        self._userAgent = 'Waveface AOStream/1.0'
        self._tokenUri = 'https://accounts.google.com/o/oauth2/token'

        self._http = httplib2.Http()
        credentials = OAuth2Credentials(self._accessToken, self._clientId, self._clientSecret, self._refreshToken, None, self._tokenUri, self._userAgent)
        self._http = credentials.authorize(self._http)

    def getMyId(self):
        try:
            userInfo = build('oauth2', 'v2', http=self._http).userinfo().get().execute()
            self.myId = userInfo['email']
        except:
            return None
        return self.myId

    def isTokenValid(self):
        try:
            userInfo = build('oauth2', 'v2', http=self._http).userinfo().get().execute()
        except AccessTokenRefreshError as e:
            return ErrorCode.E_INVALID_TOKEN
        except:
            self._logger.exception('GoogleBase::isTokenValid() exception')
            return ErrorCode.E_FAILED
        else:
            return ErrorCode.S_OK
