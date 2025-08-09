from clean_phone_name import clean_phone_name, clean_phone_name_of_hoanghamobile
from rouge import Rouge
from semantic_search import FAISSVectorStore
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time
from typing import Dict
from tqdm import tqdm
import re
import unicodedata

# Lock để đồng bộ hóa việc ghi vào danh sách kết quả
results_lock = Lock()

class MultiMetricEvaluator:
    """Class để đánh giá sử dụng nhiều thước đo khác nhau"""
    def __init__(self, config: Dict):
        self.config = config
        self.rouge_scorer = Rouge() if config.get('use_rouge', False) else None
        self.vector_store = FAISSVectorStore() if config.get('use_semantic', False) else None

    def calculate_rouge_score(self, text1: str, text2: str) -> float:
        if not self.rouge_scorer:
            return 0.0
        try:
            return self.rouge_scorer.threading_calculation(text1, text2)
        except:
            return 0.0

    def calculate_semantic_score(self, text1: str, text2: str) -> float:
        if not self.vector_store:
            return 0.0
        try:
            return self.vector_store.similarity(text1, text2)
        except:
            return 0.0

    def calculate_all_scores(self, text1: str, text2: str) -> Dict[str, float]:
        """Tính tất cả các score được cấu hình, trả về dict dynamic"""

        scores = {}
        if text1 == text2:
            scores["string"] = 1.0
            return scores
        else:
            scores["string"] = 0.0
            return scores
        # scores = {}
        # if self.config.get('use_rouge', False):
        #     scores['rouge'] = self.calculate_rouge_score(text1, text2)
        # if self.config.get('use_semantic', False):
        #     scores['semantic'] = self.calculate_semantic_score(text1, text2)
        # # Combined nếu có >1
        # if len(scores) > 1:
        #     weights = self.config.get('weights', {})
        #     combined = sum(scores[key] * weights.get(key, 0) for key in scores)
        #     scores['combined'] = combined
        # return scores


def clean_title(title: str, dataset_type: str, use_clean: bool) -> str:
    if not use_clean:
        return title
    return (clean_phone_name_of_hoanghamobile(title)
            if dataset_type.lower() == 'hoanghamobile'
            else clean_phone_name(title))


def process_row_pair(idx1, row1, idx2, row2, evaluator, config) -> Dict:
    try:
        # Clean titles
        t1 = clean_title(row1['title_cleaned'], config.get('dataset1_type', ''), config.get('clean_titles', False))
        t2 = clean_title(row2['title_cleaned'], config.get('dataset2_type', ''), config.get('clean_titles', False))
        scores = evaluator.calculate_all_scores(t2, t1)
        # Main score check
        main_key = config.get('main_score', 'rouge')
        main_score = scores.get(main_key, 0.0)
        if main_score < config.get('threshold', 0.0):
            return None
        # Build result
        result = {
            "_id1": row1["_id"],
            "_id2": row2["_id"],
            'tititle_cleanedtle': row1['title_cleaned'],
            'references': row2['title'],
            'is_cleaned': config.get('clean_titles', False),
            'main_score': main_score,
            'main_score_type': main_key,
            'capacities_1': row1["capacities"],
            "capacities_2": row2["capacities"],
            'colors_1': row1["color_options"],
            'colors_2': row2["color_options"]
        }
        # Thêm cleaned titles nếu có
        if config.get('clean_titles', False):
            result['title_cleaned'] = t1
            result['references_cleaned'] = t2
        else:
            result['title_cleaned'] = t1
            result['references_cleaned'] = t2
        # Thêm từng score riêng biệt như các cột riêng
        for key, val in scores.items():
            result[f"{key}_score"] = val
        return result
    except Exception as e:
        print(f"Error processing ({idx1},{idx2}): {e}")
        return None


def create_chunks(df1, df2, size: int = 1000):
    chunks, cur = [], []
    for i, r1 in df1.iterrows():
        for j, r2 in df2.iterrows():
            cur.append((i, r1, j, r2))
            
            if len(cur) >= size:
                chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    return chunks


def process_chunk(chunk, evaluator, config):
    local = []
    for args in chunk:
        res = process_row_pair(*args, evaluator, config)
        if res:
            local.append(res)
    return local


def normalize_title(s):
    # 2.1 bắt buộc str
    s = str(s)
    # 2.2 Unicode normalize
    s = unicodedata.normalize('NFKC', s)
    # 2.3 lower + strip + gộp khoảng trắng
    s = s.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def main():
    config = {
        'use_rouge': True,
        'use_semantic': False,
        'weights': {'rouge': 0.7, 'semantic': 0.3},
        'main_score': 'string',
        'threshold': 0.8,
        'clean_titles': False,
        'dataset1_type': 'hoanghamobile',
        'dataset2_type': 'other',
        'chunk_size': 1000,
        'max_workers': 8
    }

    print("Đang đọc dữ liệu...")
    df1 = pd.read_csv('hoanghamobile_merged.csv')
    df2 = pd.read_csv('fptshop_cleaned.csv')

    # Xóa các dòng trùng hệt cột 'title'
    df1['title'] = df1['title'].str.strip()              # loại whitespace thừa
    df1 = df1.drop_duplicates(subset='title', keep='first')

    df2['title'] = df2['title'].str.strip()
    df2 = df2.drop_duplicates(subset='title', keep='first')

    print(f"Size df1={len(df1)}, df2={len(df2)}")

    evaluator = MultiMetricEvaluator(config)
    chunks = create_chunks(df1, df2, config['chunk_size'])
    total_chunks = len(chunks)
    print(f"Tổng số chunks: {total_chunks}")

    all_results = []
    start_time = time.time()

    # Thread pool với tiến trình hiển thị
    with ThreadPoolExecutor(max_workers=min(config['max_workers'], total_chunks)) as executor:
        futures = {executor.submit(process_chunk, chunk, evaluator, config): idx for idx, chunk in enumerate(chunks)}
        with tqdm(total=total_chunks, desc="Processing chunks") as pbar:
            for future in as_completed(futures):
                res = future.result()
                all_results.extend(res if res else [])
                pbar.update(1)

    elapsed = time.time() - start_time
    print(f"Hoàn thành {total_chunks} chunks trong {elapsed:.1f}s, thu được {len(all_results)} kết quả.")

    if not all_results:
        print("Không có kết quả phù hợp.")
        return

    df_res = pd.DataFrame(all_results)

    df_res['title_clean'] = df_res['title'].apply(normalize_title)
    df_res = df_res.drop_duplicates(subset='title_clean', keep='first')
    df_res = df_res.drop(columns=['title_clean'])


    metrics = [m for m in ['rouge','semantic','combined', 'string'] if m+'_score' in df_res.columns]
    suffix = '_cleaned' if config['clean_titles'] else ''
    fname = f"filter_duplicate_name_{'_'.join(metrics)}{suffix}_hoanghamobile_fptshop.csv"
    df_res.to_csv(fname, index=False)
    print(f"Đã lưu kết quả vào {fname}")

if __name__ == '__main__':
    main()
