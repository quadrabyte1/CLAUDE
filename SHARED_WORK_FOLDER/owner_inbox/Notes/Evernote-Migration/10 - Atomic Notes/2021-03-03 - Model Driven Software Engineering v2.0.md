---
title: Model Driven Software Engineering v2.0
uid: 20210303T1425
created: '2021-03-03'
updated: '2024-04-01'
source: evernote
original_notebook: My Notes5
tags: []
aliases: []
---

- ☐

  Raising the Level of Abstraction

  - ☐

    Barriers to entry

    - ☐

      Steep learning curve

    - ☐

      Expensive modeling tools

    - ☐

      Significant change in approach

  - ☐

    A powerful analogy: Computer Aided Design (CAD)

    - ☐

      Thirty years ago, still lots of drafting tables, vellum, and pencils

    - ☐

      Today, not a drafting table in sight

    - ☐

      So many advantages to the data-driven approach of CAD

  - ☐

    Advantages of abstraction that modeling brings

    - ☐

      Much of the software task can be done in data, rather then code

    - ☐

      A code generator will always follow coding standards

    - ☐

      *The model is the code...*

- ☐

  A Methodical Approach: Executable UML

  - ☐

    Relies on the Universal Modeling Language (UML)

  - ☐

    More than just a series of diagrams--more like a database representation

  - ☐

    Three layers (every time)

    - ☐

      Domain chart—organizes the problem into high level packages

    - ☐

      Class diagrams—formalizes the organization of each domain’s data

    - ☐

      State machine diagrams—expresses the dynamic behavior of each class, if any

  - ☐

    Domain chart

    - ☐

      A map of the entire problem

    - ☐

      Including the hierarchy of dependencies

    - ☐

      Not all domains must be modeled--some may be "realized"

  - ☐

    Class Diagrams

    - ☐

      One class diagram for each modeled domain

    - ☐

      Including: classes with attributes, formal relationships among classes

    - ☐

      The "database" representation of the problem

  - ☐

    State Machines

    - ☐

      Any class with dynamic behavior gets a state machine model

    - ☐

      State machines are driven by events

    - ☐

      Events are attached to transitions between states

    - ☐

      Assumption: events are never lost and never casually discarded

- ☐

  A Simple Example: Mine Sweeper

  - ☐

    The model

    - ☐

      Simple domain chart with only two domains

      - ☐

        ***User Interface*** depends upon ***Mine Logic*** to get work done (realized)

      - ☐

        ***Mine Logic*** is represented by a full model

    - ☐

      Class diagram has two classes, an interface block, and an enumeration

      - ☐

        ***Game Board*** -- an abstraction for the area of play

      - ☐

        ***Space*** -- represents one of the squares of the game board

      - ☐

        ***Mine Sweeper Bridge*** -- provides all the interface options for clients

      - ☐

        ***eSPACE_STATE*** -- all possibilities for the attribute ***CurrentSpaceState***

    - ☐

      State machines

      - ☐

        ***Game Board SM***-- basically just a single state to start a new game

      - ☐

        ***Space SM*** -- here is where all the real work is done

  - ☐

    The generated code

    - ☐

      Target language in this case is C#

    - ☐

      Action language is simply proper C# code (transferred directly to source code)

    - ☐

      All the infrastructure is supplied by the code generator

    - ☐

      Generated code is well formatted and easy to read

  - ☐

    Demo: It works

    - ☐

      ***User Interface*** domain was written in C#

    - ☐

      All the pixels and clicks are handled by the realized domain

    - ☐

      But all the behavior of the game is handled by the ***Mine Logic*** domain

  - ☐

    Demo: Debugging

- ☐

  For More Information

  - ☐

    Books

  - ☐

    Contact

\
