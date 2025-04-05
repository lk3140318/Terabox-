import re
import httpx
import logging
import asyncio
from urllib.parse import urlparse, parse_qs
from typing import Tuple, Optional

from .. import config

LOGGER = logging.getLogger(__name__)

# Enhanced Regex to capture sharekey/ID from various URL formats
TERABOX_LINK_REGEX = re.compile(
    r"https?://(?:(?:1024)?terabox|teraboxlink|terafileshare)\.(?:com|app)/([s]/)?([a-zA-Z0-9_-]+)"
)

# User agent to mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.google.com/", # Add a referer
    "DNT": "1", # Do Not Track header
    "Sec-GPC": "1" # Global Privacy Control
}

# --- IMPORTANT NOTE ---
# The logic below for extracting the direct download link is based on observed patterns
# and common techniques used by such sites. Terabox frequently changes its methods.
# This implementation MIGHT BREAK and WILL LIKELY REQUIRE UPDATES.
# It attempts common strategies:
# 1. Look for direct link patterns in the HTML source.
# 2. Check for JavaScript variables holding link data.
# 3. Potentially mimic API calls if needed (more complex, not fully implemented here).
# Using the provided TERABOX_COOKIE is ESSENTIAL.

async def get_terabox_download_link(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Attempts to extract the direct download link, filename, and size from a Terabox URL.

    Args:
        url: The Terabox share URL.

    Returns:
        A tuple (direct_link, filename, file_size_str) or (None, None, None) if failed.
        file_size_str is a human-readable string like "1.2 GB".
    """
    LOGGER.info(f"Attempting to resolve Terabox link: {url}")
    cookies = {"Cookie": config.TERABOX_COOKIE} # Pass cookie string directly

    # Add cookie header and specific referer for the request
    request_headers = HEADERS.copy()
    request_headers["Cookie"] = config.TERABOX_COOKIE
    request_headers["Referer"] = "https://www.terabox.com/" # More specific referer

    try:
        async with httpx.AsyncClient(http2=True, timeout=30.0, follow_redirects=True) as client:
            # Initial request to get the page content
            response = await client.get(url, headers=request_headers)
            response.raise_for_status() # Raise error for bad status codes
            content = response.text
            # LOGGER.debug(f"Terabox page content fetched (length: {len(content)})")

            # --- Strategy 1: Look for common link patterns in HTML ---
            # Example pattern (highly likely to change): 'dlink":"(.*?)"' or 'download":"(.*?)"'
            direct_link_match = re.search(r'["\'](?:dlink|download|download_url)["\']\s*:\s*["\'](https?://[^"\']+)["\']', content, re.IGNORECASE)
            if direct_link_match:
                direct_link = direct_link_match.group(1).replace("\\/", "/") # Handle escaped slashes
                LOGGER.info(f"Found potential direct link via pattern matching: {direct_link[:100]}...")
                # Attempt to get filename and size (these might also be nearby in HTML/JS)
                filename = await _extract_filename(content, url)
                file_size_str = await _extract_filesize_str(content)
                if filename and file_size_str:
                    LOGGER.info(f"Extracted Filename: {filename}, Size: {file_size_str}")
                    # Verify link seems valid (basic check)
                    if "http" in direct_link and ("." in urlparse(direct_link).netloc):
                         return direct_link, filename, file_size_str
                    else:
                        LOGGER.warning("Pattern matched link seems invalid, continuing search...")
                else:
                    LOGGER.warning("Could not extract filename/size for pattern matched link.")


            # --- Strategy 2: Look for JavaScript configuration objects ---
            # Often data is embedded in <script> tags like `var config = {...}`
            js_config_match = re.search(r'<script>.*?window\.__INITIAL_STATE__\s*=\s*({.*?});?.*?<\/script>', content, re.DOTALL)
            if js_config_match:
                try:
                    import json
                    js_data_str = js_config_match.group(1)
                    js_data = json.loads(js_data_str)
                    # Navigate the JS object structure (this requires inspecting the actual page source)
                    # Example path (WILL CHANGE): js_data['shareData']['fileList'][0]['dlink']
                    file_list = js_data.get('list', []) # Look in 'list' first
                    if not file_list and 'shareData' in js_data: # Fallback structure
                        file_list = js_data.get('shareData', {}).get('fileList', [])

                    if file_list and isinstance(file_list, list) and len(file_list) > 0:
                        item = file_list[0] # Assuming the first file is the target
                        direct_link = item.get('dlink') or item.get('downloadLink')
                        filename = item.get('server_filename') or item.get('filename')
                        size_bytes = item.get('size')

                        if direct_link and filename and size_bytes:
                             direct_link = direct_link.replace("\\/", "/")
                             LOGGER.info(f"Found potential direct link via JS object: {direct_link[:100]}...")
                             file_size_str = _format_bytes(int(size_bytes))
                             LOGGER.info(f"Extracted Filename: {filename}, Size: {file_size_str} ({size_bytes} bytes)")
                             if "http" in direct_link:
                                return direct_link, filename, file_size_str
                             else:
                                 LOGGER.warning("JS object link seems invalid.")
                        else:
                            LOGGER.warning("Could not extract required fields (dlink, filename, size) from JS object.")
                    else:
                        LOGGER.warning("Could not find relevant file list in JS object.")

                except json.JSONDecodeError:
                    LOGGER.warning("Failed to decode JavaScript __INITIAL_STATE__ JSON.")
                except Exception as e:
                    LOGGER.error(f"Error parsing JavaScript data: {e}")


            # --- Fallback/Alternative Strategy (If the above fail) ---
            # Sometimes the link might require another request based on info from the first page
            # This part is highly speculative and needs specific reverse engineering
            # Example: Find an API endpoint URL and necessary parameters (like fs_id)
            fs_id_match = re.search(r'["\']fs_id["\']\s*:\s*(\d+)', content)
            share_id_match = re.search(r'["\']shareid["\']\s*:\s*(\d+)', content)
            uk_match = re.search(r'["\']uk["\']\s*:\s*(\d+)', content) # User ID

            if fs_id_match and share_id_match and uk_match:
                fs_id = fs_id_match.group(1)
                share_id = share_id_match.group(1)
                uk = uk_match.group(1)
                LOGGER.info(f"Found potential API params: fs_id={fs_id}, share_id={share_id}, uk={uk}")

                # Construct potential API endpoint URL (THIS IS A GUESS)
                # Need to find the correct API endpoint and parameters by inspecting network traffic
                api_url = f"https://www.terabox.com/api/download?shareid={share_id}&uk={uk}&fidlist=[{fs_id}]" # Example endpoint
                LOGGER.info(f"Attempting API call (experimental): {api_url}")
                try:
                    api_response = await client.get(api_url, headers=request_headers, timeout=15.0)
                    api_response.raise_for_status()
                    api_data = api_response.json()
                    LOGGER.debug(f"API Response Data: {api_data}")
                    # Process API response (structure depends entirely on the actual API)
                    if api_data.get("errno") == 0 and api_data.get("list"):
                        dlink_info = api_data["list"][0]
                        direct_link = dlink_info.get("dlink")
                        filename = await _extract_filename(content, url) # Try extracting from initial page again
                        file_size_str = await _extract_filesize_str(content) # Try extracting from initial page again
                        if direct_link:
                            LOGGER.info(f"Successfully obtained link via API call: {direct_link[:100]}...")
                            if not filename: filename = "terabox_video.mp4" # Default filename
                            if not file_size_str: file_size_str = "Unknown"
                            return direct_link, filename, file_size_str
                        else:
                            LOGGER.warning("API call successful but no 'dlink' found in response.")
                    else:
                        LOGGER.warning(f"API call failed or returned error: {api_data.get('errno', 'N/A')}")

                except httpx.RequestError as e:
                    LOGGER.error(f"HTTP error during Terabox API call: {e}")
                except json.JSONDecodeError:
                     LOGGER.error("Failed to decode JSON response from Terabox API.")
                except Exception as e:
                    LOGGER.error(f"Error during Terabox API call processing: {e}")

            # If all methods fail
            LOGGER.error("Could not find direct download link after trying multiple methods.")
            return None, None, None

    except httpx.HTTPStatusError as e:
        LOGGER.error(f"HTTP Error fetching Terabox page: {e.response.status_code} - {e.request.url}")
        if e.response.status_code in [401, 403]:
             LOGGER.error("Authorization error. The TERABOX_COOKIE might be invalid or expired.")
        return None, None, None
    except httpx.RequestError as e:
        LOGGER.error(f"Network error accessing Terabox: {e}")
        return None, None, None
    except Exception as e:
        LOGGER.error(f"An unexpected error occurred in get_terabox_download_link: {e}", exc_info=True)
        return None, None, None

async def _extract_filename(content: str, fallback_url: str) -> Optional[str]:
    """Helper to find filename using various patterns."""
    # Prioritize specific JS patterns if available
    filename_match = re.search(r'["\']server_filename["\']\s*:\s*["\']([^"\']+)["\']', content)
    if filename_match:
        return filename_match.group(1)

    # Look in title tag
    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()
        # Clean up common title suffixes
        title = title.replace("- Terabox", "").replace("Terabox:", "").strip()
        # Basic check if it looks like a filename
        if '.' in title and len(title) < 150: # Avoid overly long strings
            return title

    # Fallback: derive from URL path if possible (less reliable)
    try:
        parsed_url = urlparse(fallback_url)
        # Extract last part of path, could be share key or filename depending on URL structure
        name_part = parsed_url.path.split('/')[-1]
        if name_part and len(name_part) > 4: # Basic sanity check
             return f"{name_part}.mp4" # Assume mp4 if no other info
    except Exception:
        pass # Ignore errors in fallback

    return "terabox_video.mp4" # Default fallback

async def _extract_filesize_str(content: str) -> Optional[str]:
    """Helper to find file size string using various patterns."""
    # Pattern: "size":1234567 or 'size':"1234567"
    size_match = re.search(r'["\']size["\']\s*:\s*"?(\d+)"?', content)
    if size_match:
        try:
            size_bytes = int(size_match.group(1))
            return _format_bytes(size_bytes)
        except ValueError:
            pass

    # Pattern: Looking for human-readable size like "1.2 GB" or "500 MB" near download buttons/info
    size_str_match = re.search(r'(\d+(\.\d+)?\s*(?:GB|MB|KB))', content, re.IGNORECASE)
    if size_str_match:
        return size_str_match.group(1).upper() # Return like "1.2 GB"

    return "Unknown" # Default fallback

def _format_bytes(size_bytes: int) -> str:
    """Converts bytes to a human-readable string (KB, MB, GB)."""
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def extract_terabox_link(text: str) -> Optional[str]:
    """Extracts the first valid Terabox link from text."""
    match = TERABOX_LINK_REGEX.search(text)
    return match.group(0) if match else None
