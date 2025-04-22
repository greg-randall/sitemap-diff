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
        # If static directory doesn't exist, create default CSS and JS
        create_default_static_files(output_dir)


def create_default_static_files(output_dir: Path) -> None:
    """
    Create default static files if they don't exist.
    
    Args:
        output_dir: Path to output directory
    """
    # Create directories
    static_dir = output_dir / "static"
    css_dir = static_dir / "css"
    js_dir = static_dir / "js"
    
    css_dir.mkdir(parents=True, exist_ok=True)
    js_dir.mkdir(parents=True, exist_ok=True)
    
    # Create default CSS
    default_css = """body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 20px;
    color: #333;
}
h1, h2 {
    color: #2c3e50;
}
.container {
    max-width: 1200px;
    margin: 0 auto;
}
.chart-container {
    height: 400px;
    margin-bottom: 40px;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 20px;
}
th, td {
    text-align: left;
    padding: 12px;
    border-bottom: 1px solid #ddd;
}
th {
    background-color: #f2f2f2;
}
tr:hover {
    background-color: #f5f5f5;
}
.new {
    color: green;
}
.deleted {
    color: red;
}
.no-changes {
    color: gray;
    font-style: italic;
}
.back-link {
    margin-bottom: 20px;
    display: inline-block;
}
"""
    (css_dir / "style.css").write_text(default_css)
    
    # Create default JavaScript for charts
    default_js = """function createChart(chartData) {
    const ctx = document.getElementById('diffChart').getContext('2d');
    const diffChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.timestamps,
            datasets: [
                {
                    label: 'URLs Added',
                    data: chartData.added,
                    backgroundColor: 'rgba(75, 192, 75, 0.2)',
                    borderColor: 'rgba(75, 192, 75, 1)',
                    borderWidth: 2,
                    pointRadius: 4
                },
                {
                    label: 'URLs Deleted',
                    data: chartData.deleted,
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 2,
                    pointRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of URLs'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Scan Time'
                    }
                }
            }
        }
    });
}
"""
    (js_dir / "charts.js").write_text(default_js)


def create_default_templates() -> None:
    """
    Create default templates if they don't exist.
    """
    script_dir = Path(__file__).parent.absolute()
    templates_dir = script_dir / "templates"
    templates_dir.mkdir(exist_ok=True)
    
    # Create index.html template
    index_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sitemap Diff Report - {{ domain }}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="static/css/style.css">
</head>
<body>
    <div class="container">
        <h1>Sitemap Diff Report for {{ domain }}</h1>
        
        <h2>Summary</h2>
        <p>Total runs: {{ runs_count }}</p>
        <p>Total URLs added: <span class="new">{{ total_added }}</span></p>
        <p>Total URLs deleted: <span class="deleted">{{ total_deleted }}</span></p>
        
        <h2>Trends Over Time</h2>
        <div class="chart-container">
            <canvas id="diffChart"></canvas>
        </div>
        
        <h2>All Runs</h2>
        <table>
            <tr>
                <th>Timestamp</th>
                <th>Added</th>
                <th>Deleted</th>
                <th>Report</th>
            </tr>
            {% for run in runs %}
            <tr>
                <td>{{ run.formatted_timestamp }}</td>
                <td class="new">{{ run.new_count }}</td>
                <td class="deleted">{{ run.deleted_count }}</td>
                <td>
                    {% if run.has_changes %}
                    <a href="report_{{ run.timestamp }}.html">View Report</a>
                    {% else %}
                    <span class="no-changes">No changes</span>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
    
    <script src="static/js/charts.js"></script>
    <script>
        // Parse the chart data from the server
        const chartData = {{ chart_data|safe }};
        
        // Create the chart
        document.addEventListener('DOMContentLoaded', function() {
            createChart(chartData);
        });
    </script>
</body>
</html>
"""
    (templates_dir / "index.html").write_text(index_template)
    
    # Create run_report.html template
    run_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sitemap Diff Report - {{ timestamp }}</title>
    <link rel="stylesheet" href="static/css/style.css">
</head>
<body>
    <div class="container">
        <a class="back-link" href="index.html">&larr; Back to overview</a>
        
        <h1>Sitemap Diff Report</h1>
        <p><strong>Scan time:</strong> {{ timestamp }}</p>
        
        <h2>Summary</h2>
        <p>New URLs: <span class="new">{{ new_urls|length }}</span></p>
        <p>Deleted URLs: <span class="deleted">{{ deleted_urls|length }}</span></p>
        
        <h2>New URLs</h2>
        {% if new_urls %}
        <table>
            <tr><th>URL</th></tr>
            {% for url in new_urls %}
            <tr><td class="new">{{ url }}</td></tr>
            {% endfor %}
        </table>
        {% else %}
        <p>No new URLs found.</p>
        {% endif %}
        
        <h2>Deleted URLs</h2>
        {% if deleted_urls %}
        <table>
            <tr><th>URL</th></tr>
            {% for url in deleted_urls %}
            <tr><td class="deleted">{{ url }}</td></tr>
            {% endfor %}
        </table>
        {% else %}
        <p>No deleted URLs found.</p>
        {% endif %}
    </div>
</body>
</html>
"""
    (templates_dir / "run_report.html").write_text(run_template)


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
    
    # Ensure templates exist
    create_default_templates()
    
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