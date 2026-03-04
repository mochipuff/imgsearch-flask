import json
import logging
import urllib.parse
from typing import List, Dict, Optional
from dataclasses import dataclass
from functools import lru_cache
from bs4 import BeautifulSoup
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os

# Konfigurasi Logging yang lebih robust
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraper.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ImageResult:
    """Data class untuk hasil pencarian gambar"""
    original_url: str
    thumbnail: str
    title: str
    source: str = ""
    width: int = 0
    height: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'original_url': self.original_url,
            'thumbnail': self.thumbnail,
            'title': self.title,
            'source': self.source,
            'width': self.width,
            'height': self.height
        }

class RequestManager:
    """Manajer request dengan circuit breaker pattern"""
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        self._session = None
        self._failure_count = 0
        self._max_failures = 3
        
    @property
    def session(self):
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                self._session.headers.update(self.headers)
            except ImportError:
                logger.error("requests library not installed")
        return self._session

class RobustImageScraper:
    """
    Advanced Scraper Engine dengan Auto-Fallback mechanism dan caching.
    Mendukung rotasi metode request untuk mem-bypass anti-bot ringan/menengah.
    """
    
    def __init__(self):
        self.request_manager = RequestManager()
        self._cache = {}
        self._cache_ttl = 300  # 5 menit cache
        
    def _fetch_curl_cffi(self, url: str) -> Optional[str]:
        """Fetch menggunakan curl_cffi untuk impersonasi browser"""
        try:
            from curl_cffi import requests as curl_requests
            logger.info("Using curl_cffi...")
            
            resp = curl_requests.get(
                url, 
                headers=self.request_manager.headers, 
                impersonate="chrome120",
                timeout=15,
                allow_redirects=True
            )
            resp.raise_for_status()
            logger.info(f"curl_cffi success: {len(resp.text)} chars")
            return resp.text
        except ImportError:
            logger.debug("curl_cffi not installed, skipping...")
            return None
        except Exception as e:
            logger.warning(f"curl_cffi failed: {e}")
            return None

    def _fetch_cloudscraper(self, url: str) -> Optional[str]:
        """Fetch menggunakan cloudscraper untuk bypass Cloudflare"""
        try:
            import cloudscraper
            logger.info("Using cloudscraper...")
            
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
            resp = scraper.get(url, headers=self.request_manager.headers, timeout=15)
            resp.raise_for_status()
            logger.info(f"cloudscraper success: {len(resp.text)} chars")
            return resp.text
        except ImportError:
            logger.debug("cloudscraper not installed, skipping...")
            return None
        except Exception as e:
            logger.warning(f"cloudscraper failed: {e}")
            return None

    def _fetch_standard_requests(self, url: str) -> Optional[str]:
        """Fetch menggunakan standard requests dengan retry logic"""
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            logger.info("Using standard requests with retry...")
            
            session = requests.Session()
            retry = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            resp = session.get(
                url, 
                headers=self.request_manager.headers, 
                timeout=15,
                allow_redirects=True
            )
            resp.raise_for_status()
            logger.info(f"Standard requests success: {len(resp.text)} chars")
            return resp.text
        except Exception as e:
            logger.warning(f"Standard requests failed: {e}")
            return None

    def _fetch_urllib(self, url: str) -> Optional[str]:
        """Fallback terakhir menggunakan urllib"""
        try:
            import urllib.request
            import ssl
            
            logger.info("Using urllib fallback...")
            
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, headers=self.request_manager.headers)
            with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            logger.warning(f"urllib failed: {e}")
            return None

    def get_html(self, url: str) -> str:
        """Auto-fallback mechanism untuk fetch HTML"""
        cache_key = f"html:{url}"
        
        # Check cache
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                logger.info("Returning cached HTML")
                return cached_data
        
        methods = [
            self._fetch_curl_cffi,
            self._fetch_cloudscraper,
            self._fetch_standard_requests,
            self._fetch_urllib
        ]
        
        for method in methods:
            try:
                html = method(url)
                if html and len(html) > 1000:  # Validasi minimal content
                    # Cache result
                    self._cache[cache_key] = (html, time.time())
                    return html
            except Exception as e:
                logger.error(f"Method {method.__name__} error: {e}")
                continue
        
        raise Exception("All scraping methods failed. Service may be temporarily unavailable.")

    def parse_bing_images(self, html: str, limit: int) -> List[ImageResult]:
        """Parse HTML Bing Images dengan multiple selector strategy"""
        soup = BeautifulSoup(html, 'lxml')
        images = []
        
        # Strategy 1: Parse dari attribute 'm' (JSON data)
        selectors = [
            ("a", {"class_": "iusc"}),
            ("div", {"class_": "imgpt"}),
            ("a", {"class_": "iusc"}),
            ("div", {"class_": "mimg"}),
        ]
        
        for tag, attrs in selectors:
            elements = soup.find_all(tag, **attrs)
            logger.info(f"Found {len(elements)} elements with {tag} {attrs}")
            
            for element in elements:
                try:
                    img_data = self._extract_image_data(element)
                    if img_data and img_data.original_url:
                        images.append(img_data)
                        
                    if len(images) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error parsing element: {e}")
                    continue
            
            if len(images) >= limit:
                break
        
        # Strategy 2: Parse dari meta tags
        if len(images) < limit:
            meta_images = self._parse_meta_tags(soup, limit - len(images))
            images.extend(meta_images)
        
        return images[:limit]
    
    def _extract_image_data(self, element) -> Optional[ImageResult]:
        """Extract image data dari element HTML"""
        # Coba parse dari attribute 'm'
        m_attr = element.get("m")
        if m_attr:
            try:
                m_data = json.loads(m_attr)
                return ImageResult(
                    original_url=m_data.get("murl", ""),
                    thumbnail=m_data.get("turl", ""),
                    title=m_data.get("t", m_data.get("desc", "No Title")),
                    source=m_data.get("purl", ""),
                    width=m_data.get("w", 0),
                    height=m_data.get("h", 0)
                )
            except json.JSONDecodeError:
                pass
        
        # Coba parse dari img tag
        img_tag = element.find("img")
        if img_tag:
            return ImageResult(
                original_url=img_tag.get("src", img_tag.get("data-src", "")),
                thumbnail=img_tag.get("src", ""),
                title=img_tag.get("alt", "No Title")
            )
        
        return None
    
    def _parse_meta_tags(self, soup, limit: int) -> List[ImageResult]:
        """Fallback parsing dari meta tags"""
        images = []
        meta_tags = soup.find_all("meta", property="og:image")
        
        for tag in meta_tags[:limit]:
            img_url = tag.get("content", "")
            if img_url:
                images.append(ImageResult(
                    original_url=img_url,
                    thumbnail=img_url,
                    title="Image"
                ))
        
        return images

    def search(self, query: str, limit: int = 10, offset: int = 1) -> Dict:
        """
        Search images dengan comprehensive error handling dan metadata
        """
        import time
        start_time = time.time()
        
        encoded_query = urllib.parse.quote_plus(query)
        # Bing menggunakan parameter 'first' untuk paginasi
        url = f"https://www.bing.com/images/search?q={encoded_query}&first={offset}&count={limit}&form=IRFLTR"
        
        logger.info(f"Searching: '{query}' (offset: {offset}, limit: {limit})")
        
        try:
            html = self.get_html(url)
            images = self.parse_bing_images(html, limit)
            
            processing_time = time.time() - start_time
            
            # Logika boolean jika gambar habis
            has_more = len(images) == limit
            next_offset = offset + limit if has_more else None
            
            logger.info(f"Found {len(images)} images in {processing_time:.2f}s")
            
            return {
                'images': [img.to_dict() for img in images],
                'next_offset': next_offset,
                'has_more': has_more,
                'total_found': len(images),
                'processing_time': round(processing_time, 2),
                'query': query
            }
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

