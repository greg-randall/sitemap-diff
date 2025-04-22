#!/usr/bin/env python3
"""
Spider all sitemaps for a site, cache them locally,
and dump every page URL with its source sitemap.

Usage:
    ./sitemap_spider.py https://example.com
    ./sitemap_spider.py https://example.com --verbose
    ./sitemap_spider.py https://example.com --quiet
"""

import argparse
import datetime
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Set, Optional, NamedTuple
from urllib.parse import urlparse, quote

import requests
import tldextract
import pandas as pd
from usp.tree import sitemap_tree_for_homepage
from tqdm import tqdm


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Silence noisy usp logger
logging.getLogger('usp').setLevel(logging.ERROR)

# Create a custom logger for stats that should show in quiet mode
def log_stat(message: str) -> None:
    """Log a statistic that should be visible even in quiet mode."""
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} - {message}")


class UrlStatus(Enum):
    """Status of a URL in diff comparison."""
    NEW = 'new'
    DELETED = 'deleted'


class UrlDiff(NamedTuple):
    """Result of comparing URLs between runs."""
    new_urls: Set[str]
    deleted_urls: Set[str]


@dataclass
class SiteConfig:
    """Configuration for a site to be spidered."""
    url: str
    base_url: str
    domain: str
    suffix: str
    domain_dir: Path
    output_dir: Path
    timestamp: str = field(default_factory=lambda: str(int(datetime.datetime.now().timestamp())))

def setup_site_config(url: str) -> SiteConfig:
    """
    Create site configuration from URL.
    
    Args:
        url: Site URL
        
    Returns:
        SiteConfig object
    """
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    ext = tldextract.extract(base_url)
    timestamp = str(int(datetime.datetime.now().timestamp()))
    
    # Include subdomain in folder name if it exists
    if ext.subdomain:
        domain_dir = Path(f"{ext.subdomain}.{ext.domain}.{ext.suffix}")
    else:
        domain_dir = Path(f"{ext.domain}.{ext.suffix}")
        
    output_dir = domain_dir / timestamp
    
    return SiteConfig(
        url=url,
        base_url=base_url,
        domain=ext.domain,
        suffix=ext.suffix,
        domain_dir=domain_dir,
        output_dir=output_dir,
        timestamp=timestamp
    )


def format_timestamp(unix_timestamp: str) -> str:
    """
    Convert Unix timestamp to a human-readable datetime string in local time.
    
    Args:
        unix_timestamp: Unix timestamp as string
        
    Returns:
        Formatted datetime string like '4/22/2025 10:39:23am'
    """
    # Convert Unix timestamp string to integer
    timestamp = int(unix_timestamp)
    
    # Convert to datetime (in UTC)
    dt_utc = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    
    # Convert to local time
    dt_local = dt_utc.astimezone()
    
    # Format for different platforms (handle both Unix and Windows format codes)
    try:
        # Try Unix-style format first (no leading zeros)
        date_part = dt_local.strftime("%-m/%-d/%Y")
        time_part = dt_local.strftime("%-I:%M:%S%p").lower()
    except ValueError:
        # Fall back to Windows-style format
        try:
            date_part = dt_local.strftime("%#m/%#d/%Y")
            time_part = dt_local.strftime("%#I:%M:%S%p").lower()
        except ValueError:
            # Last resort: use standard format and remove leading zeros manually
            date_part = dt_local.strftime("%m/%d/%Y").replace('/0', '/').lstrip('0')
            time_part = dt_local.strftime("%I:%M:%S%p").lower().lstrip('0')
    
    return f"{date_part} {time_part}"


def get_sitemap_nodes(tree, base_url: str) -> List:
    """
    Get sitemap nodes, filtering out robots.txt and homepage URLs.
    
    Args:
        tree: Sitemap tree
        base_url: Base URL of the site
        
    Returns:
        List of filtered sitemap nodes
    """
    # Normalize base URL with and without trailing slash
    base_url_variants = [base_url]
    if base_url.endswith('/'):
        base_url_variants.append(base_url[:-1])
    else:
        base_url_variants.append(base_url + '/')
    
    return [
        node for node in tree.all_sitemaps() 
        if not node.url.lower().endswith('/robots.txt') and
        node.url not in base_url_variants
    ]


