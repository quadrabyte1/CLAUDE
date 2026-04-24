---
title: Untitled note
uid: 20250309T1141
created: '2025-03-09'
updated: '2025-03-09'
source: evernote
original_notebook: My Notes1
tags: []
aliases: []
---

[Monica.im](https://Monica.im) Manus tool

1.0

import requests from bs4 import BeautifulSoup from urllib.parse import urljoin, urlparse

def is_broken_link(url): try: response = requests.head(url, allow_redirects=True) return response.status_code != 200 except requests.RequestException: return True

def check_links(url, visited): if url in visited: return visited.add(url)

`print(f"Checking: {url}") if is_broken_link(url):     print(f"Broken link found: {url}")     return try:     response = requests.get(url)     soup = BeautifulSoup(response.text, 'html.parser')     domain = urlparse(url).netloc     for link in soup.find_all('a', href=True):         link_url = urljoin(url, link['href'])         link_domain = urlparse(link_url).netloc         if link_domain == domain:             check_links(link_url, visited)         else:             print(f"External link found: {link_url}") except requests.RequestException as e:     print(f"Error accessing {url}: {e}") `

if **name** == "**main**": start_url = 'http://example.com'  \# Replace with your starting URL visited_links = set() check_links(start_url, visited_links)
