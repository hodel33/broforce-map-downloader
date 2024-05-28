"""
BROFORCE MAP DOWNLOADER

The Broforce Map Downloader is perfect for those of you who've purchased Broforce from a platform other than Steam
or simply wish to play custom maps offline. This Python application automates the process of downloading and 
organizing user-created maps based on specified filters such as gameplay type, difficulty level, time period and rating. 

God speed Broforce!
© 2024 Hodel33 - https://github.com/hodel33  
"""

# Built-in libraries
import random as rd
import time
import re
import os
from pathlib import Path
import configparser
from collections import defaultdict
import xml.etree.ElementTree as ET

# Third-party libraries -> requirements.txt
import requests
from bs4 import BeautifulSoup


# Broforce's Steam app ID
app_id = 274190  

# Directory for storing maps
maps_directory = Path('maps')
maps_directory.mkdir(parents=True, exist_ok=True) # Create the directory for storing maps if it doesn't already exist

# Config file for storing settings
config_file = 'config.ini'

# Mapping gameplay_types, difficulty_levels and time_periods to their corresponding characters
gameplay_types_map = {'1': 'Standard', '2': 'Puzzle', '3': 'Story', '4': 'Experimental', '5': 'Challenge', '6': 'Deathmatch'}
difficulty_levels_map = {'1': 'Normal', '2': 'Challenging', '3': 'Brotal'}
time_periods_map = {'-1': 'All Time', '1': 'Today', '7': '1 Week', '90': '3 Months', '180': '6 Months', '365': '1 Year'}


def clean_cfg_string(s):
    """
    Clean a string by stripping whitespace and removing duplicate characters.
    """
    return "".join(sorted(set(s.strip())))

def create_default_config(file_path):
    """
    Create a default configuration file with preset values and detailed comments.
    """
    config_content = """
[Settings]

# Number of pages to process
number_of_pages = 3

# Number of items per page (9, 18, 30)
maps_per_page = 18

# Time period in days (-1, 1, 7, 90, 180, 365), -1 = All Time
time_period = -1

# Gameplay types to include (see below)
gameplay_types = 135

# Difficulty levels to include (see below)
difficulty_levels = 1

# Gameplay Type
# ----------------------
# 1 - Standard
# 2 - Puzzle
# 3 - Story
# 4 - Experimental
# 5 - Challenge
# 6 - Deathmatch

# Difficulty
# ----------------------
# 1 - Normal
# 2 - Challenging
# 3 - Brotal
    """
    with open(file_path, 'w') as configfile:
        configfile.write(config_content.strip())
    print("Default configuration created at:", file_path)

def load_and_validate_config(config_file):
    """
    Load and validate the configuration values from the given file.
    Check if the file exists, and create a default if it doesn't.
    """
    if not Path(config_file).exists():
        create_default_config(config_file)

    config = configparser.ConfigParser()
    config.read(config_file)

    # Load values as strings
    number_of_pages = config.get('Settings', 'number_of_pages') # Number of pages to process
    maps_per_page = config.get('Settings', 'maps_per_page') # Number of items per page (9, 18, 30)
    time_period = config.get('Settings', 'time_period') # Time period in days (-1, 1, 7, 90, 180, 365), -1 = of all time
    gameplay_types_str = clean_cfg_string(config.get('Settings', 'gameplay_types')) # Gameplay types to include
    difficulty_levels_str = clean_cfg_string(config.get('Settings', 'difficulty_levels')) # Difficulty levels to include

    # Check number_of_pages
    if not number_of_pages.isdigit() or int(number_of_pages) <= 0:
        raise ValueError("Invalid number_of_pages in config (must be a positive number)")
    number_of_pages = int(number_of_pages)

    # Check maps_per_page
    if maps_per_page not in {'9', '18', '30'}:
        raise ValueError("Invalid maps_per_page in config (must be one of the following values: 9, 18, 30)")
    maps_per_page = int(maps_per_page)

    # Check time_period
    if time_period not in {'-1', '365', '180', '90', '7', '1'}:
        raise ValueError("Invalid time_period in config (must be one of the following values: -1, 1, 7, 90, 180, 365)")
    time_period = int(time_period)

    # Check gameplay_types_str
    if not all(char in gameplay_types_map for char in gameplay_types_str):
        raise ValueError("Invalid gameplay_type in config (check config.ini for info)")
    gameplay_types = {char: gameplay_types_map[char] for char in gameplay_types_str}

    # Check difficulty_levels_str
    if not all(char in difficulty_levels_map for char in difficulty_levels_str):
        raise ValueError("Invalid difficulty_level in config (check config.ini for info)")
    difficulty_levels = {char: difficulty_levels_map[char] for char in difficulty_levels_str}

    return number_of_pages, maps_per_page, time_period, gameplay_types, difficulty_levels

