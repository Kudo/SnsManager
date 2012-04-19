import urllib, urllib2
import json
from FbBase import FbBase

class FbUserInfo(FbBase):
    def __init__(self, *args, **kwargs):
        """
        Constructor of FbUserInfo
        """
        FbBase.__init__(self, *args, **kwargs)
        self.name, self.email = self._cacheMyInfo()

    def _cacheMyInfo(self):
        uri = urllib.basejoin(self.graphUri, '/me')
        uri += '?{0}'.format(urllib.urlencode({
            'access_token': self.accessToken,
        }))
        try:
            conn = urllib2.urlopen(uri, timeout=self._timeout)
            resp = json.loads(conn.read())
        except urllib2.URLError as e:
            self.logger.error('Unable to get data from Facebook. e[{0}]'.format(e))
            return None, None
        except ValueError as e:
            self.logger.error('Unable to parse returned data. e[{0}]'.format(e))
            return None, None
        if 'name' not in resp or 'email' not in resp:
            self.logger.error('Unable to get name or email attribute from returned data. resp[{0}]'.format(json.dumps(resp)))
            return None, None
        return resp['name'], resp['email']

    def getMyName(self):
        return self.name

    def getMyEmail(self):
        return self.email

    def getMyAvatar(self, type='square'):
        """
            Get Avatar link

            Note of type:
            You can specify the picture size you want with the type argument, 
            which should be one of square (50x50), small (50 pixels wide, variable height), 
            normal (100 pixels wide, variable height), 
            and large (about 200 pixels wide, variable height) 
        """
        uri = urllib.basejoin(self.graphUri, '/me/picture')
        uri += '?{0}'.format(urllib.urlencode({
            'access_token': self.accessToken,
            'type': type,
        }))
        try:
            conn = urllib2.urlopen(uri, timeout=self._timeout)
            imgUri = conn.geturl() # Facebook will trigger redirect and we need the uri not the data
        except urllib2.URLError as e:
            self.logger.error('Unable to get data from Facebook. e[{0}]'.format(e))
            return None
        return imgUri
