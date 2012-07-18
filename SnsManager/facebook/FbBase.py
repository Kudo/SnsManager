import urllib, urllib2
import urllib3, urllib3.exceptions
import json
from SnsManager.SnsBase import SnsBase

class FbBase(SnsBase):
    def __init__(self, *args, **kwargs):
        """
        Constructor of FbBase
        """
        super(FbBase, self).__init__(*args, **kwargs)
        self._graphUri = 'https://graph.facebook.com/'
        self.myName, self.myEmail, self.myId = self._cacheMyInfo()

    def _cacheMyInfo(self):
        uri = urllib.basejoin(self._graphUri, '/me')
        uri += '?{0}'.format(urllib.urlencode({
            'access_token': self._accessToken,
        }))
        try:
            conn = self._httpConn.urlopen('GET', uri, timeout=self._timeout)
            resp = json.loads(conn.data)
        except urllib3.exceptions.HTTPError as e:
            self._logger.error('Unable to get data from Facebook. uri[{0}] e[{1}]'.format(uri, e))
            return None, None, None
        except ValueError as e:
            self._logger.error('Unable to parse returned data. data[{0}] e[{1}]'.format(conn.data, e))
            return None, None, None
        if not resp or 'name' not in resp or 'email' not in resp or 'id' not in resp:
            self._logger.error('Unable to get name or email attribute from returned data. resp[{0}]'.format(json.dumps(resp)))
            return None, None, None
        return resp['name'], resp['email'], resp['id']

    def getMyName(self):
        return self.myName

    def getMyEmail(self):
        return self.myEmail

    def getMyId(self):
        return self.myId

    def getMyAvatar(self, type='square'):
        """
            Get Avatar link

            Note of type:
            You can specify the picture size you want with the type argument, 
            which should be one of square (50x50), small (50 pixels wide, variable height), 
            normal (100 pixels wide, variable height), 
            and large (about 200 pixels wide, variable height) 
        """
        uri = urllib.basejoin(self._graphUri, '/me/picture')
        uri += '?{0}'.format(urllib.urlencode({
            'access_token': self._accessToken,
            'type': type,
        }))
        try:
            conn = urllib2.urlopen(uri, timeout=self._timeout)
            imgUri = conn.geturl() # Facebook will trigger redirect and we need the uri not the data
        except urllib3.exceptions.HTTPError as e:
            self._logger.error('Unable to get data from Facebook. e[{0}]'.format(e))
            return None
        return imgUri

    def isTokenValid(self):
        uri = urllib.basejoin(self._graphUri, '/me')
        uri += '?{0}'.format(urllib.urlencode({
            'access_token': self._accessToken,
        }))
        try:
            conn = self._httpConn.urlopen('GET', uri, timeout=self._timeout)
            respCode = conn.status
        except urllib3.exceptions.HTTPError as e:
            self._logger.error('Unable to get data from Facebook. uri[{0}] e[{0}]'.format(uri, e))
            return False
        if respCode == 200:
            return True
        return False
