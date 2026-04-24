---
title: Node and nom (trying to fix a bunch of error messages)
uid: 20131204T0317
created: '2013-12-04'
updated: '2024-04-01'
source: evernote
original_notebook: My Notes4
tags: []
aliases: []
---

## from [https://github.com/joyent/node/wiki/installation](https://github.com/joyent/node/wiki/installation) 

## Mac OSX

It's easiest to use a [package manager (as mentioned above)](https://github.com/joyent/node/wiki/Installing-Node.js-via-package-manager#osx) such as brew or macports.

### Building on Mac OSX 10.8 with Xcode 4.5

1.  

    ☐

    Install Command Line Tools

    Xcode: Preferences-\>Downloads install Command Line Tools

    *Note: I installed Xcode 4.5 in **`/Applications/Xcode`*

2.  

    ☐

    Download node.js src code

3.  

    ☐

    Compiling Source Code

\
-

\

\

\

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

2013-12-03 18:55 node\[5093\] (CarbonCore.framework) FSEventStreamStart: register_with_server: ERROR: f2d_register_rpc() =\> (null) (-21)

^CEnding process and children

Interrupting process group 5095

Waiting on process group 5095

2013-12-03 18:56 python2.7\[5095\] (CarbonCore.framework) streamRef-\>cfRunLoopSourceRef != NULL \|\| streamRef-\>event_source != NULL(): failed assertion: Must call FSEventStreamScheduleWithRunLoop() before calling FSEventStreamInvalidate()

2013-12-03 18:56 python2.7\[5095\] (CarbonCore.framework) FSEventStreamRelease: ERROR: over-released FSEventStreamRef

Exception in thread Thread-1:

Traceback (most recent call last):

  File "/usr/local/Cellar/python/2.7.5/Frameworks/Python.framework/Versions/2.7/lib/python2.7/threading.py", line 808, in \_\_bootstrap_inner

    self.run()

  File "/Users/trbm/.virtualenvs/edx-platform/lib/python2.7/site-packages/watchdog/observers/api.py", line 253, in run

    self.on_thread_exit()

  File "/Users/trbm/.virtualenvs/edx-platform/lib/python2.7/site-packages/watchdog/observers/api.py", line 409, in on_thread_exit

    self.unschedule_all()

  File "/Users/trbm/.virtualenvs/edx-platform/lib/python2.7/site-packages/watchdog/observers/api.py", line 405, in unschedule_all

    self.\_clear_emitters()

  File "/Users/trbm/.virtualenvs/edx-platform/lib/python2.7/site-packages/watchdog/observers/api.py", line 282, in \_clear_emitters

    for emitter in self.\_emitters:

TypeError: PyCObject_AsVoidPtr called with null pointer

Done waiting on process group 5095

Ending process and children

Interrupting process group 5094

Waiting on process group 5094

Done waiting on process group 5094

Ending process and children

Interrupting process group 5093

Waiting on process group 5093

Done waiting on process group 5093

(edx-platform)

~/edx_all/edx-platform\> npm list

mitx@0.1.0 /Users/trbm/edx_all/edx-platform

├── coffee-script@1.6.3

├─┬ grunt@0.4.2

│ ├── async@0.1.22

│ ├── coffee-script@1.3.3

│ ├── colors@0.6.2

│ ├── dateformat@1.0.2-1.2.3

│ ├── eventemitter2@0.4.13

│ ├── exit@0.1.2

│ ├─┬ findup-sync@0.1.2

│ │ └── lodash@1.0.1

│ ├── getobject@0.1.0

│ ├─┬ glob@3.1.21

│ │ ├── graceful-fs@1.2.3

│ │ └── inherits@1.0.0

│ ├── hooker@0.2.3

│ ├── iconv-lite@0.2.11

│ ├─┬ js-yaml@2.0.5

│ │ ├─┬ argparse@0.1.15

│ │ │ ├── underscore@1.4.4

│ │ │ └── underscore.string@2.3.3

│ │ └── esprima@1.0.4

│ ├── lodash@0.9.2

│ ├─┬ minimatch@0.2.12

│ │ ├── lru-cache@2.5.0

│ │ └── sigmund@1.0.0

│ ├─┬ nopt@1.0.10

│ │ └── abbrev@1.0.4

│ ├─┬ rimraf@2.0.3

│ │ └── graceful-fs@1.1.14

│ ├── underscore.string@2.2.1

│ └── which@1.0.5

└─┬ grunt-contrib-sass@0.5.1

  ├── async@0.2.9

  └── dargs@0.1.0

(edx-platform)

~/edx_all/edx-platform\> npm list help

mitx@0.1.0 /Users/trbm/edx_all/edx-platform

└── (empty)

