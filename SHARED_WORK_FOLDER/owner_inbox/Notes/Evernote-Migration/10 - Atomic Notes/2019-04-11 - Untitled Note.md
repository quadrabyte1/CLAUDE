---
title: Untitled Note
uid: 20190411T1739
created: '2019-04-11'
updated: '2024-04-01'
source: evernote
original_notebook: My Notes5
tags: []
aliases: []
source_url: about:blank
---

notes for improving the model compiler output:

\

- ☐

  this construct can be replaced by a dictionary lookup:

  - ☐

    for single_bit_fact_candidate in SingleBitFact_list:      

  - ☐

        if single_bit_fact_candidate.FactID.value == event_instance.FactID:        # if we have found the SingleBitFact

  - ☐

            single_bit_fact = single_bit_fact_candidate

- ☐

  AllTrue...AnyFalse construct would be better expressed by a boolean expression using a True relationship and a False relationship

  - ☐

    question then is: do we need to support parenthetical grouping somehow?

\
