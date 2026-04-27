---
title: How to perform Web Scraping using Selenium and Python | BrowserStack
uid: 20241016T1444
created: '2024-10-16'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes1
tags: []
aliases: []
source_url: https://www.browserstack.com/guide/web-scraping-using-selenium-python
---

\

How to perform Web Scraping using Selenium and Python \| BrowserStack

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIgdHZmVV8iIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjaDJJaHYiIC8+PC9zdmc+)

Web Clip

\

[Skip to main content](https://www.browserstack.com/guide/web-scraping-using-selenium-python#main-content)

[](https://www.browserstack.com/ "BrowserStack Logo")

[Categories ](https://www.browserstack.com/guide/web-scraping-using-selenium-python# "Categories Dropdown")

[Home](https://www.browserstack.com/ "BrowserStack") [Guide](https://www.browserstack.com/guide)

# How to perform Web Scraping using Selenium and Python

By Sakshi Pandey, Community Contributor - February 7, 2023

[](https://www.linkedin.com/shareArticle?url=https%3A%2F%2Fwww.browserstack.com%2Fguide%2Fweb-scraping-using-selenium-python "Share on LinkedIn") [](http://www.facebook.com/sharer.php?u=https%3A%2F%2Fwww.browserstack.com%2Fguide%2Fweb-scraping-using-selenium-python "Share on Facebook") [](https://twitter.com/share?url=https%3A%2F%2Fwww.browserstack.com%2Fguide%2Fweb-scraping-using-selenium-python&text=How%20to%20perform%20Web%20Scraping%20using%20Selenium%20and%20Python&via=browserstack "Share on Twitter") [](https://www.browserstack.com/guide/web-scraping-using-selenium-pythonwhatsapp://send?text=How%20to%20perform%20Web%20Scraping%20using%20Selenium%20and%20Python%20https%3A%2F%2Fwww.browserstack.com%2Fguide%2Fweb-scraping-using-selenium-python "Share on WhatsApp")

Table of Contents

- •[What is Selenium Web Scraping, and Why is it used?](https://www.browserstack.com/guide/web-scraping-using-selenium-python#toc0)
- •[Applications of Web Scraping](https://www.browserstack.com/guide/web-scraping-using-selenium-python#toc1)
- •[Understanding the Role of Selenium and Python in Scraping](https://www.browserstack.com/guide/web-scraping-using-selenium-python#toc2)
- •[Example: Web Scraping the Title and all Instances of a Keyword from a Specified URL](https://www.browserstack.com/guide/web-scraping-using-selenium-python#toc3)
- •[How to perform Web Scraping using Selenium and Python](https://www.browserstack.com/guide/web-scraping-using-selenium-python#toc4)
- •[Other Features of Selenium with Python](https://www.browserstack.com/guide/web-scraping-using-selenium-python#toc5)

Data is a universal need to solve business and research problems. Questionnaires, surveys, interviews, and forms are all data collection methods; however, they don’t quite tap into the biggest data resource available. The Internet is a huge reservoir of data on every plausible subject. Unfortunately, most websites do not allow the option to save and retain the data which can be seen on their web pages. Web scraping solves this problem and enables users to scrape large volumes of the data they need. 

### What is Selenium Web Scraping, and Why is it used?

Web scraping is the automated gathering of content and data from a website or any other resource available on the internet. Unlike screen scraping, web scraping extracts the HTML code under the webpage. Users can then process the HTML code of the webpage to extract data and carry out data cleaning, manipulation, and analysis. Exhaustive amounts of this data can even be stored in a database for large-scale data analysis projects. The prominence and need for data analysis, along with the amount of raw data which can be generated using web scrapers, has led to the development of tailor-made python packages which make web scraping easy as pie.

Web Scraping with [Selenium](https://www.browserstack.com/selenium "Selenium") allows you to gather all the required data using Selenium Webdriver [Browser Automation](https://www.browserstack.com/guide/what-is-browser-automation "What is Browser Automation?"). Selenium crawls the target URL webpage and gathers data at scale. This article demonstrates how to do web scraping using Selenium.

### Applications of Web Scraping

1.  1**Sentiment analysis:** While most websites used for sentiment analysis, such as social media websites, have APIs which allow users to access data, this is not always enough. In order to obtain data in real-time regarding information, conversations, research, and trends it is often more suitable to web scrape the data.
2.  2**Market Research:** eCommerce sellers can track products and pricing across multiple platforms to conduct market research regarding consumer sentiment and competitor pricing. This allows for very efficient monitoring of competitors and price comparisons to maintain a clear view of the market.
3.  3**Technological Research:** Driverless cars, face recognition, and recommendation engines all require data. Web Scraping often offers valuable information from reliable websites and is one of the most convenient and used data collection methods for these purposes.
4.  4**Machine Learning:** While sentiment analysis is a popular machine learning algorithm, it is only one of many. One thing all machine learning algorithms have in common, however, is the large amount of data required to train them. Machine learning fuels research, technological advancement, and overall growth across all fields of learning and innovation. In turn, web scraping can fuel data collection for these algorithms with great accuracy and reliability.

### Understanding the Role of Selenium and Python in Scraping

Python has libraries for almost any purpose a user can think up, including libraries for tasks such as web scraping. Selenium comprises several different open-source projects used to carry out [browser automation](https://www.browserstack.com/guide/what-is-browser-automation "What is Browser Automation?"). It supports bindings for several popular programming languages, including the language we will be using in this article: Python.

Initially, [Selenium with Python](https://www.browserstack.com/guide/python-selenium-to-run-web-automation-test "Selenium with Python Tutorial: Getting started with Test Automation") was developed and used primarily for [cross browser testing](https://www.browserstack.com/cross-browser-testing "Cross Browser Testing"); however, over time, more creative use cases, such as web scraping, have been found. 

[Selenium](https://www.browserstack.com/selenium "Selenium") uses the Webdriver protocol to automate processes on various popular browsers such as Firefox, Chrome, and Safari. This automation can be carried out locally (for purposes such as testing a web page) or remotely (for purposes such as web scraping).

**Also Read:** [Page Object Model and Page Factory in Selenium Python](https://www.browserstack.com/guide/page-object-model-in-selenium-python "Page Object Model and Page Factory in Selenium Python")

### Example: Web Scraping the Title and all Instances of a Keyword from a Specified URL

The general process followed when performing web scraping is:

1.  1Use the webdriver for the browser being used to get a specific URL.
2.  2Perform automation to obtain the information required.
3.  3Download the content required from the webpage returned.
4.  4Perform data parsing and manipulation of the content.
5.  5Reformat, if needed, and store the data for further analysis.

In this example, user input is taken for the URL of an article. Selenium is used along with BeautifulSoup to scrape and then carry out data manipulation to obtain the title of the article and all instances of a user input keyword found in it. Following this, a count is taken of the number of instances found of the keyword, and all this text data is stored and saved in a text file called **article_scraping.txt**.

[Run Selenium Python Tests on Real Devices](https://www.browserstack.com/users/sign_up?product=automate)

### How to perform Web Scraping using Selenium and Python

**Pre-Requisites:**

- •Set up a Python Environment.
- •Install Selenium v4. If you have conda or anaconda set up then using the *pip package installer* would be the most efficient method for Selenium installation. Simply run this command (on anaconda prompt, or directly on the Linux terminal):

```
pip install selenium
```

- •Download the latest WebDriver for the browser you wish to use, or install webdriver_manager by running the command, also install BeautifulSoup:

```

pip install webdriver_manager
pip install beautifulsoup4
```

**Step 1:** Import the required packages.

```

from selenium import webdriver

from selenium.webdriver.chrome.service import Service

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup

import codecs

import re

from webdriver_manager.chrome import ChromeDriverManager
```

Selenium is needed in order to carry out web scraping and automate the chrome browser we’ll be using. Selenium uses the webdriver protocol, therefore the webdriver manager is imported to obtain the ChromeDriver compatible with the version of the browser being used. BeautifulSoup is needed as an HTML parser, to parse the HTML content we scrape. Re is imported in order to use regex to match our keyword. Codecs are used to write to a text file.

**Step 2:** Obtain the version of ChromeDriver compatible with the browser being used.

```

driver=webdriver.Chrome(service=Service(ChromeDriverManager().install()))
```

**Step 3:** Take the user input to obtain the URL of the website to be scraped, and web scrape the page.

```

val = input(“Enter a url: “)

wait = WebDriverWait(driver, 10)

driver.get(val)
get_url = driver.current_url
wait.until(EC.url_to_be(val))
if get_url == val:
    page_source = driver.page_source
```

For this example, the user input is: [https://www.browserstack.com/guide/how-ai-in-visual-testing-is-evolving ](https://www.browserstack.com/guide/how-ai-in-visual-testing-is-evolving "How AI in Visual Testing is transforming the Testing Landscape")

The driver is used to get this URL and a wait command is used in order to let the page load. Then a check is done using the [current URL method](https://www.browserstack.com/guide/get-current-url-in-selenium-and-python "Get Current URL in Selenium using Python: Tutorial") to ensure that the correct URL is being accessed.

**Step 4:** Use **BeautifulSoup** to parse the HTML content obtained.

```

soup = BeautifulSoup(page_source,features=”html.parser”)
keyword=input(“Enter a keyword to find instances of in the article:”)
matches = soup.body.find_all(string=re.compile(keyword))

len_match = len(matches)

title = soup.title.text
```

The HTML content web scraped with Selenium is parsed and made into a soup object. Following this, user input is taken for a keyword for which we will search the article’s body. The keyword for this example is “**data**”. The body tags in the soup object are searched for all instances of the word “**data**” using **regex**. Lastly, the text in the title tag found within the soup object is extracted.

**Step 4:** Store the data collected into a text file.

```

file=codecs.open(‘article_scraping.txt’, ‘a+’)

file.write(title+“n”)

file.write(“The following are all instances of your keyword:n”)

count=1

for i in matches:

    file.write(str(count) + “.” +  i  + “n”)

    count+=1

file.write(“There were “+str(len_match)+” matches found for the keyword.”

file.close()

driver.quit()
```

Use **codecs** to open a text file titled **article_scraping.txt** and write the title of the article into the file, following this number, and append all instances of the keyword within the article. Lastly, append the number of matches found for the keyword in the article. Close the file and quit the driver.

**Output:**

**Text File Output:**

The title of the article, the two instances of the keyword, and the number of matches found can be visualized in this text file.

How to use tags to efficiently collect data from web scraped HTML pages:

```

print([tag.name for tag in soup.find_all()])

print([tag.text for tag in soup.find_all()])
```

The above code snippet can be used to print all the tags found in the **soup** object and all text within those tags. This can be helpful to debug code or locate any errors and issues.

### Other Features of Selenium with Python

You can use some of Selenium’s inbuilt features to carry out further actions or perhaps automate this process for multiple web pages. The following are some of the most convenient features offered by Selenium to carry out efficient [Browser Automation](https://www.browserstack.com/guide/what-is-browser-automation "What is Browser Automation?") and Web Scraping with Python:

- •**Filling out forms or carrying out searches**

Example of Google search automation using Selenium with Python.

```

from selenium import webdriver

from selenium.webdriver.chrome.service import Service

from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.common.keys import Keys

from selenium.webdriver.common.by import By



driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))



driver.get(“https://www.google.com/”)

search = driver.find_element(by=By.NAME,value=“q”)

search.send_keys(“Selenium”)

search.send_keys(Keys.ENTER)
```

First, the driver loads google.com, which finds the search bar using the name locator. It types “**Selenium**” into the searchbar and then hits enter.

**Output**:

- •**Maximizing the window**

```
driver.maximize_window()
```

- •**Taking Screenshots**

```
driver.save_screenshot(‘article.png’)
```

- •**Using locators to find elements**

Let’s say we don’t want to get the entire page source and instead only want to web scrape a select few elements. This can be carried out by using [Locators in Selenium](https://www.browserstack.com/guide/locators-in-selenium "Locators in Selenium: A Detailed Guide").

These are some of the locators compatible for use with Selenium:

1.  1Name
2.  2ID
3.  3Class Name
4.  4Tag Name
5.  5[CSS Selector](https://www.browserstack.com/guide/css-selectors-cheat-sheet "Quick CSS Selectors Cheat Sheet")
6.  6[XPath](https://www.browserstack.com/guide/find-element-by-xpath-in-selenium "How to find element by XPath in Selenium with Example")

Know the [Effective ways to use XPath in Selenium](https://www.browserstack.com/guide/xpath-in-selenium "Effective ways to use XPath in Selenium")

Example of scraping using locators:

```
from selenium import webdriver

from selenium.webdriver.chrome.service import Service

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.common.by import By

from webdriver_manager.chrome import ChromeDriverManager
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
val = input(“Enter a url: “)
wait = WebDriverWait(driver, 10)

driver.get(val)

get_url = driver.current_url

wait.until(EC.url_to_be(val))

if get_url == val:

header=driver.find_element(By.ID, “toc0”)

print(header.text)
```

This example’s input is the same article as the one in our web scraping example. Once the webpage has loaded the element we want is directly retrieved via ID, which can be found by using Inspect Element. 

**Output**:

The title of the first section is retrieved by using its locator “**toc0**” and printed.

- •**Scrolling**

```

driver.execute_script(“window.scrollTo(0, document.body.scrollHeight);”)
```

This scrolls to the bottom of the page, and is often helpful for websites that have infinite scrolling.

**Conclusion**

This guide explained the process of Web Scraping, Parsing, and Storing the Data collected. It also explored Web Scraping specific elements using locators in Python with Selenium. Furthermore, it provided guidance on how to automate a web page so that the desired data can be retrieved. The information provided should prove to be of service to carry out reliable data collection and perform insightful data manipulation for further downstream data analysis.

It is recommended to run Selenium Tests on a [real device cloud](https://www.browserstack.com/real-device-cloud "Real Device Cloud") for more accurate results since it considers real user conditions while running tests. With [BrowserStack Automate](https://www.browserstack.com/automate "Scale testing, ship fast without bottlenecks"), you can access 3000+ real device-browser combinations and test your web application thoroughly for a seamless and consistent user experience.

[Test Selenium with Python on Real Device Cloud](https://www.browserstack.com/users/sign_up?product=automate)

Was this post useful?

Yes, Thanks Not Really

[](https://www.linkedin.com/shareArticle?url=https%3A%2F%2Fwww.browserstack.com%2Fguide%2Fweb-scraping-using-selenium-python "Share on LinkedIn") [](http://www.facebook.com/sharer.php?u=https%3A%2F%2Fwww.browserstack.com%2Fguide%2Fweb-scraping-using-selenium-python "Share on Facebook") [](https://twitter.com/share?url=https%3A%2F%2Fwww.browserstack.com%2Fguide%2Fweb-scraping-using-selenium-python&text=How%20to%20perform%20Web%20Scraping%20using%20Selenium%20and%20Python&via=browserstack "Share on Twitter") [](https://www.browserstack.com/guide/web-scraping-using-selenium-pythonwhatsapp://send?text=How%20to%20perform%20Web%20Scraping%20using%20Selenium%20and%20Python%20https%3A%2F%2Fwww.browserstack.com%2Fguide%2Fweb-scraping-using-selenium-python "Share on WhatsApp")

Tags

[Automation Testing](https://www.browserstack.com/guide/tag/automation-testing "Automation Testing") [Selenium](https://www.browserstack.com/guide/tag/selenium "Selenium") [Website Testing](https://www.browserstack.com/guide/tag/website-testing "Website Testing")

### Related Articles

[](https://www.browserstack.com/guide/get-current-url-in-selenium-and-python "Get Current URL in Selenium using Python: Tutorial")

### Get Current URL in Selenium using Python: Tutorial

Detailed guide on how to use Get Current URL using Selenium in Python for validating URL of a websit...

Learn More

[](https://www.browserstack.com/guide/take-screenshot-with-selenium-python "How to take Screenshots using Python and Selenium")

### How to take Screenshots using Python and Selenium

How do you automate screenshot capturing of websites with Selenium and Python? Try this step-by-step...

Learn More

[](https://www.browserstack.com/guide/download-file-using-selenium-python "How to download a file using Selenium and Python")

### How to download a file using Selenium and Python

Step-by-step tutorial on how to download a file from a website using Selenium and Python. Code snipp...

Learn More

## Ready to try BrowserStack?

Over 6 million developers and 50,000 teams test on BrowserStack. Join them.

Products

- [Live](https://www.browserstack.com/live)
- [Automate](https://www.browserstack.com/automate)
- [Automate TurboScale Beta](https://www.browserstack.com/automate-turboscale)
- [Percy](https://www.browserstack.com/percy)
- [App Live](https://www.browserstack.com/app-live)
- [App Automate](https://www.browserstack.com/app-automate)
- [App Percy](https://www.browserstack.com/app-percy)
- [Test Management](https://www.browserstack.com/test-management)
- [Test Observability](https://www.browserstack.com/test-observability)
- [Accessibility Testing](https://www.browserstack.com/accessibility-testing)
- [Accessibility Automation](https://www.browserstack.com/accessibility-testing/features/automated-tests)
- [App Accessibility Testing](https://www.browserstack.com/app-accessibility-testing)
- [Low Code Automation](https://www.browserstack.com/low-code-automation)
- [Bug Capture](https://www.browserstack.com/bug-capture)
- [Nightwatch.js](https://nightwatchjs.org/)
- [Enterprise](https://www.browserstack.com/enterprise?ref=footer)

Tools

- [SpeedLab](https://www.browserstack.com/speedlab)
- [Screenshots](https://www.browserstack.com/screenshots)
- [Responsive](https://www.browserstack.com/responsive)

Platform

- [Browsers & Devices](https://www.browserstack.com/list-of-browsers-and-platforms)
- [Data Centers](https://www.browserstack.com/data-centers)
- [Real Device Features](https://www.browserstack.com/device-features)
- [Security](https://www.browserstack.com/security)
- [Trust Center](https://www.browserstack.com/trust)

Solutions

- [Test on iPhone](https://www.browserstack.com/test-on-iphone)
- [Test on iPad](https://www.browserstack.com/test-on-ipad)
- [Test on Galaxy](https://www.browserstack.com/test-on-galaxy)
- [Test In IE](https://www.browserstack.com/test-in-internet-explorer)
- [Android Testing](https://www.browserstack.com/android-testing)
- [iOS Testing](https://www.browserstack.com/ios-testing)
- [Cross Browser Testing](https://www.browserstack.com/cross-browser-testing)
- [Emulators & Simulators](https://www.browserstack.com/emulators-simulators)
- [Selenium](https://www.browserstack.com/selenium)
- [Cypress](https://www.browserstack.com/automate/cypress)
- [Android Emulators](https://www.browserstack.com/android-emulators)
- [Visual Testing](https://www.browserstack.com/percy/visual-testing)

Resources

- [Test on Right Devices](https://www.browserstack.com/test-on-the-right-mobile-devices)
- [Support](https://www.browserstack.com/support)
- [Status](https://status.browserstack.com/)
- [Release Notes](https://www.browserstack.com/release-notes)
- [Case Studies](https://www.browserstack.com/case-study)
- [Blog](https://www.browserstack.com/blog)
- [Events](https://www.browserstack.com/events)
- [Test University Beta](https://www.browserstack.com/test-university)
- [Champions](https://www.browserstack.com/browserstack-champions)
- [Mobile Emulators](https://www.browserstack.com/mobile-browser-emulator)
- [Guide](https://www.browserstack.com/guide)
- [Responsive Design](https://www.browserstack.com/responsive-design)

Company

- [About Us](https://www.browserstack.com/company)
- [Customers](https://www.browserstack.com/customers)
- [Careers We’re hiring!](https://www.browserstack.com/careers)
- [Open Source](https://www.browserstack.com/open-source)
- [Partners](https://www.browserstack.com/partners)
- [Press](https://www.browserstack.com/press)

[](https://www.browserstack.com/ "BrowserStack Logo")

Social

- [![](data:image/svg+xml,%3csvg%20width='19'%20height='17'%20viewBox='0%200%2024%2024'%20fill='none'%20xmlns='http://www.w3.org/2000/svg'%20aria-labelledby='footerSocialTwitterIconTitle%20footerSocialTwitterIconDesc'%20data-evernote-id='457'%20class='js-evernote-checked'%3e%3ctitle%20id='footerSocialTwitterIconTitle'%20data-evernote-id='2059'%20class='js-evernote-checked'%3eBrowserStack%20Twitter%20Account%3c/title%3e%3cdesc%20id='footerSocialTwitterIconDesc'%20data-evernote-id='2060'%20class='js-evernote-checked'%3eAn%20illustration%20of%20white%20twitter%20Logo%3c/desc%3e%3cpath%20d='M14.0955%2010.3165L22.2864%201H20.3456L13.2303%209.08768L7.55141%201H1L9.58949%2013.2311L1%2023H2.94072L10.4501%2014.4571L16.4486%2023H23L14.0955%2010.3165ZM11.4365%2013.3385L10.5649%2012.1198L3.64059%202.43161H6.62193L12.2117%2010.2532L13.0797%2011.4719L20.3447%2021.6381H17.3634L11.4365%2013.3385Z'%20fill='white'%20data-evernote-id='2061'%20class='js-evernote-checked'%3e%3c/path%3e%3c/svg%3e)](https://twitter.com/browserstack "Twitter")
- [![](data:image/svg+xml,%3csvg%20version='1.1'%20xmlns='http://www.w3.org/2000/svg'%20xmlns:xlink='http://www.w3.org/1999/xlink'%20x='0px'%20y='0px'%20viewBox='0%200%2019%2017'%20style='enable-background:new%200%200%2019%2017%3b'%20xml:space='preserve'%20aria-labelledby='footerSocialFaceBookIconTitle%20footerSocialFaceBookIconDesc'%20role='img'%20data-evernote-id='458'%20class='js-evernote-checked'%3e%3ctitle%20id='footerSocialFaceBookIconTitle'%20data-evernote-id='2064'%20class='js-evernote-checked'%3eBrowserStack%20FaceBook%20Account%3c/title%3e%3cdesc%20id='footerSocialFaceBookIconDesc'%20data-evernote-id='2065'%20class='js-evernote-checked'%3eAn%20illustration%20of%20white%20FaceBook%20Logo%3c/desc%3e%3cstyle%20type='text/css'%20data-evernote-id='2066'%20class='js-evernote-checked'%3e%20.sfacebook%7bfill:%23FFFFFF%3b%7d%3c/style%3e%3cpath%20class='sfacebook%20js-evernote-checked'%20d='M7.38%2c5.67H5.25V8.5h2.12V17h3.54V8.5h2.58l0.25-2.83h-2.83V4.49c0-0.68%2c0.14-0.94%2c0.79-0.94h2.04V0h-2.7%20C8.51%2c0%2c7.38%2c1.12%2c7.38%2c3.27V5.67z'%20data-evernote-id='2067'%3e%3c/path%3e%3c/svg%3e)](https://www.facebook.com/pages/BrowserStack/305988982776051 "Facebook")
- [![](data:image/svg+xml,%3csvg%20version='1.1'%20id='linkedInIconLayer_1'%20xmlns='http://www.w3.org/2000/svg'%20xmlns:xlink='http://www.w3.org/1999/xlink'%20x='0px'%20y='0px'%20viewBox='0%200%20459.5%20450.7'%20xml:space='preserve'%20fill='%23fff'%20aria-labelledby='footerSocialLinkedInIconTitle%20footerSocialLinkedInIconDesc'%20role='img'%20data-evernote-id='459'%20class='js-evernote-checked'%3e%3ctitle%20id='footerSocialLinkedInIconTitle'%20data-evernote-id='2070'%20class='js-evernote-checked'%3eBrowserStack%20LinkedIn%20Account%3c/title%3e%3cdesc%20id='footerSocialLinkedInIconDesc'%20data-evernote-id='2071'%20class='js-evernote-checked'%3eAn%20illustration%20of%20white%20LinkedIn%20Logo%3c/desc%3e%3cpath%20d='M3.4%2c146.6l92.8-1.2v303.8l-92.8%2c1.2L3.4%2c146.6L3.4%2c146.6z'%20data-evernote-id='2072'%20class='js-evernote-checked'%3e%3c/path%3e%3cpath%20d='M173.9%2c146.6l88.7-1.1v38.6l0%2c10.9c26.3-25.7%2c53.3-45.2%2c96.6-45.2c51%2c0%2c100.4%2c21.4%2c100.4%2c91v208.4l-90%2c1.3%20V291.5c0-35.1-8.8-57.7-50.7-57.7c-36.9%2c0-52.4%2c6.6-52.4%2c55.2v160.4l-92.5%2c1.1L173.9%2c146.6L173.9%2c146.6z'%20data-evernote-id='2073'%20class='js-evernote-checked'%3e%3c/path%3e%3cpath%20d='M101.6%2c50.8c0%2c28.1-22.7%2c50.8-50.8%2c50.8S0%2c78.8%2c0%2c50.8C0%2c22.7%2c22.7%2c0%2c50.8%2c0C78.8%2c0%2c101.6%2c22.7%2c101.6%2c50.8%20L101.6%2c50.8z'%20data-evernote-id='2074'%20class='js-evernote-checked'%3e%3c/path%3e%3c/svg%3e)](https://www.linkedin.com/company/browserstack/ "LinkedIn")
- [![](data:image/svg+xml,%3csvg%20enable-background='new%200%200%20176%20124'%20viewBox='0%200%20176%20124'%20xmlns='http://www.w3.org/2000/svg'%20aria-labelledby='footerSocialYoutubeIconTitle%20footerSocialYoutubeIconDesc'%20role='img'%20data-evernote-id='460'%20class='js-evernote-checked'%3e%3ctitle%20id='footerSocialYoutubeIconTitle'%20data-evernote-id='2077'%20class='js-evernote-checked'%3eBrowserStack%20Youtube%20Channel%3c/title%3e%3cdesc%20id='footerSocialYoutubeIconDesc'%20data-evernote-id='2078'%20class='js-evernote-checked'%3eAn%20illustration%20of%20white%20youtube%20Logo%3c/desc%3e%3cpath%20d='m172.3%2019.4c-2-7.6-8-13.6-15.6-15.7-13.7-3.7-68.7-3.7-68.7-3.7s-55%200-68.8%203.7c-7.6%202-13.5%208-15.6%2015.7-3.6%2013.8-3.6%2042.6-3.6%2042.6s0%2028.8%203.7%2042.6c2%207.6%208%2013.6%2015.6%2015.7%2013.7%203.7%2068.7%203.7%2068.7%203.7s55%200%2068.8-3.7c7.6-2%2013.5-8%2015.6-15.7%203.6-13.8%203.6-42.6%203.6-42.6s0-28.8-3.7-42.6zm-102.3%2068.8v-52.4l46%2026.2z'%20fill='%23fff'%20data-evernote-id='2079'%20class='js-evernote-checked'%3e%3c/path%3e%3c/svg%3e)](https://www.youtube.com/c/browserstack "YouTube")
- [![](data:image/svg+xml,%3csvg%20xmlns='http://www.w3.org/2000/svg'%20xmlns:xlink='http://www.w3.org/1999/xlink'%20width='18'%20height='18'%20viewBox='0%200%2018%2018'%20aria-labelledby='footerSocialInstagramIconTitle%20footerSocialInstagramIconDesc'%20role='img'%20data-evernote-id='461'%20class='js-evernote-checked'%3e%3ctitle%20id='footerSocialInstagramIconTitle'%20data-evernote-id='2082'%20class='js-evernote-checked'%3eBrowserStack%20Instagram%20Account%3c/title%3e%3cdesc%20id='footerSocialInstagramIconDesc'%20data-evernote-id='2083'%20class='js-evernote-checked'%3eAn%20illustration%20of%20white%20instagram%20Logo%3c/desc%3e%20%3cdefs%20data-evernote-id='2084'%20class='js-evernote-checked'%3e%20%3cpath%20id='prefix__a'%20d='M0%200.006L17.994%200.006%2017.994%2017.998%200%2017.998z'%20data-evernote-id='2085'%20class='js-evernote-checked'%3e%3c/path%3e%20%3c/defs%3e%20%3cg%20fill='none'%20fill-rule='evenodd'%20data-evernote-id='2086'%20class='js-evernote-checked'%3e%20%3cmask%20id='prefix__b'%20fill='%23fff'%20data-evernote-id='2087'%20class='js-evernote-checked'%3e%20%3cpath%20id='prefix__a'%20d='M0%200.006L17.994%200.006%2017.994%2017.998%200%2017.998z'%20data-evernote-id='2085'%20class='js-evernote-checked'%3e%3c/path%3e%20%3c/mask%3e%20%3cpath%20fill='%23FFF'%20d='M8.997.006c-2.443%200-2.75.01-3.71.054-.957.043-1.611.196-2.183.418-.592.23-1.094.538-1.594%201.038S.702%202.518.472%203.109C.25%203.682.098%204.336.054%205.293.01%206.253%200%206.56%200%209.003c0%202.443.01%202.75.054%203.71.044.957.196%201.611.418%202.183.23.592.538%201.094%201.038%201.594s1.002.808%201.594%201.038c.572.222%201.226.374%202.184.418.96.044%201.266.054%203.71.054%202.443%200%202.749-.01%203.709-.054.957-.044%201.611-.196%202.184-.418.591-.23%201.093-.538%201.593-1.038s.808-1.002%201.038-1.594c.222-.572.375-1.226.418-2.184.044-.96.054-1.266.054-3.71%200-2.443-.01-2.749-.054-3.709-.044-.957-.196-1.611-.418-2.184-.23-.591-.538-1.093-1.038-1.593S15.482.708%2014.891.478C14.318.256%2013.664.104%2012.707.06c-.96-.044-1.266-.054-3.71-.054zm0%201.62c2.402%200%202.687.01%203.636.053.877.04%201.353.187%201.67.31.42.163.72.358%201.035.673.315.315.51.615.673%201.035.123.317.27.793.31%201.67.043.949.052%201.234.052%203.636s-.009%202.687-.052%203.635c-.04.878-.187%201.354-.31%201.671-.163.42-.358.72-.673%201.035-.315.314-.615.51-1.035.673-.317.123-.793.27-1.67.31-.949.043-1.233.052-3.636.052-2.402%200-2.687-.01-3.635-.053-.878-.04-1.354-.186-1.671-.31-.42-.163-.72-.358-1.035-.672-.314-.315-.51-.615-.673-1.035-.123-.317-.27-.793-.31-1.67-.043-.95-.052-1.234-.052-3.636s.01-2.687.053-3.636c.04-.877.186-1.353.31-1.67.163-.42.358-.72.672-1.035.315-.315.615-.51%201.035-.673.317-.123.793-.27%201.67-.31.95-.043%201.234-.052%203.636-.052z'%20mask='url(%23prefix__b)'%20data-evernote-id='2089'%20class='js-evernote-checked'%3e%3c/path%3e%20%3cpath%20fill='%23FFF'%20d='M8.997%2012.002c-1.656%200-2.999-1.343-2.999-3%200-1.656%201.343-2.998%203-2.998%201.655%200%202.998%201.343%202.998%202.999%200%201.656-1.343%202.999-2.999%202.999zm0-7.62c-2.551%200-4.62%202.07-4.62%204.62%200%202.553%202.069%204.621%204.62%204.621%202.552%200%204.62-2.068%204.62-4.62s-2.068-4.62-4.62-4.62zM14.88%204.2c0%20.596-.484%201.08-1.08%201.08-.596%200-1.08-.484-1.08-1.08%200-.596.484-1.08%201.08-1.08.596%200%201.08.484%201.08%201.08'%20data-evernote-id='2090'%20class='js-evernote-checked'%3e%3c/path%3e%20%3c/g%3e%3c/svg%3e)](https://www.instagram.com/browserstack "Instagram")

[![](data:image/svg+xml,%3csvg%20width='24'%20height='24'%20alt='Contact%20Us'%20viewBox='0%200%2024%2024'%20fill='none'%20xmlns='http://www.w3.org/2000/svg'%20aria-labelledby='footerContactUsIconTitle%20footerContactUsIconDesc'%20role='img'%20data-evernote-id='462'%20class='js-evernote-checked'%3e%3ctitle%20id='footerContactUsIconTitle'%20data-evernote-id='2093'%20class='js-evernote-checked'%3eBrowserStack%20Contact%20Us%20Icon%3c/title%3e%3cdesc%20id='footerContactUsIconDesc'%20data-evernote-id='2094'%20class='js-evernote-checked'%3eAn%20illustration%20of%20white%20contact%20us%20icon%3c/desc%3e%3cpath%20d='M19%203H18V1H16V3H8V1H6V3H5C3.89%203%203%203.9%203%205V19C3%2020.1%203.89%2021%205%2021H19C20.1%2021%2021%2020.1%2021%2019V5C21%203.9%2020.1%203%2019%203ZM12%206C13.66%206%2015%207.34%2015%209C15%2010.66%2013.66%2012%2012%2012C10.34%2012%209%2010.66%209%209C9%207.34%2010.34%206%2012%206ZM18%2018H6V17C6%2015%2010%2013.9%2012%2013.9C14%2013.9%2018%2015%2018%2017V18Z'%20fill='white'%20data-evernote-id='2095'%20class='js-evernote-checked'%3e%3c/path%3e%3c/svg%3e)Contact Us](https://www.browserstack.com/contact?ref=footer)

© 2024 BrowserStack. All rights reserved.

- [Terms of Service](https://www.browserstack.com/terms)
- [Privacy Policy](https://www.browserstack.com/privacy)
- [Cookie Policy](https://www.browserstack.com/cookie-policy)
- [Sitemap](https://www.browserstack.com/sitemap)

\

## See also

- [[Software Development]]
