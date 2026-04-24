---
title: Untitled Note
uid: 20190311T1905
created: '2019-03-11'
updated: '2024-04-02'
source: evernote
original_notebook: My Notes3
tags: []
aliases: []
source_url: https://duckduckgo.com/?q=schlaer+mellor&t=brave&ia=web
---

submitted: Thu 14-Mar-19 08:54 AM

\

\

Participant Outcomes: By the end of this paper, participants will be able to

Locate a set of tools on the web with which they should be able to go through the whole demonstrated example (also available online and simple enough to model-compile, C++ compile, and run):

   \* Visual Studio -- free from Microsoft and includes both the C++ compiler and an IDE to run the example

   \* A transform tool (written in C#) that uses a set of XSL files to do the model compilation

   \* The example model in both Cameo and Enterprise Architect formats

   \* Plus the exported XML representations of the model from those tools (as that is what is needed by the model compiler)

   \* A simple test jig application written in Visual C++ to exercise the generated code

   \* Step by step instructions on how to put all the pieces to together to run the example.

\

Thomas has been building embedded software systems for forty years in Silicon Valley. He has been an enthusiastic proponent of model-driven software development since being trained in the Schlaer-Mellor modeling/development methodology in the '80s. With experience building model-based systems in a variety of application fields (medical devices, solar energy applications, electrical vehicles, laboratory analysis equipment, and DNA sequencing), Thomas has seen a disappointing degree of adoption of this very promising technology. He has recently embarked on an effort to do whatever he can to get the word out that model driven development is a path to a quantum leap in the quality, robustness, and maintainability of software systems.

\

*The Model Is the Code*

\

*The use of models in the software development community has been very slow to take hold over the last few decades. There are many reasons for this slow uptake of a very powerful approach, but perhaps two of the most obstinate impediments are these:*

- ☐

  *the learning curve is widely seen as very steep, and*

- ☐

  *even if a model is produced before coding begins, that model becomes obsolete rather quickly as the "real work" of writing and debugging code progresses.*

\

*But there is good news on both these fronts: *

- ☐

  *There is a methodological approach to creating software through the use of a set of simple rules and using only a small subset of the vast array of visual elements provided by UML--Executable UML (heavily based on work by Sally Shlaer, Stephen Mellor, Andrew Mangogna, and Leon Starr).*

- ☐

  *Any of the available modeling tools can be used to handle the model construction tasks (provided those tools can export the contents of the model in the standard XMI format).*

- ☐

  *Given a relatively simple set of XML =\> source code transforms and a small amount of supporting code, it is possible to:*

  - ☐

    *move 90% (or more) of the development work into the realm of the modeling tool of choice,*

  - ☐

    *produce actual executable (and eventually shippable) code directly from the constructed model, and,*

  - ☐

    *because the model is the source of truth for the generated code, guarantee that the model remains relevant, informative, and useful throughout the life of the project.*

\

*The aim of this presentation is to take the audience through an existing fault management system that was developed for use on a surgical robot. This simple application was developed entirely through an information model and accompanying state models following the Executable UML philosophy and using a set of supporting tools that will soon be made available in the public domain. Without diving into the modeling techniques used (there are books available that will help interested audience members learn those aspects of the approach) the emphasis here will be to illustrate just how the model can be transformed into running code.*

\

*After a quick tour of the various parts of the modeling/code development system, we will *

- ☐

  *run the code compiler to produce the executable code,*

- ☐

  *run a simple test jig application that exercises the generated code,*

- ☐

  *debug a minor problem that becomes apparent when the code runs (to alleviate a common concern that the generated code is so complicated and hard to understand it cannot easily be debugged), and*

- ☐

  *finally, add a new feature to the application through the addition of a new state in one of the state models.*

\

*By the end of the presentation, it will hopefully be clear that this approach is not as daunting as it first appears. By putting the tools we have demonstrated to use (all of them freely available through a Git repository on the web) most of the development necessary to solve some other particular problem would be limited to creating good models rather than writing hundreds of lines of code.*
