import os
import re
import time
import json
import uuid
import dateutil
import urllib, urllib2
import urlparse
from datetime import datetime
from dateutil import parser as dateParser
from FbBase import FbBase, FbErrorCode
from FbUserInfo import FbUserInfo

class FbImporter(FbBase):
    class DIRECTION:
        FORWARD=1
        BACKWARD=2

    def __init__(self, *args, **kwargs):
        """
        Constructor of FbBase

        In:
            tmpFolder           --  tmp folder to store photo files *optional* default is /tmp 

        """
        FbBase.__init__(self, *args, **kwargs)

        self._tmpFolder = kwargs['tmpFolder'] if 'tmpFolder' in kwargs else '/tmp'

    def getData(self, direction=DIRECTION.FORWARD, since=None, limit=30):
        """
        Get data from Facebook feed

        In:
            direction       --  Direction to retrieve data
            since           --  The start time to get data
                                given None means current time
                                or given python's datetime instance as input
            limit           --  Maximum entity number to retrieve

        Out:
            Return a python dict object
            {
                'data': [               # List of data
                    {
                        'message': 'Text',
                        'links': [ 'uri' ],
                        'photos': [ '/path/to/file' ],
                        'createdTime': <datetime object>,
                        'updatedTime': <datetime object>,
                    },
                ],
                'count': 30,                    # count in data list
                'retCode': FbErrorCode.S_OK,    # returned code which is instance of FbErrorCode
                'lastTime': <datetime object>,  # if direction is FORWARD, the value is the oldest feed time
                                                # Otherwise, the value is the latest feed time

            }
        """
        params = {
            'access_token' : self._accessToken,
            'limit' : limit,
        }
        if direction is FbImporter.DIRECTION.FORWARD:
            if since:
                params['since'] = self._datetime2Timestamp(since)
        else:
            if since:
                params['until'] = self._datetime2Timestamp(since)
            else:
                params['until'] = self._datetime2Timestamp(datetime.now())

        retDict = {
            'retCode': FbErrorCode.E_FAILED,
            'count': 0,
            'data': {},
        }

        uri = '{0}me/feed?{1}'.format(self._graphUri, urllib.urlencode(params))
        self._logger.debug('FbImporter::getData() uri to retrieve [%s]' % uri)
        conn = urllib2.urlopen(uri, timeout=self._timeout)
        feedData = json.loads(conn.read())
        if 'data' not in feedData or 'paging' not in feedData:
            retDict['retCode'] = FbErrorCode.E_NO_DATA
            return retDict

        feedHandler = FbFeedsHandler(tmpFolder=self._tmpFolder,
            myFbId=FbUserInfo(accessToken=self._accessToken).getMyId(),
            accessToken=self._accessToken,
            feeds=feedData,
            logger=self._logger,
            )
        handledData = feedHandler.doAction()

        retDict['data'] = handledData
        retDict['count'] = len(retDict['data'])
        if handledData is not None:
            retDict['retCode'] = FbErrorCode.S_OK

        if direction is FbImporter.DIRECTION.FORWARD:
            ts = urlparse.parse_qs(urlparse.urlsplit(feedData['paging']['previous']).query)['since'][0]
        else:
            ts = urlparse.parse_qs(urlparse.urlsplit(feedData['paging']['next']).query)['until'][0]
        retDict['lastTime'] = datetime.fromtimestamp(int(ts))

        return retDict

    def _datetime2Timestamp(self, datetimeObj):
        return int(time.mktime(datetimeObj.timetuple()))

class FbFeedsHandler(FbBase):
    def __init__(self, *args, **kwargs):
        FbBase.__init__(self, *args, **kwargs)
        self._tmpFolder = kwargs.get('tmpFolder', '/tmp')
        self._feeds = kwargs['feeds']
        self._myFbId = kwargs['myFbId']

    def doAction(self):
        if 'data' not in self._feeds:
            raise ValueError()

        retData = []
        for feed in self._feeds['data']:
            if not self._feedFilter(feed):
                continue
            parsedData = self._feedParser(feed)
            if parsedData:
                self._dumpData(parsedData)
                retData.append(parsedData)
        return retData

    def _convertTimeFormat(self, fbTime):
        return dateParser.parse(fbTime)

    def _storeFileToTemp(self, fileUri):
        fileExtName = fileUri[fileUri.rfind('.') + 1:]
        newFileName = os.path.join(self._tmpFolder, "{0}.{1}".format(str(uuid.uuid1()), fileExtName))
        try:
            conn = urllib2.urlopen(fileUri)
            fileObj = file(newFileName, 'w')
            fileObj.write(conn.read())
            fileObj.close()
        except:
            return None
        return newFileName

    def _feedFilter(self, feed):
        # Strip contents which not posted by me
        if feed['from']['id'] != self._myFbId:
            return False

        # Type filter
        if 'type' not in feed:
            raise ValueError()
        fType = feed['type']
        if fType == 'status':
            # For status + story case, it might be event commenting to friend or adding friend
            # So we filter message field
            if 'message' in feed:
                return True
        elif fType == 'link':
            if 'message' in feed:
                return True
        elif fType == 'photo':
            # photo + link: Please note that repost of others' link will also be in 
            return True
        return False

    def _dumpData(self, data):
        self._logger.debug(u"\ncreatedTime[{0}]\nupdatedTime[{1}]\nmessage[{2}]\nlinks[{3}]\nphotos[{4}]\n".format(
                data['createdTime'].isoformat(),
                data['updatedTime'].isoformat(),
                data['message'],
                data['links'],
                data['photos'],
        ).encode('utf-8'))

    def _imgLinkHandler(self, uri):
        fPath = None
        # Strip safe_image.php
        urlsplitObj = urlparse.urlsplit(uri)
        if urlsplitObj.path == '/safe_image.php':
            queryDict = urlparse.parse_qs(urlsplitObj.query)
            if 'url' in queryDict:
                uri = queryDict['url'][0]

        # Replace subfix to _o, e.g. *_s.jpg to *_o.jpg
        rePattern = re.compile('(_\w)(\.\w+?$)')
        if re.search(rePattern, uri):
            origPic = re.sub(rePattern, '_o\\2', uri)
            fPath = self._storeFileToTemp(origPic)
            if fPath:
                return fPath
        # If we cannot retrieve original picture, turn to use the link Facebook provided instead.
        fPath = self._storeFileToTemp(uri)
        return fPath

    def _feedParser(self, feed):
        ret = None
        if 'message' in feed:
            ret = {}
            ret['message'] = feed['message']
            ret['createdTime'] = self._convertTimeFormat(feed['created_time'])
            ret['updatedTime'] = self._convertTimeFormat(feed['updated_time'])
            ret['links'] = []
            if 'link' in feed:
                ret['links'].append(feed['link'])
            ret['photos'] = []
            if 'picture' in feed:
                imgPath = self._imgLinkHandler(feed['picture'])
                if imgPath:
                    ret['photos'].append(imgPath)
        return ret
