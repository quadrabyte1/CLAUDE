---
title: Untitled Note
uid: 20160901T1909
created: '2016-09-01'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes4
tags:
- journal
aliases: []
---

private int assertConditionTrue(char\* conditionDescription, int conditionValue)

Thursday, September 01, 2016

12:09 PM

 

private int assertConditionTrue(char\* conditionDescription, int conditionValue)

{

if (!conditionValue)                                                // if the conditon value is NOT true, announce that fact

{

SupervisorDebug(DEBUG_FULL, "      assertConditionTrue failed: %s", conditionDescription);

}

return conditionValue;

}

 

 

private int AssertConditionFalse(char\* name, int value)

{

if (value)

{

SupervisorDebug(DEBUG_FULL, "AssertConditionFalse failed: %s", name);

 

}

return value;

}

 

 

Created with Microsoft OneNote 2010

One place for all your notes and information
