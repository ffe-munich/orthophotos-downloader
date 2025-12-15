from .utils.logging import setup_logging
from .data_scraping.auto_downloader import AutoOrthophotoDownloader, auto_download_orthophotos

setup_logging()

# Make the auto downloader easily accessible at package level
__all__ = ['AutoOrthophotoDownloader', 'auto_download_orthophotos']
