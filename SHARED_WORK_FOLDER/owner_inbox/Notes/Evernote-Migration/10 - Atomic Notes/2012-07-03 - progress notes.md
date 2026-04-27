---
title: progress notes
uid: 20120703T2109
created: '2012-07-03'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes4
tags: []
aliases: []
---

- ☐

  finish the WiX implementation 

  both dashboard and EAComplier will do it that way when available

- ☐

  \

- ☐

  \

- ☐

  \

- ☐

  for Edward some TLVs are not appearing in the list because those attribute types are not recognized

  the types are legal but the EACompiler needed rework to use the derived types .xml file for the lookupneed a string version to roll into EAComiler at build timeadded a new file output from derivation: DerivedDataTypes.vb to hold just a single string value version of the xml filethe reworked type handling doesn't like pointer typeswhich breaks Kevin's way of loading up the message for Dashboard delivery

  \

  change that handling to use a new allocated string type: TRACE_ENTRYbut turns out Jon has added the module id to filter trace entries which makes the trace entry a 20-byte thing -- no good for in-memory viewingKevin and I come up wth a better scheme for the trace buffer:enumerate domainseach domain gets a bit in a maskdashboard can have checkboxes for each domaindon't change the DEBUGTRACE macro so nothing will break (here comes the magic)undef DEBUGTRACE in each domain's code file, adding in the domain id under the hoodexcept where foreground is concerned -- that will be the un-undef'd version because there is no domain thereimplementing that now...bump... gotta fix the build I broke

## See also

- [[Software Development]]