(edx-platform)

~/edx_all/edx-platform\> npm help

Usage: npm \<command\>

where \<command\> is one of:

    add-user, adduser, apihelp, author, bin, bugs, c, cache,

    completion, config, ddp, dedupe, deprecate, docs, edit,

    explore, faq, find, find-dupes, get, help, help-search,

    home, i, info, init, install, isntall, issues, la, link,

    list, ll, ln, login, ls, outdated, owner, pack, prefix,

    prune, publish, r, rb, rebuild, remove, repo, restart, rm,

    root, run-script, s, se, search, set, show, shrinkwrap,

    star, stars, start, stop, submodule, tag, test, tst, un,

    uninstall, unlink, unpublish, unstar, up, update, v,

    version, view, whoami

npm \<cmd\> -h     quick help on \<cmd\>

npm -l           display full usage info

npm faq          commonly asked questions

npm help \<term\>  search for help on \<term\>

npm help npm     involved overview

Specify configs in the ini-formatted file:

    /Users/trbm/.npmrc

or on the command line via: npm \<command\> --key value

Config info can be viewed via: npm help config

npm@1.3.11 /usr/local/lib/node_modules/npm

(edx-platform)

~/edx_all/edx-platform\> npm faq

(edx-platform)

~/edx_all/edx-platform\>

(edx-platform)

~/edx_all/edx-platform\>

(edx-platform)

~/edx_all/edx-platform\>

(edx-platform)

~/edx_all/edx-platform\> git clo

git: 'clo' is not a git command. See 'git --help'.

Did you mean one of these?

clone

column

(edx-platform)

