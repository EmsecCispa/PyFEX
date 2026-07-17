# download_pypi_packages_fixed.py
import os
import sys
import csv
import time
import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import re
import json

class PyPIDownloader:
    """
    Download PYPI packages with improved URL parsing
    """
    
    def __init__(self, output_dir="benign_downloads_direct", max_workers=3):
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.base_url = "https://pypi.org/pypi/"
        self.downloaded_packages = set()
        self.failed_packages = set()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.setup_logging()
        
        # Load existing packages
        self.load_existing_packages()
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.output_dir / 'download.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_existing_packages(self):
        """Load already downloaded packages from directory"""
        try:
            for item in self.output_dir.iterdir():
                if item.is_file() and item.suffix in ['.whl', '.tar.gz', '.zip']:
                    package_name = self.extract_package_name(item.name)
                    if package_name:
                        self.downloaded_packages.add(package_name.lower())
            
            self.logger.info(f"Found {len(self.downloaded_packages)} already downloaded packages")
        except Exception as e:
            self.logger.error(f"Error loading existing packages: {e}")
    
    def extract_package_name(self, filename):
        """
        Extract package name from filename
        """
        # Remove file extensions
        name = filename.replace('.tar.gz', '').replace('.whl', '').replace('.zip', '')
        
        # Remove version numbers and other suffixes
        parts = name.split('-')
        if parts:
            return parts[0].lower()
        return None

    def get_package_info_from_json(self, package_name):
        """
        Get package information using PyPI JSON API (more reliable)
        """
        try:
            url = f"{self.base_url}{package_name}/json"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 404:
                self.logger.warning(f"Package not found on PyPI: {package_name}")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Get the latest version
            latest_version = data['info']['version']
            
            # Get download URLs from releases
            releases = data.get('releases', {})
            if latest_version in releases:
                files = releases[latest_version]
                if files:
                    # Prefer source distributions
                    source_files = [f for f in files if f['packagetype'] == 'sdist']
                    if source_files:
                        return source_files[0]['url']
                    
                    # Fall back to wheels
                    wheel_files = [f for f in files if f['packagetype'] == 'bdist_wheel']
                    if wheel_files:
                        return wheel_files[0]['url']
            
            self.logger.warning(f"No download files found for {package_name}")
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error getting info for {package_name}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error parsing JSON for {package_name}: {e}")
            return None

    def get_package_download_url_fallback(self, package_name):
        """
        Fallback method using simple API if JSON API fails
        """
        try:
            simple_url = f"https://pypi.org/simple/{package_name}/"
            response = requests.get(simple_url, timeout=30)
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            
            # Parse HTML for links
            links = re.findall(r'<a[^>]*href="([^"]+\.(tar\.gz|zip|whl))"[^>]*>', response.text)
            
            if not links:
                return None
            
            # Prefer source distributions
            source_dists = [link[0] for link in links if link[0].endswith(('.tar.gz', '.zip'))]
            if source_dists:
                return source_dists[0]
            
            # Fall back to wheels
            wheels = [link[0] for link in links if link[0].endswith('.whl')]
            if wheels:
                return wheels[0]
            
            return None
            
        except Exception as e:
            self.logger.error(f"Fallback method failed for {package_name}: {e}")
            return None

    def get_package_download_url(self, package_name):
        """
        Get download URL with multiple fallback methods
        """
        # Try JSON API first (most reliable)
        url = self.get_package_info_from_json(package_name)
        if url:
            return url
        
        # Try fallback method
        self.logger.debug(f"JSON API failed for {package_name}, trying fallback...")
        url = self.get_package_download_url_fallback(package_name)
        if url:
            return url
        
        self.logger.warning(f"All methods failed to find download URL for: {package_name}")
        return None
    
    def download_package(self, package_name):
        """
        Download a single package
        """
        # Skip if already downloaded
        if package_name.lower() in self.downloaded_packages:
            self.logger.info(f"Skipping already downloaded: {package_name}")
            return {'name': package_name, 'status': 'skipped', 'reason': 'already_downloaded'}
        
        try:
            # Get download URL
            download_url = self.get_package_download_url(package_name)
            if not download_url:
                self.logger.warning(f"No download URL found for: {package_name}")
                return {'name': package_name, 'status': 'failed', 'reason': 'no_download_url'}
            
            # Handle relative URLs
            if download_url.startswith('/'):
                download_url = f"https://pypi.org{download_url}"
            elif not download_url.startswith(('http://', 'https://')):
                download_url = f"https://files.pythonhosted.org{download_url}"
            
            # Download the package
            filename = os.path.basename(download_url)
            filepath = self.output_dir / filename
            
            self.logger.info(f"Downloading {package_name} -> {filename}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(download_url, stream=True, timeout=60, headers=headers)
            response.raise_for_status()
            
            # Check file size
            total_size = int(response.headers.get('content-length', 0))
            
            # Download with progress
            with open(filepath, 'wb') as f:
                downloaded_size = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
            
            # Verify download
            if total_size > 0 and downloaded_size != total_size:
                self.logger.error(f"Download incomplete for {package_name}: {downloaded_size}/{total_size}")
                filepath.unlink(missing_ok=True)
                return {'name': package_name, 'status': 'failed', 'reason': 'incomplete_download'}
            
            # Add to downloaded set
            self.downloaded_packages.add(package_name.lower())
            
            file_size = filepath.stat().st_size
            self.logger.info(f"Successfully downloaded {package_name} ({file_size / 1024 / 1024:.2f} MB)")
            
            return {
                'name': package_name,
                'status': 'success',
                'filename': filename,
                'size': file_size,
                'url': download_url
            }
            
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout downloading {package_name}")
            return {'name': package_name, 'status': 'failed', 'reason': 'timeout'}
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error downloading {package_name}: {e}")
            return {'name': package_name, 'status': 'failed', 'reason': 'network_error'}
        except Exception as e:
            self.logger.error(f"Unexpected error downloading {package_name}: {e}")
            return {'name': package_name, 'status': 'failed', 'reason': str(e)}
    
    def load_package_list_from_csv(self, csv_file):
        """
        Load package names from CSV file
        """
        packages = []
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:  # Skip empty rows
                        package_name = row[0].strip()
                        if package_name and not package_name.startswith('#'):
                            packages.append(package_name)
            
            self.logger.info(f"Loaded {len(packages)} packages from {csv_file}")
            return packages
            
        except Exception as e:
            self.logger.error(f"Error loading CSV file {csv_file}: {e}")
            return []
    
    def download_all_packages(self, package_list):
        """
        Download all packages with thread pool
        """
        total_packages = len(package_list)
        self.logger.info(f"Starting download of {total_packages} packages with {self.max_workers} workers")
        
        results = []
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_package = {
                executor.submit(self.download_package, pkg): pkg 
                for pkg in package_list
            }
            
            # Process completed downloads
            for i, future in enumerate(as_completed(future_to_package), 1):
                package_name = future_to_package[future]
                try:
                    result = future.result(timeout=300)  # 5 minute timeout per package
                    results.append(result)
                    
                    # Log progress every 50 packages or at the end
                    if i % 50 == 0 or i == total_packages:
                        elapsed = time.time() - start_time
                        success_count = sum(1 for r in results if r['status'] == 'success')
                        failed_count = sum(1 for r in results if r['status'] == 'failed')
                        
                        self.logger.info(f"Progress: {i}/{total_packages} "
                                       f"({i/total_packages*100:.1f}%) | "
                                       f"Success: {success_count} | "
                                       f"Failed: {failed_count} | "
                                       f"Elapsed: {elapsed/60:.1f}min")
                        
                except Exception as e:
                    self.logger.error(f"Error processing {package_name}: {e}")
                    results.append({
                        'name': package_name,
                        'status': 'failed',
                        'reason': 'processing_error'
                    })
        
        return results
    
    def generate_statistics(self, results):
        """
        Generate download statistics
        """
        successful = [r for r in results if r['status'] == 'success']
        skipped = [r for r in results if r['status'] == 'skipped']
        failed = [r for r in results if r['status'] == 'failed']
        
        total_size = sum(r.get('size', 0) for r in successful)
        
        stats = {
            'total': len(results),
            'successful': len(successful),
            'skipped': len(skipped),
            'failed': len(failed),
            'success_rate': (len(successful) / len(results)) * 100 if results else 0,
            'total_size_mb': total_size / 1024 / 1024,
            'average_size_mb': (total_size / len(successful)) / 1024 / 1024 if successful else 0
        }
        
        return stats
    
    def save_results(self, results, stats):
        """
        Save download results to JSON file
        """
        output_file = self.output_dir / 'download_results.json'
        
        output_data = {
            'metadata': {
                'download_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'statistics': stats,
                'output_directory': str(self.output_dir)
            },
            'results': results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Results saved to {output_file}")

def main():
    """
    Main function to download PYPI packages from famous.csv
    """
    # Configuration
    config = {
        'csv_file': 'famous.csv',  # Path to your CSV file
        'output_dir': 'benign_downloads_direct',
        'max_workers': 3,  # Be nice to PyPI servers
    }
    
    # Create downloader
    downloader = PyPIDownloader(
        output_dir=config['output_dir'],
        max_workers=config['max_workers']
    )
    
    # Load package list from CSV
    packages = downloader.load_package_list_from_csv(config['csv_file'])
    
    if not packages:
        logging.error("No packages found to download")
        return
    
    # Download packages
    results = downloader.download_all_packages(packages)
    
    # Generate statistics
    stats = downloader.generate_statistics(results)
    
    # Print summary
    logging.info("=" * 60)
    logging.info("DOWNLOAD SUMMARY:")
    logging.info(f"Total packages: {stats['total']}")
    logging.info(f"Successful: {stats['successful']}")
    logging.info(f"Skipped (already downloaded): {stats['skipped']}")
    logging.info(f"Failed: {stats['failed']}")
    logging.info(f"Success rate: {stats['success_rate']:.1f}%")
    logging.info(f"Total size: {stats['total_size_mb']:.2f} MB")
    logging.info(f"Average package size: {stats['average_size_mb']:.2f} MB")
    
    # Save results
    downloader.save_results(results, stats)
    
    # Save failed packages for retry
    failed_packages = [r['name'] for r in results if r['status'] == 'failed']
    if failed_packages:
        failed_file = downloader.output_dir / 'failed_packages.txt'
        with open(failed_file, 'w', encoding='utf-8') as f:
            for pkg in failed_packages:
                f.write(f"{pkg}\n")
        logging.info(f"Failed packages saved to {failed_file}")

if __name__ == "__main__":
    main()