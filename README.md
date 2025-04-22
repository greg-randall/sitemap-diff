# Sitemap Monitoring Tool

A comprehensive tool for tracking and visualizing website content changes by monitoring sitemaps over time. This system crawls website sitemaps, detects URL additions and removals, and generates interactive reports to visualize these changes.

## Features

- **Sitemap Crawling**: Automatically discovers and downloads all sitemaps for a domain
- **Change Detection**: Identifies new and deleted URLs between crawls
- **CSV Exports**: Saves all discovered URLs and their changes to CSV files
- **HTML Reports**: Generates interactive HTML reports with:
  - Summary statistics of added/removed URLs
  - Line charts showing URL changes over time
  - Detailed per-crawl reports of specific URL changes
- **Flexible Usage**: Run as a standalone tool or integrate into larger workflows

## Installation

### Prerequisites

```bash
pip install requests tldextract pandas usp tqdm jinja2
```

### Setup

1. Clone this repository
2. Ensure the scripts are executable:
   ```bash
   chmod +x differ.py reporter.py
   ```

## Usage

### Crawling Sitemaps

```bash
./differ.py https://example.com
./differ.py https://example.com --verbose
./differ.py https://example.com --quiet
```

### Generating Reports

```bash
./reporter.py https://example.com
./reporter.py https://example.com --output-dir /path/to/reports
```

## How It Works

### Crawler (`differ.py`)

1. Validates the input URL
2. Creates output directories based on domain name and timestamp
3. Discovers all sitemaps using the `usp` (Ultimate Sitemap Parser) library
4. Downloads each sitemap locally
5. Extracts all page URLs and their source sitemaps
6. Compares with previous runs to identify new and deleted URLs
7. Generates a `diff.csv` file with all changes

### Reporter (`reporter.py`)

1. Finds all diff.csv files from previous crawler runs
2. Aggregates data from all diffs
3. Creates a main index report with summary statistics and trends chart
4. Generates individual run reports for each crawler run that had changes
5. Sets up all necessary HTML templates, CSS, and JavaScript

## Project Structure

```
├── differ.py           # Sitemap crawler and diff generator
├── reporter.py         # HTML report generator
├── templates/          # HTML templates (created automatically)
│   ├── index.html      # Main report template
│   └── run_report.html # Individual run report template
└── static/             # Static assets (created automatically)
    ├── css/
    │   └── style.css   # CSS styles for reports
    └── js/
        └── charts.js   # JavaScript for charts
```

## Data Storage

The tool organizes data by domain and timestamp:

```
example.com/
├── 1650640583/         # Timestamp of first run
│   ├── [sitemap files] # Downloaded sitemap files
│   └── urls.csv        # All discovered URLs
├── 1650726983/         # Timestamp of second run
│   ├── [sitemap files]
│   ├── urls.csv
│   └── diff.csv        # Changes since previous run
└── reports/            # Generated HTML reports
    ├── index.html
    ├── report_1650726983.html
    └── static/
```

## Visualization Features

The generated reports include:

- Summary statistics (total runs, total URLs added/deleted)
- Interactive line chart showing URL changes over time
- Table of all runs with links to detailed reports
- Detailed per-run reports showing specific URLs added or removed

## Use Cases

- **Content Auditing**: Monitor website growth or content pruning
- **SEO Monitoring**: Track indexable content changes
- **Competitive Analysis**: Monitor competitor website changes
- **Content Migration Validation**: Verify URLs are properly maintained during site migrations
- **Automated Testing**: Integrate into CI/CD pipelines to verify content deployment

## Extending the Tool

The modular design makes it easy to extend:
- Modify `differ.py` to capture additional metadata from sitemaps
- Update the HTML templates to add new visualizations
- Integrate with notification systems to alert on significant changes