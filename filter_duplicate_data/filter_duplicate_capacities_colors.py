import pandas as pd
import numpy as np
import ast

# Đọc dữ liệu
# Giả sử CSV có cột capacities_1 và colors_1 dưới dạng chuỗi list

df = pd.read_csv("results_string_hoanghamobile_fptshop.csv")

# 1. Parse list columns cho capacities_1 và colors_1

def parse_list_column(x):
    if pd.isna(x):
        return []
    try:
        v = ast.literal_eval(x)
        return v if isinstance(v, list) else []
    except:
        return []

# capacities_1_list: list các dung lượng
# colors_1_list: list các chuỗi màu tương ứng (mỗi chuỗi có thể chứa nhiều màu phân tách bởi ",")
df['capacities_1_list'] = df['capacities_1'].apply(parse_list_column)
df['colors_1_list']     = df['colors_1'].apply(parse_list_column)

# 2. Normalize capacities_2_list

df['capacities_2_list'] = (
    df['capacities_2']
      .fillna('')
      .str.replace(r'\s+', '', regex=True)
      .str.split(',')
      .apply(lambda lst: [c for c in lst if c])
)

# 3. Parse colors_2_list thành list thuần các màu

def normalize_color_list(x):
    if isinstance(x, str):
        return [p.strip().replace('Màu ', '') for p in x.split(',') if p.strip()]
    else:
        return []

df['colors_2_list'] = df['colors_2'].apply(normalize_color_list)

# 4. So sánh row-by-row, cặp theo index giữa capacities_1_list và colors_1_list

rows = []
for _, r in df.iterrows():
    caps1 = r['capacities_1_list']       # ví dụ ['256GB','128GB']
    cols1 = r['colors_1_list']           # ví dụ ['Màu Đen, Xanh Dương, Màu Vàng', 'Xanh Dương, Màu Vàng, Màu Đen']
    caps2 = r['capacities_2_list']       # ví dụ ['128GB']
    cols2 = r['colors_2_list']           # ví dụ ['Xanh', 'Đen', 'Bạc']

    for idx, cap in enumerate(caps1):
        # lấy chuỗi màu tương ứng cùng index, parse thành list
        raw = cols1[idx] if idx < len(cols1) else ''
        # tách colors1_for_cap
        if isinstance(raw, str):
            colors1_for_cap = [p.strip().replace('Màu ', '') for p in raw.split(',') if p.strip()]
        else:
            colors1_for_cap = []

        # chỉ xét nếu cap có ở bên 2
        if cap in caps2:
            common = list(set(colors1_for_cap) & set(cols2))
            rows.append({
                '_id1': r['_id1'],
                '_id2': r["_id2"],
                'title_cleaned': r['title_cleaned'],
                'references_cleaned': r['references_cleaned'],
                'capacity': cap,
                'colors1_for_cap': colors1_for_cap,
                'colors2_for_row': cols2,
                'common_colors': common,
                'num_common_colors': len(common)
            })

# 5. Kết quả DataFrame
result = pd.DataFrame(rows)
print(result)

result.to_csv("filter_duplicate.csv")
