---
title: Better web scraping in Python with Selenium, Beautiful Soup, and pandas
uid: 20241016T1436
created: '2024-10-16'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes1
tags: []
aliases: []
source_url: https://www.freecodecamp.org/news/better-web-scraping-in-python-with-selenium-beautiful-soup-and-pandas-d6390592e251
---

\

Better web scraping in Python with Selenium, Beautiful Soup, and pandas

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIgdHZmVV8iIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjaDJJaHYiIC8+PC9zdmc+)

Web Clip

\

April 16, 2018 / [\#JavaScript](https://www.freecodecamp.org/news/tag/javascript/)

# Better web scraping in Python with Selenium, Beautiful Soup, and pandas

By Dave Gray

### Web Scraping

Using the Python programming language, it is possible to “scrape” data from the web in a quick and efficient manner.

Web scraping is defined as:

> a tool for turning the unstructured data on the web into machine readable, structured data which is ready for analysis. ([source](https://www.promptcloud.com/blog/should-data-scientists-learn-web-scraping))

Web scraping is a valuable [tool in the data scientist’s skill set](https://medium.com/@Francesco_AI/data-science-skills-list-9f38863adab5).

*Now, what to scrape?*

![](_attachments/1PFcYTwR35sTl2we1WhUuFg.jpeg) *“Search drill down options” == Keep clicking until you find what you want.*

### Publicly Available Data

The [KanView](http://kanview.ks.gov/PayRates/PayRates_Agency.aspx) website supports “Transparency in Government”. That is also the slogan of the site. The site provides payroll data for the State of Kansas. And that’s great!

Yet, like many government websites, it buries the data in drill-down links and tables. This often requires “best guess navigation” to find the specific data you are looking for. I wanted to use the public data provided for the universities within Kansas in a research project. Scraping the data with Python and saving it as JSON was what I needed to do to get started.

### JavaScript links increase the complexity

Web scraping with Python often requires no more than the use of the [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) module to reach the goal. [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) is a popular Python library that makes web scraping by traversing the DOM (document object model) easier to implement.

However, the [KanView](http://kanview.ks.gov/PayRates/PayRates_Agency.aspx) website uses JavaScript links. Therefore, examples using Python and Beautiful Soup will not work without some extra additions.

![](_attachments/1Xw5kfdCZT3ndmQiK6gFpDA.jpeg) \_\[https://pypi.python.org/pypi/selenium\](https://pypi.python.org/pypi/selenium" rel="noopener" target="*blank" title=")*

### Selenium to the rescue

The [Selenium package](https://pypi.org/project/selenium/) is used to automate web browser interaction from Python. With Selenium, programming a Python script to automate a web browser is possible. Afterwards, those pesky JavaScript links are no longer an issue.

```
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
```

Selenium will now start a browser session. For Selenium to work, it must access the browser driver. By default, it will look in the same directory as the Python script. Links to Chrome, Firefox, Edge, and Safari drivers [available here](https://pypi.python.org/pypi/selenium). The example code below uses Firefox:

```
#launch url
url = "http://kanview.ks.gov/PayRates/PayRates_Agency.aspx"

# create a new Firefox session
driver = webdriver.Firefox()
driver.implicitly_wait(30)
driver.get(url)

python_button = driver.find_element_by_id('MainContent_uxLevel1_Agencies_uxAgencyBtn_33') #FHSU
python_button.click() #click fhsu link
```

The `python_button.click()` above is telling Selenium to click the JavaScript link on the page. After arriving at the Job Titles page, Selenium hands off the page source to Beautiful Soup.

![](_attachments/1_jcqKfi3H0vETIPeGhiAfg.jpeg) \_\[https://www.crummy.com/software/BeautifulSoup/\](https://www.crummy.com/software/BeautifulSoup/" rel="noopener" target="*blank" title=")*

### Transitioning to Beautiful Soup

[Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) remains the best way to traverse the DOM and scrape the data. After defining an empty list and a counter variable, it is time to ask Beautiful Soup to grab all the links on the page that match a regular expression:

```
#Selenium hands the page source to Beautiful Soup
soup_level1=BeautifulSoup(driver.page_source, 'lxml')

datalist = [] #empty list
x = 0 #counter

for link in soup_level1.find_all('a', id=re.compile("^MainContent_uxLevel2_JobTitles_uxJobTitleBtn_")):
    ##code to execute in for loop goes here
```

You can see from the example above that Beautiful Soup will retrieve a JavaScript link for each job title at the state agency. Now in the code block of the for / in loop, Selenium will click each JavaScript link. Beautiful Soup will then retrieve the table from each page.

```
#Beautiful Soup grabs all Job Title links
for link in soup_level1.find_all('a', id=re.compile("^MainContent_uxLevel2_JobTitles_uxJobTitleBtn_")):

    #Selenium visits each Job Title page
    python_button = driver.find_element_by_id('MainContent_uxLevel2_JobTitles_uxJobTitleBtn_' + str(x))
    python_button.click() #click link

    #Selenium hands of the source of the specific job page to Beautiful Soup
    soup_level2=BeautifulSoup(driver.page_source, 'lxml')

    #Beautiful Soup grabs the HTML table on the page
    table = soup_level2.find_all('table')[0]

    #Giving the HTML table to pandas to put in a dataframe object
    df = pd.read_html(str(table),header=0)

    #Store the dataframe in a list
    datalist.append(df[0])

    #Ask Selenium to click the back button
    driver.execute_script("window.history.go(-1)") 

    #increment the counter variable before starting the loop over
    x += 1
```

![](_attachments/1GB1VDH40BeSMPHcbTYVT9g.jpeg) \_\[https://pandas.pydata.org/\](https://pandas.pydata.org/" rel="noopener" target="*blank" title=")*

### pandas: Python Data Analysis Library

Beautiful Soup passes the findings to pandas. Pandas uses its `read_html` function to read the HTML table data into a dataframe. The dataframe is appended to the previously defined empty list.

Before the code block of the loop is complete, Selenium needs to click the back button in the browser. This is so the next link in the loop will be available to click on the job listing page.

When the for / in loop has completed, Selenium has visited every job title link. Beautiful Soup has retrieved the table from each page. Pandas has stored the data from each table in a dataframe. Each dataframe is an item in the datalist. The individual table dataframes must now merge into one large dataframe. The data will then be converted to JSON format with [pandas.Dataframe.to_json](https://pandas.pydata.org/pandas-docs/stable/generated/pandas.DataFrame.to_json.html):

```
#loop has completed

#end the Selenium browser session
driver.quit()

#combine all pandas dataframes in the list into one big dataframe
result = pd.concat([pd.DataFrame(datalist[i]) for i in range(len(datalist))],ignore_index=True)

#convert the pandas dataframe to JSON
json_records = result.to_json(orient='records')
```

Now Python creates the JSON data file. It is ready for use!

```
#get current working directory
path = os.getcwd()

#open, write, and close the file
f = open(path + "fhsu_payroll_data.json","w") #FHSU
f.write(json_records)
f.close()
```

### The automated process is fast

The automated web scraping process described above completes quickly. Selenium opens a browser window you can see working. This allows me to show you a screen capture video of how fast the process is. You see how fast the script follows a link, grabs the data, goes back, and clicks the next link. It makes retrieving the data from hundreds of links a matter of single-digit minutes.

### The full Python code

Here is the full Python code. I have included an import for tabulate. It requires an extra line of code that will use tabulate to pretty print the data to your command line interface:

```
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import re
import pandas as pd
from tabulate import tabulate
import os

#launch url
url = "http://kanview.ks.gov/PayRates/PayRates_Agency.aspx"

# create a new Firefox session
driver = webdriver.Firefox()
driver.implicitly_wait(30)
driver.get(url)

#After opening the url above, Selenium clicks the specific agency link
python_button = driver.find_element_by_id('MainContent_uxLevel1_Agencies_uxAgencyBtn_33') #FHSU
python_button.click() #click fhsu link

#Selenium hands the page source to Beautiful Soup
soup_level1=BeautifulSoup(driver.page_source, 'lxml')

datalist = [] #empty list
x = 0 #counter

#Beautiful Soup finds all Job Title links on the agency page and the loop begins
for link in soup_level1.find_all('a', id=re.compile("^MainContent_uxLevel2_JobTitles_uxJobTitleBtn_")):

    #Selenium visits each Job Title page
    python_button = driver.find_element_by_id('MainContent_uxLevel2_JobTitles_uxJobTitleBtn_' + str(x))
    python_button.click() #click link

    #Selenium hands of the source of the specific job page to Beautiful Soup
    soup_level2=BeautifulSoup(driver.page_source, 'lxml')

    #Beautiful Soup grabs the HTML table on the page
    table = soup_level2.find_all('table')[0]

    #Giving the HTML table to pandas to put in a dataframe object
    df = pd.read_html(str(table),header=0)

    #Store the dataframe in a list
    datalist.append(df[0])

    #Ask Selenium to click the back button
    driver.execute_script("window.history.go(-1)") 

    #increment the counter variable before starting the loop over
    x += 1

    #end loop block

#loop has completed

#end the Selenium browser session
driver.quit()

#combine all pandas dataframes in the list into one big dataframe
result = pd.concat([pd.DataFrame(datalist[i]) for i in range(len(datalist))],ignore_index=True)

#convert the pandas dataframe to JSON
json_records = result.to_json(orient='records')

#pretty print to CLI with tabulate
#converts to an ascii table
print(tabulate(result, headers=["Employee Name","Job Title","Overtime Pay","Total Gross Pay"],tablefmt='psql'))

#get current working directory
path = os.getcwd()

#open, write, and close the file
f = open(path + "fhsu_payroll_data.json","w") #FHSU
f.write(json_records)
f.close()
```

![](_attachments/1Pn_kqhr2-rqQ7yNV-ymn6Q.jpeg) \_Photo by \[Unsplash\](https://unsplash.com/photos/ZMraoOybTLQ?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText" rel="noopener" target="\_blank" title=""\>Artem Sapegin on \<a href="https://unsplash.com/search/photos/coffee-laptop?utm_source=unsplash&utm_medium=referral&utm_content=creditCopyText" rel="noopener" target="*blank" title=")*

### Conclusion

**Web scraping** with **Python** and **Beautiful Soup** is an excellent tool to have within your skillset. Use web scraping when the data you need to work with is available to the public, but not necessarily conveniently available. When JavaScript provides or “hides” content, browser automation with **Selenium** will insure your code “sees” what you (as a user) should see. And finally, when you are scraping tables full of data, **pandas** is the Python data analysis library that will handle it all.

### Reference:

The following article was a helpful reference for this project:

[https://pythonprogramminglanguage.com/web-scraping-with-pandas-and-beautifulsoup/](https://pythonprogramminglanguage.com/web-scraping-with-pandas-and-beautifulsoup/)

Reach out to me any time on [LinkedIn](https://www.linkedin.com/in/davidagray/) or [Twitter](https://twitter.com/yesdavidgray). And if you liked this article, give it a few claps. I will sincerely appreciate it.

[https://www.linkedin.com/in/davidagray/](https://www.linkedin.com/in/davidagray/)

[**Dave Gray (@yesdavidgray) \| Twitter**](https://twitter.com/yesdavidgray)\
[*The latest Tweets from Dave Gray (@yesdavidgray). Instructor @FHSUInformatics *Developer* Musician *Entrepreneur* …*](https://twitter.com/yesdavidgray)\
[twitter.com](https://twitter.com/yesdavidgray)

------------------------------------------------------------------------

If you read this far, thank the author to show them you care.

Learn to code for free. freeCodeCamp's open source curriculum has helped more than 40,000 people get jobs as developers. [Get started](https://www.freecodecamp.org/learn/)

ADVERTISEMENT

freeCodeCamp is a donor-supported tax-exempt 501(c)(3) charity organization (United States Federal Tax Identification Number: 82-0779546)

Our mission: to help people learn to code for free. We accomplish this by creating thousands of videos, articles, and interactive coding lessons - all freely available to the public.

Donations to freeCodeCamp go toward our education initiatives, and help pay for servers, services, and staff.

You can [make a tax-deductible donation here](https://www.freecodecamp.org/donate/).

## Trending Books and Handbooks

- [Learn CSS Transform](https://www.freecodecamp.org/news/complete-guide-to-css-transform-functions-and-properties/)
- [Build a Static Blog](https://www.freecodecamp.org/news/how-to-create-a-static-blog-with-lume/)
- [Build an AI Chatbot](https://www.freecodecamp.org/news/how-to-build-an-ai-chatbot-with-redis-python-and-gpt/)
- [What is Programming?](https://www.freecodecamp.org/news/what-is-programming-tutorial-for-beginners/)
- [Python Code Examples](https://www.freecodecamp.org/news/python-code-examples-sample-script-coding-tutorial-for-beginners/)
- [Open Source for Devs](https://www.freecodecamp.org/news/a-practical-guide-to-start-opensource-contributions/)
- [HTTP Networking in JS](https://www.freecodecamp.org/news/http-full-course/)
- [Write React Unit Tests](https://www.freecodecamp.org/news/how-to-write-unit-tests-in-react-redux/)
- [Learn Algorithms in JS](https://www.freecodecamp.org/news/introduction-to-algorithms-with-javascript-examples/)
- [How to Write Clean Code](https://www.freecodecamp.org/news/how-to-write-clean-code/)
- [Learn PHP](https://www.freecodecamp.org/news/the-php-handbook/)
- [Learn Java](https://www.freecodecamp.org/news/the-java-handbook/)
- [Learn Swift](https://www.freecodecamp.org/news/the-swift-handbook/)
- [Learn Golang](https://www.freecodecamp.org/news/learn-golang-handbook/)
- [Learn Node.js](https://www.freecodecamp.org/news/get-started-with-nodejs/)
- [Learn CSS Grid](https://www.freecodecamp.org/news/complete-guide-to-css-grid/)
- [Learn Solidity](https://www.freecodecamp.org/news/learn-solidity-handbook/)
- [Learn Express.js](https://www.freecodecamp.org/news/the-express-handbook/)
- [Learn JS Modules](https://www.freecodecamp.org/news/javascript-es-modules-and-module-bundlers/)
- [Learn Apache Kafka](https://www.freecodecamp.org/news/apache-kafka-handbook/)
- [REST API Best Practices](https://www.freecodecamp.org/news/rest-api-design-best-practices-build-a-rest-api/)
- [Front-End JS Development](https://www.freecodecamp.org/news/front-end-javascript-development-react-angular-vue-compared/)
- [Learn to Build REST APIs](https://www.freecodecamp.org/news/build-consume-and-document-a-rest-api/)
- [Intermediate TS and React](https://www.freecodecamp.org/news/build-strongly-typed-polymorphic-components-with-react-and-typescript/)
- [Command Line for Beginners](https://www.freecodecamp.org/news/command-line-for-beginners/)
- [Intro to Operating Systems](https://www.freecodecamp.org/news/an-introduction-to-operating-systems/)
- [Learn to Build GraphQL APIs](https://www.freecodecamp.org/news/building-consuming-and-documenting-a-graphql-api/)
- [OSS Security Best Practices](https://www.freecodecamp.org/news/oss-security-best-practices/)
- [Distributed Systems Patterns](https://www.freecodecamp.org/news/design-patterns-for-distributed-systems/)
- [Software Architecture Patterns](https://www.freecodecamp.org/news/an-introduction-to-software-architecture-patterns/)

## Mobile App

- [](https://apps.apple.com/us/app/freecodecamp/id6446908151?itsct=apps_box_link&itscg=30200)
- [](https://play.google.com/store/apps/details?id=org.freecodecamp)

## Our Charity

[About](https://www.freecodecamp.org/news/about/) [Alumni Network](https://www.linkedin.com/school/free-code-camp/people/) [Open Source](https://github.com/freeCodeCamp/) [Shop](https://www.freecodecamp.org/news/shop/) [Support](https://www.freecodecamp.org/news/support/) [Sponsors](https://www.freecodecamp.org/news/sponsors/) [Academic Honesty](https://www.freecodecamp.org/news/academic-honesty-policy/) [Code of Conduct](https://www.freecodecamp.org/news/code-of-conduct/) [Privacy Policy](https://www.freecodecamp.org/news/privacy-policy/) [Terms of Service](https://www.freecodecamp.org/news/terms-of-service/) [Copyright Policy](https://www.freecodecamp.org/news/copyright-policy/)

\

## See also

- [[Software Development]]
