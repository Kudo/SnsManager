import os
import re
import time
import json
import uuid
import dateutil
import urllib, urllib2
import urllib3, urllib3.exceptions
import urlparse
import lxml.html
from datetime import datetime, timedelta
from dateutil import parser as dateParser
from FbBase import FbBase
from SnsManager import ErrorCode, IExporter

class FbExporter(FbBase, IExporter):
    def __init__(self, *args, **kwargs):
        """
        Constructor of FbExporter

        In:
            tmpFolder           --  tmp folder to store photo files *optional* default is /tmp 

        """
        super(FbExporter, self).__init__(*args, **kwargs)

        self._tmpFolder = kwargs['tmpFolder'] if 'tmpFolder' in kwargs else '/tmp'
        self._multiApiCrawlerSince = kwargs['multiApiCrawlerSince'] if 'multiApiCrawlerSince' in kwargs else dateParser.parse('2010-12-31')
        self.verbose = kwargs['verbose'] if 'verbose' in kwargs else False

    def getData(self, **kwargs):
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
                'retCode': ErrorCode.S_OK,    # returned code which is instance of ErrorCode

            }
        """
        retDict = {
            'retCode': ErrorCode.E_FAILED,
            'count': 0,
            'data': {},
        }
        since = kwargs.get('since', None)
        until = kwargs.get('until', None)

        if not until:
            until = datetime.now() - timedelta(1)

        tokenValidRet = self.isTokenValid()
        if ErrorCode.IS_FAILED(tokenValidRet):
            retDict['retCode'] = tokenValidRet
            return retDict

        if not self.myId:
            return retDict

        # Please make sure feed placed in first api call, since we are now havve more confident for feed API data
        for api in ['feed', 'statuses', 'checkins', 'videos', 'links', 'notes']:
            if api != 'feed' and self._multiApiCrawlerSince and (not since or since > self._multiApiCrawlerSince):
                _since = self._multiApiCrawlerSince
                if _since < until:
                    #self._logger.info('multiApiCrawlerSince < until, skip this API call. api[%s]' % (api))
                    continue
            else:
                _since = since
            _until = until
            if (api == 'links' or api == 'notes') and ((since and since <= self._multiApiCrawlerSince) or not since):
                # links/notes API did not well support since/until, so we currently crawlling all
                _after = True
            else:
                _after = None
            errorCode, data = self._apiCrawler(api, _since, _until, after=_after)
            failoverCount = 0
            failoverThreshold = 3
            while errorCode != ErrorCode.E_NO_DATA:
                if ErrorCode.IS_FAILED(errorCode):
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

                apiHandler = self._apiHandlerFactory(api)(data=data, outerObj=self)

                if _after:
                    parsedData, stopCrawling = apiHandler.parse({'since': _since, 'until': _until})
                    self._mergeData(retDict['data'], parsedData)
                    if stopCrawling:
                        errorCode = ErrorCode.E_NO_DATA
                        continue
                else:
                    parsedData, stopCrawling = apiHandler.parse()
                    self._mergeData(retDict['data'], parsedData)

                if 'next' not in data['paging']:
                    self._logger.debug('Unable to locate next in paging.')
                    errorCode = ErrorCode.E_NO_DATA
                    continue

                pagingNext = urlparse.parse_qs(urlparse.urlsplit(data['paging']['next']).query)
                if 'until' in pagingNext:
                    newSince = pagingNext['until'][0]
                    newSince = datetime.fromtimestamp(int(newSince))
                elif 'after' in pagingNext:
                    # Some Graph API call did not return until but with an 'after' instead
                    # For this case, we follow after call and filter returned elements by createdTime
                    _after = pagingNext['after'][0]

                if _after:
                    errorCode, data = self._apiCrawler(api, _since, _until, after=_after)
                elif _since and newSince >= _since:
                    self._logger.info("No more data for next paging's until >= current until")
                    errorCode = ErrorCode.E_NO_DATA
                else:
                    _since = newSince
                    errorCode, data = self._apiCrawler(api, _since, _until, after=_after)

        retDict['count'] = len(retDict['data'])
        retDict['retCode'] = ErrorCode.S_OK
        return retDict

    def _apiHandlerFactory(self, api):
        if api == 'feed':
            return self.FbApiHandlerFeed
        elif api == 'statuses':
            return self.FbApiHandlerStatuses
        elif api == 'checkins':
            return self.FbApiHandlerCheckins
        elif api == 'videos':
            return self.FbApiHandlerVideos
        elif api == 'links':
            return self.FbApiHandlerLinks
        elif api == 'notes':
            return self.FbApiHandlerNotes
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
            return ErrorCode.E_FAILED, {}
        try:
            retDict = json.loads(conn.data)
        except ValueError:
            self._logger.info('Unable to parse returned data. conn.data[%s]' % conn.data)
            return ErrorCode.E_FAILED, {}
        if 'data' not in retDict or 'paging' not in retDict:
            return ErrorCode.E_NO_DATA, {}
        return ErrorCode.S_OK, retDict


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
            return ErrorCode.E_FAILED
        except ValueError as e:
            self._logger.error('Unable to parse returned data. data[{0}] e[{1}]'.format(conn.data, e))
            return ErrorCode.E_FAILED
        if respCode != 200 or len(resp['data']) == 0:
            moreInfoLink = 'https://developers.facebook.com/tools/debug/access_token?q=' + self._accessToken
            self._logger.info('Invalid token. data[{0}] moreInfoLink[{1}]'.format(conn.data, moreInfoLink))
            return ErrorCode.E_INVALID_TOKEN
        for perm in requiredPerms:
            if perm not in resp['data'][0]:
                moreInfoLink = 'https://developers.facebook.com/tools/debug/access_token?q=' + self._accessToken
                self._logger.info('Token did not have enough permission. data[{0}] moreInfoLink[{1}]'.format(conn.data, moreInfoLink))
                return ErrorCode.E_INVALID_TOKEN
        return ErrorCode.S_OK

    class FbApiHandlerBase(object):
        def __init__(self, *args, **kwargs):
            self.outerObj = kwargs.get('outerObj')
            self._data = kwargs.get('data', None)

        def parse(self, filterDateInfo=None):
            if 'data' not in self._data:
                raise ValueError()

            retData = []
            for data in self._data['data']:
                # In some case, Facebook returned "from": null and we will skip this case.
                if data['from'] is None:
                    continue
                # Strip contents which not posted by me
                #if data['from']['id'] != self.outerObj.myId:
                #    continue

                parsedData = self.parseInner(data)
                if parsedData:
                    if data['from']['id'] == self.outerObj.myId:
                        parsedData['fromMe'] = True
                    else:
                        parsedData['fromMe'] = False

                    if not filterDateInfo:
                        self._dumpData(parsedData)
                        retData.append(parsedData)
                    else:
                        createdTime = parsedData['createdTime'].replace(tzinfo=None)
                        if createdTime >= filterDateInfo['until'].replace(tzinfo=None) and createdTime <= filterDateInfo['since'].replace(tzinfo=None):
                            self._dumpData(parsedData)
                            retData.append(parsedData)

            return retData, False

        def parseInner(self, data):
            return None

        def _convertTimeFormat(self, fbTime):
            if not fbTime:
                raise ValueError('Unable to find any time info in feed.')
            return dateParser.parse(fbTime)

        def _storeFileToTemp(self, fileUri):
            fileExtName = fileUri[fileUri.rfind('.') + 1:]
            newFileName = os.path.join(self.outerObj._tmpFolder, "{0}.{1}".format(str(uuid.uuid1()), fileExtName))
            try:
                conn = urllib2.urlopen(fileUri)
                fileObj = file(newFileName, 'w')
                fileObj.write(conn.read())
                fileObj.close()
            except:
                return None
            return newFileName

        def _dumpData(self, data):
            if self.outerObj.verbose:
                output = u"\n"
                for k, v in data.iteritems():
                    val = v
                    if isinstance(val, datetime):
                        val = val.isoformat()
                    output += u"%s[%s]\n" % (k, val)
                self.outerObj._logger.debug(output.encode('utf-8'))

        def _stripSafeImage(self, uri):
            # Strip safe_image.php
            urlsplitObj = urlparse.urlsplit(uri)
            if urlsplitObj.path == '/safe_image.php':
                queryDict = urlparse.parse_qs(urlsplitObj.query)
                if 'url' in queryDict:
                    uri = queryDict['url'][0]
            return uri

        def _imgLinkHandler(self, uri):
            if not uri:
                return None
            fPath = None
            uri = self._stripSafeImage(uri)
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
                'access_token' : self.outerObj._accessToken,
            }
            uri = '{0}{1}?{2}'.format(self.outerObj._graphUri, data['object_id'], urllib.urlencode(params))
            try:
                conn = self.outerObj._httpConn.urlopen('GET', uri, timeout=self.outerObj._timeout)
                resp = json.loads(conn.data)
            except:
                self.outerObj._logger.exception('Unable to get object from Facebook. uri[%s]' % (uri))
                return None
            # FIXME: Current we assume maximum size photo will be first element in images
            if type(resp) == dict and 'images' in resp and len(resp['images']) > 0 and 'source' in resp['images'][0]:
                return resp['images'][0]['source']
            return None

        def _getTagPeople(self, data, tagName='with_tags'):
            people = None
            if tagName in data and 'data' in data[tagName] and len(data[tagName]['data']) > 0:
                people = [{
                    'id': person['id'],
                    'name': person['name'],
                    'avatar': '{0}{1}/picture'.format(self.outerObj._graphUri, person['id']),
                } for person in data[tagName]['data']]
            return people

        def _getGpsInfo(self, data):
            place = None
            if 'place' in data:
                place = { 'name': data['place']['name'] }
                if 'location' in data['place']:
                    place['latitude'] = data['place']['location']['latitude']
                    place['longitude'] = data['place']['location']['longitude']
            return place

        def _getVideoTag(self, data, tagName='tags', objectIdName='object_id'):
            """
            To get video tags, we should get from video object due to feed data do not always expose those information.
            """
            if objectIdName not in data:
                return None
            params = {
                'access_token' : self.outerObj._accessToken,
                'fields': 'tags',
            }
            uri = '{0}{1}?{2}'.format(self.outerObj._graphUri, data[objectIdName], urllib.urlencode(params))
            try:
                conn = self.outerObj._httpConn.urlopen('GET', uri, timeout=self.outerObj._timeout)
                resp = json.loads(conn.data)
            except:
                self.outerObj._logger.exception('Unable to get object from Facebook. uri[%s]' % (uri))
                return None
            if type(resp) == dict:
                return self._getTagPeople(resp, tagName)
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
                    ret['id'] = '%s_%s' % (self.outerObj.myId, data['id'])
                ret['message'] = data['message']
                ret['caption'] = data.get('caption', None)
                ret['createdTime'] = self._convertTimeFormat(data.get('created_time', data.get('updated_time', None)))
                ret['updatedTime'] = self._convertTimeFormat(data.get('updated_time', data.get('created_time', None)))
                if 'application' in data:
                    ret['application'] = data['application']['name']
                ret['links'] = []
                if 'link' in data:
                    ret['links'].append(data['link'])
                ret['photos'] = []

                place = self._getGpsInfo(data)
                if place:
                    ret['place'] = place

                if isFeedApi:
                    people = self._getTagPeople(data)
                else:
                    people = self._getTagPeople(data, tagName='tags')
                if people:
                    ret['people'] = people

                if 'picture' in data:
                    imgPath = self._imgLinkHandler(data['picture'])
                    if imgPath:
                        ret['photos'].append(imgPath)
            return ret

        def _albumIdFromObjectId(self, objectId):
            params = {
                'access_token' : self.outerObj._accessToken
            }

            uri = '{0}{1}/?{2}'.format(self.outerObj._graphUri, objectId, urllib.urlencode(params))
            self.outerObj._logger.debug('object URI to retrieve [%s]' % uri)
            try:
                conn = self.outerObj._httpConn.urlopen('GET', uri, timeout=self.outerObj._timeout)
            except:
                self.outerObj._logger.exception('Unable to get data from Facebook')
                return ErrorCode.E_FAILED, {}
            retDict = json.loads(conn.data)
            if 'link' not in retDict:
                return None

            searchResult = re.search('^https?://www\.facebook\.com\/photo\.php\?.+&set=a\.(\d+?)\.', retDict['link'])
            if searchResult is None:
                self.outerObj._logger.error('Unable to find album set id from link: {0}'.format(retDict['link']))
                return None
            return searchResult.group(1)


        def _dataParserAlbum(self, data, isFeedApi=True):
            ret = {}
            if isFeedApi:
                ret['id'] = data['id']
            else:
                ret['id'] = '%s_%s' % (self.outerObj.myId, data['id'])
            ret['message'] = data.get('message', None)
            # album type's caption is photo numbers, so we will not export caption for album
            ret['caption'] = None

            if 'application' in data:
                ret['application'] = data['application']['name']
            ret['createdTime'] = self._convertTimeFormat(data.get('created_time', data.get('updated_time', None)))
            ret['updatedTime'] = self._convertTimeFormat(data.get('updated_time', data.get('created_time', None)))
            # album type's link usually could not access outside, so we will not export link for photo type
            ret['links'] = []

            ret['photos'] = []
            # FIXME: Currently Facebook do not have formal way to retrieve album id from news feed, so we parse from link
            searchResult = re.search('^https?://www\.facebook\.com\/photo\.php\?.+&set=a\.(\d+?)\.', data['link'])
            if searchResult is not None:
                # this seems a photo link, try to get its albumId
                albumId = searchResult.group(1)
                self.outerObj._logger.info("found an albumID from a photo link: {0}".format(albumId))
                feedHandler = self.outerObj.FbAlbumFeedsHandler(id=albumId, outerObj=self.outerObj)
                retPhotos = feedHandler.getPhotos(maxLimit=0, basetime=ret['createdTime'], timerange=timedelta(minutes=20))
                if ErrorCode.IS_SUCCEEDED(retPhotos['retCode']):
                    ret['photos'] = retPhotos['data']

            else:
                self.outerObj._logger.error('unable to find album set id from link: {0}'.format(data['link']))

            return ret

        def _dataParserMultiPhotoCheckin(self, data, isFeedApi=True):
            ret = {}
            if isFeedApi:
                ret['id'] = data['id']
            else:
                ret['id'] = '%s_%s' % (self.outerObj.myId, data['id'])
            ret['message'] = data.get('message', None)
            ret['caption'] = None

            if 'application' in data:
                ret['application'] = data['application']['name']
            ret['createdTime'] = self._convertTimeFormat(data.get('created_time', data.get('updated_time', None)))
            ret['updatedTime'] = self._convertTimeFormat(data.get('updated_time', data.get('created_time', None)))
            ret['links'] = []

            ret['photos'] = []
            # FIXME: Currently Facebook do not have API way to get checkin photos, so we list all photos in the album.
            # Please note that this methodology cannot exactly match the checkin photos.
            searchResult = re.search('^https?://www\.facebook\.com\/photo\.php[?&]fbid=(\d+?)&', data['link'])
            if searchResult is not None:
                # [0] Get album id from photo object
                photoId = searchResult.group(1)
                params = {
                    'access_token' : self.outerObj._accessToken,
                }
                uri = '{0}{1}/?{2}'.format(self.outerObj._graphUri, photoId, urllib.urlencode(params))
                try:
                    conn = self.outerObj._httpConn.urlopen('GET', uri, timeout=self.outerObj._timeout)
                except:
                    self.outerObj._logger.error('Unable to get photo object from link: {0}'.format(data['link']))
                    return ret
                photoObj = json.loads(conn.data)
                if type(photoObj) == dict and 'link' in photoObj:
                    searchResult = re.search('^https?://www\.facebook\.com\/photo\.php\?.+&set=a\.(\d+?)\.', photoObj['link'])
                    if searchResult is not None:
                        albumId = searchResult.group(1)
                        self.outerObj._logger.info("found an albumID from a photo link: {0}".format(albumId))
                        # [1] Retrieve photos in album
                        feedHandler = self.outerObj.FbAlbumFeedsHandler(id=albumId, outerObj=self.outerObj)
                        retPhotos = feedHandler.getPhotos(maxLimit=0, basetime=ret['createdTime'], timerange=timedelta(minutes=20))
                        if ErrorCode.IS_SUCCEEDED(retPhotos['retCode']):
                            ret['photos'] = retPhotos['data']
            else:
                self.outerObj._logger.error('Unable to find photo id from link: {0}'.format(data['link']))

            return ret


        def _dataParserTagPhoto(self, data, isFeedApi=True):
            ret = {}
            if isFeedApi:
                ret['id'] = data['id']
            else:
                ret['id'] = '%s_%s' % (self.outerObj.myId, data['id'])
            params = {
                'access_token' : self.outerObj._accessToken,
            }

            ret['message'] = data.get('message', None) or data.get('story', None)
            if 'application' in data:
                ret['application'] = data['application']['name']
            ret['createdTime'] = self._convertTimeFormat(data.get('created_time', data.get('updated_time', None)))
            ret['updatedTime'] = self._convertTimeFormat(data.get('updated_time', data.get('created_time', None)))
            # photo type's link usually could not access outside, so we will not export link for photo type
            ret['links'] = []
            ret['photos'] = []

            place = self._getGpsInfo(data)
            if place:
                ret['place'] = place

            people = self._getTagPeople(data)
            if people:
                ret['people'] = people

            uri = '{0}{1}/?{2}'.format(self.outerObj._graphUri, data['object_id'], urllib.urlencode(params))
            self.outerObj._logger.debug('Tag photo URI to retrieve [%s]' % uri)
            try:
                conn = self.outerObj._httpConn.urlopen('GET', uri, timeout=self.outerObj._timeout)
            except:
                self.outerObj._logger.exception('Unable to get data from Facebook')
                # If unable to get tag object, turn to use feed's data
                imgUri = self._getFbMaxSizePhotoUri(data)
                if not imgUri and 'picture' in data:
                    imgUri = data['picture']
                imgPath = self._imgLinkHandler(imgUri)
                if imgPath:
                    ret['photos'].append(imgPath)
                return ret

            tagPhotoData = json.loads(conn.data)
            if type(tagPhotoData) == dict and 'images' in tagPhotoData:
                ret['caption'] = tagPhotoData.get('name', None)
                imgUri = tagPhotoData['images'][0]['source']
            else:
                # If returned invalid tag object data, turn to use feed's data
                imgUri = self._getFbMaxSizePhotoUri(data)

            if not imgUri and 'picture' in data:
                imgUri = data['picture']
            imgPath = self._imgLinkHandler(imgUri)
            if imgPath:
                ret['photos'].append(imgPath)

            return ret

        def _dataParserPhoto(self, data, isFeedApi=True):
            ret = {}
            if isFeedApi:
                ret['id'] = data['id']
            else:
                ret['id'] = '%s_%s' % (self.outerObj.myId, data['id'])
            ret['message'] = data.get('message', None)
            ret['caption'] = data.get('caption', None)
            if 'application' in data:
                ret['application'] = data['application']['name']
            ret['createdTime'] = self._convertTimeFormat(data.get('created_time', data.get('updated_time', None)))
            ret['updatedTime'] = self._convertTimeFormat(data.get('updated_time', data.get('created_time', None)))
            # photo type's link usually could not access outside, so we will not export link for photo type
            ret['links'] = []

            place = self._getGpsInfo(data)
            if place:
                ret['place'] = place

            people = self._getTagPeople(data)
            if people:
                ret['people'] = people

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
                ret['id'] = '%s_%s' % (self.outerObj.myId, data['id'])
            ret['message'] = data.get('message', None)
            ret['description'] = data.get('description', None)  # Link description
            ret['name'] = data.get('name', None)    # Link name
            if 'picture' in data:
                ret['picture'] = self._stripSafeImage(data['picture'])
            # Link's caption usually is the link, so we will not export caption here.
            ret['caption'] = None
            if 'application' in data:
                ret['application'] = data['application']['name']
            ret['createdTime'] = self._convertTimeFormat(data.get('created_time', data.get('updated_time', None)))
            ret['updatedTime'] = self._convertTimeFormat(data.get('updated_time', data.get('created_time', None)))
            ret['links'] = []
            isFacebookLink = False
            if 'link' in data:
                if data['link'][0] == '/':
                    data['link'] = 'http://www.facebook.com%s' % (data['link'])
                if re.search('^https?://www\.facebook\.com/.*$', data['link']):
                    isFacebookLink = True
                    ret['links'].append(data['link'])
                elif re.search('^https?://apps\.facebook\.com/.*$', data['link']):
                    # Skip Facebook apps' link
                    pass
                else:
                    ret['links'].append(data['link'])

            # For Facebook link, try to expose more information as possible
            if isFacebookLink and 'description' in data:
                ret['caption'] = data['description']

            ret['photos'] = []
            # If there are links, do not expose photos due to currently photos will overwrite links attributes
            if len(ret['links']) == 0 and 'picture' in data:
                imgPath = self._imgLinkHandler(data['picture'])
                if imgPath:
                    ret['photos'].append(imgPath)

            # If link type data without a link or picture, do not expose this record
            if len(ret['links']) == 0 and len(ret['photos']) == 0:
                return None
            return ret

        def _dataParserNote(self, data, isFeedApi=True):
            ret = {}
            if isFeedApi:
                ret['id'] = data['id']
            else:
                ret['id'] = '%s_%s' % (self.outerObj.myId, data['id'])
            ret['message'] = data.get('name', None) or data.get('subject', None)
            content = data.get('description', None) or data.get('message', None)
            if content:
                content = re.sub('<br\s*?/?>', '\n', content)
                try:
                    content = lxml.html.fromstring(content).text_content()
                except:
                    self.outerObj._logger.info('Unable to purify html. content[%s]' % content)
            ret['caption'] = content
            if 'application' in data:
                ret['application'] = data['application']['name']
            ret['createdTime'] = self._convertTimeFormat(data.get('created_time', data.get('updated_time', None)))
            ret['updatedTime'] = self._convertTimeFormat(data.get('updated_time', data.get('created_time', None)))
            ret['links'] = []
            if 'link' in data:
                if data['link'][0] == '/':
                    data['link'] = 'http://www.facebook.com%s' % (data['link'])
                if not re.search('^https?://www\.facebook\.com/.*$', data['link']):
                    ret['links'].append(data['link'])
            ret['photos'] = []
            if 'picture' in data:
                imgPath = self._imgLinkHandler(data['picture'])
                if imgPath:
                    ret['photos'].append(imgPath)
            return ret

        def _dataParserVideo(self, data, isFeedApi=True):
            ret = {}
            if isFeedApi:
                ret['id'] = data['id']
            else:
                ret['id'] = '%s_%s' % (self.outerObj.myId, data['id'])
            ret['message'] = data.get('message', None) or data.get('name', None)
            # Link's caption usually is the link, so we will not export caption here.
            ret['caption'] = None
            if 'application' in data:
                ret['application'] = data['application']['name']
            ret['createdTime'] = self._convertTimeFormat(data.get('created_time', data.get('updated_time', None)))
            ret['updatedTime'] = self._convertTimeFormat(data.get('updated_time', data.get('created_time', None)))
            ret['links'] = []
            if isFeedApi:
                if 'link' in data:
                    ret['links'].append(data['link'])
                people = self._getVideoTag(data)
                if people:
                    ret['people'] = people
            else:
                ret['links'].append('https://www.facebook.com/photo.php?v=%s' % data['id'])
                people = self._getTagPeople(data)
                if people:
                    ret['people'] = people
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
                ret['id'] = '%s_%s' % (self.outerObj.myId, data['id'])
            ret['message'] = data.get('message', None)
            if isFeedApi:
                ret['caption'] = data['caption']
            else:
                ret['caption'] = 'checked in at %s' % (data['place']['name'])

            place = self._getGpsInfo(data)
            if place:
                ret['place'] = place

            if isFeedApi:
                people = self._getTagPeople(data)
            else:
                people = self._getTagPeople(data, tagName='tags')
            if people:
                ret['people'] = people

            if 'application' in data:
                ret['application'] = data['application']['name']

            ret['createdTime'] = self._convertTimeFormat(data.get('created_time', data.get('updated_time', None)))
            ret['updatedTime'] = self._convertTimeFormat(data.get('updated_time', data.get('created_time', None)))

            # checkin type's link usually could not access outside, so we will not export link for photo type
            ret['links'] = []

            ret['photos'] = []
            if 'object_id' in data:
                albumId = self._albumIdFromObjectId(data['object_id'])

                if albumId:
                    self.outerObj._logger.info("found an albumID from a checkin link: {0}".format(albumId))
                    dataHandler = self.outerObj.FbAlbumFeedsHandler(id=albumId, outerObj=self.outerObj)
                    retPhotos = dataHandler.getPhotos(maxLimit=0, basetime=ret['createdTime'], timerange=timedelta(minutes=20))
                    if ErrorCode.IS_SUCCEEDED(retPhotos['retCode']):
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
                # Note is a link type in FeedApi
                if 'application' in data and data['application']['id'] == '2347471856':
                    return self._dataParserNote
                else:
                    return self._dataParserLink
            elif fType == 'photo':
                if self._isAlbum(data):
                    return self._dataParserAlbum
                elif self._isMultiPhotoCheckin(data):
                    return self._dataParserMultiPhotoCheckin
                elif self._isTagPhoto(data):
                    return self._dataParserTagPhoto
                else:
                    return self._dataParserPhoto
            elif fType == 'video':
                return self._dataParserVideo
            elif fType == 'checkin':
                return self._dataParserCheckin
            return None

        def _isAlbum(self, data):
            searchResult = re.search('^https?://www\.facebook\.com\/photo\.php\?.+&set=a\.(\d+?)\.', data['link'])
            if not searchResult:
                return False
            albumId = searchResult.group(1)
            params = {
                'access_token' : self.outerObj._accessToken,
            }

            uri = '{0}{1}/?{2}'.format(self.outerObj._graphUri, albumId, urllib.urlencode(params))
            self.outerObj._logger.debug('Album URI to retrieve [%s]' % uri)
            try:
                conn = self.outerObj._httpConn.urlopen('GET', uri, timeout=self.outerObj._timeout)
            except:
                self.outerObj._logger.exception('Unable to get data from Facebook')
                return False
            retDict = json.loads(conn.data)
            # If album owner is me and it's uploadable, the album is what we should crawl
            if type(retDict) == dict and 'from' in retDict and type(retDict['from']) == dict and retDict['from']['id'] == self.outerObj.myId:
                if retDict['can_upload']:
                    # Check can_upload to filter 'Wall Photos', 'Mobile photos', or something internal albums
                    return True

            return False

        def _isMultiPhotoCheckin(self, data):
            searchResult = re.search('^https?://www\.facebook\.com\/photo\.php\?.+&set=pcb\.(\d+?)[.&]', data['link'])
            if not searchResult:
                return False
            return True

        def _isTagPhoto(self, data):
            if 'story_tags' in data:
                return True
            return False

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

    class FbApiHandlerNotes(FbApiHandlerBase):
        def parseInner(self, data):
            return self._dataParserNote(data, isFeedApi=False)


    class FbAlbumFeedsHandler(FbApiHandlerBase):
        def __init__(self, *args, **kwargs):
            super(self.__class__, self).__init__(*args, **kwargs)
            self._limit = kwargs.get('limit', 25)
            self._id = kwargs['id']

        def getPhotos(self, maxLimit=0, limit=25, basetime=datetime.now(), timerange=timedelta(minutes=15)):
            retDict = {
                'retCode': ErrorCode.S_OK,
                'data': [],
                'count': 0,
            }
            offset = 0
            if maxLimit > 0 and maxLimit < limit:
                limit = maxLimit

            errorCode, feedData = self._pageCrawler(offset, limit)
            failoverCount = 0
            failoverThreshold = 3
            while errorCode != ErrorCode.E_NO_DATA:
                if ErrorCode.IS_FAILED(errorCode):
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

                offset += len(feedData['data'])
                errorCode, feedData = self._pageCrawler(offset, limit)
            return retDict

        def _pageCrawler(self, offset, limit):
            params = {
                'access_token' : self.outerObj._accessToken,
                'offset' : offset,
                'limit': limit,
            }

            uri = '{0}{1}/photos?{2}'.format(self.outerObj._graphUri, self._id, urllib.urlencode(params))
            self.outerObj._logger.debug('photos URI to retrieve [%s]' % uri)
            try:
                conn = self.outerObj._httpConn.urlopen('GET', uri, timeout=self.outerObj._timeout)
            except:
                self.outerObj._logger.exception('Unable to get data from Facebook')
                return ErrorCode.E_FAILED, {}
            retDict = json.loads(conn.data)
            if 'data' not in retDict or 'paging' not in retDict or len(retDict['data']) == 0:
                return ErrorCode.E_NO_DATA, {}
            return ErrorCode.S_OK, retDict

        def _parse(self, feedData):
            retList = []
            for data in feedData['data']:
                if 'images' in data and len(data['images']) > 0 and 'source' in data['images'][0]:
                    imgUri = data['images'][0]['source']
                    imgPath = self._imgLinkHandler(imgUri)
                    if imgPath:
                        retList.append(imgPath)
            return retList


