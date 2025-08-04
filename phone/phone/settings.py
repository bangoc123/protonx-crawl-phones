# settings.py - Optimized for multi-threading
BOT_NAME = 'phone'

SPIDER_MODULES = ['phone.spiders']
NEWSPIDER_MODULE = 'phone.spiders'

# CONCURRENT SETTINGS - Tối ưu hóa đa luồng
CONCURRENT_REQUESTS = 32  # Tăng từ 16 (mặc định) lên 32
CONCURRENT_REQUESTS_PER_DOMAIN = 16  # Giới hạn requests cho mỗi domain
CONCURRENT_REQUESTS_PER_IP = 8  # Giới hạn requests cho mỗi IP

# DOWNLOAD SETTINGS
DOWNLOAD_DELAY = 1  # Giảm delay để tăng tốc độ
RANDOMIZE_DOWNLOAD_DELAY = 0.5  # Random delay 0.5-1.5 giây
DOWNLOAD_TIMEOUT = 30  # Timeout 30 giây
DOWNLOAD_HANDLERS = {
    "http": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler",
    "https": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler",
}

# RETRY SETTINGS
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]

# AUTOTHROTTLE - Tự động điều chỉnh tốc độ crawl
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 3
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = True  # Bật để debug

# REACTOR SETTINGS - Sử dụng SelectReactor để tránh conflicts
TWISTED_REACTOR = 'twisted.internet.selectreactor.SelectReactor'

# MEMORY USAGE - Giám sát và giới hạn memory
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 2048  # 2GB limit
MEMUSAGE_WARNING_MB = 1536  # Warning ở 1.5GB

# DUPEFILTER - Tối ưu bộ lọc trùng lặp
DUPEFILTER_CLASS = 'scrapy.dupefilters.RFPDupeFilter'
DUPEFILTER_DEBUG = False

# CACHE SETTINGS
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600  # Cache 1 giờ
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 403, 404, 408]
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# CONNECTION POOLING
REACTOR_THREADPOOL_MAXSIZE = 20

# DNS SETTINGS
DNSCACHE_ENABLED = True
DNSCACHE_SIZE = 10000
DNS_TIMEOUT = 60

# ROBOTSTXT
ROBOTSTXT_OBEY = False  # Tắt để tăng tốc độ

# USER AGENT
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'

# DEFAULT REQUEST HEADERS
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# COOKIES
COOKIES_ENABLED = True
COOKIES_DEBUG = False

# TELNET CONSOLE
TELNETCONSOLE_ENABLED = False

# SPIDER MIDDLEWARES
SPIDER_MIDDLEWARES = {
    # Có thể thêm custom middleware ở đây
}

# DOWNLOADER MIDDLEWARES
DOWNLOADER_MIDDLEWARES = {
    # Retry middleware với priority cao
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
    # HTTP cache middleware
    'scrapy.downloadermiddlewares.httpcache.HttpCacheMiddleware': 900,
}

# EXTENSIONS
EXTENSIONS = {
    'scrapy.extensions.telnet.TelnetConsole': None,
    'scrapy.extensions.memusage.MemoryUsage': 0,
    'scrapy.extensions.closespider.CloseSpider': 0,
}

# CLOSESPIDER EXTENSIONS
CLOSESPIDER_TIMEOUT = 7200  # 2 giờ
CLOSESPIDER_ITEMCOUNT = 10000  # Dừng sau 10k items
CLOSESPIDER_PAGECOUNT = 50000  # Dừng sau 50k pages
CLOSESPIDER_ERRORCOUNT = 100   # Dừng sau 100 errors

# ITEM PIPELINES
ITEM_PIPELINES = {
    'phone.pipelines.MongoDBPipeline': 300,
}

# LOG SETTINGS
LOG_LEVEL = 'INFO'
LOG_FILE = 'scrapy.log'
LOG_STDOUT = False

# FEEDS SETTINGS (nếu muốn export dữ liệu)
# FEEDS = {
#     'items.json': {
#         'format': 'json',
#         'encoding': 'utf8',
#         'store_empty': False,
#         'overwrite': True,
#     },
# }

# SCHEDULER SETTINGS
SCHEDULER = "scrapy.core.scheduler.Scheduler"
SCHEDULER_DEBUG = False
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.FifoMemoryQueue'

# STATS SETTINGS
STATS_CLASS = 'scrapy.statscollectors.MemoryStatsCollector'

# COMPRESSION
COMPRESSION_ENABLED = True

# REDIRECT SETTINGS
REDIRECT_ENABLED = True
REDIRECT_MAX_TIMES = 5

# AJAXCRAWL
AJAXCRAWL_ENABLED = False

# REQUEST FINGERPRINTER
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'