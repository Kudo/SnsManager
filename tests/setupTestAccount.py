#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import urllib
import urllib3
import urlparse
import logging

FB_APP_ID = '286999781384609'
FB_APP_SECRET = '6ac871a6451d0be21485a1e752fec5d1'
LOG_FORMAT = '%(asctime)-15s [%(filename)s %(funcName)s():%(lineno)d] - %(message)s'

g_HttpObj = urllib3.PoolManager()

#logLevel = logging.ERROR
logLevel = logging.DEBUG
logging.basicConfig(stream=sys.stdout, level=logLevel, format=LOG_FORMAT)
g_logger = logging.getLogger()

class AcctManager(object):
    def __init__(self, *args, **kwargs):
        self._appAccessToken = None
        params = {
            'client_id': FB_APP_ID,
            'client_secret': FB_APP_SECRET,
            'grant_type': 'client_credentials',
            'method': 'post',
        }
        uri = 'https://graph.facebook.com/oauth/access_token'
        conn = g_HttpObj.urlopen('POST', uri, body=urllib.urlencode(params))
        resp = urlparse.parse_qs(conn.data)
        if resp and 'access_token' in resp:
            self._appAccessToken = resp['access_token'][0]
            g_logger.debug('app_access_token[%s]' % self._appAccessToken)
        else:
            raise Exception ('Unable to get app_access_token. resp[%s]' % (conn.data))

    def createAcct(self):
        params = {
            'installed': 'true',
            'name': 'TestWfFb',
            'locale': 'en_US',
            'permissions': ','.join((
                'email',
                'user_photos',
                'user_videos',
                'user_notes',
                'user_status',
                'read_stream',
                'publish_stream',
                'status_update',
                'photo_upload',
                'video_upload',
                'publish_checkins',
                'create_note',
                )),
            'method': 'post',
            'access_token': self._appAccessToken,
        }
        uri = 'https://graph.facebook.com/%s/accounts/test-users' % (FB_APP_ID)
        conn = g_HttpObj.urlopen('POST', uri, body=urllib.urlencode(params))
        resp = json.loads(conn.data)
        g_logger.debug(json.dumps(resp, indent=4))
        print 'TestUser id[%s]' % (resp['id'])
        print 'TestUser email[%s]' % (resp['email'])
        print 'TestUser password[%s]' % (resp['password'])
        print 'TestUser access_token[%s]' % (resp['access_token'])
        return resp

    def getAcctInfo(self):
        params = {
            'access_token': self._appAccessToken,
        }
        uri = 'https://graph.facebook.com/%s/accounts/test-users?%s' % (FB_APP_ID, urllib.urlencode(params))
        conn = g_HttpObj.urlopen('GET', uri)
        g_logger.debug('resp[%s]' % (conn.data))
        return json.loads(conn.data)['data']

    def deleteAcct(self, email):
        params = {
            'method': 'delete',
            'access_token': self._appAccessToken,
        }
        uri = 'https://graph.facebook.com/%s' % (email)
        conn = g_HttpObj.urlopen('POST', uri, body=urllib.urlencode(params))
        g_logger.debug('resp[%s]' % (conn.data))

class SetupObjectSuite(object):
    def __init__(self, *args, **kwargs):
        self.accessToken = kwargs['accessToken'] if 'accessToken' in kwargs else None
        self._graphUri = 'https://graph.facebook.com'

    def doAction(self):
        for n in dir(self):
            if n.startswith('setup_'):
                getattr(self, n)()


    def setup_StatusSelfPost(self):
        params = {
            'message': 'Test message',
            'access_token': self.accessToken,
        }
        uri = '%s/me/feed' % (self._graphUri)
        conn = g_HttpObj.urlopen('POST', uri, body=urllib.urlencode(params))
        g_logger.debug('code[%d] resp[%s]' % (conn.status, conn.data))

    def setup_PhotoSelfPost(self):
        fPath = u'/tmp/test01.jpg'
        fH = open(fPath)
        params = {
            'message': 'Test messages',
            'access_token': self.accessToken,
            'source': ('dontCare.jpg', fH.read()),
        }
        fH.close()

        uri = '%s/me/photos' % (self._graphUri)
        conn = g_HttpObj.request_encode_body('POST', uri, fields=params)
        g_logger.debug('code[%d] resp[%s]' % (conn.status, conn.data))


def main():
    acctMgr = AcctManager()
    accessToken = acctMgr.getAcctInfo()[0]['access_token']

    setupObj = SetupObjectSuite(accessToken=accessToken)
    setupObj.doAction()

if __name__ == '__main__':
    main()
