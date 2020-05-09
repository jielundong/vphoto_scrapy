import os
from scrapy.cmdline import execute

os.chdir(os.path.dirname(os.path.realpath(__file__)))

try:
    execute(
        [
            'scrapy',
            'crawl',
            'vphoto',
            '-o',
            'out.json',
            '-a',
            #'urls=http://vphotos.cn/7G8r,http://vphotos.cn/7G8d,http://vphotos.cn/7G7r'
            'urls=http://vphotos.cn/7G8r'
        ]
    )
except SystemExit:
    pass