import os
import sys
import multiprocessing
from time import gmtime, strftime

# Thêm current directory vào Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def run_single_spider():
    """Chạy spider đơn với high concurrency"""
    try:
        from scrapy.crawler import CrawlerProcess
        from scrapy.utils.project import get_project_settings
        from crawl_phone import JobSpider
        
        # Lấy settings
        settings = get_project_settings()
        
        # Tối ưu settings cho single process
        settings.set('CONCURRENT_REQUESTS', 32)
        settings.set('CONCURRENT_REQUESTS_PER_DOMAIN', 16)
        settings.set('DOWNLOAD_DELAY', 1)
        settings.set('RANDOMIZE_DOWNLOAD_DELAY', 0.5)
        settings.set('AUTOTHROTTLE_ENABLED', True)
        settings.set('AUTOTHROTTLE_START_DELAY', 0.5)
        settings.set('AUTOTHROTTLE_MAX_DELAY', 3)
        settings.set('AUTOTHROTTLE_TARGET_CONCURRENCY', 2.0)
        settings.set('AUTOTHROTTLE_DEBUG', True)
        
        # Memory và performance settings
        settings.set('MEMUSAGE_ENABLED', True)
        settings.set('MEMUSAGE_LIMIT_MB', 2048)
        settings.set('REACTOR_THREADPOOL_MAXSIZE', 20)
        
        # Cache và retry
        settings.set('HTTPCACHE_ENABLED', True)
        settings.set('RETRY_ENABLED', True)
        settings.set('RETRY_TIMES', 3)
        
        print("🚀 Starting optimized single spider...")
        print(f"⚙️  Concurrent requests: {settings.get('CONCURRENT_REQUESTS')}")
        print(f"⚙️  Per domain: {settings.get('CONCURRENT_REQUESTS_PER_DOMAIN')}")
        print(f"⚙️  Download delay: {settings.get('DOWNLOAD_DELAY')}")
        print(f"⚙️  AutoThrottle: {settings.get('AUTOTHROTTLE_ENABLED')}")
        
        # Tạo và chạy crawler
        process = CrawlerProcess(settings)
        process.crawl(JobSpider)
        process.start()
        
        print("✅ Spider completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error running spider: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def run_spider_in_process(process_id, settings_dict):
    """Chạy spider trong process riêng biệt"""
    try:
        import os
        print(f"🚀 Process {process_id} (PID: {os.getpid()}) starting...")
        
        from scrapy.crawler import CrawlerProcess
        from scrapy.settings import Settings
        from crawl_phone import JobSpider
        
        # Tạo settings
        settings = Settings(settings_dict)
        
        # Adjust settings cho process này
        settings.set('CONCURRENT_REQUESTS', max(8, settings_dict.get('CONCURRENT_REQUESTS', 32) // 2))
        settings.set('CONCURRENT_REQUESTS_PER_DOMAIN', max(4, settings_dict.get('CONCURRENT_REQUESTS_PER_DOMAIN', 16) // 2))
        
        # Tạo và chạy crawler
        process = CrawlerProcess(settings)
        process.crawl(JobSpider)
        process.start()
        
        print(f"✅ Process {process_id} completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Process {process_id} error: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def main():
    """Main function đơn giản"""
    print("=" * 60)
    print("🕷️ Simple Multi-threaded Crawler")
    print("=" * 60)
    print(f"🕐 Started at: {strftime('%Y-%m-%d %H:%M:%S', gmtime())}")
    print(f"💻 Available CPU cores: {multiprocessing.cpu_count()}")
    print(f"🐍 Python version: {sys.version.split()[0]}")
    print("-" * 60)
    
    print("\nChoose running mode:")
    print("1. Single process with high concurrency (RECOMMENDED)")
    print("2. Exit")
    
    try:
        choice = input("\nEnter your choice (1-2): ").strip()
    except KeyboardInterrupt:
        print("\nExiting...")
        return
    
    if choice == "1":
        print("\n" + "="*50)
        print("🚀 SINGLE PROCESS MODE (HIGH CONCURRENCY)")
        print("="*50)
        print("This mode uses:")
        print("✅ 32 concurrent requests")
        print("✅ 16 requests per domain")
        print("✅ Auto-throttling enabled")
        print("✅ Memory monitoring")
        print("✅ HTTP caching")
        print("-" * 50)
        
        try:
            success = run_single_spider()
            if success:
                print("\n🎉 Crawling completed successfully!")
            else:
                print("\n❌ Crawling failed!")
        except KeyboardInterrupt:
            print("\n⚠️ Crawling interrupted by user")
    
    elif choice == "2":
        print("👋 Goodbye!")
        return
    
    else:
        print("❌ Invalid choice. Please enter 1, 2")
        return
    
    print(f"\n✅ Session ended at: {strftime('%Y-%m-%d %H:%M:%S', gmtime())}")
    print("=" * 60)

if __name__ == "__main__":
    # Set multiprocessing start method for compatibility
    if hasattr(multiprocessing, 'set_start_method'):
        try:
            multiprocessing.set_start_method('spawn', force=True)
        except RuntimeError:
            pass  # Already set
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Program terminated by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        print(traceback.format_exc())
    
    print("\nThank you for using Crawler! 🕷️")