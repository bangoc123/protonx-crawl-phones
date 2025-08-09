import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer
import json
import pandas as pd

class FAISSVectorStore:
    def __init__(self, model_name='BAAI/bge-m3'):
        """
        Khởi tạo FAISS vector store
        Args:
            model_name: Tên model embedding (ví dụ: BAAI/bge-m3)
        """
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        self.index = None
        self.texts = []
        self.metadata = []
        
    def create_index(self, index_type='flat'):
        """
        Tạo FAISS index
        Args:
            index_type: Loại index ('flat', 'ivf', 'hnsw')
        """
        if index_type == 'flat':
            # Index phẳng - chính xác nhất nhưng chậm với dữ liệu lớn
            self.index = faiss.IndexFlatIP(self.dimension)  # Inner Product
            # Hoặc dùng: faiss.IndexFlatL2(self.dimension) cho L2 distance
            
        elif index_type == 'ivf':
            # IVF index - nhanh hơn với dữ liệu lớn
            nlist = 100  # số cluster
            quantizer = faiss.IndexFlatIP(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist)
            
        elif index_type == 'hnsw':
            # HNSW index - rất nhanh cho similarity search
            M = 16  # số connection
            self.index = faiss.IndexHNSWFlat(self.dimension, M)
            
    def add_texts(self, texts, metadata_list=None):
        """
        Thêm texts vào index
        Args:
            texts: List các text cần embed
            metadata_list: List metadata tương ứng (optional)
        """
        if not texts:
            return
            
        # Tạo embeddings
        print(f"Đang tạo embeddings cho {len(texts)} texts...")
        embeddings = self.model.encode(texts, convert_to_tensor=False, show_progress_bar=True)
        embeddings = np.array(embeddings, dtype=np.float32)
        
        # Normalize embeddings cho cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Train index nếu cần (cho IVF)
        if hasattr(self.index, 'is_trained') and not self.index.is_trained:
            print("Đang train index...")
            self.index.train(embeddings)
            
        # Thêm vào index
        self.index.add(embeddings)
        
        # Lưu texts và metadata
        self.texts.extend(texts)
        if metadata_list:
            self.metadata.extend(metadata_list)
        else:
            self.metadata.extend([{}] * len(texts))
            
        print(f"Đã thêm {len(texts)} vectors. Total: {self.index.ntotal}")
    
    def search(self, query, k=5):
        """
        Tìm kiếm similar texts
        Args:
            query: Text query
            k: Số kết quả trả về
        Returns:
            List tuple (text, score, metadata)
        """
        if self.index.ntotal == 0:
            return []
            
        # Embed query
        query_embedding = self.model.encode([query], convert_to_tensor=False)
        query_embedding = np.array(query_embedding, dtype=np.float32)
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding, k)
        
        # Trả về kết quả
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1:  # -1 means no result found
                results.append({
                    'text': self.texts[idx],
                    'score': float(score),
                    'metadata': self.metadata[idx],
                    'index': int(idx)
                })
        
        return results
    
    def save_index(self, index_path="faiss_vector_store.index", metadata_path=None):
        """
        Lưu index và metadata
        Args:
            index_path: Đường dẫn lưu FAISS index
            metadata_path: Đường dẫn lưu metadata (optional)
        """
        # Lưu FAISS index
        faiss.write_index(self.index, index_path)
        
        # Lưu texts và metadata
        if not metadata_path:
            metadata_path = index_path.replace('.index', '_metadata.pkl')
            
        with open(metadata_path, 'wb') as f:
            pickle.dump({
                'texts': self.texts,
                'metadata': self.metadata,
                'dimension': self.dimension,
                'model_name': self.model_name  # Lưu tên model
            }, f)
        
        print(f"Đã lưu index tại: {index_path}")
        print(f"Đã lưu metadata tại: {metadata_path}")
        print(f"Model used: {self.model_name}, Dimension: {self.dimension}")
    
    def load_index(self, index_path, metadata_path=None):
        """
        Load index và metadata
        Args:
            index_path: Đường dẫn FAISS index
            metadata_path: Đường dẫn metadata
        """
        # Load metadata trước để check dimension
        if not metadata_path:
            metadata_path = index_path.replace('.index', '_metadata.pkl')
            
        with open(metadata_path, 'rb') as f:
            data = pickle.load(f)
            self.texts = data['texts']
            self.metadata = data['metadata']
            saved_dimension = data['dimension']
            saved_model_name = data.get('model_name', 'unknown')
        
        # Check model compatibility
        if saved_model_name != 'unknown' and saved_model_name != self.model_name:
            print(f"Warning: Current model ({self.model_name}) khác với saved model ({saved_model_name})")
            print("Để đảm bảo chất lượng search, nên sử dụng cùng model.")
        
        # Check dimension compatibility
        if self.dimension != saved_dimension:
            print(f"Error: Model dimension ({self.dimension}) khác với saved dimension ({saved_dimension})")
            print(f"Hãy sử dụng model có dimension {saved_dimension} hoặc tạo lại index.")
            # Recreate model with saved dimension info if possible
            raise ValueError(f"Dimension mismatch: expected {saved_dimension}, got {self.dimension}")
        
        # Load FAISS index
        self.index = faiss.read_index(index_path)
        
        print(f"Đã load {len(self.texts)} texts từ {index_path}")
        print(f"Model: {saved_model_name}, Dimension: {saved_dimension}")

