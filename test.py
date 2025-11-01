import logging
import requests
import json
import os
import time
import asyncio
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from bs4 import BeautifulSoup

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION CHANGES ---
# 1. Bot credentials
BOT_TOKEN = "8482314639:AAGqtergUDCwWWlEbDHUboikWOpbVn5Ab2c"
# Updated CHAT_ID for the group -1003028949899
CHAT_ID = "-1003237492963" # Target Group/Channel for real-time updates

# Files to store data
PRODUCT_CODES_FILE = "product_codes.txt"
PRODUCT_DETAILS_FILE = "product_details.json"
OUT_OF_STOCK_FILE = "out_of_stock.txt"
NOTIFIED_OUT_OF_STOCK_FILE = "notified_out_of_stock.txt"
NOTIFIED_NEW_PRODUCTS_FILE = "notified_new_products.txt"
NOTIFIED_PRICE_CHANGES_FILE = "notified_price_changes.json"

# SHEIN API endpoints
CATALOG_API_URL = "https://www.sheinindia.in/api/category/sverse-5939-37961"
DELIVERY_API_URL = "https://www.sheinindia.in/api/edd/checkDeliveryDetails"

# Default Pin codes for background monitoring and /n when no pin is specified
DEFAULT_PIN_CODE_N = "504231" # Default for /n command
MONITOR_PIN_CODES = ["504231"] # Used for background alerts

# Headers and Cookies (keeping them as provided)
HEADERS = {
    'accept': 'application/json',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    'x-tenant-id': 'SHEIN'
}

COOKIES = {
    "V": "1",
    "_abck": "60A3EA44D6452E391F47D20DED1FE802~-1~YAAQ2W8nF+tpMS+aAQAADUH3QA64OTc8xz7NHwZ0GS7QI2ORkCs503JGsao/mUXDYUkWccjzt0kNFHJXwJbgdYaSPBdyp94eHG02V8KPGi+jtQozik03WhmecvQK9KCI14NJDtA2W+aWFRsHzRY1MafwFoEWnVBzQI5I2lJFliraP3c/7aLl8NpP8g94G/sDZMerju2+lmDSxRb8IugFsRIPzoAdTsHzaPlYRqe8R5zQFE0LZzkvoJXsbQTwzy8O2VZ7N3cbk3AJuIo30CsxcIbQucvXULZZMSwj3SLh3kvlMbzfnHyTdCgoyfomS2KzhkFmjBEyu/z3gsVwAwU9GKvfVIvQrmkXs2uY6ATLlhzqkSi90riguLd+uwJ0IBmQLlhPXM/uAQZRQiebZXwSur1TFWiDc0zRf8zVhDjIv2oBavNN6BCEyM8Tmonh4D+6RHaS/GAGj38=~-1~-1~-1~-1~-1",
    "bm_sz": "AAE0BB48D9D9A1E8D27EC3997A2E51D5~YAAQ2W8nF+xpMS+aAQAADUH3QB3te1dbaBY7zrBgwg4XJo6gCuqVEJ4fYsW6l8XqAKcbEqEjagpdWdZZwreP46IC1gT4WwGkslJubaOFBfkyHDQov71kJDHQntaS3mSH2XoAD4b4KIZbMCgaw3IcXZFmfywIIeJK6SPPUsM1fFk0fNoch9ZwdOjHUsXdtyy3RSfg3aojY/pbj/EYh/9WT9KCAT4BzmAkvThWn50yEWIEMcXPHBKOC4YRdOJ2MggfQdDRw18PaeL0LYMZFBND63SNamrBqx0YkLwtXBpSrJ24yixsDYkRptiGbOZVz9834jtUtJcznnTUpysP2+qbt7bgq5CsBIooElwapS8ih8eT~4405554~4469554"
}


# Global variables to store data
PRODUCTS_CACHE = {}
PREVIOUS_CATALOG = {}

# Thread pool for concurrent requests
executor = ThreadPoolExecutor(max_workers=10)

# --- UTILITY FUNCTIONS (NO CHANGES NEEDED) ---

def load_product_codes():
    """Load existing product codes from file"""
    if not os.path.exists(PRODUCT_CODES_FILE):
        return set()
    with open(PRODUCT_CODES_FILE, 'r') as f:
        return set(line.strip() for line in f)