def fetch_all_map_urls():
    """
    Fetch all possible map URLs based on specified parameters.
    """
    filter_base_url = f'https://steamcommunity.com/workshop/browse/?appid={app_id}&browsesort=trend&section=readytouseitems&actualsort=trend&p={{}}&days={time_period}&numperpage={maps_per_page}'

    all_map_urls = []
    # Get list of existing maps (workshop IDs)
    existing_workshop_ids = get_existing_workshop_ids(maps_directory)

    print(f"\n\n")
    print(f"************      FETCHING URLS      ************")
    print()

    # Cycle through each gameplay type and difficulty
    for gameplay_key, gameplay_value in gameplay_types.items():
        for difficulty_key, difficulty_value in difficulty_levels.items():

            # Modify the URL to filter by gameplay type and difficulty
            base_url = f'{filter_base_url}&requiredtags[]={difficulty_value}&requiredtags[]={gameplay_value}'

            for page in range(1, number_of_pages + 1):
                print(f"\n------   {gameplay_value} - {difficulty_value} - Page {page}   ------\n")

                try:
                    response = _try_request(base_url.format(page))
                    if response.status_code != 200:
                        print(f"Failed to fetch page {page}.  Status code: {response.status_code}\n")
                        continue
                except requests.exceptions.RequestException as e:
                    print(f"Failed to fetch page {page}. Error: {e}\n")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.find_all('div', class_='workshopItem')

                # Check if the page is empty and break the loop if true
                if not items:
                    print(f"No items found on Page {page}, skipping remaining pages for {gameplay_value} - {difficulty_value}")
                    break

                for item in items:
                    link = item.find('a', href=True)
                    title_tag = item.find('div', class_='workshopItemTitle ellipsis')
                    rating_img = item.find('img', class_='fileRating')
                    if link and title_tag and rating_img:
                        workshop_id = link['href'].split('id=')[1].split('&')[0]
                        if workshop_id in existing_workshop_ids:
                            print(f"Skipping already downloaded map: {workshop_id} - {title_tag.text.strip()}")
                            continue
                        print(f"Fetching the URL for map: {workshop_id} - {title_tag.text.strip()}")
                        title = title_tag.text.strip()
                        star_rating = extract_star_rating(rating_img['src'])
                        filename_prefix = f'{gameplay_key}{difficulty_key}{star_rating}'
                        download_url = f'http://steamworkshop.download/download/view/{workshop_id}'
                        all_map_urls.append((download_url, title, filename_prefix, workshop_id))

    return all_map_urls

def download_all_maps(all_map_urls):
    """
    Download all maps from the collected URLs.
    """
    total_maps = len(all_map_urls)
    successfully_downloaded_maps = 0

    print(f"\n\n")
    print(f"************      DOWNLOADING MAPS      ************")
    print(f"\n")

    for index, (download_url, title, filename_prefix, workshop_id) in enumerate(all_map_urls, start=1):
        print(f"[{index}/{total_maps}] Downloading map: {workshop_id} - {title}")
        success = download_map(maps_directory, download_url, title, filename_prefix, workshop_id)
        if success:
            successfully_downloaded_maps += 1
        time.sleep(rd.randint(1, 2))
    
    return successfully_downloaded_maps

