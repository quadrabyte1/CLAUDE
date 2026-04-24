---
title: Untitled Note
uid: 20180515T1715
created: '2018-05-15'
updated: '2024-04-02'
source: evernote
original_notebook: My Notes3
tags: []
aliases: []
---

**System Software Architecture**

The Verb Digital Surgery System is comprised of a large number of physical systems and devices which must all operate in a coherent, logical, and intuitive manner. It is the responsibility of each of the system software units to manage such behavior and the responsibility of the System Software Architecture to insure that all those software units behave in a coordinated, carefully managed way. 

\

The System Software Architecture is much like the Conductor of a full orchestra, with each of the individual software units corresponding to the individual Musicians playing each of the Instruments which make up the orchestra. A patient's procedure can be likened to the entire orchestra creating the full richness of a composer's symphony with all of it's various themes, nuances, and color. Of course, as the symphony is playing it may not be obvious to a casual observer that there are, in fact, multiple musical strands being blended and intertwined as the full performance unfolds. 

\

Similarly, the surgical procedure is actually composed of a number of individual tasks which must be performed perfectly, at the proper times, by specific parts of the overall system. This document is intended to identify those individual tasks to convey a sense of the overall architecture of the system, much as a student of our imagined symphony might study its many pages to discover what component parts go into the production of such a complex performance.

\

Much like the various themes which appear, disappear, and then appear again in the symphony, the Verb Digital Surgery System supports a fairly small number of interactive mechanisms which become active, go inactive, and return to activity at some later time during the procedure in the OR. 

\

Each of those interaction mechanisms are described in the following pages. Each mechanism is described via a set of annotated copies of the overall system block diagram along with a short description of just what is going on at each step of the process. For reference, the full set of mechanisms is listed here:

\

**Interactive Mechanisms**

**Engagement**

The behavior and intention of the surgeon must be tracked carefully during a procedure to guarantee that no tool movements occur when the surgeon does not intend movement. When the surgeon is paying close attention to the state of the surgical system, the patient, and the team of support people in the OR, we say the surgeon is "Engaged." It is only when in this state that the surgical system will translate the surgeon's movements of the UID devices into movement of the corresponding Tools. 

**Visualization**

**Safety Monitoring**

**Tool Behavior**

**Surgeon Affordances**

**Data Gathering and Logging**

\

\

\

**Engagement**

The behavior and intention of the surgeon must be tracked carefully during a procedure to guarantee that no tool movements occur when the surgeon does not intend movement. When the surgeon is paying close attention to the state of the surgical system, the patient, and the team of support people in the OR, we say the surgeon is "Engaged." It is only when in this state that the surgical system will translate the surgeon's movements of the UID devices into movement of the corresponding Tools. 

\

**Engagement -- Eye Tracking**

If the surgeon shifts her visual attention away from the endoscope-provided view of the surgical process it musts be assumed that she is no longer intends to move any of the surgical tools under her control. The Gaze User Engagement Monitor Runner will detect the loss of visual attention and will report that fact to the Workspace User Engagement Runner.

\

**Engagement -- UID Tracking**

If the surgeon either  drops or sets aside  one of the UID  devices it musts be  assumed that she  no longer intends  to move any of  the surgical tools  under her control.  The UID Service  will detect that  one (or both) of  the UIDs have  gone to an  unused state and  will report that  fact to the  Workspace User  Engagement  Runner.

\

**Engagement -- Surgeon Chair Swivel**

The surgeon's chair is capable of swiveling approximately 270 degrees providing three different orientations of the chair:

- ☐

  Pointing straight forward toward the Open Display Monitor

- ☐

  90 degrees to the left of the forward orientation to allow entry/exit on the left side of the Surgeon Bridge

- ☐

  90 degrees to the right of the forward orientation to allow entry/exit on the right side of the Surgeon Bridge

The Surgeon Bridge Controller will detect whenever the chair is swiveled away from the straightforward position and will will report that  fact to the  Workspacee User  Engagement  Runner.

\

**Engagement -- Engagement Evaluation**

If any of the monitored conditions change to a state which indicates that the surgeon does **not** intend to move the surgical tools, we say the surgeon is "Disengaged" and all movement of tools is suspended. 

\

**Engagement -- Report Engagement Status**

The Workspace User Engagement Runner is responsible for testing for changes in the Engaged/Disengaged status of the surgeon, reporting those changes to the Platform Controller.
