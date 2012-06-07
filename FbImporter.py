import os
import re
import time
import json
import uuid
import dateutil
import urllib, urllib2
import urllib3, urllib3.exceptions
import urlparse
from datetime import datetime, timedelta
from dateutil import parser as dateParser
from FbBase import FbBase, FbErrorCode
from FbUserInfo import FbUserInfo

class FbImporter(FbBase):
    def __init__(self, *args, **kwargs):
        """
        Constructor of FbBase

        In:
            tmpFolder           --  tmp folder to store photo files *optional* default is /tmp 

        """
        FbBase.__init__(self, *args, **kwargs)

        self._tmpFolder = kwargs['tmpFolder'] if 'tmpFolder' in kwargs else '/tmp'

    def getData(self, since=None, until=None):
        """
        Get data from Facebook feed

        In:
            since           --  The start time to get data
                                given None means current time
                                or given python's datetime instance as input
            until           --  The end time to get date
                                given None means yesterday
                                or given python's datetime instance as input

            Example: (Please note that the direction to retrieve data is backward)
                Now   --->   2012/04/01   --->   2012/01/01
                You can specify since=None and until=<datetime of 2012/01/01>
                or since=<datetime of 2012/04/01> until=<datetime of 2012/01/01>

        Out:
            Return a python dict object
            {
                'data': [               # List of data
                    {
                        'id': 'postId',
                        'message': 'Text',                      # None if no message from Facebook
                        'caption': 'quoted text'                # None if no caption from Facebook
                        'links': [ 'uri' ],
                        'photos': [ '/path/to/file' ],
                        'createdTime': <datetime object>,
                        'updatedTime': <datetime object>,
                    },
                ],
                'count': 30,                    # count in data list
                'retCode': FbErrorCode.S_OK,    # returned code which is instance of FbErrorCode

            }
        """
        retDict = {
            'retCode': FbErrorCode.E_FAILED,
            'count': 0,
            'data': [],
        }

        if not until:
            until = datetime.now() - timedelta(1)

        if not self.isTokenValid():
            retDict['retCode'] = FbErrorCode.E_INVALID_TOKEN
            return retDict

        fbId = FbUserInfo(accessToken=self._accessToken, logger=self._logger).getMyId()
        if not fbId:
            return retDict

        errorCode, feedData = self._pageCrawler(since, until)
        failoverCount = 0
        failoverThreshold = 3
        while errorCode != FbErrorCode.E_NO_DATA:
            if FbErrorCode.IS_FAILED(errorCode):
                failoverCount += 1
                # If crawling failed (which is not no data), wait and try again
                if failoverCount <= failoverThreshold:
                    time.sleep(2)
                    errorCode, feedData = self._pageCrawler(since, until)
                    continue
                else:
                    # FIXME: For over threshold case, need to consider how to crawl following data
                    # Currently return error 
                    retDict['retCode'] = errorCode
                    return retDict

            feedHandler = FbFeedsHandler(tmpFolder=self._tmpFolder,
                myFbId=fbId,
                accessToken=self._accessToken,
                feeds=feedData,
                logger=self._logger,
                )
            parsedData = feedHandler.parse()
            retDict['data'] += parsedData

            since = urlparse.parse_qs(urlparse.urlsplit(feedData['paging']['next']).query)['until'][0]
            since = datetime.fromtimestamp(int(since))
            errorCode, feedData = self._pageCrawler(since, until)


        retDict['count'] = len(retDict['data'])
        retDict['retCode'] = FbErrorCode.S_OK
        return retDict

    def _datetime2Timestamp(self, datetimeObj):
        return int(time.mktime(datetimeObj.timetuple()))

    def _pageCrawler(self, since, until):
        params = {
            'access_token' : self._accessToken,
        }

        # Handle since/until parameters, please note that our definitions of since/until are totally different than Facebook
        if since:
            params['until'] = self._datetime2Timestamp(since)
        if until:
            params['since'] = self._datetime2Timestamp(until)
        if since and until and since < until:
            raise ValueError('since cannot older than until')

        uri = '{0}me/feed?{1}'.format(self._graphUri, urllib.urlencode(params))
        self._logger.debug('URI to retrieve [%s]' % uri)
        try:
            conn = self._httpConn.urlopen('GET', uri, timeout=self._timeout)
        except: 
            self._logger.exception('Unable to get data from Facebook')
            return FbErrorCode.E_FAILED, {}
        retDict = json.loads(conn.data)
        if 'data' not in retDict or 'paging' not in retDict:
            return FbErrorCode.E_NO_DATA, {}
        return FbErrorCode.S_OK, retDict

    def isTokenValid(self):
        """
        Check the access token validness as well as the permissions
        """
        uri = urllib.basejoin(self._graphUri, '/me/permissions')
        uri += '?{0}'.format(urllib.urlencode({
            'access_token': self._accessToken,
        }))
        requiredPerms = [
            'read_stream',
            'user_photos',
            'user_status',
        ]
        try:
            conn = self._httpConn.urlopen('GET', uri, timeout=self._timeout)
            respCode = conn.status
            resp = json.loads(conn.data)
        except urllib3.exceptions.HTTPError as e:
            self._logger.error('Unable to get data from Facebook. uri[{0}] e[{1}]'.format(uri, e))
            return False
        except ValueError as e:
            self._logger.error('Unable to parse returned data. data[{0}] e[{1}]'.format(conn.data, e))
            return False
        if respCode != 200 or len(resp['data']) == 0:
            return False
        for perm in requiredPerms:
            if perm not in resp['data'][0]:
                return False
        return True


