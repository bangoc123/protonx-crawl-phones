import re
import unicodedata
import pandas as pd

# Danh sách màu phổ biến (mở rộng thêm)
COLORS = [
    'đen', 'trắng', 'bạc', 'xanh', 'hồng', 'đỏ', 'vàng', 'cam', 'tím', 'nâu', 'xám',
    'black', 'white', 'blue', 'red', 'gold', 'silver', 'green', 'yellow', 'purple', 
    'pink', 'gray', 'grey', 'orange', 'brown',
    # Màu có tính từ bổ nghĩa - sắp xếp từ dài đến ngắn để tránh match sai
    'đen huyền bí', 'vàng hoàng kim', 'xanh dương', 'đỏ hoàng hôn', 'tím sương đêm',
    'xanh bạc', 'vàng hồng', 'midnight đen', 'glaring vàng', 'diamond đen',
    'sunset đỏ', 'neon purple', 'midnightblue', 'skyblue'
]

def clean_phone_name(raw_name: str) -> str:
    # 0. Chuyển về str và chuẩn hoá Unicode và chữ thường, cắt khoảng trắng
    raw_name = str(raw_name).lower().strip()
    name = unicodedata.normalize('NFKC', raw_name)
    
    # 1. Loại bỏ tiền tố "điện thoại" và "đtdđ" ở đầu
    name = re.sub(r'^(?:điện thoại|đtdđ)\s+', '', name)
    
    # 2. Loại bỏ chú thích "- Chỉ có tại..." hoặc "| Chính hãng..." 
    name = re.split(r'\s+-\s+chỉ có tại', name)[0]
    name = re.split(r'\s+\|\s+chính hãng', name)[0]
    
    # 3. Chuẩn hóa 'plus' thành '+' 
    name = re.sub(r'(?i)\bplus\b', '+', name)
    
    # 4. Xóa các text marketing không cần thiết
    name = re.sub(r'\s+bản đặc biệt$', '', name)
    # Chỉ xóa "flex your way" khi không có năm theo sau
    if not re.search(r'flex your way\s+\d{4}', name):
        name = re.sub(r'\s+flex your way.*$', '', name)
    
    # 5. Xoá RAM/ROM/Storage với nhiều định dạng khác nhau
    # Xử lý từng pattern cụ thể để tránh xóa nhầm
    name = re.sub(r'\b\d+gb\s*\([^)]+\)\s*\d+gb\b', '', name, flags=re.IGNORECASE)  # 12GB (4+8GB) 256GB
    name = re.sub(r'\b\d+gb\s*[-/+]\s*\d+gb\b', '', name, flags=re.IGNORECASE)      # 8GB-256GB, 8GB/256GB, 8GB+256GB  
    name = re.sub(r'\b\d+\s*/\s*\d+gb\b', '', name, flags=re.IGNORECASE)             # 6/128GB
    name = re.sub(r'\(\s*\d+gb\s*-\s*\d+gb\s*\)', '', name, flags=re.IGNORECASE)    # (8GB - 128GB)
    name = re.sub(r'\(\s*\d+gb\s+\d+gb\s*\)', '', name, flags=re.IGNORECASE)        # (12GB 512GB)
    name = re.sub(r'\b\d+gb\b', '', name, flags=re.IGNORECASE)                       # 64GB
    name = re.sub(r'\b\d+tb\b', '', name, flags=re.IGNORECASE)                       # 1TB
    
    # 6. Xóa thông tin kỹ thuật khác
    name = re.sub(r'\d+\.\d+ghz', '', name, flags=re.IGNORECASE)                     # 1.2Ghz
    name = re.sub(r'\/\d+gb', '', name, flags=re.IGNORECASE)                         # /2GB, /16GB
    name = re.sub(r'\s+dual(?:\s|$)', ' ', name, flags=re.IGNORECASE)                # Dual
    
    # 7. Loại bỏ màu sắc - xử lý từ dài đến ngắn để tránh xóa nhầm
    sorted_colors = sorted(COLORS, key=len, reverse=True)
    
    # Xóa màu trong ngoặc trước - ví dụ: (Black), (Glaring Vàng)
    for color in sorted_colors:
        pattern = r'\s*\([^)]*' + re.escape(color) + r'[^)]*\)'
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # Xóa màu ở cuối chuỗi
    for color in sorted_colors:
        pattern = r'\s+' + re.escape(color) + r'(?:\s|$)'
        name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)
    
    # Xóa màu ở bất kỳ vị trí nào (không chỉ cuối)
    for color in sorted_colors:
        pattern = r'\b' + re.escape(color) + r'\b'
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # 8. Xử lý trường hợp màu có dấu "-" như "256GB-Bạc"
    for color in sorted_colors:
        pattern = r'-\s*' + re.escape(color) + r'(?:\s|$)'
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # 9. Xử lý dấu '+' - tách riêng khỏi chữ khi cần thiết
    # Trường hợp "20PRO+" -> "20pro +"
    name = re.sub(r'(?<=pro)\+(?=\s|$)', ' +', name, flags=re.IGNORECASE)
    # Trường hợp "S10 Plus" -> "S10 +"
    name = re.sub(r'\bs10\s+\+', 's10 +', name, flags=re.IGNORECASE)
    
    # 10. Xử lý trường hợp "5G" trong ngoặc
    name = re.sub(r'\(\s*5g\s*\)', ' 5g', name, flags=re.IGNORECASE)
    
    # 11. Loại bỏ dấu gạch dưới thừa và ký tự đặc biệt
    name = re.sub(r'_+', ' ', name)  # Thay _ thành khoảng trắng
    name = re.sub(r'/+', ' ', name)  # Thay / thành khoảng trắng
    
    # 12. Xóa màu sắc còn sót lại (lần 2) - sau khi đã xử lý ký tự đặc biệt
    for color in sorted_colors:
        pattern = r'\b' + re.escape(color) + r'\b'
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    name = re.sub(r'\(\s*([a-zA-Z0-9]+)\s*\)', r' \1', name)

    name = re.sub(r'\s*-\s*$', '', name)
	
    # 13. Loại bỏ ngoặc đơn trống hoặc chỉ có khoảng trắng
    name = re.sub(r'\(\s*\)', '', name)
    name = re.sub(r'\(\s+\)', '', name)
    name = re.sub(r'\s+', ' ', name)
    
    return name.strip()