def extract_star_rating(image_url):
    """
    Extract the star rating from the image URL.
    """
    match = re.search(r'(\d+)-star\.png', image_url)
    if match:
        return match.group(1)  # Return the digits found
    return '0'  # Return '0' if no matching pattern is found

def download_map(maps_directory, url, title, filename_prefix, workshop_id):
    """
    Download a map given its URL and metadata.
    """
    safe_title = " ".join(title.split()) # Normalize spaces
    safe_title = safe_title.replace(":", " -") # Replace colons with hyphens
    safe_title = "".join(x for x in safe_title if x not in '"\/*?<>|') # Remove any other illegal characters from the filename

    # Fetch the page to get the file extension and actual download link
    try:

        intermediate_response = _try_request(url)
    
        if intermediate_response.status_code == 200:

            soup = BeautifulSoup(intermediate_response.text, 'html.parser')

            # Search for all text that contains 'Filename:'
            texts = soup.find_all(string=re.compile(r"Filename:"))
            file_extension = None
            for text in texts:
                if "Filename:" in text:
                    # Extract the part after the last period which is typically the file extension
                    file_extension = text.split('.')[-1].strip()
                    if file_extension:
                        # Optional: validate the extracted extension to ensure it is plausible
                        if not re.match(r'^[a-zA-Z0-9]+$', file_extension):
                            print(f"Unusual file extension '{file_extension}' detected, skipping.\n")
                            file_extension = None
                            continue
                        break
            if file_extension is None:
                print("Filename with extension not found.")
                return False

            download_link = soup.find('a', string=re.compile(r"^Download:"))
            if download_link:
                filename = f'{filename_prefix}-{workshop_id}-{safe_title}.{file_extension}'
                full_path = maps_directory / filename
                return download_file(download_link['href'], full_path)
            else:
                print(f"Download link not found on the page.\n")
                return False
        else:
            print(f"Failed to fetch intermediary page. Status code: {intermediate_response.status_code}\n")
            return False

    except requests.exceptions.RequestException as e:
        print(f"{str(e)}\n")
        return False

def download_file(download_url, full_path):
    """
    Download a file from the specified URL to the given path with retry logic.
    """
    try:
        response = _try_request(download_url)
        if response.status_code == 200:
            with open(full_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            print(f"> {full_path} downloaded successfully!\n")
            return True
        else:
            print(f"Failed to download from {download_url}. Status code: {response.status_code}\n")
            return False

    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Error during download from {download_url}: {str(e)}\n")

def get_existing_workshop_ids(directory):
    """
    Retrieve the list of existing workshop IDs from the specified directory.
    """
    existing_ids = []
    # Walk through all directories and files within 'maps_directory'
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            filename = file_path.name
            parts = filename.split('-') # Assuming the filename format is "XYZ-123456789-Map Title.bfx"
            if len(parts) > 1 and parts[1].isdigit():
                existing_ids.append(parts[1])
    return existing_ids

def _try_request(url, max_retries=4, delay=3, timeout=9):
    """
    Attempt an HTTP GET request with retries and exponential backoff.
    """
    last_response = None
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, stream=True, timeout=timeout)
            if response.status_code == 200:
                return response
            else:
                last_response = response
                if attempt < max_retries:
                    time.sleep(delay * (2 ** (attempt - 1)))

        except requests.exceptions.RequestException as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(delay * (2 ** (attempt - 1)))

    if isinstance(last_response, requests.Response):
        return last_response

    if last_exception:
        raise last_exception
    