def download_file(session: requests.Session, url: str, dest_path: Path) -> bool:
    """
    Download a file and save it to the destination path.
    
    Args:
        session: Requests session
        url: URL to download
        dest_path: Destination path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with session.get(url, timeout=30) as resp:
            resp.raise_for_status()
            dest_path.write_bytes(resp.content)
        return True
    except requests.RequestException as e:
        logging.error(f"Failed to download {url}: {e}")
        return False


def download_sitemaps(nodes: List, out_dir: Path) -> None:
    """
    Download each sitemap file and save to output directory.
    
    Args:
        nodes: List of sitemap nodes
        out_dir: Directory to save sitemaps
    """    
    # Track errors to report after the progress bar completes
    errors = []
    
    with requests.Session() as session:
        progress_bar = tqdm(nodes, desc="Downloading sitemaps")
        for node in progress_bar:
            url = node.url
            safe_name = quote(url, safe='')
            dest = out_dir / safe_name
            
            try:
                with session.get(url, timeout=30) as resp:
                    resp.raise_for_status()
                    dest.write_bytes(resp.content)
            except requests.RequestException as e:
                # Store error instead of printing immediately
                errors.append(f"Failed to download {url}: {e}")
    
    # Display errors after progress bar is complete
    if errors:
        logging.info(f"Encountered {len(errors)} errors during download:")
        for error in errors:
            logging.error(error)


def extract_url_map(nodes: List) -> Dict[str, str]:
    """
    Map each page URL to its sitemap.xml source.
    
    Args:
        nodes: List of sitemap nodes
        
    Returns:
        Dictionary mapping page URLs to their source sitemap URLs
    """
    return {
        page.url: node.url
        for node in nodes
        for page in node.all_pages()
    }


def save_dataframe(df: pd.DataFrame, path: Path, index: bool = False) -> None:
    """
    Save a DataFrame to CSV.
    
    Args:
        df: DataFrame to save
        path: Path to save to
        index: Whether to include index
    """
    df.to_csv(path, index=index)
    # Use custom logging function for stats
    log_stat(f"Wrote {len(df)} entries to {path}")


def save_urls_csv(url_map: Dict[str, str], out_dir: Path) -> Path:
    """
    Dump the URL→source map into a CSV file.
    
    Args:
        url_map: Dictionary mapping page URLs to source sitemap URLs
        out_dir: Directory to save CSV
        
    Returns:
        Path to the created CSV file
    """
    path = out_dir / 'urls.csv'
    
    if not url_map:
        logging.warning("No URLs found to save")
        return path
        
    # Create DataFrame directly from dictionary
    df = pd.DataFrame([
        {'url': url, 'source': source} 
        for url, source in url_map.items()
    ])
    
    save_dataframe(df, path)
    return path


def load_previous_urls(csv_path: Path) -> Set[str]:
    """
    Load URLs from previous run.
    
    Args:
        csv_path: Path to CSV from previous run
        
    Returns:
        Set of URLs from previous run
    """
    try:
        df = pd.read_csv(csv_path)
        return set(df['url'])
    except Exception as e:
        logging.error(f"Error loading previous URLs: {e}")
        return set()


def find_url_differences(
    current_urls: Set[str],
    prev_urls: Set[str]
) -> UrlDiff:
    """
    Find differences between current and previous URLs.
    
    Args:
        current_urls: Set of URLs from current run
        prev_urls: Set of URLs from previous run
        
    Returns:
        UrlDiff with new_urls and deleted_urls
    """
    return UrlDiff(
        new_urls=current_urls - prev_urls,
        deleted_urls=prev_urls - current_urls
    )


def save_diff_csv(
    url_diff: UrlDiff, 
    out_dir: Path,
    prev_timestamp: str,
    current_timestamp: str
) -> Path:
    """
    Save differences to a CSV file.
    
    Args:
        url_diff: UrlDiff with new_urls and deleted_urls
        out_dir: Directory to save diff CSV
        prev_timestamp: Timestamp of previous run
        current_timestamp: Timestamp of current run
        
    Returns:
        Path to the created diff CSV file
    """
    # Format timestamps for readability
    prev_time_fmt = format_timestamp(prev_timestamp)
    current_time_fmt = format_timestamp(current_timestamp)
    
    # Create records for new and deleted URLs
    diff_rows = [
        {
            'status': UrlStatus.NEW.value, 
            'url': url,
            'previous_scan_time': prev_time_fmt,
            'current_scan_time': current_time_fmt
        } 
        for url in sorted(url_diff.new_urls)
    ] + [
        {
            'status': UrlStatus.DELETED.value, 
            'url': url,
            'previous_scan_time': prev_time_fmt,
            'current_scan_time': current_time_fmt
        } 
        for url in sorted(url_diff.deleted_urls)
    ]
    
    # Create DataFrame with column names that will be preserved even if empty
    diff_df = pd.DataFrame(diff_rows, columns=[
        'status', 'url', 'previous_scan_time', 'current_scan_time'
    ])
    diff_path = out_dir / 'diff.csv'
    save_dataframe(diff_df, diff_path)
    return diff_path

def find_latest_previous_run(domain_dir: Path, timestamp: str) -> Optional[Path]:
    """
    Find the most recent previous run directory.
    
    Args:
        domain_dir: Domain directory containing all runs
        timestamp: Current run timestamp
        
    Returns:
        Path to latest previous run or None if none exists
    """
    # Get all timestamped directories in the domain directory
    all_dirs = [d for d in domain_dir.glob('*') if d.is_dir()]
    
    # Filter to only include directories with numeric names (timestamps)
    all_runs = []
    for d in all_dirs:
        try:
            # Attempt to convert to integer to validate it's a timestamp
            int(d.name)
            all_runs.append(d)
        except ValueError:
            # Skip directories with non-numeric names
            logging.debug(f"Skipping non-timestamp directory: {d.name}")
    
    logging.debug(f"Found {len(all_runs)} previous runs in '{domain_dir}'")
    
    # Filter out current run (if it exists already)
    all_runs = [run for run in all_runs if run.name != timestamp]
    
    # Sort by timestamp (convert directory names to integers)
    sorted_runs = sorted(all_runs, key=lambda d: int(d.name))
        
    # Return the most recent previous run if any exist
    return sorted_runs[-1] if sorted_runs else None

    
def validate_url(url: str) -> bool:
    """
    Validate that a URL is properly formatted.
    
    Args:
        url: The URL string to validate
        
    Returns:
        bool: True if URL is valid, False otherwise
    """
    # Check if URL is empty
    if not url:
        logging.error("Empty URL provided")
        return False
    
    # Check for proper scheme (http or https)
    if not url.startswith(("http://", "https://")):
        logging.error("URL must start with http:// or https://")
        return False
    
    # Parse the URL to extract components
    try:
        parsed = urlparse(url)
    except Exception as e:
        logging.error(f"Could not parse URL: {e}")
        return False
    
    # Validate domain requirements
    netloc = parsed.netloc
    if not netloc:
        logging.error("URL is missing domain")
        return False
    
    if '.' not in netloc:
        logging.error("Domain must contain at least one dot (e.g., example.com)")
        return False
    
    # Check if there's something after the last dot (TLD)
    domain_parts = netloc.split('.')
    if not domain_parts[-1]:
        logging.error("URL is missing top-level domain (e.g., .com, .org)")
        return False
    
    # Check for common issues with subdomains
    if netloc.startswith('.') or '..' in netloc:
        logging.error("Invalid domain format (check dots)")
        return False
    
    # URL appears to be valid
    return True


def log_url_changes(url_diff: UrlDiff) -> None:
    """
    Log changes to URLs.
    
    Args:
        url_diff: UrlDiff with new_urls and deleted_urls
    """
    # Use custom logging for summary counts so they show in quiet mode without WARNING level
    log_stat(f"New pages: {len(url_diff.new_urls)}")
    # Keep detailed URL lists at INFO level (will be hidden in quiet mode)
    for url in sorted(url_diff.new_urls):
        logging.info(f"  NEW     {url}")

    # Use custom logging for summary counts so they show in quiet mode without WARNING level
    log_stat(f"Deleted pages: {len(url_diff.deleted_urls)}")
    # Keep detailed URL lists at INFO level (will be hidden in quiet mode)
    for url in sorted(url_diff.deleted_urls):
        logging.info(f"  DELETED {url}")

def process_diff(
    config: SiteConfig, 
    url_map: Dict[str, str]
) -> None:
    """
    Process diff between current and previous runs.
    
    Args:
        config: Site configuration
        url_map: URL→sitemap map
    """
    latest_prev = find_latest_previous_run(
        config.domain_dir,
        config.timestamp
    )
    
    if not latest_prev:
        logging.info("No previous runs found for comparison.")
        return
        
    prev_csv = latest_prev / 'urls.csv'
    if not prev_csv.exists():
        logging.info("No previous CSV found to diff against.")
        return
        
    # Get current and previous URLs
    current_urls = set(url_map.keys())
    prev_urls = load_previous_urls(prev_csv)
    
    # Find differences
    url_diff = find_url_differences(current_urls, prev_urls)
    
    # Log changes
    log_url_changes(url_diff)

    # Extract previous run timestamp from directory name
    prev_timestamp = latest_prev.name
    
    # Save diff CSV with timestamps
    diff_path = save_diff_csv(
        url_diff, 
        config.output_dir,
        prev_timestamp,
        config.timestamp
    )
    logging.info(f"Wrote diff to {diff_path}")

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Cache sitemaps and list every page URL"
    )
    parser.add_argument('site', help='e.g. https://example.com')
    parser.add_argument('-v', '--verbose', action='store_true', 
                        help='Enable verbose output')
    parser.add_argument('-q', '--quiet', action='store_true', 
                        help='Suppress non-error output except URL counts and changes')
    return parser.parse_args()


def configure_logging(args: argparse.Namespace) -> None:
    """
    Configure logging based on command-line arguments.
    
    Args:
        args: Parsed arguments
    """
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)


def main() -> None:
    """Main entry point for the sitemap spider."""
    args = parse_arguments()
    configure_logging(args)
    
    # Validate the URL before proceeding
    if not validate_url(args.site):
        sys.exit(1)  # Exit if URL is invalid
    
    # Set up site configuration
    config = setup_site_config(args.site)
    
    # Create domain directory first
    config.domain_dir.mkdir(exist_ok=True)
    # Then create output directory for this run
    config.output_dir.mkdir(exist_ok=True)
    logging.info(f"Output directory: {config.output_dir}")

    try:
        # Get sitemap tree and extract data
        tree = sitemap_tree_for_homepage(config.base_url)
        
        # Get sitemap nodes (filtering out robots.txt)
        sitemap_nodes = get_sitemap_nodes(tree, config.base_url)
        
        if not sitemap_nodes:
            logging.warning("No sitemaps found")
            sys.exit(1)

        # Download sitemaps
        logging.info("Downloading sitemaps...")
        download_sitemaps(sitemap_nodes, config.output_dir)

        # Extract URL map
        logging.info("Extracting page URLs...")
        url_map = extract_url_map(sitemap_nodes)
        if not url_map:
            logging.warning("No URLs found in sitemaps")
            sys.exit(1)

        # Save URLs to CSV
        logging.info("Saving CSV...")
        csv_path = save_urls_csv(url_map, config.output_dir)

        # DIFF CHECKING
        logging.info("Checking for differences from previous run...")
        process_diff(config, url_map)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        sys.exit(1)
        
    logging.info("Done.")


if __name__ == '__main__':
    main()