---
title: Coding and Modeling Standards
uid: 20120307T2309
created: '2012-03-07'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes4
tags:
- programming
aliases: []
---

Coding and Modeling Standards

Wednesday, March 07, 2012

3:09 PM

Coding Standard

. SlickEdit has a mechanism to 'Beautify' a file

We will establish a set of rules in that tool

Always apply the beautify operation to a file

. CamelCaseNames

. uppercase first letter if global

. lowercase first letter if static (local) to this file/module

. make everything you can static (minimal scoping)

. 4 spaces per indent step

. no tabs

. \#define UPPERCASE_WITH_UNDERSCORES

. inline comments aligned at column 70 (SE will do this for you)

. don't use /\* \*/ because they don't nest

. do use // for comments because they do

. don't use conditional compiling (ever, if possible)

. to comment out a block of code use // not \#if 0 as some people do

. do add a file header with at least some information about what its for

. don't boilerplate headers but then leave all the fields blank

. longer descriptive names are better (and with intellisense, don't type them)

. needless to say, NEVER use GOTO

. always follow structured programming techniques

with the rare exception of bailing out immediately because something is wrong...

...always have a single exit point from a function (i.e., only one single return statement)

. avoid global variables

 

Modeling Standard

. always us the autonumbering mechanism available in EA

See *Settings/Auto Names and Counters*

Triggers (events)

Always start with 'ev' and a number plus an underscore:  ev231_DoSomething

Avoid spaces (because it makes double-click + ctrl-C pickup of an event name easy)

Use CamelCaseNames

States

Spaces are okay (we never copy/paste state names)

Always start with 'S' and a number:   S123 Await Next Message

All words capitalized (or camel case)

. Classes

Spaces are okay (we never copy/paste state names)

All words capitalized (or camel case)

. Transitions

Color coding can help readability but is optional

Red = External events, sent from outside this state model

Blue = Delayed events

Yellow = Ignored events

Black = otherwise

In a properly setup project there will probably be a set of 'styles' setup to follow these conventions

. Hyperlinks

Always add a hyperlink back to the parent diagram (e.g., from a state model back "up" to the related class diagram)

In the case of a link from a class diagram to a state model, if you put the link entirely within the class rectangle, it will move with the rectangle automatically if the diagram is rearranged

. Attributes

Always add a description of exactly what the attribute is used for or means

Best to do this when you create it -- very helpful later when even you can't remember exactly what that attribute was for

Names should not use spaces (although the EACompiler will substitute spaces with underscores)

. Relationships

Relationships MUST have names--preferably like this: R100

Names must be unique

Do put the role strings in on both sides of the relationship because it helps with readability

Both ends of a relationship MUST have multiplicities indicated

1

0..1

0..\*

1..\*

 

Created with Microsoft OneNote 2010

One place for all your notes and information

## See also

- [[Software Development]]
- [[Enterprise Architect]]
