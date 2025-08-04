# pipelines.py - Optimized for multi-threading
import traceback
import pymongo
import json
from itemadapter import ItemAdapter
import os
from decouple import config
import threading
from queue import Queue
import time
from datetime import datetime
import logging

class OptimizedMongoDBPipeline(object):
    """
    MongoDB Pipeline tối ưu với connection pooling và batch processing
    """
    
    def __init__(self):
        self.url = config('url')
        # self.db_name = "thegioididong"
        # self.db_name = "cellphones"  # Sử dụng database cellphones
        self.db_name = "fptshop"  # Sử dụng database fptshop
        self.collection_name = "details_raw"  # Sử dụng collection details_raw
        
        # Connection pooling settings
        self.max_pool_size = 50  # Tăng pool size
        self.min_pool_size = 10
        self.max_idle_time_ms = 30000
        self.server_selection_timeout_ms = 5000
        self.connect_timeout_ms = 5000
        
        # Batch processing settings
        self.batch_size = 100  # Process 100 items at once
        self.batch_timeout = 5  # Max 5 seconds to wait for batch
        
        # Thread-safe queues and locks
        self.item_queue = Queue()
        self.processing_thread = None
        self.stop_event = threading.Event()
        self.stats_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'processed': 0,
            'inserted': 0,
            'duplicates': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
        
        # Initialize connection
        self.client = None
        self.db = None
        self.collection = None
        
    def open_spider(self, spider):
        """Khởi tạo kết nối khi spider bắt đầu"""
        try:
            # Tạo MongoDB client với connection pooling
            self.client = pymongo.MongoClient(
                self.url,
                maxPoolSize=self.max_pool_size,
                minPoolSize=self.min_pool_size,
                maxIdleTimeMS=self.max_idle_time_ms,
                serverSelectionTimeoutMS=self.server_selection_timeout_ms,
                connectTimeoutMS=self.connect_timeout_ms,
                retryWrites=True,
                w='majority'  # Write concern for reliability
            )
            
            # Test connection
            self.client.admin.command('ping')
            print("✅ MongoDB connection established successfully")
            
            # Get database and collection
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            
            # Create indexes for better performance
            self.create_indexes()
            
            # Start background processing thread
            self.start_background_processor()
            
            print(f"📊 Pipeline initialized with batch size: {self.batch_size}")
            
        except Exception as e:
            print(f"❌ Error connecting to MongoDB: {e}")
            raise
    
    def close_spider(self, spider):
        """Đóng kết nối khi spider kết thúc"""
        print("🔄 Closing MongoDB pipeline...")
        
        # Stop background processor
        self.stop_event.set()
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=10)
        
        # Process remaining items
        self.process_remaining_items()
        
        # Close connection
        if self.client:
            self.client.close()
            print("✅ MongoDB connection closed")
        
        # Print final statistics
        self.print_final_stats()
    
    def create_indexes(self):
        """Tạo indexes để tối ưu hiệu suất"""
        try:
            # Index on URL for faster duplicate checking
            self.collection.create_index("url", unique=True, background=True)
            
            # Index on crawled_at for time-based queries
            self.collection.create_index("crawled_at", background=True)
            
            # Index on status for filtering
            self.collection.create_index("status", background=True)
            
            print("✅ Database indexes created/verified")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not create indexes: {e}")
    
    def start_background_processor(self):
        """Khởi động thread xử lý batch trong background"""
        self.processing_thread = threading.Thread(
            target=self.batch_processor,
            daemon=True
        )
        self.processing_thread.start()
        print("🚀 Background batch processor started")
    
    def batch_processor(self):
        """Xử lý items theo batch trong background thread"""
        batch = []
        last_process_time = time.time()
        
        while not self.stop_event.is_set():
            try:
                # Get item from queue with timeout
                try:
                    item = self.item_queue.get(timeout=1.0)
                    batch.append(item)
                except:
                    # Timeout - check if we should process current batch
                    pass
                
                current_time = time.time()
                
                # Process batch if it's full or timeout reached
                should_process = (
                    len(batch) >= self.batch_size or
                    (batch and (current_time - last_process_time) >= self.batch_timeout)
                )
                
                if should_process and batch:
                    self.process_batch(batch)
                    batch = []
                    last_process_time = current_time
                    
            except Exception as e:
                print(f"❌ Error in batch processor: {e}")
                print(traceback.format_exc())
        
        # Process final batch
        if batch:
            self.process_batch(batch)
    
    def process_batch(self, batch):
        """Xử lý một batch items"""
        if not batch:
            return
        
        try:
            # Prepare bulk operations
            operations = []
            
            for item_data in batch:
                # Use upsert to handle duplicates efficiently
                operations.append(
                    pymongo.UpdateOne(
                        {"url": item_data["url"]},  # Filter
                        {"$setOnInsert": item_data},  # Only set on insert
                        upsert=True
                    )
                )
            
            # Execute bulk operation
            if operations:
                result = self.collection.bulk_write(operations, ordered=False)
                
                # Update statistics
                with self.stats_lock:
                    self.stats['processed'] += len(batch)
                    self.stats['inserted'] += result.upserted_count
                    self.stats['duplicates'] += (len(batch) - result.upserted_count)
                
                print(f"📦 Processed batch: {len(batch)} items, "
                      f"Inserted: {result.upserted_count}, "
                      f"Duplicates: {len(batch) - result.upserted_count}")
                
        except Exception as e:
            with self.stats_lock:
                self.stats['errors'] += len(batch)
            print(f"❌ Error processing batch: {e}")
            print(traceback.format_exc())
    
    def process_remaining_items(self):
        """Xử lý các items còn lại trong queue"""
        remaining_items = []
        
        # Collect remaining items
        while not self.item_queue.empty():
            try:
                item = self.item_queue.get_nowait()
                remaining_items.append(item)
            except:
                break
        
        if remaining_items:
            print(f"🔄 Processing {len(remaining_items)} remaining items...")
            self.process_batch(remaining_items)
    
    def process_item(self, item, spider):
        """Main method được Scrapy gọi cho mỗi item"""
        try:
            # Convert item to dict
            item_data = ItemAdapter(item).asdict()
            
            # Add to queue for batch processing
            self.item_queue.put(item_data)
            
            # Print progress periodically
            with self.stats_lock:
                total_processed = self.stats['processed']
                if total_processed > 0 and total_processed % 100 == 0:
                    self.print_progress_stats()
            
        except Exception as e:
            with self.stats_lock:
                self.stats['errors'] += 1
            print(f'❌ Error in process_item: {e}')
            print(traceback.format_exc())
        
        return item
    
    def print_progress_stats(self):
        """In thống kê tiến trình"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        rate = self.stats['processed'] / max(elapsed, 1)
        
        print(f"📈 Progress - Processed: {self.stats['processed']}, "
              f"Inserted: {self.stats['inserted']}, "
              f"Duplicates: {self.stats['duplicates']}, "
              f"Errors: {self.stats['errors']}, "
              f"Rate: {rate:.1f} items/sec")
    
    def print_final_stats(self):
        """In thống kê cuối cùng"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        rate = self.stats['processed'] / max(elapsed, 1)
        
        print("\n" + "="*60)
        print("📊 FINAL CRAWLING STATISTICS")
        print("="*60)
        print(f"⏱️  Total time: {elapsed:.1f} seconds")
        print(f"📄 Total processed: {self.stats['processed']} items")
        print(f"✅ Successfully inserted: {self.stats['inserted']} items")
        print(f"🔄 Duplicates skipped: {self.stats['duplicates']} items")
        print(f"❌ Errors: {self.stats['errors']} items")
        print(f"⚡ Average rate: {rate:.1f} items/second")
        print(f"💾 Queue size at end: {self.item_queue.qsize()}")
        print("="*60)

