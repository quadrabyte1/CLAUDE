---
title: Responsive Web Design Grid
uid: 20220207T1147
created: '2022-02-07'
updated: '2024-10-12'
source: evernote
original_notebook: My Notes2
tags: []
aliases: []
source_url: https://www.w3schools.com/css/css_rwd_grid.asp
---

\

Responsive Web Design Grid

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIgdHZmVV8iIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjaDJJaHYiIC8+PC9zdmc+)

Web Clip

\

[**](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Home") [Menu **](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Menu")

[Log in](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Menu") [](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Home") [](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Search W3Schools") [](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Translate W3Schools") [](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Toggle Dark Code Examples")

# Responsive Web Design - Grid-View

[❮ Previous](https://www.w3schools.com/css/css_rwd_grid.aspundefined) [Next ❯](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

------------------------------------------------------------------------

## What is a Grid-View?

Many web pages are based on a grid-view, which means that the page is divided into columns:

\

Using a grid-view is very helpful when designing web pages. It makes it easier to place elements on the page.

\

A responsive grid-view often has 12 columns, and has a total width of 100%, and will shrink and expand as you resize the browser window.

[Example: Responsive Grid View](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

------------------------------------------------------------------------

ADVERTISEMENT

------------------------------------------------------------------------

## Building a Responsive Grid-View

Lets start building a responsive grid-view.

First ensure that all HTML elements have the `box-sizing` property set to `border-box`. This makes sure that the padding and border are included in the total width and height of the elements.

Add the following code in your CSS:

\* {\
  box-sizing: border-box;\
}

Read more about the `box-sizing` property in our [CSS Box Sizing](https://www.w3schools.com/css/css_rwd_grid.aspundefined) chapter.

The following example shows a simple responsive web page, with two columns:

25%

75%

### Example

.menu {\
  width: 25%;\
  float: left;\
}\
.main {\
  width: 75%;\
  float: left;\
}\

[Try it Yourself »](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

The example above is fine if the web page only contains two columns.

However, we want to use a responsive grid-view with 12 columns, to have more control over the web page.

First we must calculate the percentage for one column: 100% / 12 columns = 8.33%.

Then we make one class for each of the 12 columns, `class="col-"` and a number defining how many columns the section should span:

### CSS:

.col-1 {width: 8.33%;}\
.col-2 {width: 16.66%;}\
.col-3 {width: 25%;}\
.col-4 {width: 33.33%;}\
.col-5 {width: 41.66%;}\
.col-6 {width: 50%;}\
.col-7 {width: 58.33%;}\
.col-8 {width: 66.66%;}\
.col-9 {width: 75%;}\
.col-10 {width: 83.33%;}\
.col-11 {width: 91.66%;}\
.col-12 {width: 100%;}

[Try it Yourself »](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

 All these columns should be floating to the left, and have a padding of 15px:

### CSS:

\[class\*="col-"\] {\
  float: left;\
  padding: 15px;\
  border: 1px solid red;\
}

Each row should be wrapped in a `<div>`. The number of columns inside a row should always add up to 12:

### HTML:

\<div class="row"\>\
  \<div class="col-3"\>...\</div\> \<!-- 25% --\>\
  \<div class="col-9"\>...\</div\> \<!-- 75% --\>\
\</div\>

The columns inside a row are all floating to the left, and are therefore taken out of the flow of the page, and other elements will be placed as if the columns do not exist. To prevent this, we will add a style that clears the flow:

### CSS:

.row::after {\
  content: "";\
  clear: both;\
  display: table;\
}

We also want to add some styles and colors to make it look better:

### Example

html {\
  font-family: "Lucida Sans", sans-serif;\
}\
\
.header {\
  background-color: \#9933cc;\
  color: \#ffffff;\
  padding: 15px;\
}\
\
.menu ul {\
  list-style-type: none;\
  margin: 0;\
  padding: 0;\
}\
\
.menu li {\
  padding: 8px;\
  margin-bottom: 7px;\
  background-color :\#33b5e5;\
  color: \#ffffff;\
  box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);\
}\
\
.menu li:hover {\
  background-color: \#0099cc;\
}

[Try it Yourself »](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

**Notice** that the webpage in the example does not look good when you resize the browser window to a very small width. In the next chapter you will learn how to fix that.

\

[❮ Previous](https://www.w3schools.com/css/css_rwd_grid.aspundefined) [Next ❯](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

\

NEW

We just launched\
W3Schools videos

[![](_attachments/htmlvideoad_footer.png)](https://www.w3schools.com/css/css_rwd_grid.aspundefined) [Explore now](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

#### [COLOR PICKER](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[![](_attachments/colorpicker2000.png)](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Facebook") [](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Instagram") [](https://www.w3schools.com/css/css_rwd_grid.aspundefined "LinkedIn") [](https://www.w3schools.com/css/css_rwd_grid.aspundefined "Join the W3schools community on Discord")

Get certified\
by completing\
a course today!

[](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

![](data:image/svg+xml,%3csvg%20id='w3_cert_badge2'%20style='margin:auto%3bwidth:85%25'%20data-name='w3_cert_badge2'%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%20300%20300'%20data-evernote-id='1021'%20class='js-evernote-checked'%3e%3cdefs%20data-evernote-id='1022'%20class='js-evernote-checked'%3e%3cstyle%20data-evernote-id='1023'%20class='js-evernote-checked'%3e.cls-1%7bfill:%2304aa6b%3b%7d.cls-2%7bfont-size:23px%3b%7d.cls-2%2c.cls-3%2c.cls-4%7bfill:%23fff%3b%7d.cls-2%2c.cls-3%7bfont-family:RobotoMono-Medium%2c%20Roboto%20Mono%3bfont-weight:500%3b%7d.cls-3%7bfont-size:20.08px%3b%7d%3c/style%3e%3c/defs%3e%3ccircle%20class='cls-1%20js-evernote-checked'%20cx='150'%20cy='150'%20r='146.47'%20transform='translate(-62.13%20150)%20rotate(-45)'%20data-evernote-id='1024'%3e%3c/circle%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='translate(93.54%2063.89)%20rotate(-29.5)'%20data-evernote-id='1025'%3ew%3c/text%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='translate(107.13%2056.35)%20rotate(-20.8)'%20data-evernote-id='1026'%3e3%3c/text%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='matrix(0.98%2c%20-0.21%2c%200.21%2c%200.98%2c%20121.68%2c%2050.97)'%20data-evernote-id='1027'%3es%3c/text%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='translate(136.89%2047.84)%20rotate(-3.47)'%20data-evernote-id='1028'%3ec%3c/text%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='translate(152.39%2047.03)%20rotate(5.12)'%20data-evernote-id='1029'%3eh%3c/text%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='translate(167.85%2048.54)%20rotate(13.72)'%20data-evernote-id='1030'%3eo%3c/text%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='translate(182.89%2052.35)%20rotate(22.34)'%20data-evernote-id='1031'%3eo%3c/text%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='matrix(0.86%2c%200.52%2c%20-0.52%2c%200.86%2c%20197.18%2c%2058.36)'%20data-evernote-id='1032'%3el%3c/text%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='matrix(0.77%2c%200.64%2c%20-0.64%2c%200.77%2c%20210.4%2c%2066.46)'%20data-evernote-id='1033'%3es%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(35.51%20186.66)%20rotate(69.37)'%20data-evernote-id='1034'%3e%20%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='matrix(0.47%2c%200.88%2c%20-0.88%2c%200.47%2c%2041.27%2c%20201.28)'%20data-evernote-id='1035'%3eC%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='matrix(0.58%2c%200.81%2c%20-0.81%2c%200.58%2c%2048.91%2c%20215.03)'%20data-evernote-id='1036'%3eE%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='matrix(0.67%2c%200.74%2c%20-0.74%2c%200.67%2c%2058.13%2c%20227.36)'%20data-evernote-id='1037'%3eR%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(69.16%20238.92)%20rotate(39.44)'%20data-evernote-id='1038'%3eT%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='matrix(0.85%2c%200.53%2c%20-0.53%2c%200.85%2c%2081.47%2c%20248.73)'%20data-evernote-id='1039'%3eI%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(94.94%20256.83)%20rotate(24.36)'%20data-evernote-id='1040'%3eF%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(109.34%20263.09)%20rotate(16.83)'%20data-evernote-id='1041'%3eI%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(124.46%20267.41)%20rotate(9.34)'%20data-evernote-id='1042'%3eE%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(139.99%20269.73)%20rotate(1.88)'%20data-evernote-id='1043'%3eD%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(155.7%20270.01)%20rotate(-5.58)'%20data-evernote-id='1044'%3e%20%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(171.32%20268.24)%20rotate(-13.06)'%20data-evernote-id='1045'%3e%20%3c/text%3e%3ctext%20class='cls-2%20js-evernote-checked'%20transform='translate(187.55%20266.81)%20rotate(-21.04)'%20data-evernote-id='1046'%3e.%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(203.27%20257.7)%20rotate(-29.24)'%20data-evernote-id='1047'%3e%20%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(216.84%20249.83)%20rotate(-36.75)'%20data-evernote-id='1048'%3e%20%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(229.26%20240.26)%20rotate(-44.15)'%20data-evernote-id='1049'%3e2%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(240.39%20229.13)%20rotate(-51.62)'%20data-evernote-id='1050'%3e0%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='translate(249.97%20216.63)%20rotate(-59.17)'%20data-evernote-id='1051'%3e2%3c/text%3e%3ctext%20class='cls-3%20js-evernote-checked'%20transform='matrix(0.4%2c%20-0.92%2c%200.92%2c%200.4%2c%20257.81%2c%20203.04)'%20data-evernote-id='1052'%3e2%3c/text%3e%3cpath%20class='cls-4%20js-evernote-checked'%20d='M196.64%2c136.31s3.53%2c3.8%2c8.5%2c3.8c3.9%2c0%2c6.75-2.37%2c6.75-5.59%2c0-4-3.64-5.81-8-5.81h-2.59l-1.53-3.48%2c6.86-8.13a34.07%2c34.07%2c0%2c0%2c1%2c2.7-2.85s-1.11%2c0-3.33%2c0H194.79v-5.86H217.7v4.28l-9.19%2c10.61c5.18.74%2c10.24%2c4.43%2c10.24%2c10.92s-4.85%2c12.3-13.19%2c12.3a17.36%2c17.36%2c0%2c0%2c1-12.41-5Z'%20data-evernote-id='1053'%3e%3c/path%3e%3cpath%20class='cls-4%20js-evernote-checked'%20d='M152%2c144.24l30.24%2c53.86%2c14.94-26.61L168.6%2c120.63H135.36l-13.78%2c24.53-13.77-24.53H77.93l43.5%2c77.46.15-.28.16.28Z'%20data-evernote-id='1054'%3e%3c/path%3e%3c/svg%3e)

[Get started](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

#### [CODE GAME](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[![](_attachments/w3lynx_200.png)](https://www.w3schools.com/css/css_rwd_grid.aspundefined) [Play Game](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

ADVERTISEMENT

------------------------------------------------------------------------

[Report Error](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[Forum](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[About](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[Shop](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

------------------------------------------------------------------------

##### Top Tutorials

[HTML Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[CSS Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[JavaScript Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[How To Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[SQL Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Python Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[W3.CSS Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Bootstrap Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[PHP Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Java Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[C++ Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[jQuery Tutorial](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\

##### Top References

[HTML Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[CSS Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[JavaScript Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[SQL Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Python Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[W3.CSS Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Bootstrap Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[PHP Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[HTML Colors](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Java Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Angular Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[jQuery Reference](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\

##### Top Examples

[HTML Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[CSS Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[JavaScript Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[How To Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[SQL Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Python Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[W3.CSS Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Bootstrap Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[PHP Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Java Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[XML Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[jQuery Examples](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\

##### Web Courses

[HTML Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[CSS Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[JavaScript Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Front End Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[SQL Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Python Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[PHP Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[jQuery Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Java Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[C++ Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[C# Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[XML Course](https://www.w3schools.com/css/css_rwd_grid.aspundefined)\
[Get Certified »](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

------------------------------------------------------------------------

W3Schools is optimized for learning and training. Examples might be simplified to improve reading and learning. Tutorials, references, and examples are constantly reviewed to avoid errors, but we cannot warrant full correctness of all content. While using W3Schools, you agree to have read and accepted our [terms of use](https://www.w3schools.com/css/css_rwd_grid.aspundefined), [cookie and privacy policy](https://www.w3schools.com/css/css_rwd_grid.aspundefined).\
\
[Copyright 1999-2022](https://www.w3schools.com/css/css_rwd_grid.aspundefined) by Refsnes Data. All Rights Reserved.\
[W3Schools is Powered by W3.CSS](https://www.w3schools.com/css/css_rwd_grid.aspundefined).\
\

[**](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[\
\
](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

[](https://www.w3schools.com/css/css_rwd_grid.aspundefined)

\
