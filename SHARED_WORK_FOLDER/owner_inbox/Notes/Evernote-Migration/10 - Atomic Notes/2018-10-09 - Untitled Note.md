---
title: Untitled Note
uid: 20181009T2241
created: '2018-10-09'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes5
tags: []
aliases: []
---

MetaVisor Requirements Collection

\

(Definition of Terms section copied to the Gdrive: [https://docs.google.com/document/d/19KFWS5UyR9SjdtFpZzgfWCVqI-Tgu57moSfP-0aF_tM/edit](https://docs.google.com/document/d/19KFWS5UyR9SjdtFpZzgfWCVqI-Tgu57moSfP-0aF_tM/edit))

\

**Definition of Terms**

The FFA and MetaVisor designs have been evolvng in parallel, with a considerable amount of collaboration between Joe Cesena and Thomas Brennan-Marquez since September 2017. Among  other things that have been decided are a significant number of entities and names for those entities. This section lists several of the most central conceptual entites by name and explains what each name signifies. Please note that the Verb System Information Model is a detailed UML class model which formalizes all of these names and the relationships among the entities. That model is also the source of the XML schema specification (in the form of an XSD file) for the new FFA representation as an XML file.

\

- - ☐

    **Reporter**

For the purposes of the MetaVisor decsion making process the entire system is divided into individual Reporters. For example, each of the robotic arms are given unique Report identification code. Because there are plans to introduce a second Surgeon Bridge to the system, each of the possible Surgeon Bridges are assigned unique Reporter identification codes. 

\

Note that a particular Reporter will, in general, be host to a number of Algorithms, each of which in turn is the source of current information about their respective Facts.

\

- - ☐

    **Truth Value**

Refers to the present true/false value of a particular Fact. For example, in the middle of the day we might say of the Fact proposition "The Sun is in the Sky" that, indeed, it has a truth value of TRUE. At night we would say that same Fact proposition had a truth value of FALSE.

\

- - ☐

    **Algorithm**

A bit of software running "close" to the hardware and responsible for making, at minimum, a true/false status determination of a single Fact. In many cases there is already software running somewhere in the system that "knows" the truth value of a particular Fact and all that needs to be done to get that status to the MetaVisor is to add a pair of reporting calls to the existing code.

\

- - ☐

    **Check**

The generic verb to describe what an Algorithm actually *does* (at least with respect to our present discussion of MetaVisor-related considerations) is to Check. For example, in our Sun in the sky example above, the software responsible for determining whether the Sun is in the sky (an Algorithm) could be said to "check" whether the Sun is in the sky or not.

\

- - ☐

    **Reporting Message**

Each Algorithm is responsible for providing a periodic reporting of the present status of a single Fact. Such reports are sent to the MetaVisor individually and always contain the following: a) the identification code for whatever Reporter is host to this Algorithm, b) the identification code for the particular Fact being reported, c) the Truth Value of that Fact as of right now, and d) an optional explanatory string which will be saved in the MetaVisor's operational log.

\

\

- - ☐

    **MetaVisor Decision Engine**

The decision making software part of the MetaVisor subsystem is called the Decision Engine. That software will recieve the simple, individual status messages sent by all the Algorithms sprinkled throughout the system. Each received message 

\

- - ☐

    **Fact**

A single bit of true/false information about the status of the system. As conditions change in the system, the Truth Values of a large number of Facts will change from True to False, False to True, and possibly back again. Each Fact is assigned a unique identifier for the purpose of reporting a fresh Truth Value to the MetaVisor. It is imperative that Facts are reported on a periodic basis, irrespective of the reported Truth Value at any particular moment. That way, the MetaVisor can be confident that the Truth Value presently on hand during the decision making process is up to date (at least within the time window represented by the reporting period for a given Fact).

\

- - ☐

    **Trigger Pattern**

Another way to think of the Status Vector representation of the system's present state is to envision a set of N bits collected together in a single binary word. Each bit is dedicated to hold the latest Truth Value of exactly one Fact. Each Situation described in the FFA has associated exactly one Trigger Pattern corresponding to the True/False values of specific Facts. The decision making software will compare each Trigger Pattern against the present Status Vector to decide when a particular Situation is, in fact, the case *right now*.

\

When Trigger Patterns need to be compared to the present configuration of the Status Vector, a set of working comparison blocks are constructed for each Situation in turn:

\

**Don't Care Block**

Assemble a set of "1" bits in a binary word of equal bit-size as the Status Vector. This block is thus initialized to indicate that *every Fact* is of no interest to the Situation about to be processed.

\

**Logical Pattern Block**

Assemble a set of "1" bits in the Logical Pattern Block of equal bit-size as the Status Vector. For each of the Facts associated with the Situation under consideration, follow these simple rules:

-- If the Situation expects a Fact's bit position to be TRUE upon detection, the bit in that position is left in the default "1" state and the corresponding position in the Don't Care Block is set to zero (because this bit position *is* of interest to this Situation).

