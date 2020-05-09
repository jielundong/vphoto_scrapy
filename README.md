# vphoto_scrapy
vphoto crawler using scrapy

usage:
scrapy crawl vphoto -a folder="files will be saved here" -a urls="urls to be scraped, using ',' to seperate multiple urls"

example:
scrapy crawl vphoto -a foler="e:\\" -a urls="http://vphotos.cn/7G8d,http://vphotos.cn/7G7r"

Only accept urls of vphoto galleries 