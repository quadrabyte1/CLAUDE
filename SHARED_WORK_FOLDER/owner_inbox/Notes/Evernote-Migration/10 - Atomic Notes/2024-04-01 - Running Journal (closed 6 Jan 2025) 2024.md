---
title: Running Journal (closed 6 Jan 2025) 2024
uid: 20240401T1538
created: '2024-04-01'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes1
tags:
- running-journal
aliases: []
---

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_9:59 AM Friday, December 20, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

\

\

\

------------------------------------------------------------------------

i built the Whence way of doing image imports before we made the decision to use markdown everywhere. i am not wedded to how we do this but some observations:

1\. the line above was actually inserted by Whence from a python call to insert_image(...) so one doesn't need to know how to do the html form at all.

2\. the markdown way is somewhat limited (e.g., i don't think you can set the image size with it). the html way (which is actually also the Whence way) provides more flexibility.

3\. i think (but not certain) the markdown way assumes everything resides in either a single folder somewhere or is in the same directory as the markdown document itself. that is both a pro and a con but worth considering.

4\. here are the things i think we need to have a good solution to offer the team:

    - an automated/easy to use tool to extract images from EA/MagicDraw modeling tools.

    - image files, however they are stored, should be under Git control. not necessarily as bundled with the markdown file(s) but somehow versioned so that changes originating in a modeling tool can be detected and tracked.

    - to support an ancient presentation form like .pdf or .docx, i think we need to be able to specify height, width, justification, etc. the way we can do with html. even for web page presentations these kinds of tweaks can be important.

5\. we could allow all three ways without much trouble--downside being that everyone will use whatever form they want and so violating the SAMENESS TRUMPS EVERYTHING rule.

\- markdown syntax works fine for Whence instruction files (just getting passed through) and of course for md-only documents.

\- Whence syntax works fine, provided the SOT document is going to be pre-processed by Whence. BTW, i am in favor of adopting that as an assumption in all cases because it basically costs nothing for the writer of an md-only document but allows all Whence mechanisms (and generally python) to be embedded in the SOT file.

\- html is probably the most limited because it only works for cases where web pages are the intended final presentation mode.

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_8:23 AM Wednesday, December 18, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  just had a good meeting with Stefan, Tom, and Alejandro where some actual modeling questions (and related database representation questions) came up and i felt useful. we talked about how "sameness trumps...everything" (and Tom said this was a lesson he had learned from me 🙂) that's part of what's wrong with my work on the team. i don't feel very useful.

\

- ☐

  just a note to keep the flow going. clearly i am done with Medtronic. totally discouraged that anyone cares about what i have been working on for the last four years. oh well. it was interesting and it is time to move on now... 3D printing and web scraping are the next things to tackle.

- ☐

  touchpad off when there is a mouse:

  - ☐

    Press and hold the Windows key, and then press the q key.

  - ☐

    In the **Search** box, type *touchpad settings*.

  - ☐

    Using the up or down arrows, highlight **Touchpad settings** (System settings), and then press the Enter key.

  - ☐

    Ensure the Touchpad On or Off toggle is highlighted (it should have a box around it), and press the Spacebar to enable or disable the touchpad

\

\

Turn off IOS 18 settings to save battery

![](_attachments/Image%2020241201%20082929.png)

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_8:57 AM Wednesday, November 27, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Can we import an EA diagram to Miro for discussion?

  - ☐

    This works to move a Drawio diagram into Miro (works great:

  - ☐

    ### Import a [Draw.io](https://Draw.io) diagram

    1.  

        ☐

        In [Draw.io](https://Draw.io), open the diagram you wish to export.

    2.  

        ☐

        Cick on the **File** menu and choose **Export as** and choose **VSDX** and choose a location to save the file to.

    3.  

        ☐

        Navigate to the Miro board you wish to import the diagram to.

    4.  

        ☐

        On the Creation toolbar at left, click on **Shapes and lines**, choose **More shapes**, and click the **Import diagram** icon at the top right of the **Diagramming** panel.

    5.  

        ☐

        In the “Import diagram as a new board” dialog box, either drag and drop the .vsdx file, or click the **Choose file** button and navigate to the .vsdx file. 

    6.  

        ☐

        When the file is selected, click **Import**. 

    7.  

        ☐

        The import process will complete. Click **Go to board** to open the new board with your diagram.

- ☐

  Saving some code to do markdown indentation

SPACES_PER_HEADING_LEVEL = '\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;\&nbsp;'

\# \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

def insert_markdown_hyperlink(text_to_show, relative_address_md_file, target_is_local=True):

    if target_is_local:                         \# if the place to go is in this same file

        relative_address_md_file = f'#{convert_to_snakecase(relative_address_md_file)}'

       

    return f'\[{text_to_show}\]({relative_address_md_file})'

   

\# \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

def insert_markdown_heading(heading_level, heading_text, hyperlink=''):

    assert type(heading_level) is int, f'when calling "insert_markdown_heading", "heading_level" must be an integer'

    assert type(heading_text) is str, f'when calling "insert_markdown_heading", "heading_text" must be a string'

   

    \# we automatically give this heading an id so it can be used as a hyperlink

    \# target, a snake-case version of the heading text

    target_id = f'\<a id="{convert_to_snakecase(heading_text)}"\>\</a\>'

   

    indentation_string = SPACES_PER_HEADING_LEVEL \* (heading_level - 1)

    markdown_level_string = '#' \* heading_level

   

    if len(hyperlink) == 0:             \# if no hyperlink supplied

        return f'\n {target_id}\n{markdown_level_string} {indentation_string}{heading_text}  \n'

    else:                               \# else make a hyperlink

        return f'\n{markdown_level_string} {indentation_string}{insert_markdown_hyperlink(heading_text, hyperlink)}\n'

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_5:42 PM Thursday, November 21, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

The user guide is ready for review. There are a few sections left unwritten but those might just be discarded. Any comments welcome.

- ☐

  Branch

  - ☐

    ***feature/TAP-126277-hugo-architecture-site***  

  - ☐

    hugo-architecture-site repository

- ☐

  Although it shouldn't really be under Git control as a generated artifact, I committed it temporarily so you could just grab it for review without worrying about generating it:

  - ☐

    hugo-architecture-site\documentation\GenerationFromData\_[UserGuide.md](https://UserGuide.md)

- ☐

  It should also generate properly as well by running this python script and I would really appreciate it if you would try to run that generation process on your computer:

  - ☐

    hugo-architecture-site\build\build_GenerationFromData\_[UserGuide.py](https://UserGuide.py)

\

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_8:32 AM Monday, November 11, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  created a GPT-40 (OpenAI) API Key:

  - ☐

    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

\

![](_attachments/image%20(29).png)

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_3:13 PM Sunday, November 10, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Qidi plus 4 3D printer arrived a couple of days ago. Just starting to play with iit.

- ☐

  Open Enrollment done today:

- ☐

  ![](_attachments/image%20(28).png)

- ☐

  \

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)

Untitled Attachment

\

\

Here is a website that would be useful as an old style, clunky one:https://www.semdesigns.com/Products/DMS/DMSToolkit.html?site=SoftwareRecommendationsHere is a website that would be useful as an old style, clunky one:

https://www.semdesigns.com/Products/DMS/DMSToolkit.html?site=SoftwareRecommendations

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_7:21 AM Thursday, October 17, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Last night I was feeling quite discouraged (again) but feeling better today. Why? No idea.

- ☐

  Stefan:

  - ☐

    Tom/Lalitha/Thomas exchange suggests we need to get to the code gen stuff for DDSl and shmio

  - ☐

    While Tom is gone:

    - ☐

      Rework all his latest changes to integrate his work with mine

      - ☐

        Just make decisions (because we have been working at cross purposes)

      - ☐

        Get the gestalt working with all those changes (out on a branch)

      - ☐

        Get going on code gen for both DDS and shmio

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_7:17 PM Wednesday, October 16, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

i watched a mediocre movie, Finch, about an engineer, a robot, and a dog that looked alot like Jake. the engineer died, leaving the dog in the care of the robot. it broke my heart to watch that part. not the part about the world of humans coming to an end. but the dog being left without his dad--even though he learned to love the robot (yeah, right) it was the dad leaving that hurt. and i have seen this pattern before. when i've thought about how much easier it would be to just flip the switch and stop existing, my heart goes out to Jake because i think he loves me as much as i love him. he would be fine, of course, but he would really miss me. Terese, Kiel, Hilary, and Nate would all miss me too, of course, but it feels like Jake is the one who be most bereft.

\

racked with sobbing, the wave comes back again and crashes on the beach of my dry and sandy feeling place. i tried to let the sobbing run its full course--just let it out i said to my heart, just let the howl begin and rise and fall and eventually whimper to an end. Jake came over and climbed into my lap, all 80 pounds of him, and licked my cheek where salty tears had dried. he looked concerned. probably puzzled by the moans and crying, both sounds he doesn't hear from me. but the feeling passed (only to flair up a couple of times again that evening).

\

i know this feeling will pass but tonight it seems i am hanging on by my fingernails. trying to get through it before i disappear forever. i want to tell Joelle--but its time for me to be strong enough to go it alone. a voice inside keeps saying "i don't know if i can/will make it" but i don't know what that means really.

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_7:17 PM Wednesday, October 16, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

name idea that seems to be available (but have to check): QLinkCheck.com

working on the problem of checking links for a Web website. Here's the approach I want to take: return

One. Use beautiful soup in python to find the links hopefully that solves the ORS problem

Two. Use bolt.new to create a webpage that shows the results.

\

Maybe a map of the site with broken links shown in red

also add a next broken button and list all broken links button

\

\

monetizing ideas:

Maybe use a per broken link payment mechanism. Maybe the cost of each broken link goes down a little bit with everyone that's found. Way to either re-report links that are still broken or ignore them once reported. Question: what else does a customer need?

\

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_4:43 PM Monday, October 14, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Stefan

  - ☐

    need some direction on where to focus over the next 3 weeks while Tom is out

  - ☐

    we agreed i should make improvement changes tstarting from his master work

  - ☐

    when i am finished, hopefully before friday, he can look over the changes (along with the rest of the team to) to discuss on firday

- ☐

  \

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_11:34 AM Saturday, October 12, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  trying to have more fun in life

  - ☐

    started inventing stuff in my head and jotting down notes

    - ☐

      HexGrid like GridFinity but on a hexagonal backbone

      - ☐

        no extra parts to print to connect sheets of hex NOR to connect tool holders either

      - ☐

        \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_3:00 PM Friday, October 11, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  working with [Bolt.new](http://Bolt.new) to see if i can build a web site, maybe to do the broken link job

- ☐

  created a new Github repository called '[https://github.com/quadrabyte1/AIGenerationWork.git](https://github.com/quadrabyte1/AIGenerationWork.git)'

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_2:26 PM Thursday, October 10, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_e\_\_

- ☐

  AI code generation discovered

- ☐

  I watched a video where a full web site was created in 67 minutes using Cursor and several other tools to get AI to do all the work. Fucking amazing.

- ☐

  I went to [namecheap.com](http://namecheap.com) and bought a domain name and hosting for \$7 or so (WTF??!)

- ☐

  Somewhere along here I had Proton create a password and I thought I forgot to jot it down

  - ☐

    Looks like it was on the [Senior Software Composer](http://seniorswc.com)s site -- quadrabyte@pm.me/Cresting2-Bubbling5-Untoasted7-Kitty8-Splicing8

    ![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iWlZWaDciIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjTHduekgiIC8+PC9zdmc+)
    https://youtube.com/watch?v=kDcM_xwmP3Q&si=buIgT4JPYewQjo8L

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_10:35 AM Wednesday, October 9, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Tom's changes

  - ☐

    moved Troika under Tools

  - ☐

    removed the check for absent files in update\_[webpage.sh](http://webpage.sh)

  - ☐

    xml files are under interface_specifications -- but not all of this data goes by that name

  - ☐

    i used CamelCase names for the instances (e.g., RangeLimitations) because the schema model spells them that way

  - ☐

    but they should not be plural either

- ☐

  A note to Stefan (possibly never sent)

  - ☐

    \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_12:36 PM Thursday, October 3, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  tagging project

  - ☐

    created a new branch TAP-133799-wrap-up-tagging-fstr-project to hold the changes

  - ☐

    also created a new user story TAP-133799

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_5:03 PM Wednesday, October 2, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  a note for Tom but I haven't sent it yet:

  - ☐

    *some questions for you:*

    - ☐

      *Whence can insert the contents of a file in a particular spot as the generic messages.md.in template file is processed for a particular message. The insertion relies on the ...md filename that is being constructed: if a file by that name is found (and here is the thrust of the question) the file is read and its contents is poured into the building .md file. Works great and I think is flexible enough that it will serve us just fine. Here's the question: the process of 'finding' that special fllename has to know what folder to look in, but that's a little bit complicated now with my set of folders getting merged into your set of files. Here are the folders of interest that might be used to hold these insertion-content files--can we pick one of these as the standard place to put these files?*

    - ☐

      *hugo-architecture-site\docs\messages -- the folder where we put all of the .md files produced from the .xml files in the troika/HEX_FILES/Messages folder. For Interface instances this folder would be hugo-architecture-site\docs\interfaces*

    - ☐

      *The Message hmtl files live in the hugo-architecture-site\software_architecture\messages folder -- but your build script wipes that away and rebuilds all of the software_architecture stuff each time so that isn't a good place to put these insertion content files.*

    - ☐

      *Troika has a folder to receive all the .md files in one place: hugo-architecture-site\troika\MD_FILES. At the moment this is the folder where the insertion files reside. But this folder will soon be deprecated because we will want to write all the .md files that are generated into the various folders under hugo-architecture-site\docs soon so that is not a good place for them to reside.*

    - ☐

      *hugo-architecture-site\toika\MD_IN_FILES is the home of the Whence-read template expansion files. No separate folders there, just a handful of template files with the most important and first one being message.md.in.*

    - ☐

      *Given all of that, any suggestions about where these insertion-content files should be stored?*

**

**

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_2:55 PM Monday, September 30, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

She said "take ten minutes now to write just a couple of short paragraphs about the long- and short-term WHY with respect to being sober now.

\

***Short Term***

The heroin high is like the scene in the Wizard of Oz when Dorothy (did it have to be "Dorothy"???) opens the dreary, monochrome door in Kansas to find the Technicolor Munchkins singing, lolipops growing up by the side of the road, gold bricks leading off into the future. The fireworks, the spectacular, the high...that's not the right thing to focus on, to chase after in Life. She said "...recalibrate the +5 -5 scale to just +3 -3 with the possibility of attaining the top (and bottom) scores rather than holding them back as potential extremes that I might experience.

I told her:

- ☐

  Jake watches me moving around in my office but his head rests on his paws, still, while his eyes and his eyebrows follow me very closely. I stop what I am doing and kneel down beside him to rub his ears and scratch his belly saying "I do love you, Dog."

- ☐

  I took out a Hobie Cat for an hour, by myself but without that sometimes dread of "being alone". It was lovely to just skim across the small whitecaps, going nowhere in particular but enjoying the flight.

\

***Long Term***

She said the Pillow List showed clearly how much I don't want to be a burden to my family. And I was heading down the wrong path to avoid that with the alcohol poison every day. The voice still chimes in "but what if life is going to be short anyway, and now you've tossed aside that Joy Bubble of drinking?" Today, in therapy, I saw a glimmer on the horizon, a shimmering ghostly outline of a billboard that read "there are myriad small joys all around you that, if you can just let yourself have them, see them, are worth so much more than the heroin high". Plus, of course, foregoiing the posion means I better my chances of ending life in a graceful, dignified way rather than crumbling into a disabled heap.

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_5:36 PM Wednesday, September 25, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

![](_attachments/image%20(23).png)

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_9:03 AM Tuesday, September 24, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  MDOT call about the emissions waiver

  - ☐

    she took care of the waiver wight away while on the phone

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_12:38 PM Tuesday, September 3, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  State Farm sent a cancellation notice that should not happen again in October, but I suspect it will

- ☐

  called Volvo

  - ☐

    David Turner

    - ☐

      left a message asking him to call @13:00

  - ☐

    two tires have had to be replaced

  - ☐

    software update (?) has twice caused malfunctions

- ☐

  Volvo called and told me to try this reset:

  - ☐

    Home button held for 30-40 seconds should revert everything back to earlier settings

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_5:18 PM Sunday, September 1, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  notes on travel wifi

  - ☐

    trying to link to my MDT phone

  - ☐

    things that helped

    - ☐

      through the 186.xx.8.x address, reset everything

    - ☐

      on the phone

      - ☐

        turn off wifi

      - ☐

        turn on hotspot -- USB only when it asks

      - ☐

        plug in the USB cable

      - ☐

        router vpn off

  - ☐

    now it seems to work

  - ☐

    test results

    - ☐

      5g through the phone: 23 Mbps/4-15 Mbps

    - ☐

      through the phone: 15/15

    - ☐

      bitter pill  296/42

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_2:57 PM Thursday, August 22, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  cake

  - ☐

    Cakes in Style

    - ☐

      [(301) 838-4247](tel:3018384247)

    - ☐

      [https://cakesinstyle.com/](https://cakesinstyle.com/)

    - ☐

      knitting

    - ☐

      called 8/22 15:45

      - ☐

        \

  - ☐

    Stella's Bakery [3012319026](tel:+13012319026)

    - ☐

      11510 Rockville Pike Ste D, 20852-2749

in Power-Shel (Administrator)l

                         vmconnect localhost my-engineering-vm

                         restart-vm my-engineering-vm

                         vmconnect localhost my-engineering-vm /edit

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_6:39 PM Wednesday, August 21, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  finished my 5 rounds of radiation today. almost no side effects. a bit weaker stream peeing. and i am feeling a bit under the weather right now--skin hurts--but i don't know if it's related to treatment.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_1:13 PM Tuesday, August 13, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Todo

  - ☐

    Parse XML database files into python population

  - ☐

    Including error checking

    - ☐

      legal associations, of course

    - ☐

      duplicate names for instances (class name/instance name provides "namespace" separation)

  - ☐

    create a markdown example like Tom's interface_specification_shmio\_[example.md](http://example.md)  (see downloads for the file)

    - ☐

      getting the enums from the population

    - ☐

      getting the Connections from the population too

    - ☐

      including a connections diagram in drawio

    - ☐

      whence process generates .md file

    - ☐

      markdown -\> web page through mkdocs

  - ☐

    Generate .m files

    - ☐

      Parse each .m and add the data to XML files

    - ☐

      For each .m file, write the appropriate .[md.in](http://md.in) (whence) file

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIiIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjMmlPRzUiIC8+PC9zdmc+)

HTML Content

- vi commands

  - Hit the Esc key to enter "Normal mode". Then you can type `:` to enter "Command-line mode". A colon (`:`) will appear at the bottom of the screen and you can type in one of the following commands. To execute a command, press the Enter key.

  - `:q` to quit (short for `:quit`)

  - `:q!` to quit without saving (short for `:quit!`)

  - `:wq` to write and quit

  - `:wq!` to write and quit, attempting to force the write if the file lacks write permission

  - `:x` to write and quit; like `:wq` but writes only if modified (short for `:exit`)

  - `:qa` to quit all (short for `:quitall`)

  - `:cq` to quit, without saving, with a nonzero exit code to indicate failure (short for `:cquit`)

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_8:41 AM Sunday, August 11, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  N3 Nano Coat application video https://n3nano.com/pages/application-guide

- ☐

  Interesting possibility: ChatGPT to do modeling diagrams

  - ☐

    ask for a Mermaid diagram of Zoo

  - ☐

    copy the result into a drawio clean diagram (see the + and Advanced on the menu bar)

  - ☐

    create the drawio diagram

  - ☐

    replacements (unless ChatGPT can be told to stop doing these things)

    - ☐

      arrows to no arrows: endArrow=open -\> endArrow=none

    - ☐

      orthogonal lines: curved=1 -\> edgeStyle=orthogonalEdgeStyle

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_10:15 AM Friday, August 9, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Ideas for web-based apps

  - ☐

    Broken Link Checker

  - ☐

    What's Available (with IMDB/Rotten Tomatoes ratings)

    - ☐

      include a link to jump to the review page

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_3:19 PM Wednesday, August 7, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  need documentation for registration

- ☐

  how expensive

  - ☐

    \$375 consultation

  - ☐

    \$340 application fee

  - ☐

    \$220 approximately for geneologists

  - ☐

    next step is to establish consultation

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_7:41 AM Tuesday, August 6, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Notes on plugins and tooling we can use:

  - ☐

    VS Code

    - ☐

      Excel : **Excel Viewer**

    - ☐

      Drawio

      - ☐

        Create a doc with drawio.png extension and it behaves exactly like both a drawio drawing (so you can edit it with that tool) AND a .png file so you can see it as an image according to the latest edits

      - ☐

        See the drawio plugin for VSCode: **[Draw.io](http://Draw.io) Integration**

      - ☐

        Notice that this technique keeps the image in the same place as the editiable file making it esier to link an embedded image with its tooling to change it

      - ☐

        Same thing for .svg files that were created from drawio

- ☐

  A PLAN

  - ☐

    **Move to Linux development environment (Thomas)**

  - ☐

    **Make the diagram extractor python from EA run in Linux**

  - ☐

    **Generate TestInputConfiguration.h for Rosty's team (Ameya)**

    - ☐

      Figure out the Bamboo mechanism that extracts from Jama:

      - ☐

        In in reference folder:

        - ☐

          see alarms_code\_[generator.py](http://generator.py)  for how they extract

        - ☐

          Software Safety Fault Table.xlsx

        - ☐

          also the Alarms Excel file that is created upon extraction (name?\_)

        - ☐

          where do these files go?

        - ☐

          can we link our processing to the Bamboo task that extracts?

    - ☐

      Convert xslx data to .xml database format

    - ☐

      Generate TestInputConfiguration.h from data

    - ☐

      Generate something for safety too?

  - ☐

    **Imbedded interface for Alejandro/Abhi**

    - ☐

      Update EA schema for that data

    - ☐

      Convert the spreadsheet version of Abhi's data to xml database file

    - ☐

      Generate

      - ☐

        mkdocs web page for that whole interface

      - ☐

        what else do they need?

  - ☐

    **Proposal for sequence diagrams SOT: VSCode/Drawio/XML**

    - ☐

      **Advantages**

      - ☐

        **No license fee**

      - ☐

        **Easier to use to create nice diagrams**

      - ☐

        Don't need LemonTree

      - ☐

        Class/block diagram/schema and sequence diagrams on the same page

      - ☐

        XML text editing, merging?, diff

      - ☐

        VSCode gives simultaneous xml and drawing views that are connected live

      - ☐

        Don't need Windows at all

      - ☐

        Much better drawing tool in Drawio than EA

      - ☐

        Effective Find and Replace in the diagram view, not just the text view

    - ☐

      **Disadvantages**

      - ☐

        **No database to hold "model" information--but maybe this is really an advantage**

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_2:53 PM Monday, August 5, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Joelle is back and that session was flat in a way i didn't like

  - ☐

    I miss the feeling of being in love with her

  - ☐

    She is just my teacher now--not gentle and nurturing but telling me the next steps to take

  - ☐

    makes me sad

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_11:02 AM Thursday, August 1, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Things to fix

  - ☐

    Ameya need Miro access

  - ☐

    striaghten out the tangle i made

  - ☐

    create a new ticket/branch for our work together

\

\

\

\

"Living Documentatoin"

Fort Point Conference Room

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_4:03 PM Friday, July 26, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  cancelled boston trip FZSNJG

  - ☐

    cancelled the boston flight because the new trip let me leave boston later so that i would be able to meet with the team longer before leaving

  - ☐

    i cancelled the hotel part online

  - ☐

    cancelled the flight part with someone at AmEx Travel (669.272.1536) because I couldn't do it online

  - ☐

    only thing is Delta issued a travel credit (\$428.99) when it cancelled

  - ☐

    need to call AmEx Travel back to book the next one with Delta and use that credit

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_5:42 PM Wednesday, July 24, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Installed EqualizerAPO followed by PCEqualizer and got good control over sound

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_8:17 AM Tuesday, July 23, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Stefan email

  - ☐

    Back when I joined Medtronic you gave me a task to do that was right up my alley: the interface project would involve:

  - ☐

        \* understanding the problem, 

  - ☐

        \* creating a database of some kind to become the SOT for all our interfaces, 

  - ☐

        \* modeling a schema for that database that could accomodate the entire problem space, and

  - ☐

        \* building a tool to generate miscellaneous artifacts from that data

\

- - ☐

    All of those tasks matched well with both my skill set and my interests. And all but the first of those tasks have been completed (multiple times over, in fact). That first task has proved harder to get a handle on but I think if finally has been achieved.

\

- - ☐

    But the problem is more difficult than I first imagined. There was always a task that didn’t make it to my imagination about what the solution would eventually be: I didn’t take into account that none of the early work was worth much without getting people to actually use the solution I would offer. And for that, we need a salesperson.

\

- - ☐

    The phase of this project we are in now, we have both agreed, is that of evangelizing (selling) the solution to the customers, convincing them that this technology is a solution to a very real problem they have NOW. It doesn’t even really matter what solution is offered because the hurdle remains: we need to convince the developers that 1) there is a data management problem that is slowng down THEIR progress as they develop software solutions, and 2) there IS a better way to manage that large amount of data that MUST be managed for a target system this complex.

\

- - ☐

    Strengths and Weaknesses:

    - ☐

      Strengths

      - ☐

        Recognizing the broad-brush problems that are negatively affecting the software development team  as we transition from the prototype mentality to a formal product mentality (we have a long way to go)

      - ☐

        Building tools to address these problems

      - ☐

        Teaching

        - ☐

          How to use the new tools once we have buy-in that such tools will be employed

        - ☐

          New ways to do software development

    - ☐

      Weaknesses

      - ☐

        Evangelism/selling changes to getting the work done is not a thing I am good at. This sort of work is heavily dependent on:

        - ☐

          forming  new relationships with people

        - ☐

          finding a way to show the customer how THIS solution addresses THEIR problem(s)

\

- - ☐

    I have lost confidence that the Interface Project will provide enough value to the Hugo Program to warrant the amount of work done, the work still to do versus the payoff. Much as I hate to admit this, I am afriad it may be time to stop work there and just write off all of the effort that has gone into the project so far. It's hard to dump such a significant effort but we should be careful not to fall for the Sunk Cost Fallacy ([https://en.wikipedia.org/wiki/Sunk_cost](https://en.wikipedia.org/wiki/Sunk_cost)).

- - ☐

    Even our own team (Tom and Lalitha) don't seem to have any confidence that modeling, in general, and the interface project, in particular, don't seem supportive. The usual problem is in the way: no time to do it "right" but still time to do it over.

- - ☐

    Other tasks that could be valuable to the team:

    - ☐

      Polarion migration/integration

    - ☐

      Reorganization of the repository folders

    - ☐

      Requirements rework

    - ☐

      Variant flags handling

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_1:18 PM Tuesday, July 16, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  a note from Lalitha about messages:

- ☐

  We have:

- ☐

  \

- ☐

  Simulink\<--\>Simulink (via Shmio & DDS)

- ☐

  \

- ☐

  Simulink \<--\> C++ (via Shmio & DDS)

- ☐

  \

- ☐

  C++ \<--\> C++ (via Shmio, UDP and DDS) (edited) 

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_8:40 AM Monday, July 15, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Monday meeting with the team

  - ☐

    Tom doesn't want to talk about these "little" details

  - ☐

    He insists "almost everything is in the database" --but 1) that isn't true (unless we really change what the database means) and 2) things are the same if and only if they are exactly the same...almost everything translates to 'some things are not there'

  - ☐

    CLASSY and the move to database/generation comes up

    - ☐

      Stefan says "do we need to do this now?"

    - ☐

      My response "no, we don't *need* to do it ever...that has been the response *every PI* since the project started

  - ☐

    Tom leaves the meeting at an hour in because he has another meeting to attend

    - ☐

      once again we don't take/have time to delve into the details that need to be ironed out

    - ☐

      but also, it won't work to just make some decisions about those details and proceed

    - ☐

      ergo, we stand still on those decisions

- ☐

  Stefan:

  - ☐

    this is why so little progress has been made on the interface project--

- ☐

  I'm ready to throw in the towel today. fuck it. i give up because it just isn't worth the emotional cost to fight the battle(s). Rapidly approaching the point of apathy, just accepting that it will not be put into effect.

  - ☐

    Point: I bet Sebastian didn't ask a bunch of people how they thought his script to produce the .m files should work. He just wrote it and it was accepted as the way it would be done.

- ☐

  Couple of hours later

  - ☐

    Maybe the problem is this: I've lost confidence in this project. I think it hit me like a ton of bricks today (a nagging voice has been suggesting for awhile now) -- this is never going to take hold. No one (except maybe me and Stefan) wants this. No one cares at all. Not even two of our team, Tom and Lalitha, think this is worth doing.

- ☐

  Then, a session with Joelle and I am angry

  - ☐

    She pushed me to tackle this hard thing, playing the evangelist role with the teams, because it was going to be a growing/learning step for me. I see that but I am also having a hard time shaking the conclusion that Rosetta is never going to be used by anyone...same old story I have seen so many times before.

  - ☐

    This session with her is so much harder than any before. Why? I have been willing to tackle other hard things with her in the past but I'm having trouble with this one. Anger comes out (I know that's just cover for fear/insecurity/hurt feelings) and I can't seem to let go of it.

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_8:15 AM Saturday, July 13, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  advantages ? to using the export-png approach to moving EA diagrams to the markdown file:

  - ☐

    markdown author doesn't need to master the SQL process to do the extraction (although we could build tools to make it easier)

  - ☐

    tracing back from the document artifact back to the diagram/model when a change needs to be made

    - ☐

      my extraction process can (does?) build a map of where the image came from in the EA model

    - ☐

      everything gets a name, including guid, to tie the artifact to the model, bidirectionally

    - ☐

      EA file and png image would be maintained in Git separately which would/might be good in the case where an artifact uses version X of a diagram but an update to the model/diagram in the EA file caused a new version to be committed

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_7:05 AM Thursday, July 11, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Jabra Enhanced Plus

  - ☐

    Tech support 833.346.1603

  - ☐

    It's a different company than "Jabra Enhanced" for some reason

  - ☐

    Warranty is 1 year

  - ☐

    ![](_attachments/image%20(25).png)

  - ☐

    \

- ☐

  Troika Details

  - ☐

    Proposal for getting diagrams out of EA

    - ☐

      Export automatically (manually) to a git controlled folder nearby the .qea location

      - ☐

        All exports in a single folder in the modeling repo?

      - ☐

        Under git control there?

    - ☐

      References in .whence files assume that folder for source

      - ☐

        \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_9:02 AM Wednesday, July 10, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  note to montgomery county:

  - ☐

    I live on Bitterroot Way in Rockville. When I last sent a message about how poor the road condition is in front of my house (between Jasmine and Sunflower Drive) you sent out a team to fill in the worst of the potholes. Thanks for that but that "fix" actually left the road looking even shabbier than it did before you came out. Having the road out in front of the house look so ragged brings the look of the whole neighborhood down and, when my house goes on the market in a few months, it will reduce the curb appeal of my house considerably. Can anything be done to improve this situation?

- ☐

  virtual meeting with Dr. Vora

  - ☐

    all kinds of problems...

- ☐

  Social Security

  - ☐

    tried to get a benefits estimate

  - ☐

    got this error multiple times:

    - ☐

      #### **We cannot create an account for the Social Security number you entered.**

    - ☐

      For further assistance, please [contact us](https://secure.ssa.gov/cet/contact-us-ui/).

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_4:11 PM Tuesday, July 9, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Medtronic SmartGit license is available in Teams:

- ☐

  ![](_attachments/image%20(27).png)

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_10:36 AM Friday, June 28, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  ### **Potomac Audiology:**

  - ☐

    **Rockville Office**11300 Rockville Pike, Suite 105

  - ☐

    Rockville, Maryland 20852

  - ☐

    NOTE: Front door faces Security Lane.

  - ☐

    **Phone:** (240) 477-1010

  - ☐

    **Fax:** 240-477-1012

  - ☐

    **Email:** [reception@potomacaudiology.com](mailto:reception@potomacaudiology.com)

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_7:07 AM Tuesday, June 25, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Medtronic tasks

  - ☐

    SWI tagging

  - ☐

    Rosetta User Guide

  - ☐

    DRM project

  - ☐

    .m file generation

    - ☐

      all the DDS messages?

    - ☐

      plus some additional internal Simulink world messages?

  - ☐

    C++ DDS messages

  - ☐

    Dmytro's alarm test

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_10:42 AM Thursday, June 13, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Called Dr. Martin's office to schedule the radiation series. Can't do that until the CT scan is done and reviewed (July 24). She said it will start 2-3 weeks after that.

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_3:54 PM Wednesday, June 12, 2024\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  expense report for the boston trip

  - ☐

    spent 0.19 over the meal allowance so i have to pay that to AmEx myself

  - ☐

    i'll wait for awhile until AmEx asks

\

\_\_\_\_\_\_\_\_\_  Mon 10-Jun-24 09:03 AM \_\_\_\_\_\_\_\_\_

- ☐

  Shay

  - ☐

    she has the new software and likes it

  - ☐

    she would like to see us

  - ☐

    to move to the new software she just needs to talk to us

    - ☐

      mortgage

    - ☐

      ss statement

    - ☐

      (she will send a checklist)

  - ☐

    anniversary mine comes up now

    - ☐

      traditional ira

  - ☐

    last year +11%

  - ☐

    ytd now +7.5%

  - ☐

    changes suggested (according to what the market is doing)

    - ☐

      themes

      - ☐

        up international holdings

      - ☐

        moving bonds to longer hold times a bit because she thinks fed rate will come down soon

      - ☐

        equity side

        - ☐

          shaving a little off to move it to international

        - ☐

          emerging markets, small right now, so she will increase that a little

\

\

\

\

\

\

\

XLSFile

- ☐

  \

- ☐

  downloading files from Google Docs

  - ☐

    kinda tricky:

    - ☐

      go to your Google Drive page

    - ☐

      download from here--google will create a zip file and store it on your computer

![](_attachments/image%20(22).png)

\

C:\Users\brennt9\OneDrive - Medtronic PLC\GitHub\ein_ng\tool\scripts\code_generator\event_logging_code_generator.py

\

\

\_\_\_\_\_\_\_\_\_  Mon 3-Jun-24 07:27 AM \_\_\_\_\_\_\_\_\_

- ☐

  New computer arrived from Medtronic, getting things set up

- ☐

  talked to Sol Systems today

  - ☐

    she said there was a duplicate payment account set up

  - ☐

    the one i set up in early march was not connected to my account

  - ☐

    should see payment by the end of the month (June)

  - ☐

    that payment should include all the sold units (between 6-11) at a little over \$400 each i think

\

computer is broken -- lots of things aren't working

\

looks like there was some sort of update (got the 25%...38%... please don't turn off your computer message for a long time earlier today) and now things are broken. i could possibly fix some of the problems but i don't have admin rights because the "M" tool that is usually in the lower left corner of the screen (down by the ivanti tool) is not coming up.

\

\

\_\_\_\_\_\_\_\_\_  Mon 20-May-24 02:55 PM \_\_\_\_\_\_\_\_\_

- ☐

  In our DogOwner schema you will see two

- ☐

  associations: R1 and R2. Note that the multiplicity beside a class where an association terminates (e.g., 1..\* or 0..1)

- ☐

  indicates two important details about how that association can be established between instances of those classes. The

\_\_\_\_\_\_\_\_\_  Fri 17-May-24 06:47 AM \_\_\_\_\_\_\_\_\_

\<Parameter Name="output_source" Dimension="1"\>

\<DataType\> OutputSourceEnum \</DataType\>

\</Parameter\>

\_\_\_\_\_\_\_\_\_  Thu 16-May-24 03:19 PM \_\_\_\_\_\_\_\_\_

- ☐

  next session topic? i used to feel like her favorite client

\

\_\_\_\_\_\_\_\_\_  Tue 14-May-24 09:09 AM \_\_\_\_\_\_\_\_\_

- ☐

  i am a software developer building an XML-based database

- ☐

  updating the SWI tagging spreadsheet

  - ☐

    ■■■■■■■■■■■■■■■■■■■■■■■■                           5.35 minutes

  - ☐

                  files with one or more SWI tags: 3834

  - ☐

                        in this number of folders: 584

  - ☐

                         files with zero SWI tags: 703

  - ☐

                                 nonproduct files: 538

  - ☐

                            committers identified: 51

  - ☐

                                      cmake files: 533

- ☐

  sent a contesting message to DC: *My car is registered in Maryland (as the ticket itself notes) and Maryland does not require two tags to be displayed.*

- ☐

  US Dermatology billing called and left a message. I went on the web site: \$0 account balance

  - ☐

    called them but on hold for a long time...

    - ☐

      ....

    - ☐

      \

\

\

Parameter

\_\_\_\_\_\_\_\_\_  Mon 13-May-24 11:24 AM \_\_\_\_\_\_\_\_\_

- ☐

  [https://www.omgwiki.org/ddsf/doku.php?id=ddsf:public:guidebook:06_append:glossary:t:topic](https://www.omgwiki.org/ddsf/doku.php?id=ddsf:public:guidebook:06_append:glossary:t:topic)

- ☐

  \

\

\_\_\_\_\_\_\_\_\_  Fri 10-May-24 05:05 PM \_\_\_\_\_\_\_\_\_

- ☐

  [*matthew.pias@gmail.com*](mailto:matthew.pias@gmail.com)

- ☐

  [*https://www.linkedin.com/in/matthew-pias*](https://www.linkedin.com/in/matthew-pias/)

\

\_\_\_\_\_\_\_\_\_  Thu 9-May-24 11:38 AM \_\_\_\_\_\_\_\_\_

- ☐

  EyesOnNorbeck

  - ☐

    reading glasses (lenses only)

    - ☐

      expected on the 24th?

  - ☐

    progressive/light sensitive (lenses only)

    - ☐

      expected on the 24th?

- ☐

  Sol Systems, two emails:

*Aina,*

**

*I need you to have someone contact me (650 815 1056) so that I can talk about this payment problem. I went on the web site and found the page shown below which says two things very clearly:*

*SREC credits have been "generated" whatever that means*

*No payments have ever been made*

*Please have someone call me as soon as possible as my patience with this whole dance is exhausted.*

**

*Thomas Brennan-Marquez *

*Following up:*

**

*I did some investigating on your web site and found a page that claimed I have no payment method specified. So that's the problem apparently. I provided all the bank details and got a confirmation screen back that everything was set up.*

**

*Still a couple of questions:*

- - - ☐

      *Why didn't anyone tell me that was the issue before now, when we have been communicating about this for multiple weeks?*

    - ☐

      *How is it possible that "everything looks fine on our end" was the response when I asked someone from Solar Energy World to look into this?*

    - ☐

      *And most importantly, now that a payment mechanism is in place, how soon can I expect to see payment for the six (6) credits already generated?*

*Thomas*

\

\

 

\_\_\_\_\_\_\_\_\_  Wed 8-May-24 06:03 PM \_\_\_\_\_\_\_\_\_

- ☐

  notes for my next session with Joelle:

  - ☐

    John (clearly feelings there)

  - ☐

    \

\

sent a note to energysage asking for help:

![](_attachments/image%20(26).png)

\_\_\_\_\_\_\_\_\_  Tue 7-May-24 08:53 AM \_\_\_\_\_\_\_\_\_

■■                                                 5.47 minutes

              files with one or more SWI tags: 3774

                    in this number of folders: 585

                     files with zero SWI tags: 765

                             nonproduct files: 537

                        committers identified: 58

                                  cmake files: 534

              done

\

\

- ☐

  \

- ☐

  \_\_\_\_\_\_\_\_\_  Mon 6-May-24 06:11 PM \_\_\_\_\_\_\_\_\_

- ☐

  starting to experiment with marijuana

- ☐

  first packet from Green Goods

  - ☐

    Ethiopian Runtz -- sativa

    - ☐

      starting out with this and going very light

    - ☐

      PAX tool makes it much easier

  - ☐

    Blue Blockers -- hybrid

  - ☐

    Carbon Fiber -- hybrid

\

\_\_\_\_\_\_\_\_\_  Mon 6-May-24 11:46 AM \_\_\_\_\_\_\_\_\_

- ☐

  increased mushroom dose to 300 mg but I think it makes me crash hard

- ☐

  so i will stop taking it

\

\_\_\_\_\_\_\_\_\_  Fri 3-May-24 09:10 AM \_\_\_\_\_\_\_\_\_

- ☐

  Google email address for sending from python  (pw: \_Go......)

  - ☐

    app password: **bhey frux ambl njoa**

- ☐

  ![](_attachments/image%20(24).png)

- ☐

  \

\

\_\_\_\_\_\_\_\_\_  Thu 2-May-24 04:34 PM \_\_\_\_\_\_\_\_\_

- ☐

  stepped up to 300 mg of mushroom today and felt nothing really. in pretty good spirits today which might be related but nothing really unusual

\

\_\_\_\_\_\_\_\_\_  Tue 30-Apr-24 01:38 PM \_\_\_\_\_\_\_\_\_

*Folks,*

*This is the second/third step in the SWI Tagging Project process.*

- ☐

  *[Here](https://medtronic-my.sharepoint.com/:x:/p/brennt9/EXVGpNZBJ2lNiP2Q-miO3zoB2dhWJZEStDxCWXh8JOSjtA?e=KwdQ4N) is a link to an Excel spreadsheet with four columns:*

  - ☐

    *Name of developer who made the latest commit to a file that has no SWI tag at present*

  - ☐

    *Directory where one or more such files can be found*

  - ☐

    *Filenames of those files needing attention*

  - ☐

    *Status of each of those files*

- ☐

  *If you are reading this email your name is on that spreadsheet somewhere—please find your name and the list of files (and one or more directories).*

- ☐

  *This won't take much time to do:*

  - ☐

    *There is a branch in the ein_ng repository:* ***feature/TAP-112047-v4.0-fstr-cleanup-complete-swi-tagging***

  - ☐

    *Please make your changes on that branch to minimize problems when we merge just these (nonfunctional) changes back to "develop"*

  - ☐

    *Go to each of the files in your list and, if that file is actually related to a SWI, add the appropriate SWI tag near the top of the file.*

    - ☐

      * For example, if the SWI identifier for a file was "EIN-SWI-5", you would add the line: *

*/// \ingroup EIN-SWI-5*

*/// \ingroup nonproduct*

**

**

\_\_\_\_\_\_\_\_\_  Wed 24-Apr-24 01:35 PM \_\_\_\_\_\_\_\_\_

- ☐

  Third day of microdosing

  - ☐

    feel better than yesterday but still thinking is kind of dull today at the computer

\

\_\_\_\_\_\_\_\_\_  Tue 23-Apr-24 03:31 PM \_\_\_\_\_\_\_\_\_

- ☐

  Second day of microdose

  - ☐

    feeling pretty blue today but i think the problem was pillow list work last night with lots of beer

- ☐

  Went down to the sailing dock only to find that the season has not started yet

\

\_\_\_\_\_\_\_\_\_  Mon 22-Apr-24 01:07 PM \_\_\_\_\_\_\_\_\_

- ☐

  first microdose 100 mg

- ☐

  discussion points for Stefan meeting

  - ☐

    Nathan

- ☐

  beginning of a meeting request with Stefan

  - ☐

    *I have taken ownership of those three FSTR features that Jan was soliciting help with. They are all three related to:*

  - ☐

    *SWI tagging of source files*

    - ☐

      *Cleaning up what is there, some are presently wrong*

    - ☐

      *Making sure that all source files have proper tags*

  - ☐

    *Code generation*

    - ☐

      *Especially the DDS Comm Library gen*

- ☐

  * *

  *This is all stuff that fits perfectly “in my wheelhouse” but I’m not sure how to deal with a Feature from the Jira perspective.*

  *Seems like the appropriate thing to do is to create a bunch of user stories describing the work that needs to be done*

  *      *

- ☐

  \

\

\_\_\_\_\_\_\_\_\_  Sat 20-Apr-24 08:15 AM \_\_\_\_\_\_\_\_\_

- ☐

  message to Dr. Martin

  - ☐

    *The MRI is done (a couple of days ago), the placement procedure is schedule for 17 July. Two things:*

  - ☐

    *1) can we schedule the treatment series as soon as possible after placement?*

  - ☐

    *2) Post-treatment, should I be careful not to book a vacation trip that will require lots of energy (like cycling or hiking) because I may have some fatigue to deal with as a side effect?*

- ☐

  message to Roku

  - ☐

    *i just got a notice that i "signed up for a subscription with Hulu via Roku Pay" but 1) i don't want to subscribe to Hulu and 2) my Roku subscription page doesn't show Hulu as a subscribed service. don't know what this all means but please don't subscribe me to Hulu*

- ☐

  T-Mobile payments problem

  - ☐

    see my notes on what happened: [T-Mobile Overcharging](evernote:///view/225409/s3/53f9a7d6-86ae-125e-154d-9003d68967d5/e719d2ef-4d96-4a74-a949-e6abfd5d1e13)

\

\_\_\_\_\_\_\_\_\_  Fri 19-Apr-24 04:51 PM \_\_\_\_\_\_\_\_\_

- ☐

  path to Microsoft XSD tool on my computer: "C:\Program Files (x86)\Microsoft SDKs\Windows\v10.0A\bin\NETFX 4.8 Tools\xsd.exe"

- ☐

  \

\_\_\_\_\_\_\_\_\_  Thu 18-Apr-24 08:55 AM \_\_\_\_\_\_\_\_\_

- ☐

  Stefan suggests XML might be better than a tab-delimited file

- ☐

  VS Code has an extension vscode-xml

- ☐

  EA can generate an XSD immediately from a block diagram (but with some issues)

- ☐

  Things to note:

  - ☐

    All block names must have no spaces

\

\_\_\_\_\_\_\_\_\_  Wed 17-Apr-24 09:26 AM \_\_\_\_\_\_\_\_\_

- ☐

  notes from Lalitha's talk:

  - ☐

    RE00321376 in Agile. Let me know if you want me to send you the pdf!

  - ☐

    Whos is in charge is a loaded question haha. Systems Engineering maintains the labeling requirements, Tech Comm is the team that updates the User Guide themselves, Quality and Human Factors set the alarm levels, Jama Alarm pulls are automated!

  - ☐

    that is a systems engineering responsibility 👍🏻

  - ☐

    who to talk to about the Jama extraction--this is the same stuff Dmytro needs

- ☐

  **FY24 Goal 1**

  1.  

      ☐

      Interface Specification Project

      1.  

          ☐

          Generate all source files needed on the C++ side to enable use of the Comm Library

      2.  

          ☐

          Generate all the source files on the Simulink side that should reflect interface specifications in data

  2.  

      ☐

      Design Documentation Automation

      1.  

          ☐

          Continue to urge writers of design documents to use the Troika tools to take advantage of updates that automatically track a single SOT

  3.  

      ☐

      Source of Truth Formalization

      1.  

          ☐

          Work with the development teams to move more specification information into a single SOT using the Rosetta tab-file format

      2.  

          ☐

          Give presentations to show actual examples illustrating how beneficial SOT =\> generated artifacts can be

- ☐

  **FY24 Goal 2**

  1.  

      ☐

      Continue to work through the assigned training modules in Cornerstone

  2.  

      ☐

      Watch for opportunities to mentor younger software engineers in good practices and why they matter

  3.  

      ☐

      Continue to encourage the use of modeling strategies in the pursuit of excellent software

- ☐

  **FY24 Goal 3 (bringing in timelines)**

  - ☐

    I don't know how to contribute to this goal

- ☐

  **FY24 Goal 4**

  1.  

      ☐

      Be supportive of software engineers, especially women and people of color, whenever an opportunity arises to assist them in advancing their careers

  2.  

      ☐

      Volunteer to serve on recruitment panels with particular emphasis on recruiting those same people

\

\

\

\_\_\_\_\_\_\_\_\_  Tue 16-Apr-24 07:43 AM \_\_\_\_\_\_\_\_\_

- ☐

  questions

  - ☐

    how to export the latest from Jama?

  - ☐

    EAR_CON_4

  - ☐

    IDU LED duplicated with each entry?

  - ☐

    **LED_WHITE_RGB**, // IDU LED - **No Command** implied?

  - ☐

    missing from my file: -26, -172

  - ☐

    // EIN-UII-158

  - ☐

                ean::AlarmOrNotification(236), shows in my file  (68)

- ☐

  sent a note to Serenity Ridge:

- ☐

  *I want to work out all the details of death before I die (which I don't anticipate anytime soon). I am interested in Serenity Ridge because I want my body to be handled in the least destructive way possible, taking the health of the planet into account. I am on your mailing list to get notices of events and tours and such that are being held at Serenity Ridge. But it occurs to me that I don't much care about how nice the place is (although I'm sure it is quite nice) because I won't be around to notice. Is it possible to simply set everything up so that neither I, my wife, or my children have to worry about the details when I die?*

\

\

\

\

\_\_\_\_\_\_\_\_\_  Mon 15-Apr-24 09:07 AM \_\_\_\_\_\_\_\_\_

- ☐

  Called Martin's office about the MRI

  - ☐

    she will poke them again to call me to schedule

  - ☐

    if I don't hear from them by 4:00 today I will call her back to let her know

  - ☐

    Dr. Martin wanted to see the MRI before we scedule radiation

\

\_\_\_\_\_\_\_\_\_  Sun 14-Apr-24 01:17 PM \_\_\_\_\_\_\_\_\_

- ☐

  left Dr. Reich a message to cancel our 4/18 appointment (because T has an interview)

- ☐

  said we could do a morning appointment on 4/25 if possible

- ☐

  otherwise 5/2 anytime would work

\

\_\_\_\_\_\_\_\_\_  Wed 10-Apr-24 10:41 AM \_\_\_\_\_\_\_\_\_

- ☐

  Called Dr. Martin's office about the MRI appointment

  - ☐

    She said she would resend a notice to the MRI place to have them call me

  - ☐

    301.217.0500

\

\_\_\_\_\_\_\_\_\_  Fri 5-Apr-24 04:04 PM \_\_\_\_\_\_\_\_\_

- ☐

  behavior doctor calls

  - ☐

    Dr. Reich, Marsha

  - ☐

    she is rather curt

  - ☐

    questionnaire beforehand

  - ☐

    she doesn't like emails -- return questionnaire by email but otherwise call

  - ☐

    3.5-5 hrs    \$700-900 dollars plus travel \$80

  - ☐

    after appointment she wants a picture

  - ☐

    electronic like venmo okay

  - ☐

    \

\

\_\_\_\_\_\_\_\_\_  Thu 4-Apr-24 06:35 AM \_\_\_\_\_\_\_\_\_

- ☐

  Undo notes:

  - ☐

    stereotype

  - ☐

    \

- ☐

  Behavior Therapist for Jake

  - ☐

    left a message to have her call back

  - ☐

    she only does house calls

- ☐

  Mayra at Chesapeake Urology

  - ☐

    she called back and explained

    - ☐

      Vora only does this placement procedure once per month

    - ☐

      so august date has to be the scheduled 8/21

    - ☐

      could we move everything sooner, doing the procedure on 7/17?

    - ☐

      might conflict with the birth but I could stay home just for that date and T could go up sooner

  - ☐

    left a message

  - ☐

    **MRI**

  - ☐

    **Dr. Vora consult virtual**

  - ☐

    **Dr. Vora placement procedure**

  - ☐

    **Begin 10-day treatment cycle**

- ☐

  Stefan:

  - ☐

    Spoke to Rob yesterday about Nathan -- he is skeptical that the Interface Project will  actually gain enough traction

  - ☐

    Tom is discouraged

  - ☐

    STAMP/STPA workshop

    - ☐

      June 3-6 in Cambridge

    - ☐

      June 7 in Boston?

      - ☐

        Meet with Delin?

  - ☐

    MSBE conference

  - ☐

    PnP effort -- how to help?

- ☐

  Note to Dr. Patel:

  - ☐

    *I'm afraid I have some Aspy characteristics--specifically the sensitivity to sticky things on my skin (this is why I really hate wearing sunscreen). The triamcinolone acetonide ointment you prescribed makes me VERY uncomfortable. I've applied it twice everywhere and both times I felt like I had been tarred and feathered (although I am sure that experience is even much worse). Is it possible to prescribe something else for this rash--very slightly better this morning after I saw you then made that second application of ointment? Terese thought there might be a cream, which I would also dislike but could stand to use, or perhaps something oral. You mentioned yesterday that the other possible treatments are not preferred but I just can't do the ointment twice a day for two weeks.*

\_\_\_\_\_\_\_\_\_  Tue 2-Apr-24 10:44 AM \_\_\_\_\_\_\_\_\_

- ☐

  called in to Flower Valley Vet for two paper scripts

  - ☐

    Simparica TRIO

  - ☐

    Apoquel

- ☐

  save a snippet

- ☐

  \

\<h3\>2.6 Quality of Service \</h3\> \<a id="26-quality-of-service"\>\</a\>

\# Table of Contents

1\. \[Example\](#example)

2\. \[Example2\](#example2)

3\. \[Third Example\](#third-example)

4\. \[Fourth Example\](#fourth-examplehttpwwwfourthexamplecom)

\

\

\## Example

\## Example2

\## Third Example

\## [Fourth Example](http://www.fourthexample.com)

\

\

\

\

\

\_\_\_\_\_\_\_\_\_  Mon 1-Apr-24 11:39 AM \_\_\_\_\_\_\_\_\_

- ☐

  closed the old Running Journal and started this one because Evernote was getting so slow to process keystrokes

- ☐

  Dr. Patel called

  - ☐

    cream will be called in

  - ☐

    we will do bloodwork on wednesday

\

## See also

- [[3D Printing]]
- [[Enterprise Architect]]
- [[Maker & Electronics]]
- [[Running]]
- [[Software Development]]