class FbFeedsHandler(FbBase):
    def __init__(self, *args, **kwargs):
        FbBase.__init__(self, *args, **kwargs)
        self._tmpFolder = kwargs.get('tmpFolder', '/tmp')
        self._feeds = kwargs.get('feeds', None)
        self._myFbId = kwargs.get('myFbId', None)

    def parse(self):
        if 'data' not in self._feeds:
            raise ValueError()

        retData = []
        for feed in self._feeds['data']:
            parser = self._feedParserFactory(feed)
            if not parser:
                continue
            parsedData = parser(feed)
            if parsedData:
                #self._dumpData(parsedData)
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

    def _dumpData(self, data):
        self._logger.debug((u"\nid[%s]\ncreatedTime[%s]\nupdatedTime[%s]\nmessage[%s]\ncaption[%s]\nlinks[%s]\nphotos[%s]\n" % (
                data['id'],
                data['createdTime'].isoformat(),
                data['updatedTime'].isoformat(),
                data['message'],
                data['caption'],
                data['links'],
                data['photos'],
        )).encode('utf-8'))

    def _imgLinkHandler(self, uri):
        if not uri:
            return None
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


    def _getFbMaxSizePhotoUri(self, feed):
        if 'object_id' not in feed:
            return None
        params = {
            'access_token' : self._accessToken,
        }
        uri = '{0}{1}?{2}'.format(self._graphUri, feed['object_id'], urllib.urlencode(params))
        try:
            conn = self._httpConn.urlopen('GET', uri, timeout=self._timeout)
            resp = json.loads(conn.data)
        except:
            self._logger.exception('Unable to get object from Facebook. uri[%s]' % (uri))
            return None
        # FIXME: Current we assume maximum size photo will be first element in images
        if type(resp) == dict and 'images' in resp and len(resp['images']) > 0 and 'source' in resp['images'][0]:
            return resp['images'][0]['source']
        return None

    def _feedParserFactory(self, feed):
        # Strip contents which not posted by me
        if feed['from']['id'] != self._myFbId:
            return None

        # Type filter
        if 'type' not in feed:
            raise ValueError()
        fType = feed['type']
        if fType == 'status':
            return self._feedParserStatus
        elif fType == 'link':
            return self._feedParserLink
        elif fType == 'photo':
            # FIXME: Currently we use dirty hack to check album post
            if 'caption' in feed and re.search('^\d+ new photos$', feed['caption']):
                return self._feedParserAlbum
            elif 'story' in feed and re.search('^.+\d+ new photos\.$', feed['story']):
                return self._feedParserAlbum
            else:
                return self._feedParserPhoto
        elif fType == 'video':
            # treat video post as link post
            return self._feedParserLink
        elif fType == 'checkin':
            return self._feedParserCheckin
        return None


    def _feedParserStatus(self, feed):
        ret = None
        # For status + story case, it might be event commenting to friend or adding friend
        # So we filter message field
        if 'message' in feed:
            ret = {}
            ret['id'] = feed['id']
            ret['message'] = feed['message']
            ret['caption'] = feed.get('caption', None)
            ret['createdTime'] = self._convertTimeFormat(feed['created_time'])
            ret['updatedTime'] = self._convertTimeFormat(feed['updated_time'])
            if 'application' in feed:
                ret['application'] = feed['application']['name']
            ret['links'] = []
            if 'link' in feed:
                ret['links'].append(feed['link'])
            ret['photos'] = []
            if 'picture' in feed:
                imgPath = self._imgLinkHandler(feed['picture'])
                if imgPath:
                    ret['photos'].append(imgPath)
        return ret

    def _albumIdFromPhotoId(self, photoId):
        params = {
            'access_token' : self._accessToken
        }

        uri = '{0}{1}/?{2}'.format(self._graphUri, photoId, urllib.urlencode(params))
        self._logger.debug('photos URI to retrieve [%s]' % uri)
        try:
            conn = self._httpConn.urlopen('GET', uri, timeout=self._timeout)
        except:
            self._logger.exception('Unable to get data from Facebook')
            return FbErrorCode.E_FAILED, {}
        retDict = json.loads(conn.data)
        if 'link' not in retDict:
            return None

        searchResult = re.search('^https?://www\.facebook\.com\/photo\.php\?.+&set=a\.(\d+?)\.', retDict['link'])
        if searchResult is None:
            return None
        return searchResult.group(1)


    def _feedParserAlbum(self, feed):
        ret = {}
        ret['id'] = feed['id']
        ret['message'] = feed.get('message', None)
        # album type's caption is photo numbers, so we will not export caption for album
        ret['caption'] = None

        if 'application' in feed:
            ret['application'] = feed['application']['name']
        ret['createdTime'] = self._convertTimeFormat(feed['created_time'])
        ret['updatedTime'] = self._convertTimeFormat(feed['updated_time'])
        # album type's link usually could not access outside, so we will not export link for photo type
        ret['links'] = []

        ret['photos'] = []
        # FIXME: Currently Facebook do not have formal way to retrieve album id from news feed, so we parse from link
        searchResult = re.search('^https?://www\.facebook\.com\/photo\.php\?.+&set=a\.(\d+?)\.', feed['link'])
        if searchResult is not None:
            # this seems a photo link, try to get its albumId
            albumId = searchResult.group(1)
            self._logger.info("found an albumID from a photo link: {0}".format(albumId))
            feedHandler = FbAlbumFeedsHandler(tmpFolder=self._tmpFolder,
                accessToken=self._accessToken,
                logger=self._logger,
                id=albumId,
            )
            retPhotos = feedHandler.getPhotos(maxLimit=0, basetime=ret['createdTime'], timerange=timedelta(minutes=20))
            if FbErrorCode.IS_SUCCEEDED(retPhotos['retCode']):
                ret['photos'] = retPhotos['data']

        else:
            self._logger.error('unable to find album set id from link: {0}'.format(feed['link']))

        return ret


    def _feedParserPhoto(self, feed):
        ret = {}
        ret['id'] = feed['id']
        ret['message'] = feed.get('message', None)
        ret['caption'] = feed.get('caption', None)
        if 'application' in feed:
            ret['application'] = feed['application']['name']
        ret['createdTime'] = self._convertTimeFormat(feed['created_time'])
        ret['updatedTime'] = self._convertTimeFormat(feed['updated_time'])
        # photo type's link usually could not access outside, so we will not export link for photo type
        ret['links'] = []
        ret['photos'] = []
        imgUri = self._getFbMaxSizePhotoUri(feed)
        if not imgUri and 'picture' in feed:
            imgUri = feed['picture']
        imgPath = self._imgLinkHandler(imgUri)
        if imgPath:
            ret['photos'].append(imgPath)
        return ret

    def _feedParserLink(self, feed):
        ret = None
        # For link + story case, it might be event to add friends or join fans page
        # So we filter story field
        if not 'story' in feed:
            ret = {}
            ret['id'] = feed['id']
            ret['message'] = feed.get('message', None)
            # Link's caption usually is the link, so we will not export caption here.
            ret['caption'] = None
            if 'application' in feed:
                ret['application'] = feed['application']['name']
            ret['createdTime'] = self._convertTimeFormat(feed['created_time'])
            ret['updatedTime'] = self._convertTimeFormat(feed['updated_time'])
            ret['links'] = []
            if 'link' in feed:
                private = False
                if 'privacy' in feed and feed['privacy']['description'] != 'Public':
                    private = True
                # skip none-public facebook link, which we cannot get web preview
                if not private or not re.search('^https?://www\.facebook\.com/.*$', feed['link']):
                    ret['links'].append(feed['link'])
            ret['photos'] = []
            if 'picture' in feed:
                imgPath = self._imgLinkHandler(feed['picture'])
                if imgPath:
                    ret['photos'].append(imgPath)
        return ret

    def _feedParserCheckin(self, feed):
        ret = {}
        ret['id'] = feed['id']
        ret['message'] = feed.get('message', None)
        ret['caption'] = feed['caption']
        # get checkin's place
        if 'place' in feed:
            lat = None
            lnt = None
            if 'location' in feed['place']:
                lat = feed['place']['location']['latitude']
                lnt = feed['place']['location']['longitude']
            ret['place'] = {
                'name': feed['place']['name'],
                'latitude': lat,
                'longitude': lnt
            }
        if 'application' in feed:
            ret['application'] = feed['application']['name']
        ret['createdTime'] = self._convertTimeFormat(feed['created_time'])
        ret['updatedTime'] = self._convertTimeFormat(feed['updated_time'])
        # checkin type's link usually could not access outside, so we will not export link for photo type
        ret['links'] = []

        ret['photos'] = []
        albumId = None
        # FIXME: Currently Facebook do not have formal way to retrieve album id from news feed, so we parse from link
        searchResult = re.search('^https?://www\.facebook\.com\/photo\.php\?fbid=(\d+)&set=s\.\d+.+', feed['link'])
        if searchResult is not None:
            # this seems a photo link, try to get its albumId
            photoId = searchResult.group(1)
            albumId = self._albumIdFromPhotoId(photoId)

        if albumId:
            self._logger.info("found an albumID from a photo link: {0}".format(albumId))
            feedHandler = FbAlbumFeedsHandler(tmpFolder=self._tmpFolder,
                accessToken=self._accessToken,
                logger=self._logger,
                id=albumId,
            )
            retPhotos = feedHandler.getPhotos(maxLimit=0, basetime=ret['createdTime'], timerange=timedelta(minutes=20))
            if FbErrorCode.IS_SUCCEEDED(retPhotos['retCode']):
                ret['photos'] = retPhotos['data']
        else:
            self._logger.error('unable to find album set id from link: {0}'.format(feed['link']))

        return ret

