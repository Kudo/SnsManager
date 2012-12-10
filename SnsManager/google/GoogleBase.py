import httplib2
from apiclient.discovery import build
from oauth2client.client import AccessTokenCredentials, AccessTokenCredentialsError
from SnsManager.SnsBase import SnsBase
from SnsManager import ErrorCode

class GoogleBase(SnsBase):
    def __init__(self, *args, **kwargs):
        super(GoogleBase, self).__init__(*args, **kwargs)
        self.myId = self.getMyId()
        self._userAgent = 'Waveface AOStream/1.0'

        self._http = httplib2.Http()
        credentials = AccessTokenCredentials(self._accessToken, self._userAgent)
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
        except AccessTokenCredentialsError as e:
            return ErrorCode.E_INVALID_TOKEN
        except:
            self._logger.exception('GoogleBase::isTokenValid() exception')
            return ErrorCode.E_FAILED
        else:
            return ErrorCode.S_OK
