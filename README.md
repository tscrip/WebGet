# WebGet
Python based queued file downloader.

The workflow for WebGet goes like this:
1. Send POST request with link to WebGet
2. WebGet adds link to SQLite DB
3. Threaded downloader checks queue for new link
4. When link is found, downloader starts downloading file
5. When download is complete, downloader checks back with SQLite queue for more files

The amount of concurrent downloads is currently set at 2, but it can easily be changed to allow more concurrent downloads.