def print_main_header():

    clear_terminal = "cls" if os.name == "nt" else "clear" # "nt" (windows), "posix" (linux/mac) / Ternary conditional operator
    os.system(clear_terminal)

    print("\033[38;5;133m") # setting a new color for the header

    print(f'''        
░█▀▄░█▀▄░█▀█░█▀▀░█▀█░█▀▄░█▀▀░█▀▀░░░█▄█░█▀█░█▀█░░░█▀▄░█▀█░█░█░█▀█░█░░░█▀█░█▀█░█▀▄░█▀▀░█▀▄
░█▀▄░█▀▄░█░█░█▀▀░█░█░█▀▄░█░░░█▀▀░░░█░█░█▀█░█▀▀░░░█░█░█░█░█▄█░█░█░█░░░█░█░█▀█░█░█░█▀▀░█▀▄
░▀▀░░▀░▀░▀▀▀░▀░░░▀▀▀░▀░▀░▀▀▀░▀▀▀░░░▀░▀░▀░▀░▀░░░░░▀▀░░▀▀▀░▀░▀░▀░▀░▀▀▀░▀▀▀░▀░▀░▀▀░░▀▀▀░▀░▀
© 2024 Hodel33
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
          ''')
    print(f"\033[0;0m") # resets the color + new line after showing the whole list

def display_settings_header():

    print(f"************      SETTINGS      ************")
    print()

def display_settings_info():

    print(f"Number of Pages: {number_of_pages}")
    print(f"Maps Per Page: {maps_per_page}")
    print(f"Time Period: {time_periods_map[str(time_period)]}")
    print(f"Gameplay Type(s): {', '.join(gameplay_types.values())}")
    print(f"Difficulty Level(s): {', '.join(difficulty_levels.values())}")

    user_input = input(f"\n\nPress ENTER to start downloading the maps (q + ENTER to exit): ").strip().lower()
    if user_input == 'q':
        exit()

def organize_files(directory):
    """
    Organize files into directories based on their rating and extension (bfg).
    """
    # Create target directories if they do not exist
    target_directories = {
        '5': directory / '5 Stars',
        '4': directory / '4 Stars',
        '3-': directory / '3 Stars and less',
        'non-bfg': directory / 'non-bfg'
    }

    for folder in target_directories.values():
        folder.mkdir(exist_ok=True)

    # Function to determine the appropriate folder based on star rating
    def get_target_folder(file_name):

        # Put all maps which doesn't have .bfg as extension in a different folder
        if not file_name.endswith('.bfg'):
            return target_directories['non-bfg']
        
        parts = file_name.split('-')
        if len(parts) > 2 and parts[0]:
            star_rating = parts[0][-1]  # Last character of the first part
            return target_directories.get(star_rating, target_directories['3-'])
        return None

    # Move files into the appropriate folders
    for file_path in directory.iterdir():
        if file_path.is_file():
            target_folder = get_target_folder(file_path.name)
            if target_folder:
                file_path.rename(target_folder / file_path.name)

def process_duplicates(directory, duplicate_maps):
    """
    Process duplicate files by moving duplicates to a specified folder and writing their details to a text file.
    """
    # Create the 'duplicates' directory if it doesn't already exist
    duplicates_dir = directory / 'duplicates'
    duplicates_dir.mkdir(exist_ok=True)

    duplicates_info = []
    for (map_name, author), files in duplicate_maps.items():
        files_sorted = sorted(files, key=lambda x: int(x[0]), reverse=True)  # Sort by ID in descending order
        main_file = files_sorted[0]

        duplicates_info.append((map_name, author, 'Main', main_file[0], main_file[1]))
        for file in files_sorted[1:]:
            file_id, file_size, filepath = file  # Unpack file details
            # Move duplicate files to the duplicates folder
            file[2].rename(duplicates_dir / filepath.name)
            duplicates_info.append((map_name, author, 'Dupl', file_id, file_size))

    # Sort duplicates_info by map_name and then by author
    duplicates_info.sort(key=lambda x: (x[0], x[1]))

    # Write duplicates info to @duplicates.txt
    duplicates_txt_path = duplicates_dir / '@duplicates.txt'
    with open(duplicates_txt_path, 'w', encoding='utf-8') as f:
        current_map_name = None
        current_author = None
        for map_name, author, status, map_id, size in duplicates_info:
            if map_name != current_map_name or author != current_author:
                if current_map_name is not None:
                    f.write("\n")
                current_map_name = map_name
                current_author = author
                f.write(f"'{map_name}' by {author}\n")
            f.write(f"{status} - ID {map_id} - Size (B) {size}\n")