~/edx_all/edx-platform\> git clone [https://github.com/joyent/node.git](https://github.com/joyent/node.git)

Cloning into 'node'...

remote: Counting objects: 113626, done.

remote: Compressing objects: 100% (35955/35955), done.

remote: Total 113626 (delta 90108), reused 98307 (delta 75915)

Receiving objects: 100% (113626/113626), 69.04 MiB \| 543.00 KiB/s, done.

Resolving deltas: 100% (90108/90108), done.

Checking connectivity... done

(edx-platform)

~/edx_all/edx-platform\> cd node

(edx-platform)

~/edx_all/edx-platform/node\> git checkout v0.8.2

Note: checking out 'v0.8.2'.

You are in 'detached HEAD' state. You can look around, make experimental

changes and commit them, and you can discard any commits you make in this

state without impacting any branches by performing another checkout.

If you want to create a new branch to retain commits you create, you may

do so (now or later) by using -b with the checkout command again. Example:

  git checkout -b new_branch_name

HEAD is now at cc6084b... 2012.07.09, Version 0.8.2 (Stable)

(edx-platform)

~/edx_all/edx-platform/node\> export CC=/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang

(edx-platform)

~/edx_all/edx-platform/node\> export CXX=/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang++

(edx-platform)

~/edx_all/edx-platform/node\> ./configure && make && sudo make install

{ 'target_defaults': { 'cflags': \[\],

                       'default_configuration': 'Release',

                       'defines': \[\],

                       'include_dirs': \[\],

                       'libraries': \[\]},

  'variables': { 'host_arch': 'x64',

                 'node_install_npm': 'true',

                 'node_install_waf': 'true',

                 'node_no_strict_aliasing': 0,

                 'node_prefix': '',

                 'node_shared_openssl': 'false',

                 'node_shared_v8': 'false',

                 'node_shared_zlib': 'false',

                 'node_use_dtrace': 'false',

                 'node_use_etw': 'false',

                 'node_use_openssl': 'true',

                 'target_arch': 'x64',

                 'v8_no_strict_aliasing': 0,

                 'v8_use_snapshot': 'true'}}

creating  ./config.gypi

creating  ./config.mk

/Applications/Xcode.app/Contents/Developer/usr/bin/make -C out BUILDTYPE=Release

  CC(target) /Users/trbm/edx_all/edx-platform/node/out/Release/obj.target/http_parser/deps/http_parser/http_parser.o

In file included from ../deps/http_parser/http_parser.c:24:

**../deps/http_parser/http_parser.h:30:10:** **fatal error:** **'sys/types.h' file not found**

\#include \<sys/types.h\>

**         ^**

1 error generated.

make\[1\]: \*\*\* \[/Users/trbm/edx_all/edx-platform/node/out/Release/obj.target/http_parser/deps/http_parser/http_parser.o\] Error 1

make: \*\*\* \[node\] Error 2

(edx-platform)

~/edx_all/edx-platform/node\> teerm

-bash: teerm: command not found

(edx-platform)

~/edx_all/edx-platform/node\> ls ../deps

ls: ../deps: No such file or directory

(edx-platform)

~/edx_all/edx-platform/node\> ./configure && make && sudo make install

{ 'target_defaults': { 'cflags': \[\],

                       'default_configuration': 'Release',

                       'defines': \[\],

                       'include_dirs': \[\],

                       'libraries': \[\]},

  'variables': { 'host_arch': 'x64',

                 'node_install_npm': 'true',

                 'node_install_waf': 'true',

                 'node_no_strict_aliasing': 0,

                 'node_prefix': '',

                 'node_shared_openssl': 'false',

                 'node_shared_v8': 'false',

                 'node_shared_zlib': 'false',

                 'node_use_dtrace': 'false',

                 'node_use_etw': 'false',

                 'node_use_openssl': 'true',

                 'target_arch': 'x64',

                 'v8_no_strict_aliasing': 0,

                 'v8_use_snapshot': 'true'}}

creating  ./config.gypi

creating  ./config.mk

/Applications/Xcode.app/Contents/Developer/usr/bin/make -C out BUILDTYPE=Release

  CC(target) /Users/trbm/edx_all/edx-platform/node/out/Release/obj.target/http_parser/deps/http_parser/http_parser.o

In file included from ../deps/http_parser/http_parser.c:24:

**../deps/http_parser/http_parser.h:83:60:** **error:** **unknown type name 'size_t'**

typedef int (\*http_data_cb) (http_parser\*, const char \*at, size_t length);

**                                                           ^**

**../deps/http_parser/http_parser.h:284:1:** **error:** **unknown type name 'size_t'**

size_t http_parser_execute(http_parser \*parser,

**^**

**../deps/http_parser/http_parser.h:287:28:** **error:** **unknown type name 'size_t'**

                           size_t len);

**                           ^**

**../deps/http_parser/http_parser.h:308:44:** **error:** **unknown type name 'size_t'**

int http_parser_parse_url(const char \*buf, size_t buflen,

**                                           ^**

**../deps/http_parser/http_parser.c:25:10:** **fatal error:** **'assert.h' file not found**

\#include \<assert.h\>

**         ^**

5 errors generated.

make\[1\]: \*\*\* \[/Users/trbm/edx_all/edx-platform/node/out/Release/obj.target/http_parser/deps/http_parser/http_parser.o\] Error 1

make: \*\*\* \[node\] Error 2

(edx-platform)

~/edx_all/edx-platform/node\> npm help

Usage: npm \<command\>

where \<command\> is one of:

    add-user, adduser, apihelp, author, bin, bugs, c, cache,

    completion, config, ddp, dedupe, deprecate, docs, edit,

    explore, faq, find, find-dupes, get, help, help-search,

    home, i, info, init, install, isntall, issues, la, link,

    list, ll, ln, login, ls, outdated, owner, pack, prefix,

    prune, publish, r, rb, rebuild, remove, repo, restart, rm,

    root, run-script, s, se, search, set, show, shrinkwrap,

    star, stars, start, stop, submodule, tag, test, tst, un,

    uninstall, unlink, unpublish, unstar, up, update, v,

    version, view, whoami

npm \<cmd\> -h     quick help on \<cmd\>

npm -l           display full usage info

npm faq          commonly asked questions

npm help \<term\>  search for help on \<term\>

npm help npm     involved overview

Specify configs in the ini-formatted file:

    /Users/trbm/.npmrc

or on the command line via: npm \<command\> --key value

Config info can be viewed via: npm help config

npm@1.3.11 /usr/local/lib/node_modules/npm

(edx-platform)

~/edx_all/edx-platform/node\> npm

Usage: npm \<command\>

where \<command\> is one of:

    add-user, adduser, apihelp, author, bin, bugs, c, cache,

    completion, config, ddp, dedupe, deprecate, docs, edit,

    explore, faq, find, find-dupes, get, help, help-search,

    home, i, info, init, install, isntall, issues, la, link,

    list, ll, ln, login, ls, outdated, owner, pack, prefix,

    prune, publish, r, rb, rebuild, remove, repo, restart, rm,

    root, run-script, s, se, search, set, show, shrinkwrap,

    star, stars, start, stop, submodule, tag, test, tst, un,

    uninstall, unlink, unpublish, unstar, up, update, v,

    version, view, whoami

npm \<cmd\> -h     quick help on \<cmd\>

npm -l           display full usage info

npm faq          commonly asked questions

npm help \<term\>  search for help on \<term\>

npm help npm     involved overview

Specify configs in the ini-formatted file:

    /Users/trbm/.npmrc

or on the command line via: npm \<command\> --key value

Config info can be viewed via: npm help config

npm@1.3.11 /usr/local/lib/node_modules/npm

(edx-platform)

~/edx_all/edx-platform/node\>
