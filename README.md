BING IMAGE SEARCH SCRAPER

PROJECT OVERVIEW
-----------------
A robust, production-ready web application for scraping and searching images 
from Bing Images. Built with Flask and Socket.IO, featuring multiple fallback 
mechanisms for reliable data retrieval, rate limiting, and real-time 
communication capabilities.

SYSTEM REQUIREMENTS
--------------------
- Python 3.8 or higher
- Operating System: Windows, Linux, or macOS
- Network: Active internet connection required for image scraping

DEPENDENCIES
-------------
Core Packages:
  - flask
  - flask-socketio
  - flask-limiter
  - beautifulsoup4
  - eventlet

Optional Packages (for enhanced scraping):
  - curl_cffi
  - cloudscraper
  - requests
  - urllib3

INSTALLATION
-------------
1. Clone or extract the project files to your desired directory

2. Create a virtual environment (recommended):
   $ python -m venv venv
   
3. Activate the virtual environment:
   Windows:   venv\\Scripts\\activate
   Linux/Mac: source venv/bin/activate

4. Install required packages:
   $ pip install flask flask-socketio flask-limiter beautifulsoup4 eventlet
   
   For enhanced scraping capabilities, also install:
   $ pip install curl_cffi cloudscraper requests

CONFIGURATION
--------------
Environment Variables (optional):
  - SECRET_KEY          : Application secret key (default: 'dev-secret-key-change-in-production')
  - FLASK_DEBUG         : Enable debug mode (default: 'False')
  - PORT                : Server port (default: 5000)

Configuration Files:
  - scraper.log         : Application logs (auto-generated)

USAGE
------
Starting the Server:
  $ python app.py
  
  The server will start on http://0.0.0.0:5000 (or your specified PORT)

Accessing the Application:
  - Open a web browser and navigate to: http://localhost:5000
  - The interface provides real-time image search functionality

API Endpoints:
  - GET  /              : Main application interface
  - GET  /health        : Health check endpoint (returns JSON status)

WebSocket Events:
  - connect             : Client connection established
  - request_search      : Initiate image search (params: query, offset, limit)
  - search_response     : Search results returned
  - search_error        : Error notification
  - disconnect          : Client disconnected

Search Parameters:
  - query  (string)     : Search term (required, max 200 characters)
  - offset (integer)    : Pagination offset (default: 1)
  - limit  (integer)    : Results per request (default: 10, max: 20)

ARCHITECTURE
-------------
Core Components:

1. RobustImageScraper
   - Multi-layered fallback system for HTTP requests
   - Intelligent caching mechanism (TTL: 300 seconds)
   - HTML parsing with multiple selector strategies
   - Rate limiting and error handling

2. RequestManager
   - Session management
   - Request header configuration
   - Browser impersonation capabilities

3. Flask Application
   - RESTful API endpoints
   - WebSocket real-time communication
   - Rate limiting (200/day, 50/hour per IP)
   - Comprehensive logging

Scraping Methods (in priority order):
  1. curl_cffi          : Chrome impersonation with TLS fingerprint spoofing
  2. cloudscraper       : Cloudflare protection bypass
  3. standard requests  : HTTP with retry logic
  4. urllib fallback    : Basic HTTP client (last resort)

FEATURES
---------
- Real-time image search via WebSocket
- Multiple scraping fallback mechanisms
- Built-in rate limiting and abuse prevention
- Response caching for improved performance
- Comprehensive logging system
- Health check endpoint for monitoring
- Cross-origin resource sharing (CORS) support
- Automatic retry logic with exponential backoff
- Duplicate image detection and filtering

SECURITY CONSIDERATIONS
------------------------
- Rate limiting enabled by default (200 requests/day, 50/hour per IP)
- SSL certificate verification disabled in urllib fallback (see code notes)
- Secret key should be changed in production environment
- Debug mode should be disabled in production

TROUBLESHOOTING
----------------
Issue: No images returned
  Solution: Check internet connection and verify Bing Images accessibility

Issue: "All scraping methods failed" error
  Solution: Install optional dependencies (curl_cffi, cloudscraper) for better
            compatibility with protection services

Issue: Rate limit exceeded
  Solution: Wait for the hourly or daily limit to reset

Issue: WebSocket connection fails
  Solution: Ensure eventlet is installed and firewall allows port access

LOGGING
--------
Log files are generated in the application directory:
  - scraper.log         : Application events and errors
  - Console output      : Real-time operation status

Log levels: INFO, WARNING, ERROR, DEBUG

PERFORMANCE NOTES
------------------
- Cache TTL: 300 seconds (5 minutes)
- Maximum results per request: 20 images
- Default timeout for HTTP requests: 15 seconds
- WebSocket ping timeout: 10 seconds
- Maximum HTTP buffer size: 1MB

VERSION HISTORY
----------------
v1.0.0 (Current)
  - Enhanced error handling
  - Improved caching mechanism
  - Added health check endpoint
  - Optimized WebSocket configuration

LICENSE
--------
You can publish this project into your production server (maybe needs a improvement on security system).
Users are responsible for complying with Bing's Terms of Service and 
applicable laws regarding web scraping in their jurisdiction.

SUPPORT & MAINTENANCE
----------------------
For issues, updates, or contributions:
  - Review logs in scraper.log
  - Check Flask and Socket.IO documentation
  - Verify all dependencies are up to date