def clean_phone_name_of_hoanghamobile(title):
	# Chuyển về chữ thường
	title = title.lower().strip()
	
	title = unicodedata.normalize('NFKC', str(title))
	
	# Loại bỏ các từ khóa đầu và cuối
	title = re.sub(r'^điện\s+thoại\s*', '', title)
	title = re.sub(r'\s*-?\s*chính\s+hãng.*$', '', title)
	title = re.sub(r'\s*-?\s*\(bhđt\).*$', '', title)
	title = re.sub(r'\s*-?\s*dgw.*$', '', title)
	title = re.sub(r'\s*-?\s*vn/a.*$', '', title)
	
	# Loại bỏ TẤT CẢ các thông tin về dung lượng, RAM, storage
	# Pattern 1: (12+12gb/256gb) hoặc (8+8gb/256gb)
	title = re.sub(r'\s*-?\s*\(\d+\+?\d*gb[/+]\d+gb\)', '', title)
	
	# Pattern 2: 12GB (4-8GB) 256GB
	title = re.sub(r'\s*-?\s*\d+gb\s*\(\d+-\d+gb\)\s*\d+gb', '', title)
	
	# Pattern 3: 12GB 4-8GB 256GB
	title = re.sub(r'\s*-?\s*\d+gb\s+\d+-\d+gb\s+\d+gb', '', title)
	
	# Pattern 4: 8gb+12gb/256gb
	title = re.sub(r'\s*-?\s*\d+gb\+\d+gb/\d+gb', '', title)
	
	# Pattern 5: (8gb/256gb) hoặc 8gb/256gb
	title = re.sub(r'\s*-?\s*\(?\d+gb/\d+gb\)?', '', title)
	
	# Pattern 6: 4/64gb, 6/128gb (pattern đặc biệt)
	title = re.sub(r'\s*-?\s*\d+/\d+gb', '', title)
	
	# Pattern 7: (512gb), (256gb) - chỉ dung lượng
	title = re.sub(r'\s*-?\s*\(\d+gb\)', '', title)
	
	# Pattern 8: 8gb, 256gb - số đơn lẻ với gb
	title = re.sub(r'\s*-?\s*\d+gb\b', '', title)
	
	# Pattern 9: 12gb/1tb
	title = re.sub(r'\s*-?\s*\d+gb/\d+tb', '', title)
	
	# Loại bỏ TOÀN BỘ các thông tin kỹ thuật khác
	title = re.sub(r'\s*-?\s*\d+\s*sim', '', title)  # 2 sim
	title = re.sub(r'\s*,\s*\d+\s*sim', '', title)  # , 2 sim
	title = re.sub(r'\s*-?\s*pin\s+\d+\s*mah', '', title)  # pin 5000mah
	title = re.sub(r'\s*-?\s*sạc\s+nhanh\s+\d+w', '', title)  # sạc nhanh 18w
	title = re.sub(r'\s*-?\s*màn\s+hình\s+\d+\s*hz', '', title)  # màn hình 90hz
	title = re.sub(r'\s*-?\s*snapdragon\s+\d+g?', '', title)  # snapdragon 720g
	title = re.sub(r'\s*-?\s*\(máy\s+người\s+già\)', '', title)
	title = re.sub(r'\s*-?\s*cruze\s+lite', '', title)
	title = re.sub(r'\s*-?\s*white\s+pearl', '', title)
	title = re.sub(r'\s*-?\s*di\s+dộng', '', title)  # di dộng
	title = re.sub(r'\s*-?\s*di\s+động', '', title)  # di dộng
	title = re.sub(r'\s*-?\s*\d+\s*tb', '', title)  # 1tb, 512tb

	title = title.replace('apple', '')
	
	# Xử lý riêng các pattern 4G/5G - CHỈ xóa nếu không phải part của tên
	# Chỉ xóa khi có dấu gạch ngang hoặc dấu phẩy trước: "- 4g", "- 5g", ", 4g"
	title = re.sub(r'\s*-\s*[45]g\b', '', title)  # - 4g, - 5g
	title = re.sub(r'\s*,\s*[45]g\b', '', title)  # , 4g, , 5g
	title = re.sub(r'\s*-?\s*\([45]g\)', '', title)  # (5g)
	
	# XỬ LÝ ĐẶC BIỆT: "ai - samsung galaxy s24 ultra" → bỏ phần "ai -"
	title = re.sub(r'^ai\s*-\s*', '', title)
	
	# CHỈ loại bỏ số >= 128 ở cuối (các dung lượng phổ biến)
	# KHÔNG xóa số trong tên sản phẩm như "redmi 12", "iphone 15", "nokia 3210", "tcl 305"
	title = re.sub(r'\s*-?\s*(128|256|512|1024)\s*$', '', title)  # dung lượng phổ biến ở cuối
	
	# Loại bỏ dấu gạch ngang và dấu phẩy thừa
	title = re.sub(r'^-+\s*', '', title)  # đầu
	title = re.sub(r'\s*-+\s*$', '', title)  # cuối
	title = re.sub(r'\s*,+\s*$', '', title)  # dấu phẩy cuối
	title = re.sub(r'^,+\s*', '', title)  # dấu phẩy đầu
	
	# Loại bỏ dấu "/" thừa ở cuối
	title = re.sub(r'/+\s*$', '', title)
	
	# Loại bỏ "điện thoại" còn sót lại
	title = re.sub(r'điện\s+thoại\s*', '', title)
	
	# Xử lý dấu gạch ngang - ưu tiên phần có thương hiệu
	if '-' in title:
		parts = [p.strip() for p in title.split('-') if p.strip()]
		if parts:
			# Danh sách thương hiệu phổ biến
			brands = ['samsung', 'xiaomi', 'oppo', 'vivo', 'realme', 
					 'nokia', 'iphone', 'galaxy', 'poco', 'tecno', 'nubia', 
					 'oscal', 'redmi', 'itel', 'nothing', 'vivo', 'nokia', 'vsmart', 'masstel', 'asus', 'tcl']
			
			# Tìm phần có chứa tên thương hiệu
			brand_part = None
			for part in parts:
				if any(brand in part.lower() for brand in brands):
					brand_part = part
					break
			
			# Nếu có phần chứa thương hiệu, dùng nó. Không thì lấy phần dài nhất
			if brand_part:
				title = brand_part
			else:
				title = max(parts, key=len) if parts else ""

	title = re.sub(r'(?i)plus', '+', title)
	
	# Tách '+' nếu dính liền chữ (ví dụ 'Pro+5G' -> 'Pro + 5G')
	title = re.sub(r'(?<=\w)\+(?=\w)', ' + ', title)
	title = re.sub(r'(?<=\w)\s*\+', ' +', title)
	title = re.sub(r'\+\s*(?=\w)', '+ ', title)

	# Làm sạch cuối cùng
	title = re.sub(r'\(([^)]*)\)', r'\1', title)

	title = re.sub(r'\s+', ' ', title).strip()
	
	return title




