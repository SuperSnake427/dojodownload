###################################################################################################
#
# Download Class Dojo Feed
#
# Drew Hall (drewahall@gmail.com)
#
# Based on code by kecebongsoft (https://gist.github.com/dedy-purwanto/6ad1fa7c702981f35f25da780c50914d)
#
# Revision History:
#   - 26 Aug 2023 - Modified to only pull data after a particular date, added multi-threading to 
#                   speed up the downloads, changed file naming format to organize photos from multiple 
#                   classes/children, general refactoring
#
#
# Notes:
#   - You need to get the session cookie from Chrome to set dojo_log_session_id, dojo_login.sid, and dojo_home_login.sid
#     follow this guide https://stackoverflow.com/questions/12908881/how-to-copy-cookies-in-google-chrome
#   - JSON scheme:
#       - _items{}: 
#           - 0:
#               - contents:
#                   - attachments
#               - time:
#       - _links
#           - prev
#           - next
#
###################################################################################################
import requests
import json
from tqdm import tqdm
from pathlib import Path
import concurrent.futures
from datetime import datetime


##########################
##   Global Variables   ##
##########################
FEED_URL = 'https://home.classdojo.com/api/storyFeed?includePrivate=true'
DESTINATION = r'./classdojo_output'

SESSION_COOKIES = {                     # Credentials from your browser (look in the cookies)
    'dojo_log_session_id': '',
    'dojo_login.sid': '',
    'dojo_home_login.sid': ''}
NUM_JOBS = 10                           # Number of parallel downloads
AFTER_DATE = '1-Jul-2018'               # Only download content after this date


##########################
##      Functions       ##
##########################
def save_json(json_content: dict, filename: Path):
    '''
    Dump the contents to a JSON file

    Parameters:
        - json_content: dictionary with JSON data to save

    Returns:

    '''
    # Make the folder if it does not exist
    filename.parents[0].mkdir(parents=True, exist_ok=True)

    # Write/Overwrite the file
    with open(filename, 'w') as f: 
        f.write(json.dumps(json_content, indent=4))

def load_json(filename: Path) -> dict:
    '''
    Load the items from a JSON file

    Parameters:
        - filename: path to datafile
    
    Results:
        - items array
    '''
    with open(filename, 'r') as f:
        items = json.loads(f.read())

    return items

def get_items(url: str) -> (list[dict], str):
    '''
    Open a classdojo story and return the prev link (for traversing) and an array of items (possibly with attachments)

    Parameters:
        - url: hyperlink to the classdojo feed

    Returns:
        - 

    '''
    print(f'Fetching items: {url}..')
    resp = requests.get(url, cookies=SESSION_COOKIES)
    data = resp.json()

    # Get the link to the previous item
    prev = data.get('_links', {}).get('prev', {}).get('href')

    # Return a list of items
    return data['_items'], prev

def scrape(feed_url: str, filename: Path) -> list[dict]:
    '''
    Get the links from the ClassDojo feed and save the results in a JSON file

    Parameters:
        - feed_url: starting URL

    Results:
        - list of items to parse

    '''
    items, prev = get_items(feed_url)

    # ClassDojo feed is a circular list, follow it until you get back to the feed
    while prev and feed_url != prev:
        new_items, prev = get_items(prev)
        items.extend(new_items)

    # Save the data to a JSON file
    save_json(items, filename)

    return items

def get_urls(items: dict, after_date=None) -> list[tuple[str, str]]:
    '''
    Get the links from the ClassDojo feed and save the results in a JSON file

    Parameters:
        - feed_url: starting URL
        - after_date: Date after which to downloaded content, None to download everything 

    Results:
        - list of tuples (URL, filename)

    '''
    urls = []

    if after_date:
        dt = datetime.strptime(after_date, '%d-%b-%Y')

    for item in items:
        # Check to see if we need to add it or not based on the date
        dt_item = datetime.strptime(item['time'], '%Y-%m-%dT%H:%M:%S.%fZ')
        dt_str = dt_item.strftime('%m-%d-%Y')
        if not after_date or (dt_item > dt):
            # See if it has any attachments
            if attachments := item['contents'].get('attachments', {}):
                group = item['headerSubtext'].replace('/', '_')
                for attachment in attachments:
                    url = attachment['path']
                    # Use the existing filename if present, otherwise
                    if 'metadata' in attachment.keys() and 'filename' in attachment['metadata'].keys():  
                        filename = attachment['metadata']['filename']
                    else:
                        filename = get_name_from_url(url)

                    urls.append((url, f'{DESTINATION}/{group}/{dt_str}-{filename}'))
                
    return urls

def get_name_from_url(url: str) -> str:
    '''
    Get the filename from the url

    Parameters:
        - url: hyperlink with filename to download

    Results:
        - filename
    '''
    parts = url.split('/')
    return '_'.join(parts[3:]).replace('-', '_')

def download_urls(urls: list[tuple[str, str]]):
    '''
    Download items multithreaded

    Parameters:
        - urls: list of urls

    Results:

    '''
    # Create a progress bar
    with tqdm(total = len(urls)) as pbar:
        # Create a threadpool
        with concurrent.futures.ProcessPoolExecutor(max_workers = NUM_JOBS) as executor:
            futures = {executor.submit(download, url=url[0], filename=Path(url[1])): url for url in urls}

            # Track the progress
            for _ in concurrent.futures.as_completed(futures):
                pbar.update(1)
        
def download(url: str, filename: Path):
    '''
    Download a file

    Parameters:
        - link: url to download file
        - filemane: filename 
    
    Results:
        
    '''
    #print(f'Downloading {url} -> {filename}')
    
    # Create the folder if it does not exist
    filename.parents[0].mkdir(parents=True, exist_ok=True)

    with open(filename, 'wb') as f:
        resp = requests.get(url, cookies=SESSION_COOKIES)
        f.write(resp.content)

def main():
    data_file = Path(f'{DESTINATION}/data.json')

    # Scrape the website or load from disk
    if data_file.exists() and input('File exists! Rescrape? [Y/n]').upper() == 'N':
        items = load_json(data_file)
    else:
        items = scrape(FEED_URL, data_file)

    # Get a list of files to download
    urls = get_urls(items, AFTER_DATE)

    # Download!
    download_urls(urls)
    print('Done!')

if __name__ == '__main__':
    main()