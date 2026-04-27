---
title: Keil microVision tool
uid: 20110830T2104
created: '2011-08-30'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes4
tags:
- arm
aliases: []
---

Keil microVision tool

Tuesday, August 30, 2011

2:04 PM

Found the place to setup the memory mapping for simulation:

Added this line to simulation.ini in the project's directory to get rid of the access errors when running

MAP 0x40000000,0x40003FFF READ WRITE

 

 

Created with Microsoft OneNote 2010

One place for all your notes and information

## See also

- [[Maker & Electronics]]
