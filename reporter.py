#!/usr/bin/env python3
"""
Generate reports from sitemap diff data.

Usage:
    ./sitemap_report.py https://example.com
    ./sitemap_report.py https://example.com --output-dir /path/to/reports
"""

import argparse
import sys
import json
import datetime
import shutil
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import tldextract
import jinja2  # New dependency


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
        print("Error: Empty URL provided")
        return False
    
    # Check for proper scheme (http or https)
    if not url.startswith(("http://", "https://")):
        print("Error: URL must start with http:// or https://")
        return False
    
    # Parse the URL to extract components
    try:
        parsed = urlparse(url)
    except Exception as e:
        print(f"Error: Could not parse URL: {e}")
        return False
    
    # Validate domain requirements
    netloc = parsed.netloc
    if not netloc:
        print("Error: URL is missing domain")
        return False
    
    if '.' not in netloc:
        print("Error: Domain must contain at least one dot (e.g., example.com)")
        return False
    
    # Check if there's something after the last dot (TLD)
    domain_parts = netloc.split('.')
    if not domain_parts[-1]:
        print("Error: URL is missing top-level domain (e.g., .com, .org)")
        return False
    
    # Check for common issues with subdomains
    if netloc.startswith('.') or '..' in netloc:
        print("Error: Invalid domain format (check dots)")
        return False
    
    # URL appears to be valid
    return True


def setup_domain_dir(url: str) -> Path:
    """
    Create domain directory from URL.
    
    Args:
        url: Site URL
        
    Returns:
        Path to domain directory
    """
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    ext = tldextract.extract(base_url)
    
    # Include subdomain in the directory name if it exists
    if ext.subdomain:
        domain_dir = Path(f"{ext.subdomain}.{ext.domain}.{ext.suffix}")
    else:
        domain_dir = Path(f"{ext.domain}.{ext.suffix}")
    
    if not domain_dir.exists():
        print(f"Error: No data directory found for {domain_dir}")
        sys.exit(1)
    
    return domain_dir


def find_all_diffs(domain_dir: Path) -> list:
    """
    Find all diff.csv files in the domain directory.
    
    Args:
        domain_dir: Path to domain directory
        
    Returns:
        List of (timestamp_dir, diff_path) tuples
    """
    all_diffs = []
    
    for timestamp_dir in sorted(domain_dir.glob('*')):
        if not timestamp_dir.is_dir():
            continue
        
        diff_path = timestamp_dir / 'diff.csv'
        if diff_path.exists():
            all_diffs.append((timestamp_dir, diff_path))
    
    return all_diffs


def read_diff_data(diff_path: Path) -> pd.DataFrame:
    """
    Read data from a diff.csv file.
    
    Args:
        diff_path: Path to diff.csv file
        
    Returns:
        DataFrame with diff data, or empty DataFrame if file doesn't exist
    """
    try:
        return pd.read_csv(diff_path)
    except Exception as e:
        print(f"Warning: Couldn't read {diff_path}: {e}")
        return pd.DataFrame(columns=['status', 'url', 'previous_scan_time', 'current_scan_time'])


def aggregate_diff_data(all_diffs: list) -> dict:
    """
    Aggregate data from all diff.csv files.
    
    Args:
        all_diffs: List of (timestamp_dir, diff_path) tuples
        
    Returns:
        Dictionary with aggregated data
    """
    aggregate_data = {
        'runs': [],
        'total_added': 0,
        'total_deleted': 0,
        'chart_data': {
            'timestamps': [],
            'added': [],
            'deleted': []
        }
    }
    
    for timestamp_dir, diff_path in all_diffs:
        timestamp = timestamp_dir.name
        df = read_diff_data(diff_path)
        
        # Count new and deleted URLs
        new_count = len(df[df['status'] == 'new'])
        deleted_count = len(df[df['status'] == 'deleted'])
        
        # Format timestamp for display
        timestamp_dt = datetime.datetime.fromtimestamp(int(timestamp))
        formatted_timestamp = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Add to runs list
        run_data = {
            'timestamp': timestamp,
            'formatted_timestamp': formatted_timestamp,
            'new_count': new_count,
            'deleted_count': deleted_count,
            'diff_path': str(diff_path),
            'has_changes': new_count > 0 or deleted_count > 0
        }
        aggregate_data['runs'].append(run_data)
        
        # Update totals
        aggregate_data['total_added'] += new_count
        aggregate_data['total_deleted'] += deleted_count
        
        # Add to chart data
        aggregate_data['chart_data']['timestamps'].append(formatted_timestamp)
        aggregate_data['chart_data']['added'].append(new_count)
        aggregate_data['chart_data']['deleted'].append(deleted_count)
    
    return aggregate_data


def setup_template_engine() -> jinja2.Environment:
    """
    Set up the Jinja2 template engine.
    
    Returns:
        Jinja2 Environment
    """
    # Get the directory of the current script
    script_dir = Path(__file__).parent.absolute()
    
    # Set up the template loader
    template_loader = jinja2.FileSystemLoader(searchpath=script_dir / "templates")
    template_env = jinja2.Environment(loader=template_loader)
    
    return template_env


