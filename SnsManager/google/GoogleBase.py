import httplib2
from apiclient.discovery import build
from oauth2client.client import AccessTokenCredentials, AccessTokenCredentialsError
from SnsManager.SnsBase import SnsBase
from SnsManager import ErrorCode

class GoogleBase(SnsBase):
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.myId = self.getMyId()
        self._userAgent = 'Waveface AOStream/1.0'

    def getMyId(self):
        try:
            http = httplib2.Http()
            credentials = AccessTokenCredentials(self._accessToken, self._userAgent)
            http = credentials.authorize(http)
            userInfo = build('oauth2', 'v2', http=http).userinfo().get().execute()
            self.myId = userInfo['email']
        except:
            return None
        return self.myId

    def isTokenValid(self):
        try:
            http = httplib2.Http()
            credentials = AccessTokenCredentials(self._accessToken, self._userAgent)
            http = credentials.authorize(http)
            userInfo = build('oauth2', 'v2', http=http).userinfo().get().execute()
        except AccessTokenCredentialsError as e:
            return ErrorCode.E_INVALID_TOKEN
        except:
            self._logger.exception('GoogleBase::isTokenValid() exception')
            return ErrorCode.E_FAILED
        else:
            return ErrorCode.S_OK