# Legacy pipeline for backward compatibility
class MongoDBPipeline(OptimizedMongoDBPipeline):
    """Backward compatibility wrapper"""
    
    def __init__(self):
        print("⚠️  Using legacy MongoDBPipeline. Consider switching to OptimizedMongoDBPipeline")
        super().__init__()
        # Use smaller batch size for legacy mode
        self.batch_size = 50

# Additional specialized pipelines

class FastMongoDBPipeline(OptimizedMongoDBPipeline):
    """Ultra-fast pipeline for high-volume crawling"""
    
    def __init__(self):
        super().__init__()
        # Aggressive settings for maximum speed
        self.batch_size = 200
        self.batch_timeout = 2
        self.max_pool_size = 100
        
        print("🚀 FastMongoDBPipeline initialized for high-volume crawling")

class SafeMongoDBPipeline(OptimizedMongoDBPipeline):
    """Conservative pipeline with extra error handling"""
    
    def __init__(self):
        super().__init__()
        # Conservative settings for reliability
        self.batch_size = 50
        self.batch_timeout = 10
        self.max_pool_size = 20
        
        print("🛡️  SafeMongoDBPipeline initialized for reliable crawling")
    
    def process_batch(self, batch):
        """Override with extra error handling"""
        try:
            super().process_batch(batch)
        except Exception as e:
            print(f"⚠️ Batch failed, processing items individually...")
            # Fallback: process items one by one
            for item_data in batch:
                try:
                    self.collection.update_one(
                        {"url": item_data["url"]},
                        {"$setOnInsert": item_data},
                        upsert=True
                    )
                    with self.stats_lock:
                        self.stats['processed'] += 1
                        self.stats['inserted'] += 1
                except Exception as item_error:
                    print(f"❌ Failed to process item {item_data.get('url', 'unknown')}: {item_error}")
                    with self.stats_lock:
                        self.stats['errors'] += 1