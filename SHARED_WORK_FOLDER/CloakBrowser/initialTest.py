

from cloakbrowser import launch 

browser = launch()
page = browser.page
page.goto("https://www.example.com")
browser.close()