class FbAlbumFeedsHandler(FbFeedsHandler):
    def __init__(self, *args, **kwargs):
        FbFeedsHandler.__init__(self, *args, **kwargs)
        self._limit = kwargs.get('limit', 25)
        self._id = kwargs['id']

    def getPhotos(self, maxLimit=0, limit=25, basetime=datetime.now(), timerange=timedelta(minutes=15)):
        retDict = {
            'retCode': FbErrorCode.S_OK,
            'data': [],
            'count': 0,
        }
        offset = 0
        if maxLimit > 0 and maxLimit < limit:
            limit = maxLimit

        errorCode, feedData = self._pageCrawler(offset, limit)
        failoverCount = 0
        failoverThreshold = 3
        while errorCode != FbErrorCode.E_NO_DATA:
            if FbErrorCode.IS_FAILED(errorCode):
                failoverCount += 1
                # If crawling failed (which is not no data), wait and try again
                if failoverCount <= failoverThreshold:
                    time.sleep(2)
                    errorCode, feedData = self._pageCrawler(offset, limit)
                    continue
                else:
                    # FIXME: For over threshold case, need to consider how to crawl following data
                    # Currently return error
                    retDict['retCode'] = errorCode
                    return retDict

            parsedData = []
            for feed in feedData['data']:
                photoDatetime = self._convertTimeFormat(feed['created_time'])
                if photoDatetime > basetime + timerange:
                    continue
                if photoDatetime < basetime - timerange:
                    retDict['data'] += parsedData
                    retDict['count'] += len(parsedData)
                    return retDict

                if 'images' in feed and len(feed['images']) > 0 and 'source' in feed['images'][0]:
                    imgUri = feed['images'][0]['source']
                    imgPath = self._imgLinkHandler(imgUri)
                    if imgPath:
                        parsedData.append(imgPath)

            retDict['data'] += parsedData
            retDict['count'] += len(parsedData)

            if maxLimit > 0:
                if retDict['count'] + limit > maxLimit:
                    limit = maxLimit - retDict['count']

                if retDict['count'] >= maxLimit:
                    break

            offset = urlparse.parse_qs(urlparse.urlsplit(feedData['paging']['next']).query)['offset'][0]
            errorCode, feedData = self._pageCrawler(offset, limit)
        return retDict

    def _pageCrawler(self, offset, limit):
        params = {
            'access_token' : self._accessToken,
            'offset' : offset,
            'limit': limit,
        }

        uri = '{0}{1}/photos?{2}'.format(self._graphUri, self._id, urllib.urlencode(params))
        self._logger.debug('photos URI to retrieve [%s]' % uri)
        try:
            conn = self._httpConn.urlopen('GET', uri, timeout=self._timeout)
        except:
            self._logger.exception('Unable to get data from Facebook')
            return FbErrorCode.E_FAILED, {}
        retDict = json.loads(conn.data)
        if 'data' not in retDict or 'paging' not in retDict or len(retDict['data']) == 0:
            return FbErrorCode.E_NO_DATA, {}
        return FbErrorCode.S_OK, retDict

    def _parse(self, feedData):
        retList = []
        for feed in feedData['data']:
            if 'images' in feed and len(feed['images']) > 0 and 'source' in feed['images'][0]:
                imgUri = feed['images'][0]['source']
                imgPath = self._imgLinkHandler(imgUri)
                if imgPath:
                    retList.append(imgPath)
        return retList


