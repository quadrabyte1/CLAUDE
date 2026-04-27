---
title: Untitled Note
uid: 20170309T2341
created: '2017-03-09'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes3
tags: []
aliases: []
source_url: http://stackoverflow.com/questions/2846653/how-to-use-threading-in-python
---

Python Notes     

\

loading a .py file to execute: 

exec(open('zzz.py').read())

\

------------------------------------------------------------------------

\

formatting printed output (see [https://pyformat.info/](https://pyformat.info/)):

\

     "\_\_{:{fieldWidth}.{precision}f}\_\_".format( 3.1415, fieldWidth=10, precision=3 )    =\>  '\_\_     3.142\_\_'

\

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIiIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjMmlPRzUiIC8+PC9zdmc+)

HTML Content

```
'{:{width}.{prec}f}'.format(2.7182, width=5, prec=2)
```

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIiIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjMmlPRzUiIC8+PC9zdmc+)

HTML Content

\

*` 2.72`*

\

------------------------------------------------------------------------

help('modules') will show every available module -- not what is loaded right now

------------------------------------------------------------------------

creating and running tests in PyCharm: [http://confluence.jetbrains.com/display/PYH/Creating+and+running+a+Python+unit+test](http://confluence.jetbrains.com/display/PYH/Creating+and+running+a+Python+unit+test)

------------------------------------------------------------------------

Notes on heapqueue can be found here: https://docs.python.org/2/library/heapq.html

------------------------------------------------------------------------

\

here's an example of using threading and a queue that is useful (from [http://stackoverflow.com/questions/2846653/how-to-use-threading-in-python](http://stackoverflow.com/questions/2846653/how-to-use-threading-in-python)):

\

`def get_url(q, url):`

`     q.put(urllib2.urlopen(url).read())`

\

` theurls = ["http://google.com", "http://yahoo.com"]`

\

` q = Queue.Queue()`

\

`for u in theurls:`

`     t = threading.Thread(target=get_url, args = (q,u))`

`     t.daemon = True`

`     t.start()`

\

` s = q.get()print s`

## See also

- [[Software Development]]
