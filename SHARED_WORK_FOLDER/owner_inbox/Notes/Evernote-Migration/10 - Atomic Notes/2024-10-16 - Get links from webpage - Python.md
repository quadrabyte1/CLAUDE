---
title: Get links from webpage - Python
uid: 20241016T1434
created: '2024-10-16'
updated: '2024-10-16'
source: evernote
original_notebook: My Notes1
tags: []
aliases: []
source_url: https://pythonprogramminglanguage.com/get-links-from-webpage/
---

\

Get links from webpage - Python

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIgdHZmVV8iIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjaDJJaHYiIC8+PC9zdmc+)

Web Clip

\

[![](_attachments/logo.png)](https://pythonprogramminglanguage.com/)

[](https://pythonprogramminglanguage.com/)

# Python

Learn Python Programming

[GUI](https://pythonprogramminglanguage.com/python-gui/) [PyQT](https://pythonprogramminglanguage.com/pyqt/) [Machine Learning](https://pythonprogramminglanguage.com/python-machine-learning/) [Web](https://pythonprogramminglanguage.com/web-application/)

# Get links from webpage

Do you want to scrape links?

The module urllib2 can be used to download webpage data. Webpage data is always formatted in HTML format.

To cope with the HTML format data, we use a Python module named BeautifulSoup. BeautifulSoup is a Python module for parsing webpages (HTML).

**Related course:** [Complete Python Programming Course & Exercises](https://gum.co/dcsp)

## [](https://pythonprogramminglanguage.com/get-links-from-webpage/#Get-all-links-from-a-webpage "Get all links from a webpage")Get all links from a webpage

All of the links will be returned as a [list](https://pythonprogramminglanguage.com/lists/), like so:

```
['//slashdot.org/faq/slashmeta.shtml', ... ,'mailto:feedback@slashdot.org', '#', '//slashdot.org/blog', '#', '#', '//slashdot.org']
```

We scrape a webpage with these steps:

- download webpage data (html)
- **create beautifulsoup object** and parse webpage data
- use soups method **findAll** to find all links by the a tag
- store all links in list

To get all links from a webpage:

[TABLE]

## [](https://pythonprogramminglanguage.com/get-links-from-webpage/#How-does-it-work "How does it work?")How does it work?

This line downloads the webpage data (which is surrounded by HTML tags):

[TABLE]

The next line loads it into a BeautifulSoup object:

[TABLE]

The link codeblock will then get all links using .findAll(‘a’), where ‘a’ is the indicator for links in html.\

[TABLE]

Finally we show the list of links:

[TABLE]

[Download network examples](https://pythonprogramminglanguage.com/network-examples.zip)

\

[](https://pythonprogramminglanguage.com/get-links-from-webpage/#) [Leave a Reply:\
\
](https://pythonprogramminglanguage.com/get-links-from-webpage/%3C/div%3E%3Cbr%3E%3Cdiv%20class=)

Email address\

Message\

\

Yves • Wed, 29 Jun 2016

Thanks for the super informative content.\
Just to save some time from new users, I just spend a couple of minutes trying to get BeautifulSoup working.\
The new version apparently have some bugs on it and the correct syntax at the beginning is:\
from bs4 import BeautifulSoup.

[](https://pythonprogramminglanguage.com/get-links-from-webpage/%3C/div%3E%3Cbr%3E%3Cdiv%20class=)

[Guest • Fri, 22 Jul 2016](https://pythonprogramminglanguage.com/get-links-from-webpage/%3C/div%3E%3Cbr%3E%3Cdiv%20class=)

[from bs4 import BeautifulSoup\
](https://pythonprogramminglanguage.com/get-links-from-webpage/%3C/div%3E%3Cbr%3E%3Cdiv%20class=)[https://www.crummy.com/soft...](https://www.crummy.com/software/BeautifulSoup/bs4/doc/ "https://www.crummy.com/software/BeautifulSoup/bs4/doc/")

[Cookie policy](https://pythonprogramminglanguage.com/cookie-policy/) \| [Privacy policy](https://pythonprogramminglanguage.com/privacy-policy/) \| [Contact](https://pythonprogramminglanguage.com/contact/) \| [Zen](https://python-commandments.org/zen-of-python/) \| [Get](https://www.python.org/downloads/)

© 2023 https://pythonprogramminglanguage.com

\
