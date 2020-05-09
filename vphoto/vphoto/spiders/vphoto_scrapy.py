import scrapy
from scrapy.http import FormRequest
import logging
import json
import os
from urllib.parse import urlsplit, parse_qs


class Cvphoto(scrapy.Spider):
    name = "vphoto"
    start_urls = []

    def __init__(self, *args, **kwargs):
        logger = logging.getLogger('scrapy.vphoto')
        logger.setLevel(logging.INFO)
        self._folder = kwargs.get('folder')
        if not self._folder:
            self._folder = os.getcwd()
        if not os.path.exists(self._folder):
            self.createFolder(self._folder)
        urls =  kwargs.get('urls')
        if urls :
            self.start_urls += urls.split(",")
        self._pages = {}
        super().__init__(*args, **kwargs)

    def parse(self, response):
        realUrl = response.url
        self.logger.info("processing url: {}".format(realUrl))
        sn = self.getAlbumSn(realUrl)
        self._pages[sn] = {}
        yield self.getMetaData(sn)

    def getAlbumSn(self, realUrl):
        o = urlsplit(realUrl)
        if o.hostname == 'gallery.vphotos.cn':
            return parse_qs(o.query)['vphotowechatid'][0]
        return ""

    def getMetaData(self, sn):
        query = """{"query":"{findAlbumModule(request:{albumSn:\\"%s\\"}){choicePhotos{smallWidth smallHeight thumbUrl smallUrl photoName} title{headTitle subHeadTitle titleFontSize} support{serviceSupportSwitch photographerLevelName cloudDeviceName photographerCount} count{mediaDataCount{photoCount totalCount videoCount} visitCount}} findAlbumActivity(request:{albumSn:\\"%s\\"}){activity{content address time status}}}" }""" % (sn, sn)
        return scrapy.Request(url="https://api.vphotos.cn/gateway/album/gq", method="POST", meta={'sn': sn}, body=query, callback=self.parseMetaData)

    def parseMetaData(self, response):
        res = json.loads(response.text)
        sn = response.meta['sn']
        title = res.get('data').get('findAlbumModule').get(
            'title').get('headTitle')
        photoCount = res.get('data').get('findAlbumModule').get(
            'count').get('mediaDataCount').get('photoCount')
        self._pages[sn]['title'] = title
        self._pages[sn]['photoCount'] = photoCount
        #self.logger.info("pages {} ".format(self._pages))
        folder = os.path.join(self._folder, title)
        if not os.path.exists(folder):
            self.createFolder(folder)
        yield self.getUid(sn)

    def getUid(self, sn):
        params = {'weChatId': sn, 'albumSn': sn}
        return FormRequest(url="https://api.vphotos.cn/vphotosgallery/wechat/album/getuId", formdata=params, meta={'sn': sn}, callback=self.parseUid)

    def parseUid(self, response):
        res = json.loads(response.text)
        sn = response.meta['sn']
        uid = res.get('data').get('uId')
        self._pages[sn]['uid'] = uid
        #self.log("pages {} ".format(self._pages))
        yield self.getAllPhotos(sn)

    def getAllPhotos(self, sn):
        pageInfo = self._pages[sn]
        uId = pageInfo['uid']
        pageSize = 100
        url = """https://api.vphotos.cn/gateway/albumphoto/v1/album/photo/mobile/find?pageSize={pageSize}&sort=asc&rank=3&weChatId={weChatId}&albumSn={albumSn}&uId={uId}""".format(
            pageSize=pageSize, weChatId=sn, albumSn=sn, uId=uId)
        return scrapy.Request(url=url, meta={'sn': sn}, callback=self.parseAllPhotos)

    def parseAllPhotos(self, response):
        photos = json.loads(response.text)
        sn = response.meta['sn']
        pageInfo = self._pages[sn]
        uId = pageInfo['uid']
        photos = [(photo.get('photoId'), photo.get('photoName'))
                  for photo in photos]
        if not self._pages[sn].get('photos'):
            self._pages[sn]['photos'] = photos
            self.log("first set of photos info loaded")
        else:
            self._pages[sn]['photos'] = self._pages[sn]['photos'] + photos
            self.log("appending photos")
        # self.log(self._pages[sn]['photos'])
        loadedPhotoCount = len(self._pages[sn]['photos'])
        self.log("loaded photos count {}".format(loadedPhotoCount))
        photoCount = self._pages[sn]['photoCount']
        if photoCount == loadedPhotoCount:
            self.log("all photos info are loaded, starting to download")
            yield from self.downloadLargePhotos(sn)
        else:
            self.log("requesting next 100 photos info")
            url = """https://api.vphotos.cn/gateway/albumphoto/v1/album/photo/mobile/find?pageSize={pageSize}&lastPhotoId={lastPhotoId}&offset={offset}&sort=asc&rank=3&weChatId={weChatId}&albumSn={albumSn}&uId={uId}""".format(
                pageSize=100, lastPhotoId=self._pages[sn]['photos'][-1][0], offset=loadedPhotoCount, weChatId=sn, albumSn=sn, uId=uId)
            self.log(url)
            yield scrapy.Request(url=url, meta={'sn': sn}, callback=self.parseAllPhotos)
        #self.log("pages : {}".format(self._pages))

    def downloadLargePhotos(self, sn):
        url = """https://api.vphotos.cn/vphotosgallery/wechat/album/getPhotoUrl"""
        pageInfo = self._pages[sn]
        uId = pageInfo['uid']
        photos = pageInfo['photos']
        title = pageInfo['title']
        params = {
            'photoId': '',
            'uId': str(uId),
            'photoSizeType': '4',
            'weChatId': sn,
            'albumSn': sn
        }
        requests = []
        index = 1
        for id in photos[0:1]:
            params['photoId'] = id[0]
            photoName = id[1]
            path = os.path.join(self._folder, title, photoName)
            if not os.path.exists(path):
                requests.append(FormRequest(url=url, formdata=params, meta={
                                'sn': sn, 'idx': index, 'path': path}, callback=self.parseDownloadPhoto))
            else:
                self.log("skip existed file : {} , index : {}".format(path, index))
            index = index + 1
        return requests

    def parseDownloadPhoto(self, response):
        photoInfo = json.loads(response.text)
        path = response.meta['path']
        index = response.meta['idx']
        photoUrl = photoInfo.get('data').get('smallUrl')

        self.log("downloading : index {} -->> {} to {}".format(index, photoUrl, path))
        yield scrapy.Request(url=photoUrl, meta={'path': path}, callback=self.downloadFile)

    def downloadFile(self, response):
        local_filename = response.meta['path']
        # NOTE the stream=True parameter below
        with open(local_filename, 'wb') as f:
            f.write(response.body)
        self.log("downloaded {}".format(local_filename))

    def createFolder(self, title):
        try:
            os.mkdir(title)
        except OSError:
            self.log("Creation of the directory {} failed".format(title))
            return False
        else:
            self.log("Successfully created the directory {} ".format(title))
        return True
# def _getCurTime(self):
#     return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