# Konfigurasi Flask & WebSocket (SocketIO)
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Rate limiting
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )
    
    # SocketIO dengan konfigurasi optimal
    socketio = SocketIO(
        app, 
        async_mode='eventlet',
        cors_allowed_origins="*",
        ping_timeout=10,
        ping_interval=5,
        max_http_buffer_size=1e6
    )
    
    scraper_engine = RobustImageScraper()
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': time.time(),
            'version': '2.0.0'
        })
    
    @socketio.on('connect')
    def handle_connect():
        logger.info(f"Client connected: {request.sid if hasattr(request, 'sid') else 'unknown'}")
        emit('connected', {'message': 'Connected to Image Search Engine'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info("Client disconnected")
    
    @socketio.on('request_search')
    def handle_search(data):
        query = data.get('query', '').strip()
        offset = data.get('offset', 1)
        limit = min(data.get('limit', 10), 20)  # Max 20 per request
        
        if not query:
            emit('search_error', {
                'message': 'Search query cannot be empty',
                'code': 'EMPTY_QUERY'
            })
            return
        
        if len(query) > 200:
            emit('search_error', {
                'message': 'Query too long (max 200 characters)',
                'code': 'QUERY_TOO_LONG'
            })
            return
        
        try:
            results = scraper_engine.search(query, limit=limit, offset=offset)
            results['is_load_more'] = offset > 1
            emit('search_response', results)
            
        except Exception as e:
            logger.error(f"Error during search: {e}")
            emit('search_error', {
                'message': str(e),
                'code': 'SEARCH_ERROR',
                'suggestion': 'Please try again in a few moments'
            })
    
    @socketio.on_error_default
    def default_error_handler(e):
        logger.error(f"SocketIO error: {e}")
        emit('search_error', {
            'message': 'An unexpected error occurred',
            'code': 'INTERNAL_ERROR'
        })
    
    return app, socketio

# Global imports for health check
import time
from flask import request

if __name__ == '__main__':
    app, socketio = create_app()
    
    # Production-ready server configuration
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config['DEBUG'],
        use_reloader=app.config['DEBUG'],
        log_output=True
    )