def list_duplicate_maps(directory):
    """
    Scans for .bfg files in a directory and identifies duplicates by name and size, returning a dictionary with map names and file sizes.
    """
    map_details = defaultdict(list)
    duplicates = {}

    # Use rglob to recursively search for all files
    for filepath in directory.rglob('*.bfg'):  # This ensures only .bfg files are considered
        filename = filepath.stem  # Get the filename without the extension
        parts = filename.split('-')
        if len(parts) > 2:
            map_id = parts[1]  # Assuming the ID is always the second part
            map_name = '-'.join(parts[2:])  # Combine everything after the second dash
            file_size = filepath.stat().st_size  # Get file size in bytes
            
            # Extract author info from the file
            file_info = extract_info_from_bfg(filepath)
            author = file_info.get('author', '<unknown>')  # Use '<unknown>' if author not found
            
            map_details[(map_name, author)].append((map_id, file_size, filepath))

    # Identify duplicates and collect their IDs
    for (map_name, author), ids in map_details.items():
        if len(ids) > 1:
            duplicates[(map_name, author)] = ids

    return duplicates

def extract_info_from_bfg(file_path):
    """
    Extracts information from a .bfg map file.
    """
    start_tag = b'<?xml'
    end_tag = b'</CampaignHeader>'
    chunk_size = 1024  # Adjust as needed to ensure the entire XML is captured

    with open(file_path, 'rb') as file:
        content = file.read(chunk_size)
    
    xml_start_index = content.find(start_tag)
    xml_end_index = content.find(end_tag) + len(end_tag)
    
    if xml_start_index == -1 or xml_end_index == -1:
        # raise ValueError(f"Invalid .bfg file format: XML header not found in file {file_path}")
        return {}  # Return empty info if XML header not found

    xml_content = content[xml_start_index:xml_end_index].decode('utf-8', errors='ignore')

    # Parse the XML content
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        # raise ValueError(f"XML parsing error in file {file_path}: {e}")
        return {}  # Return empty info if XML parsing fails

    tags = ['name', 'author', 'description', 'length', 'md5', 'hasBrotalityScoreboard', 'hasTimeScoreBoard', 'gameMode']
    info = {tag: (root.find(tag).text if root.find(tag) is not None else '') for tag in tags}

    return info

if __name__ == '__main__':

    print_main_header()
    display_settings_header()
    
    try:
        number_of_pages, maps_per_page, time_period, gameplay_types, difficulty_levels = load_and_validate_config(config_file) # Assign the validated config vars
    except ValueError as e:
        print(f"Error: {e}")
        input(f"\n\nPlease correct the Config file and restart the program. Press ENTER to exit: ")
        exit()

    display_settings_info()
    
    all_map_urls = fetch_all_map_urls()
    if not all_map_urls:
        print(f"\n")
        print(f"************      NO NEW MAPS      ************")
        print(f"\n\nThere are no new maps found to download.\n")
        input(f"\nPlease update the settings in the Config file and restart the program. Press ENTER to exit: ")
        exit()

    successfully_downloaded_maps = download_all_maps(all_map_urls)

    # Organize files into directories based on their rating and extension (bfg)
    organize_files(maps_directory)

    # Get duplicate maps info
    duplicate_maps = list_duplicate_maps(maps_directory)

    # Process duplicate maps
    process_duplicates(maps_directory, duplicate_maps)

    print(f"\n")
    print(f"************      DOWNLOAD COMPLETE      ************")
    print(f"\n\n{successfully_downloaded_maps} map(s) were successfully downloaded.\n")
    input(f"\nGod speed Broforce! Press ENTER to exit and start kicking some ass: ")