# # Ví dụ sử dụng
def main():
    # Khởi tạo vector store
    store = FAISSVectorStore(model_name='BAAI/bge-m3')
    
    # Tạo index
    store.create_index(index_type='flat')  # hoặc 'ivf', 'hnsw'
    
    # # Dữ liệu mẫu
    # sample_texts = [
    #     "Python là một ngôn ngữ lập trình phổ biến",
    #     "Machine learning giúp máy tính học từ dữ liệu",
    #     "FAISS là thư viện tìm kiếm vector hiệu quả",
    #     "Deep learning là một phần của machine learning",
    #     "Embedding vector giúp biểu diễn text dưới dạng số"
    # ]
    
    # sample_metadata = [
    #     {"category": "programming", "topic": "python"},
    #     {"category": "AI", "topic": "machine_learning"},
    #     {"category": "tools", "topic": "vector_search"},
    #     {"category": "AI", "topic": "deep_learning"},
    #     {"category": "NLP", "topic": "embeddings"}
    # ]
    
    
    # # Thêm texts vào index
    # store.add_texts(sample_texts, sample_metadata)

    df = pd.read_csv("hoanghamobile-question-answer-cleaned")

    texts = df["title"].tolist()
    metadatas = df.drop(columns=["title"]).to_dict(orient="records")

    store.add_texts(texts, metadatas)
    
    # Tìm kiếm
    # query = "học máy và AI"
    # results = store.search(query, k=3)
    
    # print(f"\nKết quả tìm kiếm cho: '{query}'")
    # print("-" * 50)
    # for i, result in enumerate(results):
    #     print(f"{i+1}. Score: {result['score']:.4f}")
    #     print(f"   Text: {result['text']}")
    #     print(f"   Metadata: {result['metadata']}")
    #     print()
    
    # Lưu index
    store.save_index('hoanghamobile_store.index')
    
    # # Load lại index (ví dụ) - SỬ DỤNG CÙNG MODEL NAME
    # new_store = FAISSVectorStore(model_name='BAAI/bge-m3')  # Phải cùng model
    # new_store.load_index('my_vector_store.index')
    
    # # Test search với store đã load
    # results2 = new_store.search(query, k=2)
    # print(f"Kết quả sau khi load lại index:")
    # for result in results2:
    #     print(f"- {result['text']} (Score: {result['score']:.4f})")

# # Ví dụ với dữ liệu từ file
# def load_from_file_example():
#     """Ví dụ load dữ liệu từ file JSON"""
    
#     # Tạo file dữ liệu mẫu
#     sample_data = [
#         {
#             "text": "Artificial Intelligence đang thay đổi thế giới",
#             "metadata": {"source": "article1.txt", "date": "2024-01-01"}
#         },
#         {
#             "text": "Neural networks là nền tảng của deep learning",
#             "metadata": {"source": "article2.txt", "date": "2024-01-02"}
#         },
#         {
#             "text": "Natural Language Processing giúp máy hiểu ngôn ngữ",
#             "metadata": {"source": "article3.txt", "date": "2024-01-03"}
#         }
#     ]
    
#     # Lưu dữ liệu mẫu
#     with open('sample_data.json', 'w', encoding='utf-8') as f:
#         json.dump(sample_data, f, ensure_ascii=False, indent=2)
    
#     # Load và index dữ liệu
#     with open('sample_data.json', 'r', encoding='utf-8') as f:
#         data = json.load(f)
    
#     store = FAISSVectorStore()
#     store.create_index('flat')
    
#     texts = [item['text'] for item in data]
#     metadata = [item['metadata'] for item in data]
    
#     store.add_texts(texts, metadata)
#     store.save_index('document_store.index')
    
#     print("Đã tạo document store từ file JSON!")

if __name__ == "__main__":
    main()
    # load_from_file_example()