if __name__ == '__main__':
	test_case = [
		"Inoi A54 12GB (4+8GB) 256GB",
		"OPPO Reno11 F 5G 8GB-256GB",
		"realme Note 70 4GB/64GB",
		"Xiaomi Redmi Note 14 Pro+ 5G 12GB/512GB",
		"Xiaomi 15 Ultra 5G 16GB/512GB Trắng",
		"HONOR X6b 6GB/128GB Tím",
		"OPPO Find X8 5G 16GB/512GB Hồng",
		'Xiaomi POCO X6 Pro 5G 8GB 256GB - Chỉ có tại CellphoneS', 
		'iPhone 16e 256GB | Chính hãng VN/A', 
		'Xiaomi Redmi Note 13 Pro Plus 5G 8GB 256GB',
		'Điện thoại Nubia Z70 Ultra 5G 16GB 512GB bản đặc biệt', 
		'TECNO SPARK 20PRO+ 8GB 256GB', 
		'TECNO SPARK 30 5G 6GB 128GB', 
		'Nokia 110 4G Pro', 
		'Xiaomi 11T', 
		'Điện thoại OPPO A55 (4GB - 64GB)', 
		'Samsung Galaxy A73 (5G) 256GB - Chỉ có tại CellphoneS', 
		'Itel 9211 4G', 
		'realme C75X 8GB-128GB', 
		'realme C75X 8GB+128GB',
		'Samsung Galaxy S22 (8GB - 128GB)',
		'Samsung A26 5G 8GB - 256GB', 
		'OPPO Reno12 5G (12GB 512GB)', 
		'Galaxy Z Flip3 5G Flex Your Way 2022', 
		'Samsung Galaxy Z Flip 5 8GB 512GB', 
		'Xiaomi Redmi A2+', 
		'Vivo X60t Pro Plus', 
		'Huawei Mate Xs 2', 
		'Samsung Galaxy A34 8GB 256GB-Bạc', 
		'Nokia 8.4',
		'iPhone 16 Pro Max 256GB',
		####
		'Samsung Galaxy S21 FE 5G 6/128GB', # samsung galaxy s21 fe 5g 6/
		'Điện thoại Huawei Y6 Prime (2018) Đen (Black)', # huawei y6 prime đen
		'Điện thoại Vsmart Live 4GB-64GB Đen huyền bí (Midnight Đen)', # vsmart live đen huyền bí
		'Điện thoại Oppo A7 64GB Vàng Hoàng Kim (Glaring Vàng) - CPH1905', # oppo a7 vàng hoàng kim
		'Điện thoại Honor 10 Xanh (Blue) - COL-L29', # honor 10 xanh
		'Điện thoại Samsung J2 Pro Xanh Dương', # samsung j2 pro xanh dương
		'Điện thoại Oppo Reno Xanh (Green) - CPH1917', # oppo reno xanh
		'Điện thoại Honor 7S Vàng (Gold) -DUA-L22', # honor 7s vàng -dua-l22
		'Điện thoại Oppo F7 Đen (Diamond Đen) - CPH1819', # oppo f7 đen
		'ĐTDĐ Mobiistar B248 White Blue', # đtdđ mobiistar b248 white blue
		'Samsung Galaxy J2 Gold', # samsung galaxy j2 gold
		'Điện thoại Xiaomi Mi A2 Lite 4GB-64GB Vàng (Gold)', # xiaomi mi a2 lite vàng
		'Điện thoại Samsung Galaxy A5 2016 Vàng Hồng', # samsung galaxy a5 2016 vàng
		'samsung galaxy core prime gray', # samsung galaxy core prime gray
		'Nokia 5310 (2020)', # nokia 5310
		'Điện thoại Vivo 1820-Y91C Đỏ Hoàng Hôn (Sunset Đỏ)', # vivo 1820-y91c đỏ hoàng hôn
		'Samsung Galaxy S21 FE 5G 8/128GB', # samsung galaxy s21 fe 5g 8/
		'Điện thoại Oppo R17 Pro Tím Sương Đêm (Neon Purple) - CPH1877', # oppo r17 pro tím sương đêm
		'Điện thoại Huawei P20 Pro Xanh (MidnightBlue)_CLT-L29', # huawei p20 pro xanh _clt-l29
		'Điện thoại Samsung A6 Plus (2018) Xanh Dương', # samsung a6 + xanh dương
		'Điện thoại Honor 10 Lite 64GB Xanh Bạc (SkyBlue)_HRY-LX1MEB', # honor 10 lite xanh bạc _hry-lx1meb
		'Asus Z010D Zenfone Max Black1.2Ghz/2GB/16GB_ZC550KL-6A019WW', # asus z010d zenfone max black1.2ghz//16gb_zc550kl-6a019ww\
		'Sony Xperia C4 Dual (E5333)', # sony xperia c4 dual
		'Samsung S10 Plus 1TB', # samsung s10 + 1tb
		'Mobiistar  Lai Zumbo J( 2017)', # mobiistar lai zumbo j
	]

	# Wiko U pulse

	# print("Test kết quả:")
	# print("-" * 50)
	# for test_case in test_case:
	# 	result = clean_phone_name(test_case)
	# 	print(f"Input:  {test_case}")
	# 	print(f"Output: {result}")
	# 	print("-" * 50)

	df = pd.read_csv("phone_of_fptshop.csv")
	df["title_cleaned"] = df["title"].apply(clean_phone_name)
	df.to_csv("fptshop_cleaned.csv")