def save_product_codes(codes):
    """Save product codes to file"""
    with open(PRODUCT_CODES_FILE, 'w') as f:
        for code in codes:
            f.write(f"{code}\n")

def load_product_details():
    """Load product details from file"""
    if not os.path.exists(PRODUCT_DETAILS_FILE):
        return {}
    try:
        with open(PRODUCT_DETAILS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_product_details(details):
    """Save product details to file"""
    with open(PRODUCT_DETAILS_FILE, 'w') as f:
        json.dump(details, f, indent=2)

def load_out_of_stock():
    """Load out of stock products from file"""
    if not os.path.exists(OUT_OF_STOCK_FILE):
        return set()
    with open(OUT_OF_STOCK_FILE, 'r') as f:
        return set(line.strip() for line in f)

def save_out_of_stock(codes):
    """Save out of stock products to file"""
    with open(OUT_OF_STOCK_FILE, 'w') as f:
        for code in codes:
            f.write(f"{code}\n")

def load_notified_out_of_stock():
    """Load already notified out of stock products"""
    if not os.path.exists(NOTIFIED_OUT_OF_STOCK_FILE):
        return set()
    with open(NOTIFIED_OUT_OF_STOCK_FILE, 'r') as f:
        return set(line.strip() for line in f)

def save_notified_out_of_stock(codes):
    """Save already notified out of stock products"""
    with open(NOTIFIED_OUT_OF_STOCK_FILE, 'w') as f:
        for code in codes:
            f.write(f"{code}\n")

def load_notified_new_products():
    """Load already notified new products"""
    if not os.path.exists(NOTIFIED_NEW_PRODUCTS_FILE):
        return set()
    with open(NOTIFIED_NEW_PRODUCTS_FILE, 'r') as f:
        return set(line.strip() for line in f)

def save_notified_new_products(codes):
    """Save already notified new products"""
    with open(NOTIFIED_NEW_PRODUCTS_FILE, 'w') as f:
        for code in codes:
            f.write(f"{code}\n")

def load_notified_price_changes():
    """Load already notified price changes"""
    if not os.path.exists(NOTIFIED_PRICE_CHANGES_FILE):
        return {}
    try:
        with open(NOTIFIED_PRICE_CHANGES_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_notified_price_changes(data):
    """Save already notified price changes"""
    with open(NOTIFIED_PRICE_CHANGES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def fetch_catalog():
    """Fetch product catalog from SHEIN API with retry mechanism"""
    params = {
        'fields': 'SITE',
        'currentPage': '0',
        'pageSize': '45',
        'format': 'json',
        'query': ':relevance:genderfilter:Men',
        'sortBy': 'relevance',
        'gridColumns': '5',
        'facets': 'genderfilter:Men',
        'segmentIds': '',
        'advfilter': 'true',
        'platform': 'Desktop',
        'showAdsOnNextPage': 'false',
        'is_ads_enable_plp': 'true',
        'displayRatings': 'true',
        'store': 'shein'
    }
    
    max_retries = 100000000000000000
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.get(CATALOG_API_URL, params=params, headers=HEADERS, cookies=COOKIES, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error(f"Authentication error (403) on attempt {attempt + 1}/{max_retries}. Cookies may be expired.")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("Max retries reached. Please update the cookies in the script.")
                    return None
            else:
                logger.error(f"HTTP error {e.response.status_code}: {e}")
                return None
        except Exception as e:
            logger.error(f"Error fetching catalog: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return None
    
    return None

def check_delivery_availability(product_code, pin_code):
    """Check delivery availability for a product to a specific pin code"""
    params = {
        'productCode': product_code,
        'postalCode': pin_code,
        'quantity': '1',
        'IsExchange': 'false'
    }
    
    try:
        response = requests.get(DELIVERY_API_URL, params=params, headers=HEADERS, cookies=COOKIES, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error checking delivery for {pin_code}: {e}")
        return None

async def check_delivery_for_pins(product_code, pin_codes):
    """Check delivery availability for a list of pin codes"""
    delivery_info = {}
    
    # Create tasks for concurrent execution
    loop = asyncio.get_event_loop()
    tasks = []
    
    for pin_code in pin_codes:
        task = loop.run_in_executor(executor, check_delivery_availability, product_code, pin_code)
        tasks.append((pin_code, task))
    
    # Wait for all tasks to complete
    for pin_code, task in tasks:
        try:
            delivery_data = await task
            if delivery_data:
                status = delivery_data.get('status', {})
                status_code = status.get('statusCode', -1)
                
                if status_code == 0:
                    product_details = delivery_data.get('productDetails', [])
                    if product_details:
                        detail = product_details[0]
                        delivery_info[pin_code] = {
                            'serviceable': detail.get('servicability', False),
                            'delivery_method': detail.get('deliveryMethod', 'Unknown'),
                            'cod_eligible': detail.get('codEligible', False),
                            'reason': detail.get('reasonForNotServiceability', '')
                        }
                    else:
                        delivery_info[pin_code] = {
                            'serviceable': False,
                            'delivery_method': 'Unknown',
                            'cod_eligible': False,
                            'reason': 'No delivery information available'
                        }
                else:
                    delivery_info[pin_code] = {
                        'serviceable': False,
                        'delivery_method': 'Unknown',
                        'cod_eligible': False,
                        'reason': 'Failed to check delivery'
                    }
            else:
                delivery_info[pin_code] = {
                    'serviceable': False,
                    'delivery_method': 'Unknown',
                    'cod_eligible': False,
                    'reason': 'API error'
                }
        except Exception as e:
            logger.error(f"Error processing delivery for {pin_code}: {e}")
            delivery_info[pin_code] = {
                'serviceable': False,
                'delivery_method': 'Unknown',
                'cod_eligible': False,
                'reason': 'Processing error'
            }
    
    return delivery_info

async def check_delivery_for_all_pins(product_code):
    """Check delivery availability for all MONITOR_PIN_CODES (used for alerts)"""
    return await check_delivery_for_pins(product_code, MONITOR_PIN_CODES)

# --- REVISED HELPER FUNCTION ---
def format_product_info(product, index=None, delivery_info=None):
    """Format product information for display"""
    name = product.get('name', 'Unknown Product')
    code = product.get('code', 'Unknown Code')
    price = product.get('price', {}).get('formattedValue', 'Price not available')
    offer_price = product.get('offerPrice', {}).get('formattedValue', '')
    rating = product.get('averageRating', 0)
    rating_count = product.get('ratingCount', 0)
    url = f"https://www.sheinindia.in{product.get('url', '')}"
    
    # Get color from the product data
    color_group = product.get('fnlColorVariantData', {}).get('colorGroup', '')
    color = color_group.split('_')[-1] if '_' in color_group else color_group
    
    # Get primary image - try different image formats
    images = product.get('images', [])
    image_url = ''
    
    if images:
        # Try to get the best quality image
        for img in images:
            if img.get('format') == 'product' and img.get('imageType') == 'PRIMARY':
                image_url = img.get('url', '')
                break
        
        # If not found, try any other format
        if not image_url:
            for img in images:
                if img.get('url'):
                    image_url = img.get('url')
                    break
    
    # Get tags
    tags = []
    category_tags = product.get('tags', {}).get('categoryTags', [])
    for tag in category_tags:
        if tag.get('category') == 'SELLING_POINT':
            tags.append(tag.get('primary', {}).get('name', ''))
    
    # Format message
    message = ""
    
    # Add index if provided
    if index is not None:
        # The index here is i+1 from the loops, representing the product number
        message += f"📦 <b>Product #{index + 1}</b>\n\n" 
    
    message += f"<b>{name}</b>\n"
    message += f"Code: {code}\n"
    
    if color:
        message += f"Color: {color.title()}\n"
    
    if offer_price and offer_price != price:
        message += f"Price: <s>{price}</s> {offer_price}\n"
    else:
        message += f"Price: {price}\n"
    
    if rating > 0:
        message += f"Rating: {rating} ({rating_count} reviews)\n"
    
    if tags:
        message += f"Tags: {', '.join(tags)}\n"
    
    # Add delivery information if provided
    if delivery_info:
        message += f"\n<b>🚚 Delivery Status:</b>\n"
        for pin_code, info in delivery_info.items():
            message += f"\n📍 <b>{pin_code}:</b>\n"
            message += f"Serviceable: {'✅ Yes' if info['serviceable'] else '❌ No'}\n"
            if info['serviceable']:
                message += f"Delivery Method: {info['delivery_method']}\n"
                message += f"COD Available: {'✅ Yes' if info['cod_eligible'] else '❌ No'}\n"
            else:
                if info['reason']:
                    message += f"Reason: {info['reason']}\n"
    
    message += f"\n<a href='{url}'>🔗 View on SHEIN</a>"
    
    return message, image_url

# --- MONITORING FUNCTION (CHAT_ID UPDATED FOR ALERTS) ---

async def monitor_catalog_changes(application):
    """Monitor catalog changes in real-time"""
    global PREVIOUS_CATALOG, PRODUCTS_CACHE
    
    # Load notification tracking files
    notified_out_of_stock = load_notified_out_of_stock()
    notified_new_products = load_notified_new_products()
    notified_price_changes = load_notified_price_changes()
    
    while True:
        try:
            # Fetch current catalog
            catalog_data = fetch_catalog()
            if not catalog_data:
                await asyncio.sleep(30)  # Wait 30 seconds before retrying on error
                continue
            
            current_products = catalog_data.get('products', [])
            current_codes = set(product.get('code') for product in current_products if product.get('code'))
            
            # Load previous catalog if available
            if not PREVIOUS_CATALOG:
                PREVIOUS_CATALOG = load_product_details()
            
            # Load existing product codes
            existing_codes = load_product_codes()
            out_of_stock = load_out_of_stock()
            
            # Check for new products
            new_products = []
            for product in current_products:
                code = product.get('code')
                if code and code not in existing_codes:
                    new_products.append(product)
                    existing_codes.add(code)
            
            # Check for removed products (out of stock) - only if not already notified
            removed_products = []
            for code in existing_codes:
                if code not in current_codes and code not in notified_out_of_stock:
                    # Retrieve details before potentially deleting (if product removed from PREVIOUS_CATALOG)
                    if code in PREVIOUS_CATALOG:
                        removed_products.append(PREVIOUS_CATALOG[code])
                    else:
                        removed_products.append({'code': code, 'name': 'Unknown Product'})
                    out_of_stock.add(code)
                    notified_out_of_stock.add(code)
            
            # Check for price changes - only if not already notified
            price_changes = []
            for product in current_products:
                code = product.get('code')
                if code and code in PREVIOUS_CATALOG:
                    prev_price = PREVIOUS_CATALOG.get(code, {}).get('price', {}).get('formattedValue', '')
                    curr_price = product.get('price', {}).get('formattedValue', '')
                    
                    # Create a unique key for price change
                    price_change_key = f"{code}_{prev_price}_{curr_price}"
                    
                    if (prev_price and curr_price and prev_price != curr_price and 
                        price_change_key not in notified_price_changes):
                        price_changes.append((product, old_price, curr_price))
                        notified_price_changes[price_change_key] = datetime.now().isoformat()
            
            # Update previous catalog
            for product in current_products:
                code = product.get('code')
                if code:
                    PREVIOUS_CATALOG[code] = product
            
            # Save updated data
            save_product_codes(existing_codes)
            save_product_details(PREVIOUS_CATALOG)
            save_out_of_stock(out_of_stock)
            save_notified_out_of_stock(notified_out_of_stock)
            save_notified_price_changes(notified_price_changes)
            
            # Update products cache (for immediate use if user asks)
            PRODUCTS_CACHE = {str(i+1): product for i, product in enumerate(current_products)}
            
            # Send notifications for new products (using the updated CHAT_ID)
            for product in new_products:
                code = product.get('code')
                if code and code not in notified_new_products:
                    # Check delivery for all monitor pins
                    delivery_info = await check_delivery_for_all_pins(code) 
                    message, image_url = format_product_info(product, delivery_info=delivery_info)
                    
                    try:
                        if image_url:
                            await application.bot.send_photo(
                                chat_id=CHAT_ID, # UPDATED
                                photo=image_url,
                                caption=f"🆕 <b>NEW PRODUCT ALERT!</b>\n\n{message}",
                                parse_mode='HTML'
                            )
                        else:
                            await application.bot.send_message(
                                chat_id=CHAT_ID, # UPDATED
                                text=f"🆕 <b>NEW PRODUCT ALERT!</b>\n\n{message}",
                                parse_mode='HTML'
                            )
                        
                        # Mark as notified
                        notified_new_products.add(code)
                        save_notified_new_products(notified_new_products)
                        
                        await asyncio.sleep(0.5) # Small delay
                    except Exception as e:
                        logger.error(f"Error sending new product notification: {e}")
            
            # Send notifications for removed products (using the updated CHAT_ID)
            for product in removed_products:
                code = product.get('code')
                product_name = product.get('name', 'Unknown Product')
                message = f"❌ <b>PRODUCT OUT OF STOCK!</b>\n\n"
                message += f"<b>{product_name}</b>\n"
                message += f"Code: {code}\n\n"
                message += f"This product is no longer available in the catalog."
                
                try:
                    await application.bot.send_message(
                        chat_id=CHAT_ID, # UPDATED
                        text=message,
                        parse_mode='HTML'
                    )
                    await asyncio.sleep(0.5) # Small delay
                except Exception as e:
                    logger.error(f"Error sending out of stock notification: {e}")
            
            # Send notifications for price changes (using the updated CHAT_ID)
            for product, old_price, new_price in price_changes:
                code = product.get('code')
                product_name = product.get('name', 'Unknown Product')
                message = f"💰 <b>PRICE CHANGE ALERT!</b>\n\n"
                message += f"<b>{product_name}</b>\n"
                message += f"Code: {code}\n\n"
                message += f"Old Price: {old_price}\n"
                message += f"New Price: {new_price}\n\n"
                message += f"<a href='https://www.sheinindia.in/p/{code}'>🔗 View on SHEIN</a>"
                
                try:
                    await application.bot.send_message(
                        chat_id=CHAT_ID, # UPDATED
                        text=message,
                        parse_mode='HTML'
                    )
                    await asyncio.sleep(0.5) # Small delay
                except Exception as e:
                    logger.error(f"Error sending price change notification: {e}")
            
            # Wait 5 seconds before next check (reduced frequency to avoid rate limiting)
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Error in catalog monitoring: {e}")
            await asyncio.sleep(30)  # Wait 30 seconds before retrying

# --- REVISED /n COMMAND HANDLER ---

async def deliverable_products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show only deliverable products to a specified pincode. 
    Defaults to 504231 if no pincode is provided.
    """
    
    # 2. Command modification: /n or /n <pincode>
    if context.args and re.match(r'^\d{6}$', context.args[0]):
        # /n <pincode> was typed
        target_pin_codes = [context.args[0]]
        pin_display = target_pin_codes[0]
    else:
        # /n was typed (or invalid pin) - use default
        target_pin_codes = [DEFAULT_PIN_CODE_N]
        pin_display = target_pin_codes[0]

    # Send initial message
    progress_message = await update.message.reply_text(
        f"🔍 Checking deliverable products for pin code: **{pin_display}**...\n\n"
        f"⚡ Using concurrent processing for maximum speed!",
        parse_mode='Markdown'
    )
    
    catalog_data = fetch_catalog()
    if not catalog_data:
        await progress_message.edit_text("❌ Failed to fetch products. Please try again later.\n\nIf this error persists, the cookies may have expired. Please update them in the script.")
        return
    
    products = catalog_data.get('products', [])
    if not products:
        await progress_message.edit_text("❌ No products found.")
        return
    
    # Update progress
    await progress_message.edit_text(
        f"🔍 Checking delivery for {len(products)} products to **{pin_display}**...\n\n"
        f"⚡ Processing with {executor._max_workers} concurrent workers!",
        parse_mode='Markdown'
    )
    
    deliverable_products = []
    checked_count = 0
    start_time = time.time()
    
    async def check_single_product_delivery_for_pin(product, index, total, pin_codes_to_check):
        """Check delivery for a single product against the list of pin codes"""
        code = product.get('code')
        if not code:
            return None
        
        try:
            delivery_info = await check_delivery_for_pins(code, pin_codes_to_check)
            
            # Check if product is deliverable to ANY of the pin codes in the list (in this case, just one pin)
            is_deliverable = any(info['serviceable'] for info in delivery_info.values())
            
            if is_deliverable:
                return (product, delivery_info)
        except Exception as e:
            logger.error(f"Error checking delivery for product {code}: {e}")
        
        return None

    # Process products in batches to avoid overwhelming the API
    batch_size = 5
    for batch_start in range(0, len(products), batch_size):
        batch_end = min(batch_start + batch_size, len(products))
        batch = products[batch_start:batch_end]
        
        # Create tasks for this batch
        tasks = []
        for i, product in enumerate(batch):
            task = asyncio.create_task(
                check_single_product_delivery_for_pin(product, batch_start + i, len(products), target_pin_codes)
            )
            tasks.append(task)
        
        # Wait for all tasks in this batch to complete
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result:
                    deliverable_products.append(result)
                checked_count += 1
                
                # Update progress every 5 products or every 2 seconds
                if checked_count % 5 == 0 or time.time() - start_time > 2:
                    elapsed = time.time() - start_time
                    rate = checked_count / elapsed if elapsed > 0 else 0
                    eta = (len(products) - checked_count) / rate if rate > 0 else 0
                    
                    await progress_message.edit_text(
                        f"🔍 Checking delivery for {len(products)} products to **{pin_display}**...\n\n"
                        f"✅ Checked: {checked_count}/{len(products)}\n"
                        f"📦 Deliverable: {len(deliverable_products)}\n"
                        f"⚡ Speed: {rate:.1f} products/sec\n"
                        f"⏱️ ETA: {eta:.1f} seconds",
                        parse_mode='Markdown'
                    )
            except Exception as e:
                logger.error(f"Error in task: {e}")
        
        # Small delay between batches to avoid rate limiting
        await asyncio.sleep(0.5)
    
    # Final progress update
    elapsed = time.time() - start_time
    await progress_message.edit_text(
        f"✅ Delivery check completed for **{pin_display}**!\n\n"
        f"📊 Total Products: {len(products)}\n"
        f"📦 Deliverable: {len(deliverable_products)}\n"
        f"⏱️ Time Taken: {elapsed:.1f} seconds\n"
        f"⚡ Average Speed: {len(products)/elapsed:.1f} products/sec",
        parse_mode='Markdown'
    )
    
    if not deliverable_products:
        await update.message.reply_text(f"❌ No products are deliverable to pin code **{pin_display}**.", parse_mode='Markdown')
        return
    
    # Store deliverable products in cache with indices
    global PRODUCTS_CACHE
    PRODUCTS_CACHE = {str(i+1): product for i, (product, _) in enumerate(deliverable_products)}
    
    # Send deliverable products
    await update.message.reply_text(f"📤 Sending {len(deliverable_products)} deliverable products for **{pin_display}**...", parse_mode='Markdown')
    
    for i, (product, delivery_info) in enumerate(deliverable_products):
        message, image_url = format_product_info(product, index=i, delivery_info=delivery_info)
        
        try:
            if image_url:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=image_url,
                    caption=message,
                    parse_mode='HTML'
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message,
                    parse_mode='HTML'
                )
            
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Error sending product {product.get('code')}: {e}")
    
    await update.message.reply_text(f"✅ All {len(deliverable_products)} deliverable products for **{pin_display}** sent! Use /checkdelivery <number> to check delivery again.", parse_mode='Markdown')

# --- REVISED CHECK DELIVERY COMMAND HANDLER ---

async def check_delivery_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check delivery availability for a product by number."""
    if not context.args:
        await update.message.reply_text("❌ Please provide a product number. Usage: /checkdelivery <number>\n\n💡 Use /products or /n first to see numbered products.")
        return
    
    product_number = context.args[0]
    
    # Check if products cache is populated
    if not PRODUCTS_CACHE:
        await update.message.reply_text("❌ No products cached. Please run /products or /n first.")
        return
    
    # Get product from cache
    product = PRODUCTS_CACHE.get(product_number)
    if not product:
        await update.message.reply_text(f"❌ Product #{product_number} not found. Please use /products or /n to see available products.")
        return
    
    code = product.get('code')
    progress_message = await update.message.reply_text(f"🔍 Checking delivery for product **#{product_number}** (*{code}*)...", parse_mode='Markdown')
    
    # Determine which pin codes to check:
    # 1. If the last /n command used a specific pin, we should keep that pin for reference. 
    # 2. Otherwise, check against the default MONITOR_PIN_CODES.
    
    # A simple way to handle this without full state management is to just check the monitor pins, 
    # but for a true representation of the /n list, we need the PIN_CODES used for the cached products.
    # Since the original script just checked MONITOR_PIN_CODES here anyway, we'll maintain that for simplicity:
    
    # The /n command now uses the `target_pin_codes` list, but that variable is local to `deliverable_products_command`.
    # A cleaner approach would be to check a set of relevant pins for /checkdelivery, let's use the MONITOR_PIN_CODES.
    delivery_info = await check_delivery_for_all_pins(code)

    message = f"📦 <b>Product #{product_number} - {product.get('name', 'Unknown')}</b>\n"
    message += f"Code: {code}\n\n"
    message += f"<b>🚚 Delivery Status:</b>\n"
    
    # The delivery info object keys are the pins checked (MONITOR_PIN_CODES for /checkdelivery)
    for pin_code, info in delivery_info.items():
        message += f"\n📍 <b>{pin_code}:</b>\n"
        message += f"Serviceable: {'✅ Yes' if info['serviceable'] else '❌ No'}\n"
        if info['serviceable']:
            message += f"Delivery Method: {info['delivery_method']}\n"
            message += f"COD Available: {'✅ Yes' if info['cod_eligible'] else '❌ No'}\n"
        else:
            if info['reason']:
                message += f"Reason: {info['reason']}\n"
    
    await progress_message.edit_text(message, parse_mode='HTML')

# --- OTHER COMMANDS (NO CHANGES NEEDED) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "🛍️ Welcome to SHEIN Catalog Bot!\n\n"
        "Commands:\n"
        "/products - View all products with delivery info (for pins 504231, 504231)\n"
        "/n - View only deliverable products for **504231** (FAST)\n"
        "/n <pincode> - View deliverable products for that specific pincode\n" # ADDED INFO
        "/checkdelivery <number> - Check delivery for product by number\n"
        "/status - Check monitoring status\n"
        "/reset - Reset notification tracking\n"
        "/help - Show this help message\n\n"
        "💡 Products are numbered for easy reference!\n"
        "🔔 Real-time monitoring is active to the group! You'll be notified of new products, out of stock items, and price changes!\n"
        "⚡ Optimized for speed with concurrent processing!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "🛍️ SHEIN Catalog Bot Commands:\n\n"
        "/products - View all products with delivery info (for pins 504231,504231)\n"
        "/n - View only deliverable products for **504231** (FAST)\n"
        "/n <pincode> - View deliverable products for that specific pincode\n" # ADDED INFO
        "/checkdelivery <number> - Check delivery for product by number\n"
        "/status - Check monitoring status\n"
        "/reset - Reset notification tracking\n"
        "/help - Show this help message\n\n"
        "💡 Use /products or /n first to see numbered products, then use /checkdelivery <number>\n"
        "🔔 Real-time monitoring is active to the group! You'll be notified of new products, out of stock items, and price changes!\n"
        "⚡ Optimized for speed with concurrent processing!"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check monitoring status."""
    existing_codes = load_product_codes()
    out_of_stock = load_out_of_stock()
    notified_out_of_stock = load_notified_out_of_stock()
    notified_new_products = load_notified_new_products()
    notified_price_changes = load_notified_price_changes()
    
    await update.message.reply_text(
        f"📊 <b>Monitoring Status</b>\n\n"
        f"✅ Active Products: {len(existing_codes)}\n"
        f"❌ Out of Stock: {len(out_of_stock)}\n"
        f"📢 Notified Out of Stock: {len(notified_out_of_stock)}\n"
        f"📢 Notified New Products: {len(notified_new_products)}\n"
        f"📢 Notified Price Changes: {len(notified_price_changes)}\n"
        f"🔄 Real-time Monitoring: Active\n"
        f"📍 Monitoring Pin Codes: {', '.join(MONITOR_PIN_CODES)}\n" # Changed to MONITOR_PIN_CODES
        f"👤 Notification Chat ID: {CHAT_ID} (Group/Channel)\n" # UPDATED
        f"⚡ Concurrent Processing: Enabled (10 workers)"
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset notification tracking files."""
    try:
        # Clear notification tracking files
        if os.path.exists(NOTIFIED_OUT_OF_STOCK_FILE):
            os.remove(NOTIFIED_OUT_OF_STOCK_FILE)
        if os.path.exists(NOTIFIED_NEW_PRODUCTS_FILE):
            os.remove(NOTIFIED_NEW_PRODUCTS_FILE)
        if os.path.exists(NOTIFIED_PRICE_CHANGES_FILE):
            os.remove(NOTIFIED_PRICE_CHANGES_FILE)
        
        await update.message.reply_text(
            "✅ <b>Notification tracking reset!</b>\n\n"
            "You will now receive notifications again for products that were previously notified."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error resetting notification tracking: {str(e)}")

# --- COMMANDS THAT WERE NOT MODIFIED ---
async def check_single_product_delivery(product, index, total):
    """Check delivery for a single product (used by /products)"""
    code = product.get('code')
    if not code:
        return None
    
    try:
        # Uses the monitor pins, same as before
        delivery_info = await check_delivery_for_all_pins(code) 
        
        # Check if product is deliverable to any of the monitor pin codes
        is_deliverable = any(info['serviceable'] for info in delivery_info.values())
        
        if is_deliverable:
            return (product, delivery_info)
    except Exception as e:
        logger.error(f"Error checking delivery for product {code}: {e}")
    
    return None

async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send all products one by one with images and delivery info (for MONITOR_PIN_CODES)."""
    # This remains largely the same, checking MONITOR_PIN_CODES
    progress_message = await update.message.reply_text(f"📦 Fetching all products and checking delivery for {', '.join(MONITOR_PIN_CODES)}...")
    
    catalog_data = fetch_catalog()
    if not catalog_data:
        await progress_message.edit_text("❌ Failed to fetch products. Please try again later.\n\nIf this error persists, the cookies may have expired. Please update them in the script.")
        return
    
    products = catalog_data.get('products', [])
    if not products:
        await progress_message.edit_text("❌ No products found.")
        return
    
    # Store products in cache with indices
    global PRODUCTS_CACHE
    PRODUCTS_CACHE = {str(i+1): product for i, product in enumerate(products)}
    
    await progress_message.edit_text(f"📤 Sending {len(products)} products...")
    
    for i, product in enumerate(products):
        delivery_info = await check_delivery_for_all_pins(product.get('code'))
        message, image_url = format_product_info(product, index=i, delivery_info=delivery_info)
        
        try:
            if image_url:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=image_url,
                    caption=message,
                    parse_mode='HTML'
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message,
                    parse_mode='HTML'
                )
            
            await asyncio.sleep(0.3)
            
            if (i + 1) % 5 == 0:
                await progress_message.edit_text(
                    f"📤 Sending {len(products)} products...\n"
                    f"✅ Sent: {i + 1}/{len(products)}"
                )
        except Exception as e:
            logger.error(f"Error sending product {product.get('code')}: {e}")
    
    await progress_message.edit_text(f"✅ All {len(products)} products sent! Use /checkdelivery <number> to check delivery again.")


async def post_init(application: Application) -> None:
    """Post-initialization function to start monitoring."""
    # Start the real-time monitoring task
    application.create_task(monitor_catalog_changes(application))

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("products", products_command))
    application.add_handler(CommandHandler("n", deliverable_products_command)) # REVISED HANDLER
    application.add_handler(CommandHandler("checkdelivery", check_delivery_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("reset", reset_command))
    
    # Initialize product codes file
    existing_codes = load_product_codes()
    if not existing_codes:
        catalog_data = fetch_catalog()
        if catalog_data:
            products = catalog_data.get('products', [])
            codes = set(product.get('code') for product in products if product.get('code'))
            save_product_codes(codes)
            
            for product in products:
                code = product.get('code')
                if code:
                    PREVIOUS_CATALOG[code] = product
            save_product_details(PREVIOUS_CATALOG)
    
    # Run the bot until you press Ctrl-C
    application.run_polling()

if __name__ == '__main__':
    main()
