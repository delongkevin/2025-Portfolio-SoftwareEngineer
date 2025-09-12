import os
import argparse
import logging
import base64
import chardet
import hashlib
import shutil
import re
import pandas as pd
from openpyxl import load_workbook
from bs4 import BeautifulSoup

# Allowed file types (for embedding in reports)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "txt", "html"}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Default Paths
DEFAULT_DESTINATION_PATH = os.getcwd()
EXCEL_REPORT_PATH = os.path.join(DEFAULT_DESTINATION_PATH, "Software_Test_Report.xlsx")

# Function: Detect File Encoding
def detect_encoding(file_path):
    with open(file_path, "rb") as f:
        raw_data = f.read(4096)
        result = chardet.detect(raw_data)
        return result["encoding"] if result["encoding"] else "utf-8"

# Function: Generate Unique Filename
def get_unique_filename(dest_dir, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename

    while os.path.exists(os.path.join(dest_dir, new_filename)):
        new_filename = f"{base}_{counter}{ext}"
        counter += 1

    return new_filename

# Function: Compute File Hash
def get_file_hash(file_path):
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()

# Function: Find HTML Files Recursively
def find_html_files_recursive(directory, matched_files=None):
    if matched_files is None:
        matched_files = set()

    if not os.path.exists(directory):
        logging.warning(f"Skipping non-existent path: {directory}")
        return matched_files

    try:
        for entry in os.scandir(directory):
            if entry.is_file() and entry.name.lower().endswith(".html"):
                matched_files.add(os.path.normpath(entry.path))
            elif entry.is_dir():
                find_html_files_recursive(entry.path, matched_files)
    except Exception as e:
        logging.error(f"Error searching in {directory}: {e}")

    return matched_files

# Function: Process Multiple Source Paths
def find_html_files(source_paths):
    if isinstance(source_paths, str):
        logging.error("Error: source_paths should be a list, not a string!")
        return []

    all_matched_files = set()
    for path in source_paths:
        all_matched_files.update(find_html_files_recursive(path))

    logging.info(f"Total unique HTML files found: {len(all_matched_files)}")
    return list(all_matched_files)

# Function: Copy & Embed Files (Logs & Images)
def copy_and_embed_files(source_paths, destination_path):
    """Copies and embeds logs and images into the report."""
    
    image_tags, text_content = "", ""
    copied_files = []
    embedded_hashes = set()

    if not os.path.exists(destination_path):
        os.makedirs(destination_path)

    for source_path in source_paths:
        if not os.path.exists(source_path):
            logging.warning(f"Skipping non-existent path: {source_path}")
            continue

        for root, _, files in os.walk(source_path):
            for filename in files:
                file_ext = filename.lower().split(".")[-1]

                if file_ext not in ALLOWED_EXTENSIONS:
                    continue  

                src_file = os.path.join(root, filename)
                dest_dir = os.path.join(destination_path, os.path.relpath(root, source_path))
                os.makedirs(dest_dir, exist_ok=True)

                unique_filename = get_unique_filename(dest_dir, filename)
                dest_file = os.path.join(dest_dir, unique_filename)

                try:
                    shutil.copy2(src_file, dest_file)

                    if os.path.exists(dest_file):
                        file_hash = get_file_hash(dest_file)
                        if file_hash in embedded_hashes:
                            continue

                        embedded_hashes.add(file_hash)
                        copied_files.append(dest_file)

                        if file_ext in ["png", "jpg", "jpeg", "gif"]:
                            with open(dest_file, "rb") as img_file:
                                base64_str = base64.b64encode(img_file.read()).decode('utf-8')
                                mime_type = f"image/{file_ext}"
                                image_tags += f'<img src="data:{mime_type};base64,{base64_str}" alt="{unique_filename}" style="max-width: 100%; display: block; margin: 10px 0;"><br>\n'

                        elif file_ext in ["txt", "html"]:
                            encoding = detect_encoding(dest_file)
                            with open(dest_file, "r", encoding=encoding, errors="replace") as txt_file:
                                text_content += f"<h3>{unique_filename}</h3><pre>{txt_file.read()}</pre><br>"

                except Exception as e:
                    logging.error(f"Failed to copy {src_file} to {dest_file}: {e}")

    return text_content, image_tags, copied_files

# Function: Extract Summary Data
def extract_summary_data(soup):
    """Extracts statistics from the OverviewTable in the HTML."""
    statistics_table = soup.find("table", class_="OverviewTable")
    return f"<h2>Test Statistics</h2>{str(statistics_table)}" if statistics_table else "<p><b>No statistics found.</b></p>"

# Function: Extract Failed Tests
def extract_failed_tests(soup):
    failed_tests = [str(row) for table in soup.find_all("table") for row in table.find_all("tr") if "fail" in row.get_text(strip=True).lower()]
    return f"<h2>Failed Tests</h2><table>{''.join(failed_tests)}</table>" if failed_tests else "<p><b>No failed tests found.</b></p>"

# Function: Extract Keyword Data
def extract_keyword_from_tables(soup, keyword):
    keyword_lower = keyword.lower()
    extracted_rows = [str(row) for table in soup.find_all("table") for row in table.find_all("tr") if any(keyword_lower in cell.get_text(strip=True).lower() for cell in row.find_all(["th", "td"]))]
    return f"<h2>Keyword Matches: '{keyword}'</h2><table>{''.join(extracted_rows)}</table>" if extracted_rows else "<p><b>No keyword matches found.</b></p>"

# **Main Function**
def main():
    parser = argparse.ArgumentParser(description="Generate an HTML report with extracted test data, failures, logs, and images.")
    parser.add_argument('--source_paths', type=str, nargs='+', default=[os.getcwd()], help="List of source directories.")
    parser.add_argument('--destination_path', type=str, default=DEFAULT_DESTINATION_PATH, help="Destination path for copied files.")
    parser.add_argument('--keyword', type=str, default="Evaluate response", help="Keyword to search for in reports.")

    args = parser.parse_args()

    # Find all HTML files in the source directories
    found_html_files = find_html_files(args.source_paths)

    if not found_html_files:
        logging.warning("No HTML report files found.")
        return

    # Generate the HTML report
    generate_html_report(found_html_files, args.source_paths, args.destination_path, args.keyword)

    logging.info("HTML Report generation complete.")

if __name__ == '__main__':
    main()