def setup_static_files(output_dir: Path) -> None:
    """
    Set up static files in the output directory.
    
    Args:
        output_dir: Path to output directory
    """
    script_dir = Path(__file__).parent.absolute()
    static_dir = script_dir / "static"
    
    # Create static directory in output directory if not exists
    output_static_dir = output_dir / "static"
    output_static_dir.mkdir(exist_ok=True)
    
    # Copy static files if they exist
    if static_dir.exists():
        # Create CSS directory
        output_css_dir = output_static_dir / "css"
        output_css_dir.mkdir(exist_ok=True)
        
        # Copy CSS files
        css_dir = static_dir / "css"
        if css_dir.exists():
            for css_file in css_dir.glob("*.css"):
                shutil.copy(css_file, output_css_dir)
        
        # Create JS directory
        output_js_dir = output_static_dir / "js"
        output_js_dir.mkdir(exist_ok=True)
        
        # Copy JS files
        js_dir = static_dir / "js"
        if js_dir.exists():
            for js_file in js_dir.glob("*.js"):
                shutil.copy(js_file, output_js_dir)
    else:
        print("Warning: Static files directory does not exist, exiting.")
        sys.exit()




def generate_run_report(timestamp_dir: Path, diff_path: Path, output_dir: Path, template_env: jinja2.Environment) -> Path:
    """
    Generate an individual run report.
    
    Args:
        timestamp_dir: Path to timestamp directory
        diff_path: Path to diff.csv file
        output_dir: Path to output directory
        template_env: Jinja2 template environment
        
    Returns:
        Path to generated report or None if no changes
    """
    timestamp = timestamp_dir.name
    df = read_diff_data(diff_path)
    
    # Don't create a report if there are no changes
    if len(df) == 0:
        return None
    
    # Format timestamp for display
    timestamp_dt = datetime.datetime.fromtimestamp(int(timestamp))
    formatted_timestamp = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Count new and deleted URLs
    new_urls = df[df['status'] == 'new']['url'].tolist()
    deleted_urls = df[df['status'] == 'deleted']['url'].tolist()
    
    # Prepare template context
    context = {
        'timestamp': formatted_timestamp,
        'new_urls': new_urls,
        'deleted_urls': deleted_urls
    }
    
    # Render template
    template = template_env.get_template('run_report.html')
    html_content = template.render(**context)
    
    # Save HTML file
    report_path = output_dir / f"report_{timestamp}.html"
    report_path.write_text(html_content)
    
    return report_path


def generate_index_report(domain: str, aggregate_data: dict, output_dir: Path, template_env: jinja2.Environment) -> Path:
    """
    Generate the main index report.
    
    Args:
        domain: Domain name
        aggregate_data: Aggregated diff data
        output_dir: Path to output directory
        template_env: Jinja2 template environment
        
    Returns:
        Path to generated report
    """
    # Prepare template context
    context = {
        'domain': domain,
        'runs_count': len(aggregate_data['runs']),
        'total_added': aggregate_data['total_added'],
        'total_deleted': aggregate_data['total_deleted'],
        'chart_data': json.dumps(aggregate_data['chart_data']),
        'runs': list(reversed(aggregate_data['runs']))  # Most recent first
    }
    
    # Render template
    template = template_env.get_template('index.html')
    html_content = template.render(**context)
    
    # Save HTML file
    report_path = output_dir / "index.html"
    report_path.write_text(html_content)
    
    return report_path


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Generate reports from sitemap diff data"
    )
    parser.add_argument('site', help='e.g. https://example.com')
    parser.add_argument('--output-dir', help='Directory to save reports')
    return parser.parse_args()


def main() -> None:
    """Main entry point for the sitemap reporter."""
    args = parse_arguments()
    
    # Validate the URL
    if not validate_url(args.site):
        sys.exit(1)
    
    # Extract domain from URL
    parsed = urlparse(args.site)
    ext = tldextract.extract(parsed.netloc)
    
    # Include subdomain in the domain name if it exists
    if ext.subdomain:
        domain = f"{ext.subdomain}.{ext.domain}.{ext.suffix}"
    else:
        domain = f"{ext.domain}.{ext.suffix}"
    
    # Get domain directory
    domain_dir = setup_domain_dir(args.site)
    
    # Set up output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = domain_dir / "reports"
        
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir}")
        
    # Set up template engine
    template_env = setup_template_engine()
    
    # Copy or create static files
    setup_static_files(output_dir)
    
    # Find all diff.csv files
    all_diffs = find_all_diffs(domain_dir)
    
    if not all_diffs:
        print(f"No diff data found for {domain}")
        sys.exit(1)
    
    print(f"Found {len(all_diffs)} runs with diff data")
    
    # Aggregate data
    aggregate_data = aggregate_diff_data(all_diffs)
    
    # Generate individual run reports for runs with changes
    for timestamp_dir, diff_path in all_diffs:
        df = read_diff_data(diff_path)
        if len(df) > 0:  # Only create reports for runs with changes
            run_report_path = generate_run_report(timestamp_dir, diff_path, output_dir, template_env)
            if run_report_path:
                print(f"Generated report: {run_report_path}")
    
    # Generate main index report
    index_report_path = generate_index_report(domain, aggregate_data, output_dir, template_env)
    print(f"Generated main report: {index_report_path}")
    print(f"Open {index_report_path} in a web browser to view the report")


if __name__ == '__main__':
    main()