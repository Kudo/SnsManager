#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import urllib
import urllib3
import urlparse
import logging
import mechanize

FB_APP_ID = '286999781384609'
FB_APP_SECRET = '6ac871a6451d0be21485a1e752fec5d1'

FB_TEST_ACCT_EMAIL = 'Acct'
FB_TEST_ACCT_PASSWORD = 'pass'

FB_APP_REDIRECT_URL_BASE = 'http://localhost:9090/'
FB_PERMS = (
    'email',
    'user_photos',
    'user_videos',
    'user_notes',
    'user_status',
    'read_stream',
)
LOG_FORMAT = '%(asctime)-15s [%(filename)s %(funcName)s():%(lineno)d] - %(message)s'

#logLevel = logging.ERROR
logLevel = logging.DEBUG
logging.basicConfig(stream=sys.stdout, level=logLevel, format=LOG_FORMAT)
g_logger = logging.getLogger()

g_HttpObj = urllib3.PoolManager()

class UrlHitException(Exception):
    def __init__(self, value):
        self.url = value

class HTTPRedirectHookProcessor(mechanize._urllib2_fork.HTTPRedirectHandler):
    def http_request(self, request):
        if request.get_full_url().startswith(FB_APP_REDIRECT_URL_BASE):
            raise UrlHitException(request.get_full_url())
        return request

    https_request = http_request

class OAuth(object):
    def __init__(self, *args, **kwargs):
        self.browser = self._browserInit()

    def _browserInit(self):
        br = mechanize.Browser()
        #br.set_handle_equiv(True)
        #br.set_handle_gzip(True)
        #br.set_handle_redirect(True)
        br._replace_handler('_redirect', HTTPRedirectHookProcessor())
        #br.set_handle_referer(True)
        br.set_handle_robots(False)
        #br.set_debug_http(True)
        #br.set_debug_redirects(True)
        #br.set_debug_responses(True)
        br.addheaders = [('User-agent','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11')]
        return br

    def _doAuth(self):
        params = {
            'client_id' : FB_APP_ID,
            'redirect_uri' : FB_APP_REDIRECT_URL_BASE,
            'scope' : ','.join(FB_PERMS),
        }
        uri = 'https://www.facebook.com/dialog/oauth/?%s' % (urllib.urlencode(params))
        self.browser.open(uri)
        self.browser.select_form(nr=0)
        self.browser['email'] = FB_TEST_ACCT_EMAIL
        self.browser['pass'] =  FB_TEST_ACCT_PASSWORD
        code = ''
        try:
            self.browser.submit()
        except UrlHitException as e:
            qs = e.url[e.url.find('?')+1:]
            code = urlparse.parse_qs(qs)['code'][0]
        return code

    def _exchangeToken(self, code):
        params = {
            'client_id' : FB_APP_ID,
            'client_secret' : FB_APP_SECRET,
            'code' : code,
            'redirect_uri' : FB_APP_REDIRECT_URL_BASE,
        }

        uri = 'https://graph.facebook.com/oauth/access_token?%s' % urllib.urlencode(params)
        try:
            conn = g_HttpObj.urlopen('GET', uri)
            respCode = conn.status
        except:
            g_logger.exception('Unable to send request to Facebook for exchanging token')

        if respCode == 200:
            respObj = dict([pair.split('=') for pair in conn.data.split('&')])
            if 'expires' in respObj:
                g_logger.info('expires[%s]' % (respObj['expires']))
            return True, respObj
        else:
            try:
                resp = conn.read()
                respObj = json.loads(resp)
            except:
                g_logger.error('Unable to parse returned JSON data. resp[%s]' % resp)
                return False, {}
            g_logger.error('Unable to exchange returned code. resp[%s]' % resp)
            return False, respObj

    def getToken(self):
        code = self._doAuth()
        ret, retDict = self._exchangeToken(code)
        if ret is True and 'access_token' in retDict:
            return retDict['access_token']

def main():
    oAuthObj = OAuth()
    token = oAuthObj.getToken()
    print 'Access Token[%s]' % (token)

if __name__ == '__main__':
    main()
