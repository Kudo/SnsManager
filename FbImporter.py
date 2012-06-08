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
        self.fbId = ''
        self._multiApiCrawlerSince = kwargs['multiApiCrawlerSince'] if 'multiApiCrawlerSince' in kwargs else dateParser.parse('2010-12-31')

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
                'data': {               # List of data
                    'id': {
                        'id': 'postId',
                        'message': 'Text',                      # None if no message from Facebook
                        'caption': 'quoted text'                # None if no caption from Facebook
                        'links': [ 'uri' ],
                        'photos': [ '/path/to/file' ],
                        'createdTime': <datetime object>,
                        'updatedTime': <datetime object>,
                    }, ...
                },
                'count': 30,                    # count in data dic
                'retCode': FbErrorCode.S_OK,    # returned code which is instance of FbErrorCode

            }
        """
        retDict = {
            'retCode': FbErrorCode.E_FAILED,
            'count': 0,
            'data': {},
        }

        if not until:
            until = datetime.now() - timedelta(1)

        if not self.isTokenValid():
            retDict['retCode'] = FbErrorCode.E_INVALID_TOKEN
            return retDict

        self.fbId = FbUserInfo(accessToken=self._accessToken, logger=self._logger).getMyId()
        if not self.fbId:
            return retDict

        # Please make sure feed placed in first api call, since we are now havve more confident for feed API data
        for api in ['feed', 'statuses', 'checkins', 'videos', 'links']:
            if api != 'feed' and self._multiApiCrawlerSince and (not since or since > self._multiApiCrawlerSince):
                _since = self._multiApiCrawlerSince
                if _since < until:
                    self._logger.info('multiApiCrawlerSince < until, skip this API call. api[%s]' % (api))
                    continue
            else:
                _since = since
            _until = until
            if api == 'links' and ((since and since <= self._multiApiCrawlerSince) or not since):
                # links API did not well support since/until, so we currently crawlling all
                _after = True
            else:
                _after = None
            errorCode, data = self._apiCrawler(api, _since, _until, after=_after)
            failoverCount = 0
            failoverThreshold = 3
            while errorCode != FbErrorCode.E_NO_DATA:
                if FbErrorCode.IS_FAILED(errorCode):
                    failoverCount += 1
                    # If crawling failed (which is not no data), wait and try again
                    if failoverCount <= failoverThreshold:
                        time.sleep(2)
                        errorCode, data = self._apiCrawler(api, _since, _until, after=_after)
                        continue
                    else:
                        # FIXME: For over threshold case, need to consider how to crawl following data
                        # Currently return error
                        retDict['retCode'] = errorCode
                        return retDict

                apiHandler = self._apiHandlerFactory(api)(tmpFolder=self._tmpFolder,
                    myFbId=self.fbId,
                    accessToken=self._accessToken,
                    data=data,
                    logger=self._logger,
                    )

                if _after:
                    parsedData, stopCrawling = apiHandler.parse({'since': _since, 'until': _until})
                    self._mergeData(retDict['data'], parsedData)
                    if stopCrawling:
                        errorCode = FbErrorCode.E_NO_DATA
                        continue
                else:
                    parsedData, stopCrawling = apiHandler.parse()
                    self._mergeData(retDict['data'], parsedData)

                try:
                    newSince = urlparse.parse_qs(urlparse.urlsplit(data['paging']['next']).query)['until'][0]
                    newSince = datetime.fromtimestamp(int(newSince))
                except:
                    self._logger.exception('Unable to have "until" in paging next, turn to use after and filter by createdTime')
                    # Some Graph API call did not return until but with an 'after' instead
                    # For this case, we follow after call and filter returned elements by createdTime
                    _after = urlparse.parse_qs(urlparse.urlsplit(data['paging']['next']).query)['after'][0]

                if _after:
                    errorCode, data = self._apiCrawler(api, _since, _until, after=_after)
                elif _since and newSince >= _since:
                    self._logger.info("No more data for next paging's until >= current until")
                    errorCode = FbErrorCode.E_NO_DATA
                else:
                    _since = newSince
                    errorCode, data = self._apiCrawler(api, _since, _until, after=_after)

        retDict['count'] = len(retDict['data'])
        retDict['retCode'] = FbErrorCode.S_OK
        return retDict

    def _apiHandlerFactory(self, api):
        if api == 'feed':
            return FbApiHandlerFeed
        elif api == 'statuses':
            return FbApiHandlerStatuses
        elif api == 'checkins':
            return FbApiHandlerCheckins
        elif api == 'videos':
            return FbApiHandlerVideos
        elif api == 'links':
            return FbApiHandlerLinks
        else:
            return None

    def _mergeData(self, dataDict, anotherDatas):
        for data in anotherDatas:
            objId = data['id']
            if objId in dataDict:
                self._logger.debug("Conflict data.\noriginalData[%s]\ndata[%s]" % (dataDict[objId], data))
                pass
            else:
                dataDict[objId] = data

    def _datetime2Timestamp(self, datetimeObj):
        return int(time.mktime(datetimeObj.timetuple()))

    def _apiCrawler(self, api, since, until, after=None):
        params = {
            'access_token' : self._accessToken,
        }

        if after:
            if type(after) == bool:
                params['after'] = ''
            else:
                params['after'] = after
        else:
            # Handle since/until parameters, please note that our definitions of since/until are totally different than Facebook
            if since:
                params['until'] = self._datetime2Timestamp(since)
            if until:
                params['since'] = self._datetime2Timestamp(until)
            if since and until and since < until:
                raise ValueError('since cannot older than until')

        uri = '{0}me/{1}?{2}'.format(self._graphUri, api, urllib.urlencode(params))
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

class FbApiHandlerBase(FbBase):
    def __init__(self, *args, **kwargs):
        super(FbApiHandlerBase, self).__init__(self, *args, **kwargs)
        self._tmpFolder = kwargs.get('tmpFolder', '/tmp')
        self._data = kwargs.get('data', None)
        self._myFbId = kwargs.get('myFbId', None)

    def parse(self, filterDateInfo=None):
        if 'data' not in self._data:
            raise ValueError()

        retData = []
        for data in self._data['data']:
            # Strip contents which not posted by me
            if data['from']['id'] != self._myFbId:
                continue

            parsedData = self.parseInner(data)
            if parsedData:
                if not filterDateInfo:
                    #self._dumpData(parsedData)
                    retData.append(parsedData)
                else:
                    createdTime = parsedData['createdTime'].replace(tzinfo=None)
                    if createdTime >= filterDateInfo['until'].replace(tzinfo=None) and createdTime <= filterDateInfo['since'].replace(tzinfo=None):
                        #self._dumpData(parsedData)
                        retData.append(parsedData)

        return retData, False

    def parseInner(self, data):
        return None

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
                data['createdTime'].isoformat() if isinstance(data['createdTime'], datetime) else data['createdTime'],
                data['updatedTime'].isoformat() if isinstance(data['updatedTime'], datetime) else data['updatedTime'],
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


    def _getFbMaxSizePhotoUri(self, data):
        if 'object_id' not in data:
            return None
        params = {
            'access_token' : self._accessToken,
        }
        uri = '{0}{1}?{2}'.format(self._graphUri, data['object_id'], urllib.urlencode(params))
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


    def _dataParserStatus(self, data, isFeedApi=True):
        ret = None
        # For status + story case, it might be event commenting to friend or adding friend
        # So we filter message field
        if 'message' in data:
            ret = {}
            if isFeedApi:
                ret['id'] = data['id']
            else:
                ret['id'] = '%s_%s' % (self._myFbId, data['id'])
            ret['message'] = data['message']
            ret['caption'] = data.get('caption', None)
            if isFeedApi:
                ret['createdTime'] = self._convertTimeFormat(data['created_time'])
            else:
                ret['createdTime'] = self._convertTimeFormat(data['updated_time'])
            ret['updatedTime'] = self._convertTimeFormat(data['updated_time'])
            if 'application' in data:
                ret['application'] = data['application']['name']
            ret['links'] = []
            if 'link' in data:
                ret['links'].append(data['link'])
            ret['photos'] = []
            if 'picture' in data:
                imgPath = self._imgLinkHandler(data['picture'])
                if imgPath:
                    ret['photos'].append(imgPath)
        return ret

    def _albumIdFromObjectId(self, objectId):
        params = {
            'access_token' : self._accessToken
        }

        uri = '{0}{1}/?{2}'.format(self._graphUri, objectId, urllib.urlencode(params))
        self._logger.debug('object URI to retrieve [%s]' % uri)
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
            self._logger.error('Unable to find album set id from link: {0}'.format(retDict['link']))
            return None
        return searchResult.group(1)


    def _dataParserAlbum(self, data, isFeedApi=True):
        ret = {}
        if isFeedApi:
            ret['id'] = data['id']
        else:
            ret['id'] = '%s_%s' % (self._myFbId, data['id'])
        ret['message'] = data.get('message', None)
        # album type's caption is photo numbers, so we will not export caption for album
        ret['caption'] = None

        if 'application' in data:
            ret['application'] = data['application']['name']
        ret['createdTime'] = self._convertTimeFormat(data['created_time'])
        ret['updatedTime'] = self._convertTimeFormat(data['updated_time'])
        # album type's link usually could not access outside, so we will not export link for photo type
        ret['links'] = []

        ret['photos'] = []
        # FIXME: Currently Facebook do not have formal way to retrieve album id from news feed, so we parse from link
        searchResult = re.search('^https?://www\.facebook\.com\/photo\.php\?.+&set=a\.(\d+?)\.', data['link'])
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
            self._logger.error('unable to find album set id from link: {0}'.format(data['link']))

        return ret

    def _dataParserPhoto(self, data, isFeedApi=True):
        ret = {}
        if isFeedApi:
            ret['id'] = data['id']
        else:
            ret['id'] = '%s_%s' % (self._myFbId, data['id'])
        ret['message'] = data.get('message', None)
        ret['caption'] = data.get('caption', None)
        if 'application' in data:
            ret['application'] = data['application']['name']
        ret['createdTime'] = self._convertTimeFormat(data['created_time'])
        ret['updatedTime'] = self._convertTimeFormat(data['updated_time'])
        # photo type's link usually could not access outside, so we will not export link for photo type
        ret['links'] = []
        ret['photos'] = []
        imgUri = self._getFbMaxSizePhotoUri(data)
        if not imgUri and 'picture' in data:
            imgUri = data['picture']
        imgPath = self._imgLinkHandler(imgUri)
        if imgPath:
            ret['photos'].append(imgPath)
        return ret

    def _dataParserLink(self, data, isFeedApi=True):
        # For link + story case, it might be event to add friends or join fans page
        # So we filter story field
        if 'story' in data and not re.search('shared a link.$', data['story']):
            return None

        ret = {}
        if isFeedApi:
            ret['id'] = data['id']
        else:
            ret['id'] = '%s_%s' % (self._myFbId, data['id'])
        ret['message'] = data.get('message', None)
        # Link's caption usually is the link, so we will not export caption here.
        ret['caption'] = None
        if 'application' in data:
            ret['application'] = data['application']['name']
        ret['createdTime'] = self._convertTimeFormat(data['created_time'])
        if isFeedApi:
            ret['updatedTime'] = self._convertTimeFormat(data['updated_time'])
        else:
            ret['updatedTime'] = self._convertTimeFormat(data['created_time'])
        ret['links'] = []
        if 'link' in data:
            private = False
            if 'privacy' in data:
                if data['privacy']['description'] != 'Public':
                    private = True
            # skip none-public facebook link, which we cannot get web preview
            if data['link'][0] == '/':
                data['link'] = 'http://www.facebook.com%s' % (data['link'])
            if not private or not re.search('^https?://www\.facebook\.com/.*$', data['link']):
                ret['links'].append(data['link'])
        ret['photos'] = []
        if 'picture' in data:
            imgPath = self._imgLinkHandler(data['picture'])
            if imgPath:
                ret['photos'].append(imgPath)
        if len(ret['links']) == 0 and len(ret['photos']) == 0:
            # If link type data without a link or picture, do not expose this record
            return None
        return ret

    def _dataParserVideo(self, data, isFeedApi=True):
        ret = None
        # For link + story case, it might be event to add friends or join fans page
        # So we filter story field
        if not 'story' in data:
            ret = {}
            if isFeedApi:
                ret['id'] = data['id']
            else:
                ret['id'] = '%s_%s' % (self._myFbId, data['id'])
            ret['message'] = data.get('message', None) or data.get('name', None)
            # Link's caption usually is the link, so we will not export caption here.
            ret['caption'] = None
            if 'application' in data:
                ret['application'] = data['application']['name']
            ret['createdTime'] = self._convertTimeFormat(data['created_time'])
            ret['updatedTime'] = self._convertTimeFormat(data['updated_time'])
            ret['links'] = []
            if isFeedApi:
                if 'link' in data:
                    private = False
                    if 'privacy' in data and data['privacy']['description'] != 'Public':
                        private = True
                   # skip none-public facebook link, which we cannot get web preview
                    if not private or not re.search('^https?://www\.facebook\.com/.*$', data['link']):
                        ret['links'].append(data['link'])
            else:
                ret['links'].append('https://www.facebook.com/photo.php?v=%s' % data['id'])
            ret['photos'] = []
            if 'picture' in data:
                imgPath = self._imgLinkHandler(data['picture'])
                if imgPath:
                    ret['photos'].append(imgPath)
        return ret


    def _dataParserCheckin(self, data, isFeedApi=True):
        ret = {}
        if isFeedApi:
            ret['id'] = data['id']
        else:
            ret['id'] = '%s_%s' % (self._myFbId, data['id'])
        ret['message'] = data.get('message', None)
        if isFeedApi:
            ret['caption'] = data['caption']
        else:
            ret['caption'] = 'checked in at %s' % (data['place']['name'])
        # get checkin's place
        if 'place' in data:
            lat = None
            lnt = None
            if 'location' in data['place']:
                lat = data['place']['location']['latitude']
                lnt = data['place']['location']['longitude']
            ret['place'] = {
                'name': data['place']['name'],
                'latitude': lat,
                'longitude': lnt
            }
        if 'application' in data:
            ret['application'] = data['application']['name']

        ret['createdTime'] = self._convertTimeFormat(data['created_time'])
        if isFeedApi:
            ret['updatedTime'] = self._convertTimeFormat(data['updated_time'])
        else:
            ret['updatedTime'] = self._convertTimeFormat(data['created_time'])

        # checkin type's link usually could not access outside, so we will not export link for photo type
        ret['links'] = []

        ret['photos'] = []
        if 'object_id' in data:
            albumId = self._albumIdFromObjectId(data['object_id'])

            if albumId:
                self._logger.info("found an albumID from a checkin link: {0}".format(albumId))
                dataHandler = FbAlbumFeedsHandler(tmpFolder=self._tmpFolder,
                    accessToken=self._accessToken,
                    logger=self._logger,
                    id=albumId,
                )
                retPhotos = dataHandler.getPhotos(maxLimit=0, basetime=ret['createdTime'], timerange=timedelta(minutes=20))
                if FbErrorCode.IS_SUCCEEDED(retPhotos['retCode']):
                    ret['photos'] = retPhotos['data']

        return ret

class FbApiHandlerFeed(FbApiHandlerBase):
    def parseInner(self, data):
        parser = self._dataParserFactory(data)
        if not parser:
            return None
        return parser(data)

    def _dataParserFactory(self, data):
        # Type filter
        if 'type' not in data:
            raise ValueError()
        fType = data['type']
        if fType == 'status':
            return self._dataParserStatus
        elif fType == 'link':
            return self._dataParserLink
        elif fType == 'photo':
            # FIXME: Currently we use dirty hack to check album post
            if 'caption' in data and re.search('^\d+ new photos$', data['caption']):
                return self._dataParserAlbum
            elif 'story' in data and re.search('^.+\d+ new photos\.$', data['story']):
                return self._dataParserAlbum
            else:
                return self._dataParserPhoto
        elif fType == 'video':
            return self._dataParserVideo
        elif fType == 'checkin':
            return self._dataParserCheckin
        return None

class FbApiHandlerStatuses(FbApiHandlerBase):
    def parseInner(self, data):
        return self._dataParserStatus(data, isFeedApi=False)

class FbApiHandlerCheckins(FbApiHandlerBase):
    def parseInner(self, data):
        return self._dataParserCheckin(data, isFeedApi=False)

class FbApiHandlerVideos(FbApiHandlerBase):
    def parseInner(self, data):
        return self._dataParserVideo(data, isFeedApi=False)

class FbApiHandlerLinks(FbApiHandlerBase):
    def parseInner(self, data):
        return self._dataParserLink(data, isFeedApi=False)

class FbAlbumFeedsHandler(FbApiHandlerBase):
    def __init__(self, *args, **kwargs):
        super(FbAlbumFeedsHandler, self).__init__(self, *args, **kwargs)
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
            for data in feedData['data']:
                photoDatetime = self._convertTimeFormat(data['created_time'])
                if photoDatetime > basetime + timerange:
                    continue
                if photoDatetime < basetime - timerange:
                    retDict['data'] += parsedData
                    retDict['count'] += len(parsedData)
                    return retDict

                if 'images' in data and len(data['images']) > 0 and 'source' in data['images'][0]:
                    imgUri = data['images'][0]['source']
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
        for data in feedData['data']:
            if 'images' in data and len(data['images']) > 0 and 'source' in data['images'][0]:
                imgUri = data['images'][0]['source']
                imgPath = self._imgLinkHandler(imgUri)
                if imgPath:
                    retList.append(imgPath)
        return retList