-- If the Situation expects a bit position to be FALSE upon detection, the bit in that position is set to "0" and the corresponding position in the Don't Care Block is set to zero (because this one is also of interest).

\

**Modified Status Vector Block**

This modified block is created by logically ORing the Don't Care Block with the present Status Vector--in effect setting all the bits of the Status Block to one which are of no interest to this Situation. All the bit positions which *are* of interest to the Situation will retain the Truth Value of the corresponding Fact that reflects the present status of the system.

\

Now the test for whether the Situation is presently occuring in the system becomes a simple test for equality between the Logical Pattern Block and the Modified Status Vector Block. Every bit of interest to this Situation will either be the same as the Modified Status Vector Block bit in that same position (when a Fact is found to be in the expected state presently) or the two values will not agree (when a Fact is not found to be in the expected state. Notice that all the bits in Don't Care positions will be one in both blocks and so will effectively contribute nothing to the test for equality.

\

- - ☐

    **Status Vector**

The complete set of all Facts being reported to the MetaVisor is called the Status Vector. This name corresponds to a sort of multi-dimensional state space in which the system operates throughout time. As the system state evolves, one can think of the Status Vector as "pointing" to the *present state* of the system so that each change of Truth Value causes a move to a new location in this "status space." (For more information on this concept of multi-dimensional spaces, see [Hilbert Space](https://en.wikipedia.org/wiki/Hilbert_space).)

\

- - ☐

    **Trigger Response**

Each Situation has zero or more actions to perform whenever that Situation is detected in the Status Vector. There are only a small number of action types:

\

**System Action Request**

If the detected Situation calls for a change in the operational state of the system (e.g., teleoperation must be terminated) the MetaVisor may send a message to some other part of the system to effect that change. Notice that the MetaVisor itself does not perform any of the response actions but can only make requests of other parts of the system.

\

**Auditory Request**

In cases where the staff in the OR needs to be alerted to a situation pertinent to the system, an auditory signal may be requested by the MetaVisor.

\

**LED Control Request**

Where LEDs need to be manipulated to alert staff in the OR, the MetaVisor may send a request message to cause the change.

\

**Notification Message**

One of the more common responses to exceptional conditions is just a text message which is presented to the staff on one or more of the display monitors. Note that these messages will always carry a "severity" code to guide the Notification Server with placement, color, size, etc. of the text that is displayed.

\

- - ☐

    **Situation**

The FFA is essentially a collection of possible exceptional situations which have been identified through the risk/hazard analysis process. Broadly speaking, each situation is comprised of just two parts: a set of Facts are called out which must be found in specific True/False states and a set of zero or more actions to be performed when those facts are found to be in those particular states. These two-part entities are called Situations. 

\

- - ☐

    **Functional Fault Analysis (FFA) **

Usually known by its three letter acronym, the FFA is a collection of four distinct, but related, things (see the System Information Model for the details of the relationships among them):

\

**Analysis Threads**

The Analysis Threads represent a line of reasoning which was constructed by a hazard/risk engineer. The point of an Analysis Thread is to consider all the situations which might occur when failures or unexpected operator actions happen on the system. A single Analysis Thread may group a collection of related Situations (discussed next) into a logically bound set.

\

**Situations**

Situations are said to arm/trigger when some particular set of status conditions (also known as Facts) are found to be in a particular pattern of True/False values. When that happens, the MetaVisor will issue a set of zero or more Trigger Response messages so that the system as a whole behaves properly as a result of the Situation occurring.

\

**Facts**

Facts are simply yes/no (or true/false) statements about various aspects of the system's behavior. A properly constructed collection of Facts can very precisely define when a particular Situation has occurred. For example, when an arm fails (Arm OK = false) and that arm is holding the endoscope (Holds Endoscope = true) a particular Situation has occured and will trigger with response messages. 

\

**Responses**

When a Situation triggers (becomes active because its Trigger Pattern is found) the MetaVisor will issue zero or more response messages requesting that system behavior be changed in some way appropriate to the Situation just detected.

\

\

**Decision Engine**

- - ☐

    Startup

    - ☐

      At startup the Decision Engine reads a text file in which the current set of Situations and Responses are encoded (Rules.xml)

    - ☐

      When the Rules.xml file is read, the Decision Engine runs a validity check against the appropriate .XSD schema description file before acting on the contents found in that file.

    - ☐

      Once the Rules.xml file has been validated, the Decision Engine software constructs all the necessary data structures in RAM so that the file text can be discarded.

  - ☐

    Reporting of Facts

    - ☐

      Each yes/no status item is called a Fact. 

    - ☐

      Facts are reported to the MetaVisor by software running "deeper" in the system--the MetaVisor can be imagined in a supervisory role, watching the status of the entire system from a "higher" perspective than the software/firmware running closer to the hardware can manage. 

  - ☐

    Detection of Situations

    - ☐

      Arming vs. Triggering

\

\

\

**Reporter Support Class**

\

## See also

- [[Enterprise Architect]]
- [[Maker & Electronics]]
- [[Software Development]]
