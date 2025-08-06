import traceback
import pymongo
import requests
import time
import os
import schedule
from time import gmtime, strftime
import scrapy
from bs4 import BeautifulSoup, Tag
from decouple import config
from scrapy import Request
from scrapy.spiders.sitemap import gzip_magic_number
from scrapy.utils.gz import gunzip
import gzip
import zlib
import brotli
import logging
import json
import re
from typing import List, Dict, Any
import xmltodict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import sys

# Bắt buộc dùng demjson3 để parse JS-style object literals
try:
    import demjson3
except ImportError:
    sys.exit(
        "⚠️ [LỖI] Cần cài `demjson3` để parse JS literals linh hoạt. Vui lòng chạy `pip install demjson3` và thử lại.`"
    )

# MongoDB setup
url = config('url')
client = pymongo.MongoClient(url, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
logging.getLogger("pymongo").setLevel(logging.WARNING)

try:
    print(client.admin.command('ping'))
    print("Ping thành công, đã kết nối đến primary.")
except Exception as e:
    print("LỖI khi ping:", e)

db = client["thegioididceong"]
# db = client["cellphones"]
# db = client["fptshop"]

# Lấy URLs đã có trong DB
current_links = list(db['details_raw'].find({}, {"url": 1}))  
current_set = set([item['url'] for item in current_links])
print('------Num in DB---------', len(current_links))

def cleanText(p_texts):
    txt = ''
    for p_t in p_texts:
        clean_p_t = p_t.strip()
        if clean_p_t and len(clean_p_t) >= 2:
            txt += "{}\n".format(clean_p_t)
    return txt

REMOVE_ATTRIBUTES = ['style', 'data-src', 'src', 'href', 'aria-describedby', 'data-wpel-link', 'rel', 'target', 'id', 'class', 'aria-level', 'data-mce-style', 'data-mce-href']

class JobSpider(scrapy.Spider):
    name = 'phone'
    start_urls = [
        'https://www.thegioididong.com/newsitemap/sitemap-cate',
        'https://www.thegioididong.com/newsitemap/sitemap-product', 
        'https://www.thegioididong.com/newsitemap/sitemap-news'
        # 'https://cellphones.com.vn/sitemap/sitemap_index.xml'
        # 'https://fptshop.com.vn/sitemap.xml'
    ]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        },
        'ROBOTSTXT_OBEY': False,
        
        # CONCURRENT SETTINGS - Tăng hiệu suất đa luồng
        'CONCURRENT_REQUESTS': 32,  # Tăng từ 16 (mặc định) lên 32
        'CONCURRENT_REQUESTS_PER_DOMAIN': 16,  # Giới hạn cho mỗi domain
        'CONCURRENT_REQUESTS_PER_IP': 8,  # Giới hạn cho mỗi IP
        
        # DOWNLOAD SETTINGS
        'DOWNLOAD_DELAY': 1,  # Giảm delay từ 2 xuống 1
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,  # Random delay 0.5-1.5s
        'DOWNLOAD_TIMEOUT': 30,  # Timeout 30s
        
        # RETRY SETTINGS
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],
        
        # AUTOTHROTTLE - Tự động điều chỉnh tốc độ
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 0.5,
        'AUTOTHROTTLE_MAX_DELAY': 3,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 2.0,
        'AUTOTHROTTLE_DEBUG': True,
        
        # REACTOR SETTINGS - Sử dụng SelectReactor để tránh conflicts
        'TWISTED_REACTOR': 'twisted.internet.selectreactor.SelectReactor',
        
        # MEMORY USAGE
        'MEMUSAGE_ENABLED': True,
        'MEMUSAGE_LIMIT_MB': 2048,
        
        # DUPEFILTER - Tối ưu bộ lọc trùng lặp
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.RFPDupeFilter',
        
        # LOG SETTINGS
        'LOG_LEVEL': 'INFO',
    }

    def parse(self, response):
        if response.status == 403:
            self.logger.error(f"Access forbidden for URL: {response.url}")
            return
            
        print('---response.url:', response.url)
        print('---response.status:', response.status)

        # response = requests.get(url, headers={'Accept-Encoding': 'gzip, deflate'}) # Sử dụng requests để lấy nội dung cho fptshop
        # print('---response.status_code:', response.status_code)
        # response.raise_for_status()

        if 'https://fptshop.com.vn/sitemap.xml' in self.start_urls:
            body = response.body
            headers = response.headers.get

            # 1) Xem Content-Encoding header
            encoding = headers(b'Content-Encoding', b'').decode().lower()
            self.logger.info(f"Content-Encoding: {encoding}")

            # 2) Giải nén theo header
            try:
                if 'br' in encoding:
                    body = brotli.decompress(body)
                    self.logger.info("✅ Brotli decompressed")
                elif gzip_magic_number(response):
                    try:
                        body = gunzip(body)
                    except Exception:
                        body = gzip.decompress(body)
                    self.logger.info("✅ GZIP decompressed via gunzip/gzip.decompress")
                # thử deflate/raw zlib (nếu vẫn không phải XML)
                if not body.strip().startswith(b'<'):
                    try:
                        body = zlib.decompress(body)
                        self.logger.info("✅ Zlib/Deflate decompressed")
                    except Exception:
                        pass
            except Exception as e:
                self.logger.warning(f"Decompression step failed: {e}")

            # 3) Chuyển sang text & parse XML
            try:
                text = body.decode('utf-8', errors='ignore')
                obj = xmltodict.parse(text)
                json_data = json.loads(json.dumps(obj))
            except Exception as e:
                self.logger.error(f"❌ XML parse error: {e}")
                self.logger.debug(body[:200])
                self.logger.debug(traceback.format_exc())
                return
        else:
            try:
                obj = xmltodict.parse(response.body)
                json_data = json.loads(json.dumps(obj))
                print('---json_data keys:', list(json_data.keys()))
                self.logger.info(f"Parsed XML data successfully from {response.url}")
            except Exception as e:
                self.logger.error(f"❌ XML parse error: {e}")
                self.logger.debug(response.body[:200])
                self.logger.debug(traceback.format_exc())
                return
        try:
            # Kiểm tra xem đây là sitemapindex hay urlset
            if 'sitemapindex' in json_data:
                # Đây là sitemap index - cần crawl các sitemap con
                print("📋 Found sitemapindex - crawling sub-sitemaps...")
                sitemap_list = json_data['sitemapindex'].get('sitemap', [])
                
                if isinstance(sitemap_list, dict):
                    sitemap_list = [sitemap_list]
                
                for sitemap_item in sitemap_list:
                    sitemap_url = sitemap_item.get('loc')
                    print("sitemap_url", sitemap_url)
                    if sitemap_url: # fptshop: 'products' in sitemap_url and 'dien-thoai' in sitemap_url:
                        yield Request(
                            url=sitemap_url,
                            callback=self.parse,
                            # dont_filter=True,
                            headers={'Referer': 'https://www.thegioididong.com/'},
                            # headers={'Referer': 'https://fptshop.com.vn/'},
                            # headers={'Referer': 'https://cellphones.com.vn/'},
                            priority=1  # Priority cao cho sitemap
                        )
                        
            elif 'urlset' in json_data:
                # Đây là urlset chứa các URL bài viết
                print("📄 Found urlset - extracting article URLs...")
                url_list = json_data['urlset'].get('url', [])
                
                if isinstance(url_list, dict):
                    url_list = [url_list]
                
                urls = []
                for url_item in url_list:
                    if isinstance(url_item, dict):
                        loc = url_item.get('loc')
                        if loc:
                            urls.append(loc)
                    elif isinstance(url_item, str):
                        urls.append(url_item)
                
                new_links = [url for url in urls if url not in current_set]
                print(f'📊 Total URLs: {len(urls)}, New URLs: {len(new_links)}')
                
                # Chia URLs thành batches để xử lý song song
                batch_size = 50
                for i in range(0, len(new_links), batch_size):
                    batch = new_links[i:i + batch_size]
                    for link in batch:
                        if 'http' in link and 'dtdd' in link and 'sac' not in link and 'phu-kien' not in link: # thegioididong (dtdd) # cellphones: if dien-thoai is not link, To should be check keywords such as iPhone, samsung, xiaomi, oppo, realme, nothing, infinix, vivo, tecno, sony, itel, nubia, masstel, nokia, oneplus, tcl, inoi, benco, asus
                            yield Request(
                                url=link,
                                callback=self._parse_product_info_fptshop, # thegioididong (self.parse_product_info)
                                # dont_filter=True,
                                # headers={'Referer': 'https://cellphones.com.vn/'}, # https://www.thegioididong.com/
                                # headers={'Referer': 'https://fptshop.com.vn/'},
                                headers={'Referer': 'https://www.thegioididong.com/'},
                                priority=0,  # Priority thấp hơn sitemap
                                meta={'batch_id': i // batch_size}  # Để tracking
                            )
            else:
                print("⚠️ Unknown sitemap format:", list(json_data.keys()))
                
        except Exception as e:
            print(f'❌ Error parsing sitemap {response.url}: {e}')
            print('Response body preview:', response.body[:500])
            print(traceback.format_exc())

    def parse_product_info(self, response):
        try:
            print(f'📄 Parsing product: {response.url}')
            url = response.request.url
            soup = BeautifulSoup(response.text, "lxml")

            # --- Khởi tạo các biến với giá trị mặc định ---
            product_data = {}

            # --- Tìm các container chính ---
            detail_container = soup.find("section", class_="detail")
            if not detail_container:
                print(f"⚠️ Critical: Main 'detail' container not found for {url}. Aborting.")
                return

            # Sử dụng ThreadPoolExecutor để xử lý song song các phần khác nhau
            with ThreadPoolExecutor(max_workers=8) as executor:
                # Submit các task để chạy song song
                future_basic_info = executor.submit(self.extract_basic_info, detail_container, url)
                future_options = executor.submit(self.extract_options, detail_container, url)
                future_saving_box = executor.submit(self.extract_saving_box, soup)
                future_specifications = executor.submit(self.extract_specifications, soup, url)
                future_policies = executor.submit(self.extract_policies, soup, url)

                # Collect results
                basic_info = future_basic_info.result()
                options_info = future_options.result()
                saving_info = future_saving_box.result()
                specifications = future_specifications.result()
                policies = future_policies.result()

                # Merge all data
                product_data.update(basic_info)
                product_data.update(options_info)
                product_data.update(saving_info)
                product_data['specifications'] = specifications
                product_data['policies'] = policies

            if not product_data.get('product_name'):
                print(f"⚠️ No product name found for: {url}")
                yield {
                    "url": url,
                    "product_data": product_data,
                    "crawled_at": strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                    "status": "no_name_found"
                }
                return

            print(f"✅ Successfully parsed: {product_data.get('product_name', 'Unknown')}")
            
            yield {
                "url": url,
                "product_data": product_data,
                "crawled_at": strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                "status": "success"
            }

        except Exception as e:
            print(f'❌ Error parsing article {response.url}: {e}')
            print(traceback.format_exc())
            
            yield {
                "url": response.url,
                "product_data": "",
                "crawled_at": strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                "status": f"error: {str(e)}"
            }

    def extract_basic_info(self, detail_container, url):
        """Trích xuất thông tin cơ bản của sản phẩm"""
        product_data = {}
        
        name_container = detail_container.find("div", class_="product-name")
        if name_container:
            name_tag = name_container.find("h1")
            if name_tag:
                product_data['product_name'] = name_tag.get_text(strip=True)

            quantity_tag = name_container.find("span", class_="quantity-sale")
            if quantity_tag:
                product_data['quantity_sale'] = quantity_tag.get_text(strip=True)

            rate_tag = name_container.find("div", class_="detail-rate")
            if rate_tag:
                product_data['detail_rate'] = rate_tag.get_text(strip=True)

        # Trích xuất breadcrumb
        try:
            breadcrumb_container = detail_container.find("ul", class_="breadcrumb")
            if breadcrumb_container:
                product_types = breadcrumb_container.find_all("a")
                type_list = [item.get_text(strip=True) for item in product_types]
                product_data['product_type'] = type_list
        except Exception as e:
            print(f"⚠️ Error extracting product type for {url}: {e}")
            product_data['product_type'] = []
            
        return product_data

    def extract_options(self, detail_container, url):
        """Trích xuất thông tin tùy chọn sản phẩm"""
        product_data = {}
        
        options_container = detail_container.find("div", class_="group-box03")
        if options_container:
            # Lấy dung lượng đang được chọn
            capacity_tag = options_container.select_one("div.box03:not(.color) a.act")
            if capacity_tag:
                product_data['selected_capacity'] = capacity_tag.get_text(strip=True)
            else:
                product_data['selected_capacity'] = ""

            # Lấy tất cả màu sắc
            color_tags = options_container.select("div.box03.color a")
            all_colors = [tag.get_text(strip=True) for tag in color_tags]
            product_data['all_colors'] = all_colors

            # Lấy màu sắc đang được chọn
            # color_tag = options_container.select_one("div.box03.color a.act")
            # if color_tag:
            #     product_data['selected_color'] = color_tag.get_text(strip=True)
            # else:
            #     product_data['selected_color'] = ""
        else:
            print(f"⚠️ Could not find product options container for: {url}")
            
        return product_data

    def extract_product_info(self, soup):
        """
        Trích xuất thông tin sản phẩm từ cấu trúc HTML mới, bao gồm:
        giá hiện tại, giá gốc, phần trăm giảm giá, địa điểm và khuyến mãi.
        """
        product_data = {}

        # 1. Lấy thông tin về giá, giảm giá và trả góp
        price_box = soup.select_one("div.price-one")
        if price_box:
            promo_price_tag = price_box.select_one("p.box-price-present")
            original_price_tag = price_box.select_one("p.box-price-old")
            discount_tag = price_box.select_one("p.box-price-percent")
            installment_tag = price_box.select_one("span.label--black")

            product_data['promo_price'] = promo_price_tag.get_text(strip=True) if promo_price_tag else ""
            product_data['original_price'] = original_price_tag.get_text(strip=True) if original_price_tag else ""
            product_data['discount'] = discount_tag.get_text(strip=True) if discount_tag else ""
            product_data['installment_info'] = installment_tag.get_text(strip=True) if installment_tag else ""

        # 2. Lấy thông tin về địa điểm
        location_box = soup.select_one("div#location-detail")
        if location_box:
            location_tag = location_box.select_one("a")
            product_data['location'] = location_tag.get_text(strip=True) if location_tag else ""
        
        # 3. Lấy thông tin khuyến mãi
        promo_box = soup.select_one("div.block__promo")
        if promo_box:
            promo_title_tag = promo_box.select_one("p.pr-txtb")
            promo_list_items = promo_box.select("div.divb-right p")
            
            product_data['promo_title'] = promo_title_tag.get_text(strip=True) if promo_title_tag else ""
            product_data['promo_list'] = [item.get_text(strip=True) for item in promo_list_items]

        # 4. Lấy điểm tích lũy
        loyalty_tag = soup.select_one("p.loyalty__main__point")
        if loyalty_tag:
            product_data['loyalty_points'] = loyalty_tag.get_text(strip=True)
            
        return product_data

    def extract_specifications(self, soup, url):
        """Trích xuất thông số kỹ thuật"""
        try:
            all_specifications = {}
            spec_groups = soup.select("div.box-specifi")

            for group in spec_groups:
                group_name_tag = group.select_one("h3")
                if not group_name_tag:
                    continue
                group_name = group_name_tag.get_text(strip=True)

                specs_in_group = {}
                spec_rows = group.select("ul > li")

                for row in spec_rows:
                    parts = row.find_all("aside")
                    if len(parts) == 2:
                        key = parts[0].get_text(strip=True).replace(':', '')
                        value = parts[1].get_text(separator=" ", strip=True)
                        specs_in_group[key] = value

                all_specifications[group_name] = specs_in_group
            
            return all_specifications
        except Exception as e:
            print(f"⚠️ Error extracting specifications for {url}: {e}")
            return {}

    def extract_policies(self, soup, url):
        """Trích xuất thông tin chính sách"""
        try:
            all_policies = {}

            # 1. Lấy các cam kết cơ bản
            commitments_list = []
            policy_list_tag = soup.select_one("ul.policy__list")
            if policy_list_tag:
                commitment_items = policy_list_tag.select("li > div.pl-txt")
                for item in commitment_items:
                    text = item.get_text(strip=True)
                    commitments_list.append(text)
            
            all_policies['commitments'] = commitments_list

            # 2. Lấy thông tin chi tiết từ pop-up
            popup_content_tag = soup.select_one("div#popup-baohanh-content")
            if popup_content_tag:
                warranty_box = popup_content_tag.select_one("div.warranty-box")
                if warranty_box:
                    warranty_title = warranty_box.select_one("h2.title").get_text(strip=True)
                    warranty_text = warranty_box.select_one("span").get_text(strip=True)
                    all_policies['warranty_policy'] = {
                        "title": warranty_title,
                        "details": warranty_text
                    }

                change_policy_dict = {}
                change_box = popup_content_tag.select_one("div.change-box")
                if change_box:
                    change_blocks = change_box.select("div.block-change")
                    for block in change_blocks:
                        block_title = block.select_one("h3").get_text(strip=True)
                        content_insider = block.select_one("div.content-insider")
                        if content_insider:
                            block_content = content_insider.get_text(separator="\n", strip=True)
                            change_policy_dict[block_title] = block_content

                all_policies['change_policy'] = change_policy_dict
            
            return all_policies

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất thông tin chính sách: {e}")
            return {}
    
    def _save_soup_to_file(self, soup: BeautifulSoup, filename: str = "output.html"):
        """
        Lưu nội dung của đối tượng BeautifulSoup vào một file.

        Args:
            soup (BeautifulSoup): Đối tượng BeautifulSoup chứa nội dung HTML đã được phân tích.
            filename (str): Tên file để lưu dữ liệu. Mặc định là 'output.html'.
        """
        try:
            # Sử dụng .prettify() để định dạng HTML dễ đọc
            with open(filename, "w", encoding="utf-8") as file:
                file.write(str(soup.prettify()))
            print(f"Đã lưu nội dung vào file '{filename}' thành công.")
        except Exception as e:
            print(f"Lỗi khi lưu file: {e}")
    
    def _parse_product_info_cellphones(self, response):
        """Phương thức này sẽ được gọi để trích xuất thông tin sản phẩm từ trang chi tiết"""
        try:
            print(f'📄 Parsing product: {response.url}')
            url = response.request.url
            soup = BeautifulSoup(response.text, "lxml")

            # Lưu nội dung HTML vào file để kiểm tra nếu cần
            # self._save_soup_to_file(soup, "output.html")
            # print("HTML content saved to output.html for debugging.")
            # return
            
            # --- Khởi tạo các biến với giá trị mặc định ---
            product_data = {}
            
            detail_container = soup.find("div", class_="box-detail-product")
            if not detail_container:
                print(f"⚠️ Critical: Main 'box-detail-product' container not found for {url}. Aborting.")
                return

            breadcrumb_items = []

            try:
                # 1. Tìm thẻ <script> chứa JSON-LD của breadcrumb
                breadcrumb_script = soup.find('script', {'type': 'application/ld+json'}, string=lambda s: 'BreadcrumbList' in s)

                if not isinstance(breadcrumb_script, Tag):
                    return breadcrumb_items

                # 2. Lấy nội dung JSON và parse nó
                json_data = json.loads(breadcrumb_script.string)

                # 3. Lặp qua 'itemListElement' để lấy tên của từng mục
                if isinstance(json_data, dict) and 'itemListElement' in json_data:
                    for item in json_data['itemListElement']:
                        if 'item' in item and 'name' in item['item']:
                            breadcrumb_items.append(item['item']['name'])

            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️ Lỗi khi phân tích JSON-LD của breadcrumb: {e}")
                print(traceback.format_exc())

            print(f"🔗 Breadcrumb items: {breadcrumb_items}")
            
            detail_container_left = detail_container.find("div", class_="box-detail-product__box-left")
            detail_container_center = detail_container.find("div", class_="box-detail-product__box-center")
            
            with ThreadPoolExecutor(max_workers=8) as executor:
                # Submit các task để chạy song song
                # Khởi tạo một danh sách để lưu các mục breadcrumb
                future_basic_info = executor.submit(self._extract_basic_info_cellphones, detail_container_left, url)
                future_options = executor.submit(self._extract_options_cellphones, detail_container_center, url)
                future_promotions = executor.submit(self._extract_promotions_cellphones, detail_container_center, url)
                future_payment_promotions = executor.submit(self._extract_payment_promotions_cellphones, detail_container_center, url)
                future_commitments = executor.submit(self._extract_product_commitments_cellphones, detail_container_left, url)
                future_specifications = executor.submit(self._extract_product_specifications_cellphones, detail_container_left, url)

                # Collect results
                basic_info = future_basic_info.result()
                options_info = future_options.result()
                promotions_info = future_promotions.result()
                payment_promotions_info = future_payment_promotions.result()
                commitments_info = future_commitments.result()
                specifications_info = future_specifications.result()

                # Gộp tất cả dữ liệu vào product_data
                product_data.update(basic_info)
                product_data['product_type'] = breadcrumb_items
                product_data.update(options_info)
                product_data['promotions'] = promotions_info
                product_data['payment_promotions'] = payment_promotions_info
                product_data['commitments'] = commitments_info
                product_data['specifications'] = specifications_info

            if not product_data.get('product_name'):
                print(f"⚠️ No product name found for: {url}")
                yield {
                    "url": url,
                    "product_data": product_data,
                    "crawled_at": strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                    "status": "no_name_found"
                }
                return
            
            print(f"✅ Successfully parsed: {product_data.get('product_name', 'Unknown')}")
            yield {
                "url": url,
                "product_data": product_data,
                "crawled_at": strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                "status": "success"
            }
            
        except Exception as e:
            print(f'❌ Error parsing article {response.url}: {e}')
            print(traceback.format_exc())
            yield {
                "url": response.url,
                "product_data": "",
                "crawled_at": strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                "status": f"error: {str(e)}"
            }
    
    def _extract_basic_info_cellphones(self, detail_container_left, url):
        """Trích xuất thông tin cơ bản của sản phẩm từ Cellphones"""
        try:
            product_info = {}

            # 1. Lấy tên sản phẩm
            product_name_tag = detail_container_left.select_one("div.box-product-name h1")
            if product_name_tag:
                product_info['product_name'] = product_name_tag.get_text(strip=True)

            # 2. Lấy thông tin đánh giá
            # Sửa: Dùng detail_container_left thay cho soup
            rating_box = detail_container_left.select_one("div.box-rating")
            if rating_box:
                # Lấy điểm đánh giá trung bình
                rating_score_tag = rating_box.select_one("span:not(.total-rating)")
                if rating_score_tag:
                    product_info['rating_score'] = rating_score_tag.get_text(strip=True)
                
                # Lấy tổng số lượt đánh giá
                total_rating_tag = rating_box.select_one("span.total-rating")
                if total_rating_tag:
                    # Loại bỏ dấu ngoặc
                    total_rating_text = total_rating_tag.get_text(strip=True).strip("()")
                    product_info['total_ratings'] = total_rating_text

            # 3. Lấy các nhãn chức năng ở phần dưới
            labels = []
            # Sửa: Dùng detail_container_left thay cho soup
            bottom_items = detail_container_left.select("div.box-bottom-item")
            for item in bottom_items:
                label_tag = item.select_one("span.label")
                if label_tag:
                    labels.append(label_tag.get_text(strip=True))

            # Xử lý nút "So sánh"
            # Sửa: Dùng detail_container_left thay cho soup
            compare_tag = detail_container_left.select_one("div.pdp-compare-button-box a.label")
            if compare_tag:
                labels.append(compare_tag.get_text(strip=True))
                
            product_info['actions'] = labels

            # Gán vào dictionary chính
            return product_info

        except Exception as e:
            print(f"⚠️ Error extracting header information for {url}: {e}")
            # Bạn nên trả về một dictionary rỗng thay vì gán vào biến không tồn tại
            return {}
        
    def _extract_options_cellphones(self, detail_container_center, url):
        """Trích xuất thông tin giá, phiên bản và màu sắc của sản phẩm từ Cellphones."""
        
        product_options = {}

        try:
            # 1. Lấy thông tin giá sản phẩm
            price_box = detail_container_center.select_one("div.box-product-price")
            if price_box:
                sale_price_tag = price_box.select_one("div.sale-price")
                if sale_price_tag:
                    product_options['sale_price'] = sale_price_tag.get_text(strip=True)
                
                base_price_tag = price_box.select_one("del.base-price")
                if base_price_tag:
                    product_options['base_price'] = base_price_tag.get_text(strip=True)

            # 2. Lấy thông tin các phiên bản (dung lượng)
            versions = {}
            version_box = detail_container_center.select_one("div.box-linked")
            if version_box:
                version_items = version_box.select("a.item-linked")
                for item in version_items:
                    # Kiểm tra thẻ <strong> trước khi gọi get_text
                    version_strong_tag = item.select_one("strong")
                    if version_strong_tag:
                        version_name = version_strong_tag.get_text(strip=True)
                        version_url = item.get("href")
                        is_active = "active" in item.get("class", [])
                        versions[version_name] = {
                            "url": version_url,
                            "is_active": is_active
                        }
            product_options['versions'] = versions

            # 3. Lấy thông tin các tùy chọn màu sắc
            colors = {}
            variants_box = detail_container_center.select_one("div.box-product-variants")
            if variants_box:
                variant_items = variants_box.select("li.item-variant")
                for item in variant_items:
                    # Kiểm tra thẻ <strong> và <span> trước khi gọi get_text
                    color_name_tag = item.select_one("strong.item-variant-name")
                    color_price_tag = item.select_one("span.item-variant-price")
                    
                    if color_name_tag:
                        color_name = color_name_tag.get_text(strip=True)
                        color_url = item.select_one("a").get("href")
                        is_active = "active" in item.get("class", [])
                        
                        color_price = color_price_tag.get_text(strip=True) if color_price_tag else None
                        
                        colors[color_name] = {
                            "price": color_price,
                            "url": color_url,
                            "is_active": is_active
                        }
            product_options['colors'] = colors
            
            return product_options

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất thông tin tùy chọn cho {url}: {e}")
            print(traceback.format_exc())
            return {}

    def _extract_promotions_cellphones(self, detail_container_center, url):
        """
        Trích xuất các thông tin khuyến mãi từ Cellphones.

        Args:
            detail_container_center (bs4.Tag): Thẻ BeautifulSoup chứa toàn bộ phần khuyến mãi.
            url (str): URL của trang sản phẩm.

        Returns:
            dict: Một dictionary chứa tiêu đề và danh sách các khuyến mãi.
                Trả về dictionary rỗng nếu không tìm thấy hoặc có lỗi.
        """
        promotions_data = {}

        try:
            # Lấy tiêu đề chính của phần khuyến mãi
            header_tag = detail_container_center.select_one(".box-product-promotion-header span")
            if header_tag:
                promotions_data['promotion_title'] = header_tag.get_text(strip=True)
            else:
                promotions_data['promotion_title'] = "Khuyến mãi"

            # Lấy danh sách các khuyến mãi chi tiết
            promotions_list = []
            promotion_items = detail_container_center.select(".promotion-pack_item")

            for item in promotion_items:
                promotion_detail_tag = item.select_one(".box-product-promotion-detail")
                
                if promotion_detail_tag:
                    # Lấy toàn bộ text của mục khuyến mãi
                    detail_text = promotion_detail_tag.get_text(strip=True, separator=" ")
                    
                    # Tìm đường dẫn (href) nếu có
                    link_tag = promotion_detail_tag.select_one("a")
                    link_url = link_tag['href'] if link_tag and link_tag.has_attr('href') else None

                    promotions_list.append({
                        "detail": detail_text,
                        "link": link_url
                    })

            promotions_data['promotions'] = promotions_list
            
            return promotions_data

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất thông tin khuyến mãi từ {url}: {e}")
            print(traceback.format_exc())
            return {}

    def _extract_payment_promotions_cellphones(self, detail_container_center, url):
        """
        Trích xuất các ưu đãi thanh toán từ trang sản phẩm Cellphones.

        Args:
            detail_container_center (bs4.Tag): Thẻ BeautifulSoup chứa toàn bộ phần ưu đãi.
            url (str): URL của trang sản phẩm.

        Returns:
            dict: Một dictionary chứa tiêu đề và danh sách các ưu đãi thanh toán.
                Trả về dictionary rỗng nếu không tìm thấy hoặc có lỗi.
        """
        payment_promotions_data = {}

        try:
            # Lấy tiêu đề chính của phần ưu đãi
            header_tag = detail_container_center.select_one(".box-more-promotion-title span")
            if header_tag:
                payment_promotions_data['title'] = header_tag.get_text(strip=True)
            else:
                payment_promotions_data['title'] = "Ưu đãi thanh toán"

            # Lấy danh sách các ưu đãi thanh toán chi tiết
            promotions_list = []
            # Tìm tất cả các thẻ <li> trong phần render-promotion
            promotion_items = detail_container_center.select(".render-promotion ul li")

            for item in promotion_items:
                # Lấy toàn bộ text của thẻ <li> và các thẻ con
                text = item.get_text(strip=True, separator=" ")
                
                # Tìm đường dẫn (href) nếu có
                link_tag = item.select_one("a")
                link_url = link_tag['href'] if link_tag and link_tag.has_attr('href') else None
                
                promotions_list.append({
                    "detail": text,
                    "link": link_url
                })

            payment_promotions_data['promotions'] = promotions_list
            
            return payment_promotions_data

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất ưu đãi thanh toán từ {url}: {e}")
            print(traceback.format_exc())
            return {}
    
    def _extract_product_commitments_cellphones(self, detail_container_left, url):
        """
        Trích xuất các cam kết sản phẩm từ trang sản phẩm Cellphones.

        Args:
            detail_container_left (bs4.Tag): Thẻ BeautifulSoup chứa toàn bộ phần cam kết.
            url (str): URL của trang sản phẩm.

        Returns:
            dict: Một dictionary chứa tiêu đề và danh sách các cam kết.
                Trả về dictionary rỗng nếu không tìm thấy hoặc có lỗi.
        """
        commitments_data = {}

        try:
            # Lấy tiêu đề chính của phần cam kết
            title_tag = detail_container_left.select_one(".box-warranty-info .box-title p")
            if title_tag:
                commitments_data['title'] = title_tag.get_text(strip=True)
            else:
                commitments_data['title'] = "Cam kết sản phẩm"

            # Lấy danh sách các cam kết chi tiết
            commitments_list = []
            # Tìm tất cả các thẻ div có class là item-warranty-info
            commitment_items = detail_container_left.select(".item-warranty-info")

            for item in commitment_items:
                # Lấy toàn bộ text từ thẻ div.description và các thẻ con của nó
                description_tags = item.select("div.description")
                for desc_tag in description_tags:
                    detail_text = desc_tag.get_text(strip=True, separator=" ")
                    
                    # Tìm đường dẫn (href) nếu có
                    link_tag = desc_tag.select_one("a")
                    link_url = link_tag['href'] if link_tag and link_tag.has_attr('href') else None

                    commitments_list.append({
                        "detail": detail_text,
                        "link": link_url
                    })

            commitments_data['commitments'] = commitments_list
            
            return commitments_data

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất cam kết sản phẩm từ {url}: {e}")
            print(traceback.format_exc())
            return {}
    
    def _extract_product_specifications_cellphones(self, detail_container_left, url):
        """
        Trích xuất các thông số kỹ thuật của sản phẩm từ Cellphones.

        Args:
            detail_container_left (bs4.Tag): Thẻ BeautifulSoup chứa toàn bộ phần thông số kỹ thuật.
            url (str): URL của trang sản phẩm.

        Returns:
            dict: Một dictionary chứa tiêu đề và các cặp key-value của thông số kỹ thuật.
                Trả về dictionary rỗng nếu không tìm thấy hoặc có lỗi.
        """
        specifications = {}

        try:
            # Lấy tiêu đề chính của phần thông số kỹ thuật
            title_tag = detail_container_left.select_one("#thong-so-ky-thuat .box-title h2")
            if title_tag:
                specifications['title'] = title_tag.get_text(strip=True)
            else:
                specifications['title'] = "Thông số kỹ thuật"

            # Trích xuất các thông số kỹ thuật chi tiết
            specs_list = []
            specs_table = detail_container_left.select_one("table.technical-content tbody")
            
            if specs_table:
                # Lấy tất cả các dòng thông số kỹ thuật
                spec_rows = specs_table.select("tr.technical-content-item")
                
                for row in spec_rows:
                    # Lấy key (tên thông số) từ cột đầu tiên
                    key_tag = row.select_one("td:first-child")
                    key = key_tag.get_text(strip=True) if key_tag else ""
                    
                    # Lấy value (giá trị thông số) từ cột thứ hai
                    value_tag = row.select_one("td:last-child")
                    if value_tag:
                        # Lấy toàn bộ text, đảm bảo các thẻ con như <br> và <a> được xử lý đúng
                        value_text = value_tag.get_text(strip=True, separator="\n")
                        specs_list.append({
                            "key": key,
                            "value": value_text
                        })

            specifications['items'] = specs_list
            
            return specifications

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất thông số kỹ thuật từ {url}: {e}")
            print(traceback.format_exc())
            return {}
    
    def _parse_product_info_fptshop(self, response):
        """Phương thức này sẽ được gọi để trích xuất thông tin sản phẩm từ trang chi tiết FPT Shop"""
        try:
            print(f'📄 Parsing product: {response.url}')
            url = response.request.url
            soup = BeautifulSoup(response.text, "lxml")

            # Lưu nội dung HTML vào file để kiểm tra nếu cần
            # self._save_soup_to_file(soup, "output_fptshop.html")
            # print("HTML content saved to output_fptshop.html for debugging.")
            # return

            # --- Khởi tạo các biến với giá trị mặc định ---
            product_data = {}
            
            detail_container = soup.find("div", id="ThongTinSanPham")
            if not detail_container:
                print(f"⚠️ Critical: Main 'product-detail' container not found for {url}. Aborting.")
                return

            breadcrumb_container = soup.find('nav', class_='Breadcrumb')

            breadcrumb_items = []
            if breadcrumb_container:
                # 2. Tìm tất cả các thẻ <li> bên trong container
                list_items = breadcrumb_container.find_all('li')

                for li in list_items:
                    # 3. Trong mỗi <li>, tìm thẻ <a>
                    a_tag = li.find('a')
                    
                    if a_tag:
                        # 4. Lấy toàn bộ text bên trong thẻ <a>, strip=True sẽ dọn dẹp khoảng trắng
                        # và tự động lấy text từ các thẻ con như <span>
                        text = a_tag.get_text(strip=True)
                        
                        # Đảm bảo chỉ thêm các breadcrumb có nội dung
                        if text:
                            breadcrumb_items.append(text)
            else:
                print("⚠️ Không tìm thấy container của breadcrumb ('nav' với class 'Breadcrumb').")
            
            print("breadcrumb_items", breadcrumb_items)
            
            with ThreadPoolExecutor(max_workers=8) as executor:
                # Submit các task để chạy song song
                future_basic_info = executor.submit(self._extract_basic_info_fptshop, detail_container, url)
                future_options = executor.submit(self._extract_options_fptshop, detail_container, url)
                future_price = executor.submit(self._extract_price_fptshop, detail_container, url)
                future_promotions = executor.submit(self._extract_all_promotions_fptshop, detail_container, url)
                futre_extented_warranty = executor.submit(self._extract_extended_warranty_fptshop, detail_container, url)
                future_specifications = executor.submit(self._extract_all_specs_fptshop, str(soup.prettify()), url)

                # Collect results
                basic_info = future_basic_info.result()
                options_info = future_options.result()
                price_info = future_price.result()
                promotions_info = future_promotions.result()
                extended_warranty_info = futre_extented_warranty.result()
                specifications_info = future_specifications.result()

                # Gộp tất cả dữ liệu vào product_data
                product_data.update(basic_info)
                product_data['product_type'] = breadcrumb_items
                product_data.update(options_info)
                product_data.update(price_info)
                product_data['promotions'] = promotions_info
                product_data['extended_warranty'] = extended_warranty_info
                product_data['specifications'] = specifications_info
            if not product_data.get('product_name'):
                print(f"⚠️ No product name found for: {url}")
                yield {
                    "url": url,
                    "product_data": product_data,
                    "crawled_at": strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                    "status": "no_name_found"
                }
                return
            print(f"✅ Successfully parsed: {product_data.get('product_name', 'Unknown')}")
            yield {
                "url": url,
                "product_data": product_data,
                "crawled_at": strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                "status": "success"
            }
        except Exception as e:
            print(f'❌ Error parsing article {response.url}: {e}')
            print(traceback.format_exc())
            yield {
                "url": response.url,
                "product_data": "",
                "crawled_at": strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                "status": f"error: {str(e)}"
            }
    
    def _extract_basic_info_fptshop(self, detail_container, url: str) -> dict:
        """
        Trích xuất tên sản phẩm, mã sản phẩm, điểm đánh giá và số lượng đánh giá
        từ HTML của trang FPT Shop.

        Args:
            detail_container : Đối tượng BeautifulSoup chứa toàn bộ HTML của trang.
            url (str): URL của trang sản phẩm.

        Returns:
            dict: Một dictionary chứa các thông tin chi tiết sản phẩm.
                Trả về dictionary rỗng nếu không tìm thấy thông tin hoặc có lỗi.
        """
        product_details = {
            'product_name': None,
            'rating_score': None,
            'rating_count': None
        }

        try:
            # Lấy tên sản phẩm từ thẻ <h1>
            name_tag = detail_container.select_one("h1.text-textOnWhitePrimary.b2-medium.pc\:l6-semibold")
            if isinstance(name_tag, Tag):
                product_details['product_name'] = name_tag.get_text(strip=True)

            # Lấy điểm đánh giá từ div
            rating_score_tag = detail_container.select_one("div.ml-1\.5.flex.items-center.gap-1 > div.text-textOnWhitePrimary.b2-regular")
            if isinstance(rating_score_tag, Tag):
                product_details['rating_score'] = rating_score_tag.get_text(strip=True)

            # Lấy số lượng đánh giá từ div
            rating_count_tag = detail_container.select_one("div.ml-1.cursor-pointer.text-textOnWhiteHyperLink.f1-medium.pc\:b2-medium")
            if isinstance(rating_count_tag, Tag):
                product_details['rating_count'] = rating_count_tag.get_text(strip=True)

            return product_details

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất thông tin sản phẩm từ {url}: {e}")
            print(traceback.format_exc())
            return {}
        
    def _extract_options_fptshop(self, detail_container, url: str) -> dict:
        """
        Trích xuất các tùy chọn sản phẩm như dung lượng và màu sắc từ HTML của trang FPT Shop.
        """
        product_options = {
            'storage_options': [],
            'color_options': []
        }

        try:
            # Lấy container chứa tất cả các tùy chọn (dung lượng và màu sắc)
            options_container = detail_container.select_one("div.grid.gap-y-3.pb-4.pt-3.pc\\:gap-y-2.pc\\:py-0")
            if not options_container:
                return product_options

            # Trích xuất tùy chọn dung lượng
            storage_label = options_container.find('span', string='Dung lượng')
            if storage_label:
                storage_container = storage_label.find_next_sibling('div')
                if storage_container:
                    for button in storage_container.select('button'):
                        storage_text_tag = button.select_one('span.block.text-textOnWhitePrimary.b2-medium')
                        if storage_text_tag:
                            is_selected = 'Selection_buttonSelect__7lW_h' in button.get('class', [])
                            product_options['storage_options'].append({
                                'value': storage_text_tag.get_text(strip=True),
                                'is_selected': is_selected
                            })

            # Trích xuất tùy chọn màu sắc
            color_label = options_container.find('span', string='Màu sắc')
            if color_label:
                color_container = color_label.find_next_sibling('div')
                if color_container:
                    for button in color_container.select('button'):
                        color_text_tag = button.select_one('span.block.text-textOnWhitePrimary.b2-medium')
                        color_img_tag = button.select_one('img')
                        if color_text_tag and color_img_tag:
                            is_selected = 'Selection_buttonSelect__7lW_h' in button.get('class', [])
                            product_options['color_options'].append({
                                'name': color_text_tag.get_text(strip=True),
                                'image_url': color_img_tag.get('src'),
                                'is_selected': is_selected
                            })
                            
            return product_options

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất tùy chọn sản phẩm từ {url}: {e}")
            print(traceback.format_exc())
            return {}
        
    def _extract_price_fptshop(self, detail_container, url: str) -> dict:
        """
        Trích xuất thông tin giá bán, giá gốc và điểm thưởng từ HTML.

        Args:
            detail_container (Tag): Thẻ cha chứa toàn bộ thông tin chi tiết sản phẩm.
            url (str): URL của trang sản phẩm để hỗ trợ debug.

        Returns:
            dict: Dictionary chứa giá hiện tại, giá gốc, phần trăm giảm giá, và điểm thưởng.
                Trả về dictionary rỗng nếu không tìm thấy thông tin hoặc có lỗi.
        """
        price_info = {
            'current_price': None,
            'original_price': None,
            'discount_percent': None,
            'reward_points': None,
        }
        
        try:
            price_container = detail_container.find(id='tradePrice')
            if not price_container:
                return price_info

            # Lấy giá hiện tại
            current_price_tag = price_container.select_one("span.h4-bold")
            if isinstance(current_price_tag, Tag):
                # Xử lý chuỗi giá để lấy giá trị số
                price_info['current_price'] = int(current_price_tag.get_text(strip=True).replace('₫', '').replace('.', '').strip())

            # Lấy giá gốc và phần trăm giảm giá
            original_price_tag = price_container.select_one("span.text-neutral-gray-5.line-through")
            discount_percent_tag = price_container.select_one("span.text-red-red-7")
            if isinstance(original_price_tag, Tag):
                price_info['original_price'] = int(original_price_tag.get_text(strip=True).replace('₫', '').replace('.', '').strip())
            if isinstance(discount_percent_tag, Tag):
                price_info['discount_percent'] = discount_percent_tag.get_text(strip=True)

            # Lấy điểm thưởng
            reward_points_tag = price_container.select_one("span.text-yellow-yellow-7.b2-medium")
            if isinstance(reward_points_tag, Tag):
                price_info['reward_points'] = reward_points_tag.get_text(strip=True).replace('+7.497 Điểm thưởng', '7497').strip()
                # Cần xử lý lại chuỗi điểm thưởng để lấy giá trị số nếu cần

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất giá từ {url}: {e}")
            print(traceback.format_exc())
        
        return price_info
    
    def _extract_all_promotions_fptshop(self, detail_container, url: str) -> dict:
        """
        Trích xuất toàn bộ các loại khuyến mãi (chung, thanh toán, và quà tặng) từ HTML.

        Args:
            detail_container (Tag): Thẻ cha chứa toàn bộ thông tin chi tiết sản phẩm.
            url (str): URL của trang sản phẩm để hỗ trợ debug.

        Returns:
            dict: Dictionary chứa các loại khuyến mãi đã được phân loại.
                Trả về dictionary rỗng nếu không tìm thấy hoặc có lỗi.
        """
        all_promotions = {
            'general_promotions': [],
            'payment_promotions': [],
            'other_promotions_and_gifts': []
        }
        
        try:
            # Trích xuất khuyến mãi chung (đã có từ hàm cũ)
            # promotion_container = detail_container.find('div', class_="relative flex flex-col gap-2.5 rounded-[0.375rem] border")
            promotion_container = detail_container.select_one(r'div.relative.flex.flex-col.gap-2\.5.rounded-\[0\.375rem\].border')
            if promotion_container:
                promotion_tags = promotion_container.select("p")
                all_promotions['general_promotions'] = [p_tag.get_text(strip=True) for p_tag in promotion_tags]

            
            # Trích xuất khuyến mãi thanh toán (đã có từ hàm cũ)
            promontion_and_payment_container = detail_container.select_one('div.flex.flex-col.pc\:flex-col-reverse.pc\:gap-3')
            if promontion_and_payment_container:
                # Lấy container chứa các slide khuyến mãi thanh toán
                swiper_wrapper = promontion_and_payment_container.select_one('div.swiper-wrapper')
                if isinstance(swiper_wrapper, Tag):
                    payment_promotions = []
                    for slide in swiper_wrapper.select('div.swiper-slide'):
                        img_tag = slide.select_one('img')
                        if isinstance(img_tag, Tag):
                            promotion_info = {
                                'description': img_tag.get('alt', '').strip(),
                                'image_url': img_tag.get('src', '').strip()
                            }
                            payment_promotions.append(promotion_info)
                    all_promotions['payment_promotions'] = payment_promotions


            if promontion_and_payment_container:
                promotions_list_container = promontion_and_payment_container.select_one('div.flex.flex-col.gap-3')
                if isinstance(promotions_list_container, Tag):
                    other_promotions = []
                    promotion_tags = promotions_list_container.select('p.text-textOnWhitePrimary')
                    for p_tag in promotion_tags:
                        promotion_text = p_tag.get_text(strip=True).replace("Xem chi tiết", "").strip()
                        if promotion_text:
                            other_promotions.append(promotion_text)
                    all_promotions['other_promotions_and_gifts'] = other_promotions

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất toàn bộ khuyến mãi từ {url}: {e}")
            print(traceback.format_exc())
                
        return all_promotions
    
    def _extract_extended_warranty_fptshop(self, detail_container, url: str) -> list:
        """
        Trích xuất danh sách các gói bảo hành mở rộng từ HTML.

        Args:
            detail_container (Tag): Thẻ cha chứa toàn bộ thông tin chi tiết sản phẩm.
            url (str): URL của trang sản phẩm để hỗ trợ debug.

        Returns:
            list: Danh sách các dictionary, mỗi dictionary chứa thông tin về một gói bảo hành.
                Trả về danh sách rỗng nếu không tìm thấy hoặc có lỗi.
        """
        extended_warranties = []
        
        try:
            # 1. Tìm container chính chứa toàn bộ phần "Bảo hành mở rộng"
            # container_parent = detail_container.select_one('div.flex.flex-col.overflow-hidden.bg-white.mb\:container-full.pc\:rounded-\[0\.5rem\].pc\:border.pc\:border-iconStrokeOnWhiteDefault')
            # if not container_parent:
            #     return extended_warranties

            # 2. Tìm container chứa danh sách các gói bảo hành
            warranty_list_container = detail_container.select_one('div.flex.flex-col.gap-2.px-4.pb-4.pt-3')
            if not isinstance(warranty_list_container, Tag):
                return extended_warranties
            
            # 3. Lặp qua từng gói bảo hành
            for item in warranty_list_container.select('div.relative.grid.h-14'):
                title_tag = item.select_one('p.line-clamp-2')
                current_price_tag = item.select_one('span.text-textOnWhiteBrand')
                original_price_tag = item.select_one('span.text-textOnWhiteDisable.line-through')

                warranty_info = {
                    'title': None,
                    'current_price': None,
                    'original_price': None,
                }

                if isinstance(title_tag, Tag):
                    warranty_info['title'] = title_tag.get_text(strip=True)
                
                if isinstance(current_price_tag, Tag):
                    # Xử lý chuỗi giá để lấy giá trị số
                    current_price_text = current_price_tag.get_text(strip=True).replace('₫', '').replace('.', '').strip()
                    warranty_info['current_price'] = int(current_price_text)

                if isinstance(original_price_tag, Tag):
                    # Xử lý chuỗi giá gốc
                    original_price_text = original_price_tag.get_text(strip=True).replace('₫', '').replace('.', '').strip()
                    warranty_info['original_price'] = int(original_price_text)

                extended_warranties.append(warranty_info)

        except Exception as e:
            print(f"⚠️ Lỗi khi trích xuất gói bảo hành mở rộng từ {url}: {e}")
            print(traceback.format_exc())
            
        return extended_warranties
    
    def _remove_url_keys(self, data):
        """
        Hàm đệ quy để loại bỏ các key liên quan đến URL/hình ảnh từ một dictionary hoặc list.
        """
        keys_to_remove = ['url', 'imageUrl', 'pageUrl', 'thumb', 'icon']
        
        if isinstance(data, dict):
            # Tạo danh sách các key cần xóa
            keys_to_delete = [key for key in data if key in keys_to_remove]
            for key in keys_to_delete:
                del data[key]
            
            # Gọi đệ quy cho các giá trị còn lại
            for key, value in data.items():
                self._remove_url_keys(value)
        
        elif isinstance(data, list):
            for item in data:
                self._remove_url_keys(item)
        
        return data


    def _extract_all_specs_fptshop(self, html_content: str, url: str) -> dict:
        """
        Trích xuất thông số kỹ thuật từ self.__next_f.push của FPT Shop.
        Args:
            html_content (str): HTML chứa dữ liệu JS.
            url (str): URL sản phẩm (để debug).
        Returns:
            dict: specs grouped by displayName.
        """
        product_data = {}

        # 1. Tìm block JS (lấy phần "16:...[arr,map]...")
        m = re.search(
            r'self\.__next_f\.push\(\[1,\s*"(16:.*?)"\]\)',
            html_content,
            re.DOTALL
        )
        if not m:
            print(f"⚠️ [LỖI] Không tìm thấy JS data tại {url}")
            return product_data

        # 2. Tách lấy phần raw sau "16:" và bỏ quotes bao bên ngoài
        raw = m.group(1).split(":",1)[1].strip('"').replace('\\n','').replace('\\r','')
        raw = re.sub(r'(?<!\\)"', r'\"', raw)

        raw = re.sub(r'\\(?![\\/\"bfnrtu])', r'\\\\', raw)

        # 3. Dùng json.loads để un-escape chính xác JS escapes (\\" , \\u..., v.v.)

        with open("raw.json", 'w', encoding='utf-8') as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        try:
            unescaped = json.loads(f'"{raw}"')
        except json.JSONDecodeError as e:
            print(f"⚠️ [LỖI json.loads] tại {url}: {e}")
            return product_data

        # 4. Split mảng và object map
        try:
            arr_part, map_part = unescaped.split("]", 1)
        except ValueError:
            print(f"⚠️ [LỖI] Không thể split array/map tại {url}")
            return product_data

        arr_str = arr_part + "]"
        map_str = map_part.lstrip(",")

        # 5. Build literal JS cho demjson3
        js_literal = f'{{"__root":{arr_str},{map_str}}}'

        with open("output.json", 'w', encoding='utf-8') as f:
            json.dump(js_literal, f, ensure_ascii=False, indent=2)

        # 6. Decode bằng demjson3
        try:
            obj_map = demjson3.decode(js_literal)
        except Exception as e:
            print(f"⚠️ [LỖI demjson3] tại {url}: {e}")
            return product_data

        # 7. Resolve các tham chiếu $...
        def resolve(item, seen=None):
            if seen is None:
                seen = set()
            if isinstance(item, str) and item.startswith("$"):
                key = item[1:]
                if key in seen:
                    return None
                seen.add(key)
                return resolve(obj_map.get(key), seen)
            if isinstance(item, list):
                return [resolve(i, set(seen)) for i in item]
            if isinstance(item, dict):
                return {k: resolve(v, set(seen)) for k, v in item.items()}
            return item

        root = resolve(obj_map.get("__root", []))

        # 8. Tìm tất cả attributeItem
        def find_attribute_items(o):
            if isinstance(o, dict):
                if "attributeItem" in o and isinstance(o["attributeItem"], list):
                    return o["attributeItem"]
                for v in o.values():
                    r = find_attribute_items(v)
                    if r:
                        return r
            elif isinstance(o, list):
                for i in o:
                    r = find_attribute_items(i)
                    if r:
                        return r
            return []

        items = find_attribute_items(root)

        # 9. Gom nhóm theo groupName
        for item in items:
            group = item.get("groupName", "").strip()
            info = {}
            for attr in item.get("attributes", []):
                name = attr.get("displayName", "").strip()
                val = attr.get("value")
                if name and val is not None:
                    info[name] = val
            if group:
                product_data[group] = info

        return product_data