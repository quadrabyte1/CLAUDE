---
title: Running Journal (closed 1 Apr 2024)
uid: 20201117T1759
created: '2020-11-17'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes1
tags:
- running-journal
aliases: []
---

\_\_\_\_\_\_\_\_\_  Mon 1-Apr-24 10:45 AM \_\_\_\_\_\_\_\_\_

- ☐

  WSSC Water

  - ☐

    talked to Damon

  - ☐

    told him that a check would arrive on 4/8 for 151.61

  - ☐

    he started a ticket \#847745411670336

  - ☐

    they will be getting back to me in max 48 hours

/

\

\

\_\_\_\_\_\_\_\_\_  Wed 20-Mar-24 04:54 PM \_\_\_\_\_\_\_\_\_

- ☐

  markdown: [Markdown PDF](https://github.com/yzane/vscode-markdown-pdf) is probably one of the coolest markdown extensions of VSCode. The extension let you convert markdown files to HTML, PNG, JPEG and even PDF. To use it, simply press `Cmd+Shift+P`, search for *Markdown PDF*, and select your desired output format.

\

\

\_\_\_\_\_\_\_\_\_  Tue 19-Mar-24 04:47 PM \_\_\_\_\_\_\_\_\_

- ☐

  canine behaviorist 301.384.3900

- ☐

  contractor / handymand recommendation

  - ☐

    Edgar and his company name is ELK General Contractors.  His contact phone \# is 301-760-0265. He is terrific, nice, and very reliable! We feel that his prices are very fair!  And he lives nearby.

\

\_\_\_\_\_\_\_\_\_  Wed 13-Mar-24 07:13 AM \_\_\_\_\_\_\_\_\_

life jacket

![](_attachments/image%20(68).png)

\

\

\_\_\_\_\_\_\_\_\_  Tue 12-Mar-24 12:17 PM \_\_\_\_\_\_\_\_\_

- ☐

  FsePowerCommand is doubled

\

function main(workbook: ExcelScript.Workbook) {

  let selectedSheet = workbook.getActiveWorksheet();

  // Freeze rows on selectedSheet

  selectedSheet.getFreezePanes().freezeRows(1);

}

\

\

\

v1.23 TRB-M Merged in develop branch version (and straightened out some messes on this diagram that resulted)

\

\_\_\_\_\_\_\_\_\_  Mon 11-Mar-24 02:56 PM \_\_\_\_\_\_\_\_\_

\# \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

def write_tab_file(self):

class_column_count = 0

header_column_count = 0

self.written_guid_list = \[\]

self.catalog = Catalog()

if self.enable_output_file_update:

if len(self.logged_errors) \> 0: \# if there were errors on reading/constructing

err(f'errors occurred during reading/construction disallowing tab file update')

else:

\# output_tab_file = Output_file(self.interface_specification_worksheet_filename)

output_tab_file = Output_file('junk.tab')

msg(f'writing updated tab file: {output_tab_file.fully_qualified_filename}')

header_line = ''

for class_name, attribute_list in self.column_attribute_by_class.items():

if class_name != BLANK_CLASS_NAME:

for attribute_name in attribute_list:

column_heading = class_name + '/' + attribute_name

header_line += column_heading + '\x09'

header_column_count += 1

header_line += 'Guid\x09'

output_tab_file.output_line(header_line)

column_counter = 0

for class_name, attribute_list in self.column_attribute_by_class.items():

if class_name != BLANK_CLASS_NAME:

for instance_of_class in Rosetta.rosetta.CLASS_INSTANCES_MAP\[class_name\]:

self.spinner.next()

instance_line = ''

for i in range(0, column_counter): \# for each skipped column

instance_line += '\x09'

class_column_count = len(attribute_list)

for attribute_name in attribute_list:

cell_value = getattr(instance_of_class, attribute_name)

if isinstance(cell_value, str):

instance_line += cell_value + '\x09'

else:

if len(cell_value) \> 0:

if self.column_holds_formalizing_attribute\[class_column_count - 1\]:

id_attribute_value = Rosetta.rosetta.get_id_attribute_value_by_instance_guid(cell_value\[0\])

instance_line += id_attribute_value + '\x09'

else:

instance_line += cell_value\[0\] + '\x09'

else:

instance_line += '\x09'

pass

for i in range(0, header_column_count - column_counter - class_column_count): \# pad out the rest of the line with tabs

instance_line += '\x09'

instance_line += instance_of_class.\_instance_guid + '\x09'

all_references_satisfied = True

for attribute_name in dir(instance_of_class):

if not attribute_name.startswith('\_'):

attribute = getattr(instance_of_class, attribute_name)

if isinstance(attribute, list): \# if this is a formalizing attribute

for associated_instance_guid in attribute:

\# if associated_instance_guid in self.written_guid_list:

\# the needed entry for the referenced instance may not be available yet

self.catalog.add_value(associated_instance_guid, instance_line)

all_references_satisfied = False

\# if associated_instance_guid in self.written_guid_list:

\# temporary_list = list(instance_line) \# we need a list to do character manipulation

\# for column_index in range(column_counter - 1, -1, -1):

\# associated_class_candidate_name = self.column_class_names\[column_index\]

\# if attribute_name.endswith(associated_class_candidate_name):

\# temporary_list.insert(column_index, '.') \# insert association markers in the appropriate column positions

\# instance_line = ''.join(temporary_list) \# and turn the list back into a string

\# output_tab_file.insert_line_after(attribute\[0\] + '\t\n', instance_line + '\t\n')

\# guid_match_found = True

\# break

if all_references_satisfied:

output_tab_file.output_line(instance_line)

self.written_guid_list.append(instance_of_class.\_instance_guid)

column_counter += class_column_count

handled_guid_list = \[\]

for guid_key, insert_lines in self.catalog.catalog_dictionary.items():

if guid_key in self.written_guid_list:

handled_guid_list.append(guid_key)

for insert_line in insert_lines:

temporary_list = list(insert_line) \# we need a list to do character manipulation

for column_index in range(column_counter - 1, -1, -1):

associated_class_candidate_name = self.column_class_names\[column_index\]

if attribute_name.endswith(associated_class_candidate_name):

temporary_list.insert(column_index, '.') \# insert association markers in the appropriate column positions

insert_line = ''.join(temporary_list) \# and turn the list back into a string

output_tab_file.insert_line_after(attribute\[0\] + '\t\n', instance_line + '\t\n')

\# output_tab_file.insert_line_after(attribute\[0\] + '\t\n', instance_line + '\t\n')

\# guid_match_found = True

for handled_guid in handled_guid_list: \# discard all the dictionary entries we have processed

self.catalog.catalog_dictionary.remove(handled_guid)

assert len(self.catalog.catalog_dictionary) == 0, f'catalog dictionary is not empty, but should be here'

pass

\

\

\_\_\_\_\_\_\_\_\_  Fri 8-Mar-24 11:43 AM \_\_\_\_\_\_\_\_\_

- ☐

  enabled two-factor auth on my proton account

  - ☐

    google authenticator

  - ☐

    here is doc with codes

    ![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjMl9iYVgiIC8+PC9zdmc+)
    Untitled Attachment

  - ☐

    question to dr. martin:

*...while we wait for the genetic test to come back that may determine whether i can follow the short, 5 shot, sequence?*

*i won't be undertaking the treatment until mid- to late-June so it might be too soon to do the MRI.*

**

*also, with the external radiation options, is there any issue with holding the new grandchild, due in early July, right after completing the treatment. i think you said no to that question but i wanted to be sure.*

\

\_\_\_\_\_\_\_\_\_  Thu 7-Mar-24 11:37 AM \_\_\_\_\_\_\_\_\_

- ☐

  my dinner idea in Charlottesville:  [https://www.tripadvisor.com/Restaurant_Review-g57592-d416528-Reviews-Continental_Divide-Charlottesville_Virginia.html](https://www.tripadvisor.com/Restaurant_Review-g57592-d416528-Reviews-Continental_Divide-Charlottesville_Virginia.html)

- ☐

  dispute ref: 224053137043

  - ☐

    sent several printed sheets by email (copy saved here)

\

\_\_\_\_\_\_\_\_\_  Wed 6-Mar-24 09:59 AM \_\_\_\_\_\_\_\_\_

- ☐

  RANJEET T. RAVINDRAN

  - ☐

    lots of comm experience

  - ☐

    no medical experience

  - ☐

    UML?

  - ☐

    articulate, english is good

    - ☐

      maybe a bit chatty?

  - ☐

    no big systems exp

  - ☐

    some management exp

  - ☐

    agile exp, he seems o like it

  - ☐

    lucid chart

    - ☐

      seq diagrams

    - ☐

      class diagrams

  - ☐

    he isn't looking for an architecvt position

  - ☐

    \

\

\_\_\_\_\_\_\_\_\_  Mon 4-Mar-24 08:29 AM \_\_\_\_\_\_\_\_\_

- ☐

  looking for a new doctor

  - ☐

    Bradley Watkins   240.314.7080    near Rose & Pike

- ☐

  \

if association_name in self.unique_association_names:

occurence_count = self.unique_association_names\[association_name\]

count = int(occurence_count) + 1

self.unique_association_names\[association_name\] = count

err(f'duplicate association name occurs {count} times: {association_name}')

else:

self.unique_association_names\[association_name\] = 1

- ☐

  hold this

- ☐

  //                      Filename: \`OUTPUT_FILENAME\`

- ☐

  //                File Generated: \`datetime.datetime.now()\`

- ☐

  //

- ☐

  //                Whence Version: \`Whence.whence.whence_version()\`

- ☐

  //              Rosetta5 Version: \`Rosetta.rosetta.version\`

- ☐

  //

- ☐

  //                 Database File: \`database_name\`

- ☐

  //             Template Filename: \`template_filename\`

- ☐

  //              Template Version: \`TEMPLATE_VERSION\`

\_\_\_\_\_\_\_\_\_  Fri 1-Mar-24 03:56 PM \_\_\_\_\_\_\_\_\_

- ☐

  PEPCO

  - ☐

    called about the \$465.49

  - ☐

    Spoke with Ms. DeAngelo @ 15:50 and she agreed we owe zero

  - ☐

    Doesn't know why we are getting notices of upcoming bill for \$465.49

  - ☐

    Paperless billing is OFF

\

\_\_\_\_\_\_\_\_\_  Wed 28-Feb-24 12:04 PM \_\_\_\_\_\_\_\_\_

DRM work

- ☐

  just so i don't forget, the latest slide deck is now called "GBCharter-Thomas-Brennan-Marquez (February)" and is stored on OnDrive

\

\

\_\_\_\_\_\_\_\_\_  Sat 24-Feb-24 12:37 PM \_\_\_\_\_\_\_\_\_

debug   ►►  Eigen

debug   ►►  FlatBuffers

debug   ►►  jsoncpp

debug   ►►  libarchive

debug   ►►  libcurl

debug   ►►  libssh2

debug   ►►  libmodbus

debug   ►►  openSSL

debug   ►►  RipDraw

debug   ►►  Sphlib

debug   ►►  SQLite

debug   ►►  STM32Cube HAL

debug   ►►  KSHive

debug   ►►  tinyfsm

debug   ►►  zlib

debug   ►►  Microsoft Visual C Redistribution (64-bit)

debug   ►►  Microsoft .Net Framework

debug   ►►  Secure Communication

debug   ►►  Kontron Board Monitor

debug   ►►  Central Safety Monitor

debug   ►►  Local Safety Monitor

debug   ►►  Central Alarms Handler

debug   ►►  ACA Alarms Handler

debug   ►►  SC Alarms Handler

debug   ►►  SID Audio Indicator

debug   ►►  ORTI Audio Indicator

debug   ►►  Error Bridge

debug   ►►  System Manager

debug   ►►  Node Process Manager

debug   ►►  Process Manager Bridge

debug   ►►  EtherCAT Node Process Manager

debug   ►►  Node Deployment Manager

debug   ►►  Deployment Manager Bridge

debug   ►►  EtherCAT Node Deployment Manager

debug   ►►  SMC Node Deployment Manager

debug   ►►  Inogeni Deployment Manager

debug   ►►  UPS Deployment Manager

debug   ►►  Network Switch Deployment Manager

debug   ►►  Central Log

debug   ►►  Node Log

debug   ►►  Relay Log

debug   ►►  Kpi Collector

debug   ►►  SMC Data Recorder

debug   ►►  MSC Data Recorder

debug   ►►  SRA Data Recorder

debug   ►►  Log Archival

debug   ►►  Data Access Collector

debug   ►►  ACA Network Configurator

debug   ►►  System Properties Manager

debug   ►►  Certificate Manager

debug   ►►  node

debug   ►►  QNX AXI IIC Driver

debug   ►►  Wait For Displays

debug   ►►  Clock

debug   ►►  Surgeon Console Display

debug   ►►  ORTI Display

debug   ►►  ORTI Safety Local

debug   ►►  Arm Display

debug   ►►  Arm Display Bridge

debug   ►►  GPIO Driver

debug   ►►  Safety Local

debug   ►►  Application

debug   ►►  Ergonomic Adjustment Controls

debug   ►►  E-Box Monitor

debug   ►►  OS Configuration Writer

debug   ►►  Head Tracking

debug   ►►  Video Scaler Monitor

debug   ►►  Safety Local

debug   ►►  Controller

debug   ►►  Observer

debug   ►►  TPSC Power Manager

debug   ►►  UPS Manager

debug   ►►  Safety Local

debug   ►►  Orion Relay Manager

debug   ►►  Safety Local

debug   ►►  Cart Manager

debug   ►►  Publish Cart Id

debug   ►►  Platform Hardware Id

debug   ►►  Safety Local

debug   ►►  EtherCAT Master

debug   ►►  SRA HAL

debug   ►►  SRA Controller

debug   ►►  SRA Observer

debug   ►►  Joint Primary Logger Bridge

debug   ►►  RA Controller

debug   ►►  SA Controller

debug   ►►  RASA Secondary HAL

debug   ►►  Communication

debug   ►►  Terminal Interface

debug   ►►  Electronic Platform Monitor

debug   ►►  Safety Local

debug   ►►  Joint Primary Watchdog

debug   ►►  DC Link Manager

debug   ►►  Scheduler

debug   ►►  Flash Updater

debug   ►►  Communication

debug   ►►  Hardware Configuration Provider

debug   ►►  Safety Local

debug   ►►  Primary-Secondary Bridge

debug   ►►  EtherCAT SSC

debug   ►►  HAL

debug   ►►  Relay Logger

debug   ►►  Safety Local

debug   ►►  Primary-Secondary Bridge

debug   ►►  EtherCat SSC

debug   ►►  HAL

debug   ►►  Relay Logger

debug   ►►  Safety Local

debug   ►►  Primary-Secondary Bridge

debug   ►►  EtherCat SSC

debug   ►►  HAL

debug   ►►  Relay Logger

debug   ►►  Safety Local

debug   ►►  Primary-Secondary Bridge

debug   ►►  EtherCAT SSC

debug   ►►  HAL

debug   ►►  Relay Logger

debug   ►►  Safety Local

debug   ►►  Primary-Secondary Bridge

debug   ►►  EtherCAT SSC

debug   ►►  HAL

debug   ►►  Relay Logger

debug   ►►  IDU Controller

debug   ►►  Relay Logger

debug   ►►  Safety Local

debug   ►►  EtherCAT SSC

debug   ►►  HAL

debug   ►►  Endoscope Controller

debug   ►►  Common

debug   ►►  Board Support

debug   ►►  Communication

debug   ►►  common

debug   ►►  Deployment

debug   ►►  common

debug   ►►  QNX x86 Einstein

debug   ►►  QNX Networked Zynq

debug   ►►  QNX EtherCAT Zynq

debug   ►►  Windows Einstein

debug   ►►  STM32F303

debug   ►►  Yocto Gateway

debug   ►►  dsPIC33EP Core

debug   ►►  Arm Display

debug   ►►  SMC

debug   ►►  Serialization

debug   ►►  Software

debug   ►►  common

debug   ►►  EtherCAT Communication

debug   ►►  Bootloader

debug   ►►  Updater

debug   ►►  RA_J12_Primary

debug   ►►  RA_J5_Primary

debug   ►►  RA_J6_Primary

debug   ►►  SA_J123_Primary

debug   ►►  SA_J4_Primary

debug   ►►  IDU_Primary

debug   ►►  C and C++ runtime library for Arm

debug   ►►  Connext DDS Professional

debug   ►►  DisplayLink USB Graphics Software for Windows

debug   ►►  dsPIC33EP Core

debug   ►►  EtherCAT

debug   ►►  EtherCAT Slave Stack Code ET9300

debug   ►►  EC-Master

debug   ►►  Microsoft Windows 10 IoT Enterprise

debug   ►►  Motive

debug   ►►  Network Time Protocol (NTP)

debug   ►►  openSSH

debug   ►►  QNX Neutrino RTOS

debug   ►►  Qt

debug   ►►  SNMP v1/v2c/v3 SDK

debug   ►►  STM32CubeF3 MCU packages

debug   ►►  CMSIS Cortex-M Core

debug   ►►  Yocto Project Linux

debug   ►►  SMC Node

debug   ►►  SCDC Node

debug   ►►  Serialization Node

debug   ►►  ORTI Node

debug   ►►  Orion Relay Node

debug   ►►  MSC Node

debug   ►►  Safety Node

debug   ►►  TPSC Node

debug   ►►  Gateway

debug   ►►  Cart Node

\

\_\_\_\_\_\_\_\_\_  Fri 23-Feb-24 03:51 PM \_\_\_\_\_\_\_\_\_

*Follow-up note:*

*While Process, Configuration, Reusable, and Package might all be considered specializations of Software Item, we also need ~174 instances of Software Item too, a thing that is none of those four things. We change the name of the supertype Software Item to simply Component and add a new specialization called Software Item*

\

\

\

strange dream about a trip to disneyland. denise kd kathy. terese too. separated on the way in because T and i saw someone hit by a car and T stayed back to help with trauma. ended up wasting all the money to get in and etc?   i was furious when i called to say where are u you to denise and she has split to some sort of practice thing. don't know what happened to T.

\

\

\

\_\_\_\_\_\_\_\_  Wed 14-Feb-24 08:27 AM \_\_\_\_\_\_\_\_\_

Tom's document in EA:

![](_attachments/image%20(44).png)

\

\

\

\_\_\_\_\_\_\_\_\_  Tue 6-Feb-24 08:18 AM \_\_\_\_\_\_\_\_\_

\

Seth called:

- ☐

  tax thing changed

- ☐

  srec sol systems every month

- ☐

  federal tax  gets paid to the loan holder

  - ☐

    get in touch with dividend

    - ☐

      texting the number to me

    - ☐

      309K including the roof

    - ☐

          "that comes to \$27372" that we have to pay to them to keep the payment down to

    - ☐

         \$309/\$443.65 if we keep the credit

    - ☐

         by sept/october  before that monthly changes

  - ☐

    fed form emailed he has seen the roof included

    - ☐

      18580 credit by his calculation

- ☐

  he will send our case over because it is under producing, less than we expect

\

I sent a message to Sol Systems:

*User ID 247477*

*Everything on the dashboard (and elsewhere when I poke around) looks complete with respect to getting payments setup and started. The graph showing production makes it clear that we have connected you to the system on my house. But it also says no payments have been made so far. What steps need to be taken to close that loop?*

**

\

\

![](_attachments/image%20(42).png)

\

\_\_\_\_\_\_\_\_\_  Wed 24-Jan-24 09:52 AM \_\_\_\_\_\_\_\_\_

- ☐

  left a message to have Crown Carpet Care call back

- ☐

  made Jake a grooming appointment

- ☐

  made Jake a follow up visit with Flower Valley Vet

\

\

\_\_\_\_\_\_\_\_\_  Tue 23-Jan-24 08:52 AM \_\_\_\_\_\_\_\_\_

- ☐

  Joelle:

  - ☐

    I am really irritated with T. she is bitchy and pissed off that i forget things. largely her anxiety and impatience that i don't do things exactly as she thinks i should do

  - ☐

    i wish she would go back on her meds because that softens her edges for me. i know she doesn't want to do that (wants to experience life to its fullest and all) but she isn't much fun to be around these days

  - ☐

    almost half the time i interact with her she is bitchy and less than half the time she is nice, with an occassional interval of being sweet to me

  - ☐

    i wonder how much like this i have been for her? wow. if this is similar i am actually surprised she stayed with me

\

\

\

\

- ☐

  design documents, Jan presents:

- ☐

  ![](_attachments/image%20(39).png)

- ☐

  \

\

\

\_\_\_\_\_\_\_\_\_  Mon 22-Jan-24 12:19 PM \_\_\_\_\_\_\_\_\_

- ☐

  met with Jeff to touch base

- ☐

  got into a long explanation of Troika

- ☐

  he wants me to present this to his team to handle Variants so we are going to set up a demo/meeting for when he gets back week after next:

- ☐

  ![](_attachments/image%20(46).png)

- ☐

  \

\

\

\_\_\_\_\_\_\_\_\_  Wed 10-Jan-24 05:56 PM \_\_\_\_\_\_\_\_\_

- ☐

  {"WhiteBalanceCommand"} -\> {"EndoWhiteBalanceCommand"}

\

\_\_\_\_\_\_\_\_\_  Mon 8-Jan-24 10:03 AM \_\_\_\_\_\_\_\_\_

\

- ☐

  Victoria at Kidwell & Kent promises now that a draft will be here today or latest tomorrow (I threatened to cancel everything)

\

\

![](_attachments/image%20(53).png)

- ☐

  Be careful with multiple inheritance (e.g., PInterruptMock) because it can cause really hairy problems if you hope to use this model to do automatic code generation. Although the concept is good (if a little sticky) it usually isn't valuable enough to tackle all the complexity of being sure the model compiler will do the right thing in all situations. Better to just forego it, if you can.

![](_attachments/image%20(48).png)

- ☐

  Just my personal preference (what you did isn't wrong): when drawing an 'IsA' or generalization relationship, it adds to the clarity of what is going on if you organize the subtypes below the supertype (which you did) and make the lines orthogonal like this snapshot above. It's super-easy to do in EA so it doesn't cost much to make it much cleaner.

![](_attachments/image%20(61).png)

- ☐

  What do these dashed lines mean? Comm links? Dependency, and if so, which direction does the dependency run?

\

\

\_\_\_\_\_\_\_\_\_  Wed 3-Jan-24 10:31 AM \_\_\_\_\_\_\_\_\_

- ☐

  Follow up with Kidwell & Kent

  - ☐

    should see a draft to review by the end of the day--i wonder when it would have happened if i hadn't called....

\

\_\_\_\_\_\_\_\_\_  Tue 19-Dec-23 02:05 PM \_\_\_\_\_\_\_\_\_

Time to get serious about this question of an Interface Specification Document/Template. Here's what I've been thinking for awhile now:

- ☐

  Here are the relevant parts of the Blueprint:

- ☐

  ![](_attachments/image%20(59).png)

- ☐

  and a sub panel that describes the specifics of the DDS messges:

- ☐

  ![](_attachments/image%20(56).png)

- ☐

  The upper panel from the actual blueprint document was designed to (at least begin to) cover all cases of INTERFACE between functioning agents, either hardware or software.

- ☐

  The "interface" between Software Items that are implemented as function calls in the same process and executable has not been considered--although those are arguably interfaces too. Do we want to go down to that level? And, if we do, how do we generate artifacts for consumption by the compiler to guarantee agreement between implementation and (SOT) specification?

- ☐

  I believe extending/correcting the blueprint model to include whatever interface subtleties I didn't include is possible. And we can do that tailoring as we go along, as new interfaces are taken up for specification.

- ☐

  Then, just as the DDS details have been captured in a database that conforms to (a small piece of) the blueprint model, we would build an instance population that represents the interface of interest in the database. And, of course, generate some artifacts to insure alignment into the future.

- ☐

  We have not include attributes for the blocks above but each one of them has/should have a Description attribute. If every instance of every block had a good description of what that block represents, along with good descriptions for the block abstractions the instances are based on, plus a clear explanation of what the associations mean, that would make a really good interface document.

- ☐

  So, once all of that is done, we build Whence templates (or perhaps a single one if we only want one document for the entire Interfaces set) that  present the pieces of the model and population that is relevant to an interface. Included in the Whence template can be some tables, drawings, diagrams, and text to convey to the reader the general concepts. And then the nitty-gritty details would be pulled from the instance population.

- ☐

  Now when the question comes up "what does an interface document look like?" we have a solid answer:

  - ☐

    Given the interface you are asking about:

  - ☐

    We must be sure it can be represented as a population of the blueprint model (this job falls to us)

  - ☐

    The details of the interface need to be added to the instance population with enough specificity that the governing artifact files can be correctly generated

  - ☐

    If there is any clarifying text/tables/diagrams to add, those elements must be generated

  - ☐

    All of that stuff would then be poured into a properly formatted Whence document--DONE

\

\_\_\_\_\_\_\_\_\_  Fri 15-Dec-23 12:48 PM \_\_\_\_\_\_\_\_\_

To cleverbridge about smargit:

I just requested that my auto-renewed subscription (charged yesterday) be cancelled and refunded. I just received an email saying it was cancelled but that I cannot get a refund. You can't have it both ways. Either refund the subscrption price for the year or let me use the license for a year. One without the other is not acceptable.

\

\_\_\_\_\_\_\_\_\_  Wed 13-Dec-23 12:00 PM \_\_\_\_\_\_\_\_\_

### \

![](_attachments/image%20(45).png)

\

\_\_\_\_\_\_\_\_\_  Tue 12-Dec-23 10:47 AM \_\_\_\_\_\_\_\_\_

- ☐

  Restarted Evernote today \$97.49 per year because it is just the best tool i've found

- ☐

  Started the dialog with Serenity Ridge Natural Burial today: [https://www.serenityridgemd.com/](https://www.serenityridgemd.com/)

\

\

\

\_\_\_\_\_\_\_\_\_  Wed 6-Dec-23 08:49 AM \_\_\_\_\_\_\_\_\_

- ☐

  Paid the october and november washington gas bills (\$42.2 and 89.07 plus return charges)  confirmation \#1000089595

- ☐

  Switched the autopay over to PNC

- ☐

  ![](_attachments/image%20(47).png)

- ☐

  \

\

\_\_\_\_\_\_\_\_\_  Thu 30-Nov-23 05:23 PM \_\_\_\_\_\_\_\_\_

Things that have to get done by new rosetta:

- ☐

  read the model XML and create a set of python classes with all the attributes

- ☐

  write a [file.py](http://file.py) that declares all those classes

- ☐

  read a csv file of instances and create that population

- ☐

  write an updated csv of populations (same format)

\

\_\_\_\_\_\_\_\_\_  Thu 30-Nov-23 07:50 AM \_\_\_\_\_\_\_\_\_

I have been using the Logitech MX Master mouse since its introduction in September of 2019. It is, by far, the best mouse design I have ever used. When writing software it is very convenient to be able to program the many buttons on that mouse to do the operations (like commenting out a block of code) that I have to perform about a hundred times a day. When my reliable, original MX Master stopped working I knew I had to replace it.

\

I first went to the IT portal, found the place to order a new mouse, but didn't find this particular model listed there. Next I went to Ariba. Again, I went to the place to order a new mouse and much to my surprise I found the MX Master listed. Unfortunately, when I tried to order one, Ariba said it was a restricted item, offering very helpfully "you can request that this item be placed on your company's inventory of available items". That didn't help because I knew it would take some time to process a request like that and I needed a mouse to work.

\

I decided to just go ahead and order the mouse, scheduled to arrive the very next day. It did arrive and I was back at my computer working the next morning. It seemed like a reasonable thing to expense so I submitted an expense report through Concur, listing it as an "Office Supply" item. Unfortunately, that submission was rejected--we have a \$50 limit on things purchased in that category. I would like to request a one-time exception to the \$50 limit rule. And, of course, if I ever need to purchase something like this again, I will be sure to follow the normal purchasing rules.

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

I have been using the Logitech MX Master mouse since its introduction in September of 2019. When my reliable, original MX Master stopped working I knew I had to replace it.

\

I went to the IT portal but didn't find this particular model listed there. Next I went to Ariba and found the MX Master listed. Unfortunately, Ariba said it was a restricted item and would not let me order one.

\

I decided to order the mouse from Amazon and it when it arrived I was back at my computer working the next morning. I submitted an expense report through Concur. Unfortunately, we have a \$50 limit on "Office Supply" items so that expense was rejected. I would like to request a one-time exception to the \$50 limit rule. And, of course, if I ever need to purchase something like this again, I will be sure to follow the normal purchasing rules.

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

\

I have been using my Logitech MX Master mouse for over 4 years--it is an excellent productivity tool. One day it stopped working. The IT portal didn't list it. I found it on Ariba but it was tagged a 'restricted item'. I decided to order the mouse from Amazon to get back to work ASAP. When I tried to expense it, my request was denied because we have e \$50 limit rule for Office Supplies.  I am resubmitting my request but I am requesting a one-time exception to that rule.        

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

- ☐

  Notes on greenbelt after checking with Stefan:

  - ☐

    tools to look up

    - ☐

      concept selection

    - ☐

      pugh matrix -- a contribution to one of the axes?

    - ☐

      ideation

    - ☐

      retrospective from the folks that are trying to use it

      - ☐

        what works?

      - ☐

        what needs improvement?

      - ☐

        what else could we add?

\

\_\_\_\_\_\_\_\_\_  Mon 27-Nov-23 09:02 AM \_\_\_\_\_\_\_\_\_

- ☐

  Stumpy Nubbs recommends these saw blades: [*https://ridgecarbidetool.com/*](https://ridgecarbidetool.com/)

\

\_\_\_\_\_\_\_\_\_  Tue 21-Nov-23 04:14 PM \_\_\_\_\_\_\_\_\_

- ☐

  \|  130.2503924369812    ??? =\> I   accumulated: 130.2503924369812

- ☐

          \|  125.90397953987122    ??? =\> 07b2.6   accumulated: 125.90397953987122                                                                           

- ☐

  \

- ☐

          \|  45.93548321723938    ??? =\> 07d   accumulated: 45.93548321723938

- ☐

          \|  41.97367715835571    ??? =\> 07b   accumulated: 41.97367715835571

- ☐

          \|  9.676510572433472    ??? =\> G   accumulated: 9.676510572433472

\

\_\_\_\_\_\_\_\_\_  Fri 17-Nov-23 10:46 AM \_\_\_\_\_\_\_\_\_

- ☐

  python Whence(r"C:\GIT REPOISITORIES\ein_ng\tool\troika2\whence\whence_templates\Function-Instrument Control.TEMPLATE.docx", r"C:\GIT REPOISITORIES\ein_ng\tool\troika2\whence\generated\Function-Instrument Control.docx"

\

\_\_\_\_\_\_\_\_\_  Thu 16-Nov-23 03:31 PM \_\_\_\_\_\_\_\_\_

- ☐

  \|  133.62734723091125    ??? =\> 07   accumulated: 133.62734723091125      

  - ☐

    \

self.rosetta.new_class_instance(

class_guid_or_name=class_guid,

instance_guid=instance_guid,

attribute_tuple_list=attribute_tuple_list,

)

- - ☐

    \

- ☐

          \|  130.68504118919373    ??? =\> I   accumulated: 130.68504118919373

- ☐

          \|  42.02240180969238    ??? =\> c2   accumulated: 42.02240180969238

- ☐

          \|  14.084262609481812    ??? =\> G   accumulated: 14.084262609481812

\

\_\_\_\_\_\_\_\_\_  Mon 13-Nov-23 08:39 AM \_\_\_\_\_\_\_\_\_

- ☐

  United Urology

  - ☐

    made an appointment for Nov 28

  - ☐

    FAX: 301.598.3230

  - ☐

    asked FHC Urology to send records over

- ☐

  Made an appointment with Dr. Volk for the right knee problem

\

\_\_\_\_\_\_\_\_\_  Wed 8-Nov-23 10:48 AM \_\_\_\_\_\_\_\_\_

- ☐

  Nathan's manager is Rob Drisko

\

\_\_\_\_\_\_\_\_\_  Tue 7-Nov-23 06:07 PM \_\_\_\_\_\_\_\_\_

Shay holds a retirement seminar

- ☐

  not useful

\

- ☐

  ![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)
  Untitled Attachment

- ☐

  \

\

\_\_\_\_\_\_\_\_\_  Mon 6-Nov-23 10:13 AM \_\_\_\_\_\_\_\_\_

- ☐

  Dr. Chowdhury suggests a sex therapist: [https://www.crystalcounselingandcoaching.com/](https://www.crystalcounselingandcoaching.com/)

\

\_\_\_\_\_\_\_\_\_  Fri 3-Nov-23 11:02 AM \_\_\_\_\_\_\_\_\_

- ☐

  size limit for git push:       remote: File too large (max size 1048576 bytes): tool/troika2/whence/generated/interface_explorer/ClassPages/DataTopicParameter.html

- ☐

  \

i have an mx master 3 that i absolutely love. been using it for years now but suddenly i can't program the buttons to do what i want. they do the default things but won't 'take' when i try to change the behavior. what happened and how can i fix it?

\

PetCare

You can mail your prescription to:

PetCareRx - Pharmacy52 Merton AvenueLynbrook, NY 11563

Please be sure to write your order number on your prescription.

\

\

Kidwell calls about the living trust update

- ☐

  Q: can we just amend the existing trust?

- ☐

  two ways to deal with property

  - ☐

    equal

- ☐

  deed into trust may be all we have to do

- ☐

  can put financial vehicles into trust but easier to just make trust the beneficiary of each vehicle

- ☐

  better outside of trust

- ☐

  probably don't have to make any changes except property

\

\

\_\_\_\_\_\_\_\_\_  Thu 2-Nov-23 12:41 PM \_\_\_\_\_\_\_\_\_

drugs to calm Jake

- ☐

  we tried

  - ☐

    trazadone

  - ☐

    gabapentin

- ☐

  recommended

- ☐

  Jump to a specific medication:

  - ☐

    [*Alprazolam (Xanax)*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Alprazolam)

  - ☐

    [*Amitriptyline*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Amitriptyline)

  - ☐

    [*Buspirone*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Buspirone)*                mild generalized anxiety*

  - ☐

    [*Clomipramine (Clomicalm)*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Clomipramine)*                * FDA-approved treatment for [*separation anxiety in dogs*](https://www.petmd.com/dog/conditions/behavioral/c_dg_separation_anxiety)

  - ☐

    [*Dexmedetomidine (Sileo)*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Dexmedetomidine)

  - ☐

    [*Diazepam (Valium)*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Diazepam)

  - ☐

    [*Fluoxetine (Reconcile or Prozac)*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Fluoxetine)*              * Separation anxiety                 

  - ☐

    [*Lorazepam (Ativan)*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Lorazepam)

  - ☐

    [*Paroxetine (Paxil)*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Paroxetine)*            * Generalized anxiety, anxious aggression and anxiety-related behaviors

  - ☐

    [*Sertraline (Zoloft)*](https://www.petmd.com/dog/behavior/10-medications-dog-anxiety#Sertraline)*        * can take four to six weeks to take full effect

\

\_\_\_\_\_\_\_\_\_  Wed 1-Nov-23 12:03 PM \_\_\_\_\_\_\_\_\_

\

Teri:

transfer request was denied becasue of the trust date

2004 pershing

LBE account

Pershing has 2004 date  -- should have changed it but didn't to 2019

But Shay has 2022

![](_attachments/image%20(58).png)

\

SraJointsActual

\

\[17439, 17450, 17461, 17472, 17483, 17494, 17505\]

\

\

\

\_\_\_\_\_\_\_\_\_  Tue 31-Oct-23 02:07 PM \_\_\_\_\_\_\_\_\_

body {

margin: 0;

font-family: Arial, Helvetica, sans-serif;

background-color: snow;

}

.topnav {

overflow: hidden;

background-color: \#333;

position: sticky; top: 0;

}

.topnav a {

float: left;

color: \#f2f2f2;

text-align: center;

padding: 14px 16px;

text-decoration: none;

font-size: 17px;

}

.topnav a:hover {

background-color: \#ddd;

color: black;

}

.topnav a.active {

background-color: \#04AA6D;

color: white;

}

\

\_\_\_\_\_\_\_\_\_  Fri 27-Oct-23 10:33 AM \_\_\_\_\_\_\_\_\_

Jake's 2023 vaccination report

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)

Untitled Attachment

Architecture Types diagram from Tom

![](_attachments/image%20(38).png)

\

\

\_\_\_\_\_\_\_\_\_  Wed 25-Oct-23 04:01 PM \_\_\_\_\_\_\_\_\_

Extracted subtypes of DataTopic:

![](_attachments/image%20(65).png)

\

\_\_\_\_\_\_\_\_\_  Mon 16-Oct-23 01:59 PM \_\_\_\_\_\_\_\_\_

Stefan:

- ☐

  Nathan wants to join -- would be good to have someone else who knows how it works

- ☐

  Need to go to Boston soon to wrap up QML and DDS gen

- ☐

  We need to discuss decide on database format--presently HTML but I'm not sure it will work well enough

- ☐

  I really hate working on the development repo--size issues are a constant drain on productivity

\

\_\_\_\_\_\_\_\_\_  Mon 9-Oct-23 08:50 AM \_\_\_\_\_\_\_\_\_

- ☐

  restart Evernote as my scrapbook place because Notion wasn't cutting it

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Sun 16-Apr-23 02:26 PM

Terese wants me to document all the mood stuff and especially a recent shift from bad to good that happened. Alas, I have to reconstruct it so i'll do that here:

- ☐

  Today, after Hilary and Nate's party here, feeling crappy. 0 to - 1 today. alcohol perhaps?

- ☐

  11 Apr Finished off the DDS generation project but with a big chunk of brute force. still, was a huge relief to get it off my plate. feeling, since then, much better. probably about +0 for a couple of weeks and now between 1-2.

- ☐

  \

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 23-Dec-22 10:36 AM

- ☐

  replacing broken sunglasses

- ☐

  Visionworks Rockville

- ☐

  11802-B Rockville PikeRockville, MD 20852-2742Phone: **(301) 770-7780**, Fax: + **MONTGOMERYOpen Now[Store Info](https://locations.visionworks.com/ll/US/MD/Rockville/11802~B-Rockville-Pike)**

- ☐

  ****

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 19-Dec-22 09:07 AM

- ☐

  starting Abilify as a mood stabilizer

- ☐

  \

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 14-Dec-22 10:28 AM

- ☐

  State Farm cancellation

  - ☐

    10K personal injury not available in VA

  - ☐

    but we can have 5K so we do

  - ☐

    umbrella policy is now \$154.76

  - ☐

    \

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 8-Dec-22 09:31 AM

- ☐

  surgery

  - ☐

    20680 seneca meadows parkway \# 200

  - ☐

    germantown

  - ☐

    Wegman's grocery top level parking lot, surgicenter on the left

  - ☐

    should be done about 2:30

  - ☐

    45 minutes for recovery

  - ☐

    starts at 2:00

  - ☐

    i have to be there at 12:30

  - ☐

    may not be allowed to wait in the waiting room

  - ☐

    IV sedation plus local

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 5-Dec-22 08:44 AM

- ☐

  Called orthopedic surgeon

  - ☐

    address/office

    - ☐

      William Volk

    - ☐

      301.977.6777

    - ☐

      19851 observation drive

  - ☐

    \

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 10-Nov-22 08:34 AM

- ☐

  planning the trip to Germany

  - ☐

    all done last night, but it was cancelled by Concur for some reason

  - ☐

    tried to do it again (with T's help too) but 5 times in a row Concur failed to complete the transaction

  - ☐

    calling 669-272-1536 Global Business Travel (Medtronic US) now

    - ☐

      talked to a nice person: barbara furgera -- can i tell her boss?

      - ☐

        \

      - ☐

        \

    - ☐

      out of dulles for no stops  21D, 22G

  - ☐

    106 united

  - ☐

    courtyard munich

  - ☐

    107 united

  - ☐

    \

\

- - - - ☐

        \

      - ☐

        12:10 departing 3:45 arrival in dulles

    - ☐

      ? how do i set up a vegetarian meal on the flights ?

      - ☐

        14B on outbound and return

      - ☐

        [american.com](http://american.com) will have this booking but Concur won't because she did it differently

      - ☐

        \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 29-Sep-22 08:23 AM

- ☐

  change of medical coverage?

  - ☐

    Name of rep: Virginia

    - ☐

      BCBS select consumer health plan

    - ☐

      BCBS select ppo

    - ☐

      bind

  - ☐

    \

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 26-Sep-22 04:15 PM

- ☐

  zero card is good if true

- ☐

  \$5000/mo. savings?

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 26-Sep-22 08:44 AM

- ☐

  Notes from meeting with Stefan

  - ☐

    add polarian

  - ☐

    show a use case -- Marvel example with back and forth to explain the steps

  - ☐

    detailed design level with a population is the powerful argument

  - ☐

                   simple view: model

  - ☐

                   detailed design view: population

  - ☐

          eg the wiring diagram isn't enough detail

  - ☐

          the population provides the exact detail that is needed

  - ☐

    \

  - ☐

        formal connection to the modeling level

  - ☐

        need a way to track details other than at the model level because the model view is too abstract

  - ☐

    \

  - ☐

    show other possilble use cases

  - ☐

        test case generation

  - ☐

        hardware/software interface

  - ☐

        communication interfaces

  - ☐

        (there are no tools available to do these things)

  - ☐

    \

  - ☐

    \

  - ☐

    \

  - ☐

    \

  - ☐

    \

  - ☐

    what is our meta model, refinement stack?

  - ☐

         Tom is thinking about this now

  - ☐

          S has an idea of what this should look like and we started there years ago

  - ☐

                     that will make more sense to me now

  - ☐

    \

  - ☐

    PI8 have a spike to nail down this model of our modeling world

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 22-Sep-22 01:56 PM

- ☐

  SoundCloud subscription was still running since Jan 2022

  - ☐

    Canceled it today

- ☐

  ymca arlington \$73   202.797.4473

  - ☐

        at least since last april, possibly farther

  - ☐

        timmirian.williams@ymcadc.org

  - ☐

        laura, wellness department

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 19-Sep-22 08:35 AM

- ☐

  Notes for a talk with Stefan about Tom's comments:

  - ☐

    Tom bemoaned the fact that getting anything done in the direction he is thinking is not a technical problem but a political one (true)

  - ☐

    He has arrived at the conclusion (with which I agree and Stefan has heard from me) that the Agile way is great...for some kinds of SW dev

  - ☐

    It is not so great for other kinds (like ours) because we have a mountain of tech debt that needs to be retired

  - ☐

    And retiring it is a set of Big Jobs that don't reduce easily to a bunch of little chunks that can be "delivered as value to the customer" with each sprint

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 16-Sep-22 12:39 PM

- ☐

  the battle/effort you are describing/facing is EXACTLY the battle i have been fighting for years. i am so convinced that such changes are not only worthwhile but necessary to the future engineering work that we know will be happening. so often these suggestions are seen

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 15-Sep-22 06:27 PM

- ☐

  Questions for John

  - ☐

    1\) Whence and Rosetta could be useful

  - ☐

    2\) Don't use abbreviations when you don't have to

  - ☐

    3\) Microphone move

  - ☐

    \

  - ☐

    5\) Are these requirements in Jama? or somewhere else?

  - ☐

    6\) Would you like help with model layout and routing?

  - ☐

    7\) We could help with the modeling

  - ☐

    \

  - ☐

    9\) How will we insure model/implementations are aligned?

  - ☐

    10)     veronica: logging expert? suggest the coded recording technique, would be great for security/privacy and save space/bandwidth

\

- ☐

  Move Volvo titile stuff

- ☐

  ![](_attachments/image%20(51).png)

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 2-Sep-22 04:37 PM

- ☐

  More Volvo title moving process

  - ☐

    Saw Reba today at AAA

  - ☐

    She gave me a list of things I need to get from volvo financial

    - ☐

      copy of lease agreement

    - ☐

      POA

    - ☐

      Title

  - ☐

    Called Volvo Financial 855.537.3334

    - ☐

      Spoke to Briana

    - ☐

      She is sending a copy of title but we may have to send the original to DMV directly, depends on the state

    - ☐

      Two days to process the request

    - ☐

      Then mailed via regular mail

  - ☐

    Filled out the address change form from Volvo Financial and mailed it back today

  - ☐

    State Farm

    - ☐

      Stella handled the interaction

    - ☐

      Nicole's office called

    - ☐

      She took all the information for the transfer to MD over the phone

    - ☐

      We can leave her as the agent

    - ☐

      Cost for MD coverage will be

      - ☐

        \$957/6 mos

      - ☐

        quote attached

      - ☐

        ![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)
        Untitled Attachment

      - ☐

        \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 31-Aug-22 05:04 PM

- ☐

  Volvo title moving to Maryland

  - ☐

    called AAA to find out if an office nearby can do it

    - ☐

      looking....Wheaton MD 2730 university blvd Wheaton   301.946.5200 (6 for tag and title)

    - ☐

      6.8 miles away

    - ☐

      talking to Reba

    - ☐

      what do i need to bring?

      - ☐

        (she goes away to check on something)

      - ☐

        check with State Farm for proof

        - ☐

          Jeslling Montalvan 240-669-8844

          - ☐

            apparently Nancy was taking care of the transfer over

          - ☐

            request from Nicole -- ky0r is Nancy's alias

            - ☐

              needs a copy of the policy

            - ☐

              \

      - ☐

        inspection

  - ☐

    inspection

    - ☐

      \

[TABLE]

3:00 Thursday

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 11-Aug-22 07:32 AM

- ☐

  model problems

  - ☐

    doesn't like the assocation numbers

  - ☐

    10.1 10.2 interface specification

  - ☐

    ![](_attachments/image%20(63).png)

  - ☐

    \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 8-Aug-22 04:20 PM

- ☐

  look for a visualization tool

- ☐

  next steps in rosetta meeting

  - ☐

          here are some use cases

  - ☐

          deployment decisions

  - ☐

          when to hold it? soon maybe

  - ☐

    early september when PTO is   9/12 Stefan is back

- ☐

  Tom is going on vacation for a week at the end of august

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 4-Aug-22 08:56 AM

- ☐

  Notes from PI7 planning and meeting with Stefan the next morning

\

~~add a new ticket to support phil's effort~~

~~spike to focus the SOT stuff~~

~~19425 for tom?~~

~~error reaction table -- talk to rosty about this because he wants to have some tests to verify it~~

~~      how do we get that table out of req land~~

~~      work wth rosty to make integration tests based~~

~~      make this a spike? ~~

~~                  child of 16425 Rosty's~~

~~                   "how to maintain reaction tables under Rosetta control"~~

~~      move the spec to database~~

~~      get the alarms handler stuff tested this way~~

\

**Tom** stories:

- - - - ☐

        *Stories*

        - ☐

          *search not working*

        - ☐

          *fix the endpoints mechanism and add some additional*

        - ☐

          *diagnostic tool*

          - ☐

            **

        - ☐

          *EA/Jama synchronization for Stefan*

        - ☐

          *Database cleanup SQL tasks*

          - ☐

            *including some sanity, consistency checking to run automatically*

          - ☐

            *Tom says:*

            - ☐

              *yes we should do periodic diagnostics*

            - ☐

              *how did*

        - ☐

          *Add WinWord production capability to Whence*

        - ☐

          *Explore the new EA/Jama integration tool*

          - ☐

            *how to use it?*

          - ☐

            *license?*

          - ☐

            *can Rosetta connect to it?*

        - ☐

          *Check with Bebe about the TaskTop experiment*

     DB cleanup

    maybe add some sanity checks

     winword

     Jama/EA SWI alignment

            Jama is the SOT for the items

      update EA to Jama

                  difference in attribute value can update

                    diff in items, declare an error

              run a command to do it, python

             report only the problems

\

             uniqueness is guaranteed by Jama -- let's run consistency checks on EA side

               eg if we find two of something, don't update it

       explore the Jama/EA new connection

       check with Bebe about the TaskTop experiment    

\

**Me**

    provide examples

          interface spec example for the teams

    rosty's configuration stuff

    jan's hw/sw

    send Stefan the EA/Jama thing

and the dates for Palau

    add a story for deployment decisions for Rosetta

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 3-Aug-22 12:59 PM

- ☐

  add a new ticket to support phil's effort

- ☐

  spike to focus the SOT stuff

- ☐

  19425 for tom?

- ☐

  error reaction table -- talk to rosty about this because he wants to have some tests to verify it

- ☐

        how do we get that table out of req land

- ☐

        work wth rosty to make integration tests based

- ☐

        make this a spike? 

- ☐

                    child of 16425 Rosty's

- ☐

                     "how to maintain reaction tables under Rosetta control"

- ☐

        move the spec to database

- ☐

        get the alarms handler stuff tested this way

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 2-Aug-22 09:26 AM

configuration stuff yes

rosty's manual checklist stuff is a good place to go: behavior needs to be modeled

            based on the Jama checklist

hardware/software interface

      Jan

Comm Library with CLASSY

\

\

Stories

1\) look at my two tickets

                  either close them or delete and restart them

\

2\) check with Rosty, CLASSY, Jan for features to attach to with stories

\

3\) Rosty, see 9429 -- can i put this feature under one of your features?

\

\

34759 -- phil's feature about comm library integration

16423 -- rosty's feature about testing integration

         3 jama items inform the manual checklist

rosty will send the spreadsheet

\

16448 -- also associated with phil's thing

47626  is a good one to check on

let's decouple the gen/file mainenance part from the server deployment

put a tickler on my calendar to run the gen process to keep it aligned with classy's work as they roll out the library

goal: at the end of the PI7 we officially designate iPop as the SOT for all those files

\

\

\

Anthony Gelsom

36237 stays open for the server

just set a meeting for thursday at 2 to meet and talk about where we are, what's next

\

thursday hw/sw meeting with Antoine's

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 19-Jul-22 08:01 AM

- ☐

  Just a quick note to sa**y i love our new house** on Bitterroot! Feeling better than I have felt in a long time and for several days in a row now

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 18-Jul-22 06:00 PM

- ☐

  running Instance Explorer 2 (against a specific version of the iPop.db file data)

  - ☐

    in index.js change JAMAExtraction.db to iPop.db

  - ☐

    and then to run the server

    - ☐

      cd server

    - ☐

      npm run runserver

  - ☐

    and for the client

    - ☐

      cd client

    - ☐

      npm run start

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Sun 17-Jul-22 05:32 PM

- ☐

  submitted claim for covid tests:

- ☐

  ![](_attachments/image%20(64).png)

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 15-Jul-22 01:01 PM

https://medtronic-my.sharepoint.com/:u:/p/brennt9/ETjP6L5FnBpAu2TZdoUnbUQBF4XKSCC1ld8j2KwZcAF52Q?email=umberto.de.ros%40medtronic.com&e=hq7uw5

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 22-Jun-22 09:30 AM

- ☐

  this is really not going to be easy. she is a child about her needs coming first, her feelings being expressed, her being 'a mess at the moment' so that 'this is not the time to do the things \[I am\] doing with Joelle'

- ☐

  in other words, it's her turn. 'through our whole relationship I have been taking care of you' and I need you to take care of me now! i don't know what to say about that--but it certainly triggers something (Mom!) that there are these strings attached to the care she offers to give...

- ☐

  \

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 13-Jun-22 12:58 PM

- ☐

  Closing on the Rockville house tomorrow

  - ☐

    Title company is in Old Town:

    - ☐

      3rd floor

    - ☐

      street parking and a garage across the street with validation

    - ☐

      Mathew's Bar and Grill

    - ☐

      907 King St.

    - ☐

      703.567.7933 office number

  - ☐

    Electric: PEPCO - 202-833-7500 - [www.pepco.com](http://www.pepco.com)

    - ☐

      stop service request is in for 16 Jun 2022

    - ☐

      i request start service on 17 Jun 2022

  - ☐

    Gas: Washington Gas: (703) 750-1000- [https://www.wgl.com](https://www.wgl.com)

    - ☐

      didn't like my username/password -- locked my account for 15 minutes

    - ☐

      Calling 844-WASHGAS (927-4427) to speak with a Customer Service representative.

      - ☐

        account# 210004524851

  - ☐

    Water/Sewer: Washington Suburban Sanitary Commission - 301-206-9772 - [www.wssc.dst.md.us](http://www.wssc.dst.md.us)

    - ☐

      [https://www.wsscwater.com/service](https://www.wsscwater.com/service) worked

    - ☐

      request submitted, here is the request number: 275566

  - ☐

    Internet Option: Verizon - 301-954-6260 - [www.verizon.com](http://www.verizon.com)

  - ☐

    Internet Option: Comcast - 1-800-266-2278 - [www.comcast.com](http://www.comcast.com)

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 25-May-22 07:41 AM

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 24-May-22 10:05 AM

- ☐

  Left Daniel a message at BlueRidge

- ☐

  Miracle Method of Fairfax

  - ☐

    refused to do it

- ☐

  Miracle Method of DC

  - ☐

    Wed 3-4 they will come out to give an estimate

  - ☐

    Thur/Fri works

- ☐

  Victor called back about the power washing  703.868.8478

  - ☐

    \$550 to wash the whole side fence and the little bit of back fence

  - ☐

    about 5-6 hours work

- ☐

  Arden Law Firm, LLC    410.216.7000

  - ☐

    will call back

- ☐

  Sent a request for Town and Country Movers to come by for an estimate

  - ☐

    told them we will do the packing

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 23-May-22 10:17 AM

I think we are focusing on the wrong (part of) the problem. Let me state a claim that may or may not be true, but if true, might nudge our investigation into a better way to work in a different direction:

\

Right now, as I understand it, there are multiple teams working on multiple "projects" (read: development in different areas of the code and with different goals)

Each of those efforts is using a Git branch/branches to version control progress on that work

Here I will speculate--until the development work on one of these projects reaches a certain level of maturity, that project's branches will remain completely isolated from the master branch and from all the other work going on in other projects

Once the development work is completed, those changes to the code base are (painfully) merged into the common development branch (and eventually to master when it comes time to release these changes)

\

- ☐

  Dr. Herbert's office says they need to talk to me about a pathology finding and what I need to do to follow up

  - ☐

    called and talked to the receptionist (in training)

  - ☐

    she left a message for someone to call me

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 19-May-22 03:23 PM

- ☐

  Blue Cross Blue Shield

  - ☐

    what is the "Rx Bin" number for CVS? 

  - ☐

    we are prescription coverage is through CVS Caremark  RX3893

    - ☐

      855.298.4259

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 10-Mar-22 06:43 PM

- ☐

  get in touch with Plocharsky, Christopher about system verification getting involved with req restructuring

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 9-Mar-22 08:46 AM

- ☐

  include Arvind and Nicole as optional when we meet with teams

- ☐

  teams to contact about kick-off

  - ☐

    jacobian

  - ☐

    sirius   

    - ☐

      instruments

    - ☐

      bryn finding some gaps in current state so we might be able to help focus them

    - ☐

      meet with him about what kinds of problems he is seeing:

      - ☐

        can we help by changing existing requirements?

      - ☐

        or is it problems in implementation?

  - ☐

    boosters

  - ☐

    atlas

  - ☐

    still in bed (descoping)

  - ☐

    gui (scheduled)

  - ☐

    isim team

\

- ☐

  Name changes in Rosetta.qea

  - ☐

    ASSOCIATION_ENDPOINT

  - ☐

    READ_ONLY_EXPORT

  - ☐

    READ_ONLY_IMPORT

  - ☐

    \

\

\

\

\

\

\

\

\

\

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 27-Jan-22 07:00 PM

- ☐

  Requested that big Dell monitor today. Stefan said he would approve it and the approval just went to him.

- ☐

  missing data topics:

DataTopic not found: EndoCameraHeadInfo

DataTopic not found: EndoCameraHeadState

DataTopic not found: EndoDigitalZoom

DataTopic not found: EndoDisplayMode

DataTopic not found: EndoFlipMode

DataTopic not found: EndoHeadButtonState

DataTopic not found: EndoLinkModuleInfo

DataTopic not found: EndoLinkModuleState

DataTopic not found: EndoSTechnologiesMode

DataTopic not found: EndoToggle2DLens

DataTopic not found: EndoTouchEvent

DataTopic not found: EndoWhiteBalanceActual

DataTopic not found: EndoWhiteBalanceCommand

DataTopic not found: AlarmAndNotificationMessage

DataTopic not found: AlarmAndNotificationMessage1

DataTopic not found: AlarmAndNotificationMessage2

DataTopic not found: AlarmAndNotificationMessage3

DataTopic not found: AlarmAndNotificationMessage4

DataTopic not found: AudioIndicatorMessage

DataTopic not found: LedIndicatorMessage1

DataTopic not found: LedIndicatorMessage2

DataTopic not found: LedIndicatorMessage3

DataTopic not found: LedIndicatorMessage4

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 20-Jan-22 01:51 PM

- ☐

  For the record:

  - ☐

    Saw the urologist at VHC yesterday

  - ☐

    Something odd on my tongue the last couple of evenings. Don't feel it at the moment but in case the question comes up: noticed it yesterday.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 26-Nov-21 04:44 PM

- ☐

  Adderall at 20 Mg seems to be helping

- ☐

  *J Notes*

  - ☐

    *Kids are over; enjoying their company along with T; they pack up to go home and i have a sudden feeling of dread: i have to deal with T (although nothing untoward actually happens)*

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 22-Nov-21 02:54 PM

suddenly a fury: what was that and what the hell?

what happened that i'd be so dark so hidden in this well?

i want to ask, but didn't, so is this hard for you?

but i don't trust you would answer, what you said would not be true.

\

touching is not touching (that third rail there be damned)

if there isn't something more intense, some flame that can be fanned

from roiling, burning embers up to all consuming flame

my goal is not to understand so much as just to blame.

\

i didn't promise fealty and I didn't bring my heart

to the alter of a sacrifice, to the stage of living art.

if i am

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 15-Nov-21 12:52 PM

- ☐

  Tom Baker tells me that, in German, Vorfuehreffekt means things always go wrong when doing a demo.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Sat 13-Nov-21 10:20 AM

- ☐

  T screeched when she saw the kitchen rat today.

- ☐

  sent off a query to 

  - ☐

    [800-990-0335](tel:800-990-0335)

  - ☐

    [service@planetfriendlypestcontrol.com](mailto:service@planetfriendlypestcontrol.com)

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 12-Nov-21 02:24 PM

- ☐

  called about the dishwasher and washing machine

  - ☐

    Appliance Repair Alexandria 703.224.4002

  - ☐

    coming out 15 Nov between 10-2 will call before arriving

- ☐

  started Cymbalta 90 mg today -- hope it helps

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 11-Nov-21 10:06 AM

- ☐

  parking ticket today but i sent in a dispute message--tags and plates are brand new

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 9-Nov-21 12:55 PM

- ☐

  Met with Mary June today about med changes

  - ☐

    we are going to try Adderall

    - ☐

      as needed

    - ☐

      be sure to eat

    - ☐

      don't do too much coffee

  - ☐

    and up the dose of the Cymbalta to 90

- ☐

  Sent this note to Dr. Sridhar:    (she answered back that she would send in the scripts)

*As I mentioned last week when I was in to the office, my wife, Terese, and I are looking for a primary care physician (because moved to Virginia from California last winter). I felt very comfortable with you so we have decided you would be a great choice for us. (Terese already has an appointment set up to meet with you.) My only complication with this process is that the pharmacy doesn't know which doctor is prescribing each medication I am taking.*

**

*Mary June C. So, DNP, PMHNP-BC is managing my depression medications (Wellbutrin and Cymbalta).*

**

*But the others (Simvastatin, Tadalfil, and Levothyroxine) are under another doctor's name. Right now not all of them are up for refills but I am getting low on the Simvastatin. Would it be possible for you to submit to the pharmacy the three scripts for these three meds? Hopefully, that will satisfy them and the auto-refill process will work smoothly again.*

**

*Thanks,*

*Thomas*

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 8-Nov-21 01:30 PM

- ☐

  Welbutrin does not seem to be working to keep me out of the doldrums. I have been feeling pretty low for days now. It has been over a week since Boston so that can't be it, right?

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 5-Nov-21 01:40 PM

- ☐

  not feeling too great today. zero maybe. started off the morning at -1 though.

- ☐

  had a very good session with J yesterday. she said "good work--you brought up several hard things and stayed with the feelings" -- made me happy

- ☐

  i was mad at her for making me feel shame about falling off the wagon. she didn't do that of course but that's what we talked about: shame

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 3-Nov-21 03:57 PM

- ☐

  Saw Dr. Malorie Sridhar today

  - ☐

    she needs records so I'm gathering those:

    - ☐

      \

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)

Untitled Attachment

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)

Untitled Attachment

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)

Untitled Attachment

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)

Untitled Attachment

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)

Untitled Attachment

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 21-Oct-21 07:52 AM

rewrite of the Letter to Tommy:

*i know how scary this must feel. i remember the feeling of being alone. and not just alone with huge, writhing feelings, but alone facing a confusing world with no one around to talk to about it, no one around to give helpful advice on how to get through the storm. and i know the hopeless feeling that grinds away, day after day, leaving less and less confidence that there might be light at the end of the tunnel. but we are still one person, with all the uncertainty you feel and all the desolation that seemingly surrounds you--we are still one soul and i am here to comfort you. i am here to listen. i am here to feel along with you. to cry along with you (if you can let yourself even have those feelings). i can be that parent, that adult you trust to listen and to help. no one understands as well as i do how hard this is for a child to endure. alone in deep, terrible darkness. afraid of all the unknown dangers that lurk just outside your awareness. lost in the deserted landscape of childhood emotions. i get it. i do. but here's the thing: i will stay with you. i will listen as you begin to share the really hard stuff, when you are ready, and i will just sit here with you silently, waiting patiently until that time comes. i am here. i am not leaving. i want to share with you the gift that i have also been wanting and needing so badly for sixty-five years: to be held in safety, to be heard in silence, to overcome the fear that imprisons. we will survive. we will flourish. we will untangle the rat's nest of emotion that looks impossible right now. it only seems impossible right now. together we will find a way through.*

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 15-Oct-21 09:21 AM

- ☐

  yes, the welbutrin seems to be helping

- ☐

  just had a meeting with rosty

  - ☐

    stefan's stuff (may have problems with formal connections)

  - ☐

    connecting things from that world to iPop world

- ☐

  describing what i'm excited about to Susan she suggested Rosetta Stone as an analogy to the plugboard interconnector

  - ☐

    how about **Attesor** because the RS did it --\> but i want to do it \<-- direction

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 14-Oct-21 01:26 PM

- ☐

  Country and Western song started:

I left a nickel on the table

Thanks for nothing after all

For what it's worth it's really over

Please don't wait up for my call.

\

*Refrain:*

*Even said you wouldn't do it*

*But left me drinkin' in a bar*

*With just these corny lyrics*

*And an old Martin guitar*

**

Cause it don't mean I've forgotten

Cause it don't mean I'm okay

It only means I'm leavin'

Just don't see another way

\

I'll pick me up by bootstraps

I'll rise above from ashes

Head to Phoenix for a year

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 13-Oct-21 09:29 AM

- ☐

  Possible the Welbutrin dose change is helping. I've been feeling pretty good for several days running now.

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 6-Oct-21 12:26 PM

- ☐

  Feeling a bit better today. Last couple of days have been pretty bad: -1 and -2.

- ☐

  Welbutrin doesn't seem to be helping--no surprise there.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 5-Oct-21 02:17 PM

\

The Hugo Robot-Assisted Surgery system is controlled by many communicating, independent software entities. With so many communicating entities sending/receiving several hundred distinct kinds of messages and the details of those messages (names, parameters, data types, etc.) distributed throughout the body of implementation code, it is difficult to manage those messages as development of the software continues. We gathered the details of all those communications into a central place from which various representation artifacts can be derived whenever those details change. We built a UML model and assembled an instance population for that model which reflected a few thousand details about all of those messages.

Communication among software processes is at the heart of the Hugo Robot-Assisted Surgery System. To manage the details of all those messages, we decided to centralize all of that information in a database. A document/source code generator produces many different documents for use by all the development teams needing access to that centralized information.

***Solution:***

The UML class model was constructed in Enterprise Architect by Sparx Systems, a commercially available modeling tool. Our model and our set of instances are, of course, specific to our problem space, but the approach could be applied successfully to another problem. The generator tool was created entirely by our team and designed to be ignorant of particular model being used. It could be used to manage a model and instance population targeted at a completely different problem.

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 4-Oct-21 02:53 PM

- ☐

  Joelle gives me homework:

put this in an envelope for T to give me when i am at -2 or -3

\

*this must be very scary. this must feel like it will never get better. this just hurts.*

*i understand how hard it is because i have also felt this way--no way out, no one can help with it, no one is allowed to come into the close personal space you have withdrawn to. and it must seem a mystery: why does this happen? what did you do to bring this terrible feeling on yourself? but the answer is just that this isn't your fault. this feeling of isolation, hopelessness, and fear isn't punishment for a mistake. it comes from the infant buried deep inside that felt abandoned, felt alone, felt hopelessly that mom would never come. i know how powerful those feelings are. but here's the truth: this feeling will pass. no, mom won't come when you need her to comfort you, but you can learn ways to comfort yourself. it will take practice to learn how do it yourself. it will take fal**ling into this dark place many more times, meeting there these feelings of terror th**at can only be held at bay by shutting everything down. but with time, with practice, you'll learn how to accept those feelings, let them roll in and even smother you--but only for a moment. only until you can remind yourself that you have grown so much since that infant was afraid. only until you can use the new strategies you have learned to guide yourself out from under all that weight.*

*you did nothing wrong. you were not expected to handle this better. you cannot know how to flee from this prison of unfeeling safety. the key is hidden but hidden there, in those very feelings you are trying to avoid, trying not to feel. but there is good news: i am older and wiser. i have worked hard to understand and feel these feelings. i have learned how we both can escape the cage by letting down the guard that we put in place, thinking that was a way to be protected. here's the bottom line: i am here. i will stay. i can help you.*

**

**

**

**

we not you

tell Tala

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 30-Sep-21 05:24 PM

- ☐

  Joelle session

  - ☐

    we talked about the trip to see Tala

  - ☐

    and a dog

  - ☐

    and how global warming is bad but the universe will survive

  - ☐

    then another wave of sadness as i signed off

    - ☐

      could it be just leaving? being left? venturing forth from the safe place?

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 27-Sep-21 08:48 AM

- ☐

  Joelle:

  - ☐

    Tala, Kiel, Carly visit went well but I had a tough first day (really feeling chemical)

  - ☐

    Can I use alcohol as a tool? Slippery slope

    - ☐

      socializing

    - ☐

      pouring my heart out on paper

  - ☐

    Meeting with Penny

  - ☐

    after my session with J I feel sadness, a little hopeless I guess, a little discouraged

    - ☐

      definitely soft and vulnerable

    - ☐

      wonder why? what deep wound did we touch?

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 10-Sep-21 03:21 PM

- ☐

  Got my teeth whitened today!

- ☐

  Endocrinologist because Mary June sent me off on the thyroid question and suggested that an endo doc would be good to see

- ☐

  But first, two questions:

  - ☐

    Does the doc agree that thyroid can cause depression?

  - ☐

    Can i see her without a referral?

- ☐

  Found Dr. Kate Kinnaird on BlueCross BlueShield doctor search site

  - ☐

    703.504.3000

  - ☐

    she gave me the Inova endo dept number: 877.511.4625

- ☐

  Checked with Bose about the discount

  - ☐

    \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 1-Sep-21 11:17 AM

- ☐

  feeling a bit better today. getting things done at work. not feeling listless

- ☐

  there was that knob i wanted to mention to J tomorrow: a couple of meetings (especially the one with the SOAP team) was energizing

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 31-Aug-21 11:31 AM

- ☐

  Found a knob worth turning: three cups of coffee and a meeting with a SOUP team--I got talking about modeling, up on my soapbox(es) and I got excited. Felt great right afterward. How do I find that knob when I'm feeling down?

- ☐

  Sara sent over a partial med record from Dr. Bell

  ![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)
  Untitled Attachment

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 30-Aug-21 10:59 AM

- ☐

  Finding a psychiatrist

  - ☐

    Dr. Sara Mazaheri       (571) 474-4809

    - ☐

      mailbox was full so I couldn't leave a message

  - ☐

    Caroline Ahlers, MD, LLC (chem)       https://www.psychologytoday.com/us/psychiatrists/va/alexandria/184169?sid=612bbdada42b2&ref=28

    - ☐

      105 North Virginia Avenue

    - ☐

      Suite 200

    - ☐

      Falls Church,VA22046

    - ☐

      [(571) 989-7813](tel:+1-571-989-7813)

    - ☐

      left a message

  - ☐

    Ehsan Habibpour, MD  https://www.psychologytoday.com/us/psychiatrists/va/alexandria/133236?sid=612bbdada42b2&ref=24

    - ☐

      sent an email query

  - ☐

    Mary June So

    - ☐

      [mjso@mcleancounselingcenter.com](mailto:mjso@mcleancounselingcenter.com)

    - ☐

      ### McLean Counseling Center

      - ☐

        Telephone 703-821-1073

      - ☐

        [www.mcleancounselingcenter.com](http://www.mcleancounselingcenter.com)

      - ☐

        [McLeanCounselingCenter](https://www.facebook.com/McLeanCounselingCenter)

      - ☐

        [@mcleancounselingcentervirginia](https://secure.hushmail.com/secureforms/access/@mcleancounselingcentervirginia)

      - ☐

        [6862 Elm St. Suite 205, McLean, VA, 22101](https://maps.google.com/?q=6862+Elm+St.+Suite+205+McLean+VA+22101)

    - ☐

      filled out the intake form today 1 sep 2021

    - ☐

      we are going to do the 1 hour intake once Dr. Bell sends the longer history

      - ☐

        \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 27-Aug-21 12:41 PM

- ☐

  Got my TSA Known Traveler Number (KTN): TT12G7777

- ☐

  ![](_attachments/image%20(40).png)

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 25-Aug-21 03:00 PM

- ☐

  Saw J again today, Wednesday

- ☐

  Talked about bringing back some alcohol to ease the social issue -- not a good idea we think

- ☐

  But I am going to start with a psychiatrist in case i need a med change

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 24-Aug-21 11:46 AM

- ☐

  A bit better today. Worked in the woodshop for a few hours this morning while the cleaners were working in the house. That worked great. The lathe hinged mounting is half done (just waiting on some bolts of the right size to affix it). The lower level work bench cart shelf for the planer and shop vac is done and works great. Started work on the drill press/mitre saw cart today too.

- ☐

  problem with Drew's source code, battery_status is not an enum:

  - ☐

    data.battery_details.battery_status = loaned_battery_details.get().value\<std::int32_t\>("battery_status");

  - ☐

    data.battery_details.battery_status = **static_cast\<interface::BatteryStatusEnum\>(l**oaned_battery_details.get().value\<std::int32_t\>("battery_status"));

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 23-Aug-21 07:25 PM

- ☐

  Still having a hard time. Feeling withdrawn and depressed. Better after talking to J today but still not great.

- ☐

  Called the police about the motorcycle again today.

- ☐

  Nate and I played tennis today and, although i was feeling shitty, we played pretty well. I also asked him about his shrink because it may be time to check meds.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 17-Aug-21 11:56 AM

- ☐

  Feeling a bit better today. I think talking to J yesterday helped.

- ☐

  She wants me to remind myself every day:

  - ☐

    Speaking to the root feeling of being trapped/stuck...

  - ☐

    it isn't my fault that i have these feelings

  - ☐

    someone else, a parent, should have been taking care of these needs

  - ☐

    i wasn't cared for properly by those parents, left too much on my own and alone

- ☐

  the motorcycle is still out in front of the house. i'll put a tickler on my calendar to call the police again on Monday

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 9-Aug-21 05:34 PM

- ☐

  ChargeASAP 200W charging unit arrived and works. I wanted to run the MacBook from this but needed to get the cable to do that. Alas I couldn't find an "Add to Cart" sort of button to make the purchase. WTF?

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 3-Aug-21 12:50 PM

- ☐

  feeling a bit better over the last couple of days

- ☐

  missing seeing J this week while she is out

  - ☐

    feels like I am on my own dealing with these hard feelings--even though T loves me she has no patience

- ☐

  here's a nice trick to find double DataType entries:  \<R201_DataType value="\[^\>\]+\>\n      \<R201_DataType value="\[^\>\]+\>

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 2-Aug-21 12:04 PM

- ☐

  Calling Vanguard again to get that rollover money over to Sabin

  - ☐

    877-662-7447

  - ☐

    Carly @ 12:55

    - ☐

      turns out the account number does change: [89303115](https://personal.vanguard.com/web/cfv/client-holdings/#886710102104149)

    - ☐

      looks like it completed okay

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 30-Jul-21 08:45 AM

- ☐

  called Volvo Financial to ask for proof of tax payments

  - ☐

    855.537.3334

  - ☐

    first time through the line dropped

  - ☐

    Xavier

    - ☐

      checks on his end what the deal is with VA

    - ☐

      \

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 28-Jul-21 08:17 AM

- ☐

  the Catskills are beautfiul but much too far away...

- ☐

  the trip wasn't much fun, at least for me, but maybe that was just being depressed

- ☐

  i asked J about another weekly session yesterday because i am not doing well

- ☐

  we'll talk about it this afternoon

- ☐

  called AAA about the registration question

  - ☐

    **Address:** 2231 Eisenhower Ave, Alexandria, VA  22314, United States

  - ☐

    **Phone:** [+1 703 549 1080](tel:+17035491080)

  - ☐

    she said no, can't help

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 22-Jul-21 06:00 PM

- ☐

  Off to the Catskills

  - ☐

    Tala is adorable, of course

  - ☐

    But boy there are a lot of people here...

- ☐

  Ordered a tablet/laptop to help with whiteboard discussions

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 20-Jul-21 04:20 PM

- ☐

  feeling low again. talked to J yesterday and said i hoped it was just that i missed a few doses of meds during the previous week. but today i don't think that's it. just feeling kinda lousy. no enthusiasm. starting to really think about whether i need to adjust meds.

- ☐

  *topic for J:*

  - ☐

    *she said "let me push you a little bit" then talked about what i get out of the food thing, the women taking care of me, etc.*

    - ☐

      *along the way she mentions "you used to talk about \[killing yourself\] sometimes...but now you have Tala and other reasons to live*

    - ☐

      *here's the thing: something bristled inside when she implied (?) that i no longer had that out? was that it?*

    - ☐

      *something welled up with jaw clenched and fury in its eyes...*

    - ☐

      *better talk to her about that*

  - ☐

    *another thing: i feel like i should (or perhaps i just want to) dive into something deep--try to fix something or improve something--maybe just so i can feel better*

    - ☐

      *i want to tackle something difficult (why is that?)*

    - ☐

      *but i am also afraid to do that too. not exactly afraid but too weary to tackle something that will, i know, be very taxing*

    - ☐

      *trying to take care of myself, to just say "it's okay to coast a bit here because all of this (moving, turning the corner, getting settled) is hard"*

    - ☐

      *but it just feels like such a waste of valuable J-work time*

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 15-Jul-21 08:52 AM

- ☐

  Got pretty discourage last night about the EA training folks not getting the import of

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 13-Jul-21 08:48 AM

- ☐

  Pros/Cons of instances hosted by EA

  - ☐

    Advantages to EA hosting

    - ☐

      nice to have model and population in the same file for convenience--don't have to go looking for the xml file

    - ☐

      if diagrams are useful (???) we get those for free

  - ☐

    Advantages to XML hosting

    - ☐

      No license necessary to investigate/change the population  XML file -- just use existing tool

    - ☐

      a separate xml file can be versioned separately -- the model won't change nearly as quickly/often as the population will evolve

    - ☐

      much harder to review population changes before committing (although LemonTree might help here)

    - ☐

      EA makes it easy to d&d elements around on the project tree--that might make the document generation process difficult if things move around

    - ☐

      Already have a good tool for manipulating iPop in XML

- ☐

  Publish a list of stuff to disable/enable in EA for everyone to use

  - ☐

    Traceability

  - ☐

    Notes

  - ☐

    toolbox

  - ☐

    properties window

  - ☐

    simplify the drop down menu that appears with the ^ up arrow quick linker

- ☐

  Maybe create a short movie of how to do the really easy but really handy stuff

  - ☐

    Starting EA

    - ☐

      enable/disable stuff

    - ☐

      setting up a default set of windows/tools

    - ☐

      creating a new local project (just for experimenting)

    - ☐

      using a template instead?

  - ☐

    Creating some stuff in the new project

    - ☐

      create a model inthe project tree

    - ☐

      create a first package (nameed?)

    - ☐

      create a second package (named?)

    - ☐

      back to the first package, create a diagram

      - ☐

        set the name of the diagram

  - ☐

    Tricks

    - ☐

      Auto-naming

    - ☐

      ctrl-click will create another block/class on the diagram

    - ☐

      very handy way to get a list of window-views you want to see:

      - ☐

        select a block/class

      - ☐

        use the second dropdown menu (upper right) to select the 'design' dialog

      - ☐

        ![](_attachments/image%20(41).png)

      - ☐

        Tool bars can be enabled if you don't like Ribbons

        - ☐

          ![](_attachments/image%20(60).png)

      - ☐

        \

  - ☐

    Standard settings

    - ☐

      State naming: "S100 "

    - ☐

      Event naming: "ev100 "

  - ☐

    Deleting and finding relationships

    - ☐

      from the project tree (from the model)

    - ☐

      from a diagram (not from the model)

    - ☐

      relationships are hard to see sometimes

    - ☐

      how to see what is attached

      - ☐

        double click on a block/class

      - ☐

        go to Links to see all connections

    - ☐

      go to a diagram and right click on a block

      - ☐

        select "Insert Related Elements" to get a dialog box with lots of info about what is connected and how

      - ☐

        select what you want to "bring here to this diagram"

      - ☐

        those elements will appear on this diagram

    - ☐

      \

\

\

- ☐

  ![](_attachments/image%20(62).png)

- ☐

  \

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIiIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjMmlPRzUiIC8+PC9zdmc+)

HTML Content

- Stefan and I will try to publish a list of stuff to turn on/off in this list very soon for your use.

- we will also create some short videos on 1)... by Brennan-Marquez, Thomas

  - ![👍](_attachments/20_anim_f%20(5).png)
  - ![❤️](_attachments/20_anim_f.png)
  - ![😁](_attachments/20_anim_f%20(1).png)
  - ![😮](_attachments/20_anim_f%20(2).png)
  - ![🙁](_attachments/20_anim_f%20(3).png)
  - ![😡](_attachments/20_anim_f%20(4).png)
  - 

  Brennan-Marquez, Thomas
  9:14 AM

  we will also create some short videos on 1) getting things up and going, 2) some useful basic operations, and 3) some great tricks to know

\

![](_attachments/image%20(50).png)

\

\

\

\

\

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 9-Jul-21 05:01 PM

- ☐

  got the induction cooktop installed today

- ☐

  told state farm about

  - ☐

    the trailer sale yesterday

  - ☐

    new Virginia driver's licenses

  - ☐

    terminate renter's insurance as of Jun 30

- ☐

  still working on the Volvo title thing

  - ☐

    they wanted \$2K for the sales tax that CA is collecting with each monthly payment

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 7-Jul-21 08:29 AM

- ☐

  get circuit breaker -- capital electric didn't get it yet

  - ☐

    [https://www.amazon.com/gp/product/B00002N7M0/ref=ox_sc_saved_image_1?smid=A21K7UJXVGED05&psc=1](https://www.amazon.com/gp/product/B00002N7M0/ref=ox_sc_saved_image_1?smid=A21K7UJXVGED05&psc=1)

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 6-Jul-21 11:03 AM

- ☐

  changed the title mistake on Nessie today

- ☐

  requested refill of shampoo but with no refills left it should go to Dr. Aria's office now. we'll see.

- ☐

  met with Stefan and Serge about EA and LT licenses

- ☐

  called Ansley about selling Nessie

  - ☐

    He said okay, come ahead

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 5-Jul-21 01:50 PM

- ☐

  Picked up Nessie today without incident

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 2-Jul-21 10:23 AM

- ☐

  Virginia Gas called

  - ☐

    Washington Gas energy services.com

  - ☐

    Columbia Gas

  - ☐

    acct# 320007518261

  - ☐

    703.750.1000

  - ☐

    caller was from 276.209.0816

  - ☐

    clearly a scam

- ☐

  Bill Ansley at Airstream dealer will buy Nessie

  - ☐

    call him on Tuesday to confirm drop-off on Wednesday

  - ☐

    \$30K agreed upon price

- ☐

  Terese conflict

  - ☐

    always mad after a trip

  - ☐

    number of complaints/comments/suggestions/jokes -- every fucking day

  - ☐

    fucks up my day to fight too

  - ☐

    i messages like "i'm frustrated with how much you fuck up" don't count

    - ☐

      suggest prohibiting the use of you/your in the message

  - ☐

    you do some things exceptionally well

  - ☐

    i do some things well/okay/poorly

  - ☐

    just get used to it and stop complaining about it

  - ☐

    \

- ☐

  **BlueCross BlueShield**  651.662.8000

  - ☐

    Still have those two claims showing DENIED

    - - - - - ☐

              \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 17-Jun-21 10:25 AM

            - ☐

              **BlueCross BlueShield** didn't fix the Joelle claims, have to call them today

              - ☐

                Talked to Liag again

              - ☐

                Looks like some additional work needs to be done

                - ☐

                  Still having problems with my name

                - ☐

                  We will go ahead and submit

                - ☐

                  include middle on submission

                - ☐

                  the wheels are turning

  - ☐

    Called them

    - ☐

      Talked to Liag again?

      - ☐

        nope, he wasn't clocked in yet

      - ☐

        talked to Cecily

      - ☐

        left a message to have Liag call

    - ☐

      Liag called me back and now I am furious

    - ☐

      the name field on the form will only allow 25 characters

    - ☐

      that explains the missing first/last names

    - ☐

      Liag suggests maybe I could change my name designation to something like Thomas Brennan

    - ☐

      That would have to be with Medtronic HR of course which is ridiculous

    - ☐

      Asked Liag to send me the complain form

    - ☐

      Someone told him today that it could be overridden manually but they are "really backed up" so it can't be done for a week

    - ☐

      When I simmer down I will call HR to ask if they can help with this

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 30-Jun-21 02:33 PM

- ☐

  Airstream of Virginia call

  - ☐

    Saturday is okay

- ☐

  Airstream

  - ☐

    called Puckett's extension but no answer

  - ☐

    went to the plain old customer service queue to wait

  - ☐

    Cory said

    - ☐

      if there is no problem they won't pay for it

    - ☐

      but the dealer isn't supposed to charge the customer for it

    - ☐

      he would grandfather it in

    - ☐

      said he would call Airstream of Virginia to tell them that right now 15:38

    - ☐

      A of V just called (Richard) to say Airstream was going to "good will it in" so I can pick it up on Saturday

  - ☐

    Dealers

    - ☐

      Airstream of Central Pennsylvania (Ansley RV)

      - ☐

        133.95 mi

      - ☐

        1280 Route 764 Duncansville, PA 16635

      - ☐

        814-695-9817

      - ☐

        Bill Ansley \$30K

      - ☐

        He will be in the office July 6-9

    - ☐

      Colonial Airstream

      - ☐

        177.52 mi

      - ☐

        535 Route 33 Millstone Township, NJ 08535 800-265-9019

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 29-Jun-21 01:39 PM

- ☐

  Volvo call

  - ☐

    855.537.3334

  - ☐

    what is the tax per month?

    - ☐

      4.15%

    - ☐

      \$920.75/mo. with is the amount initially on the first invoice

    - ☐

      Hilary is her name

    - ☐

      She says we don't pay tax in VA

    - ☐

      tax id of lease company: 

      - ☐

        federal tax number: 456951107  but she isn't sure this is what I needed for DMV

      - ☐

        sales and use tax number: **12-456951107F-001**

  - ☐

    power of attorney

    - ☐

      she will send it in the mail

  - ☐

    changed to Bellefonte address with her

  - ☐

    she will also send a current invoice to be used as proof of the zero tax payment

- ☐

  DMV

  - ☐

    Applied for a new license..should take about a week

- ☐

  Global Entry

  - ☐

    Started creating an account but then needed my driver's license number which hasn't come yet

    - ☐

      Once it arrives I will finish that registration

- ☐

  TSA Pre

  - ☐

    Looks easy just an online form, payment, and possibly a virtual interview

- ☐

  Volvo trade-in question

  - ☐

    Ozzy says wait until about 30 months in to see if we can switch to a smaller car

  - ☐

    "Volvo will eat about 5-6 months of payments" he said

  - ☐

    I'll put a tickler on my calendar

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 21-Jun-21 08:56 AM

- ☐

  an excellent productive day today

  - ☐

    great session with J

  - ☐

    got a first huge draft of DataTopics and DataTopicParameters cypher out to rosty to try

- ☐

  STMP/STAMP conference starts today

  - ☐

    Nancy Leveson is great

  - ☐

    Links to some good stuff she has posted:

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iWlZWaDciIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjTHduekgiIC8+PC9zdmc+)

https://www.youtube.com/watch?v=NADSBVlT7Rk

- - ☐

        

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 17-Jun-21 10:25 AM

- ☐

  BlueCross BlueShield didn't fix the Joelle claims, have to call them today

  - ☐

    Talked to Liag again

  - ☐

    Looks like some additional work needs to be done

    - ☐

      Still having problems with my name

    - ☐

      We will go ahead and submit

    - ☐

      include middle on submission

    - ☐

      the wheels are turning

- ☐

  Rosty, Stefan, and I decided to support the neoj4 tool by providing Cypher script out of the database--doing that today

- ☐

  Bringing the Interface model up to current level on the Master branch today too

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 16-Jun-21 12:27 PM

- ☐

  Gave my Executable UML tech talk

  - ☐

    Lots of good questions and interest: about 40 people showed up

  - ☐

    About 16 people stayed afterward to ask questions

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 14-Jun-21 11:17 AM

- ☐

  Brilliant Earth called about the wedding ring fix

  - ☐

    \$300 to replace two diamonds and refurbish the band

  - ☐

    will take 2 to 3 weeks

- ☐

  called Airstream of Virginia

  - ☐

    Felicia emailed on Friday to say it was ready, but

  - ☐

    there is a \$97.94 charge because there was no problem with the awning

  - ☐

    I'm about to call to talk to the manager

    - ☐

      manager of service department

      - ☐

        ...call failed on transfer...

      - ☐

        June is the frontline person to answer the phone

      - ☐

        Richard Roberts

        - ☐

          left a detailed message and asked for a callback

  - ☐

    called Jon Puckett at Airstream

    - ☐

      he didn't answer so i left a message asking him to call

    - ☐

      937.596.6111

    - ☐

      [https://www.airstream.com/company/contact/](https://www.airstream.com/company/contact/)

    - ☐

      ext 7358

      - ☐

        [jpuckett@airstream.com](mailto:jpuckett@airstream.com)

- ☐

  called Richard back at Airstream of Virginia

  - ☐

    he contacted Airstream and they say they won't cover it under warranty

- ☐

  sent a long email to Jon Puckett -- now waiting to hear

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 8-Jun-21 03:09 PM

- ☐

  **BlueCross BlueShield** still has those claims denied re: Joelle

- ☐

  Called them to follow up  651.662.8000

  - ☐

    He read through Molly's notes

  - ☐

    Oddly the January claim, 36067447306, shows as DENIED on the web site but he says he can also see an entry that says it was accepted and \$445.50 paid to deductible

  - ☐

    coverage is out of network \$700 deductible

  - ☐

    60% of 445.50 discounted rate

  - ☐

    apparently Molly didn't do anything? she left no notes about what the problem was or what the fix would be

  - ☐

    he went off for quite awhile to find out why they don't have a digital copy of my submission on either of these Feb, Mar

  - ☐

    Liag is his name

  - ☐

    he will talk to claims dept and put them through again

  - ☐

    he will call me next week with an update

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 7-Jun-21 03:54 PM

- ☐

  the beer gear went really fast

- ☐

  still feeling good and hoping that i really did turn a corner -- very good session with J today talking about how my feelings about her have changed and how i understand them now

- ☐

  finally got everything into the Bellefonte house. not all put away yet but here

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 3-Jun-21 04:04 PM

Make your own beer at home!

I have been a fan of making beer for years but just don't have the space for all the equipment. Everything but fresh ingredients and a Rhino bottle of propane are here:

   - large kettle for cooking and a rack/burner to hold it

   - cooling coil to bring down the temperature fast once cooking is complete

   - buckets with siphon valves to hold the fermenting brew

   - bottle cleaning tools and a big bucket of sanitizer

   - some bottles (you may need more for a batch)

   - a bottling tool and a bunch of caps for it

Free to a good home. Just come by to pick up all this stuff!

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 2-Jun-21 10:38 AM

- ☐

  Back from a good weekend in CT

  - ☐

    Tala is amazing. So sweet. So smart. So beautiful.

- ☐

  Doing pretty well emotionally these days. I think a corner has been turned.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 28-May-21 09:40 AM

- ☐

  Called **BlueCross BlueShield** about Joelle claims that were denied

  - ☐

    1/6/2021

    - ☐

      deductible \$445.50 applied

    - ☐

      but this was denied she says. the claim number that was 36067447306

    - ☐

      937 a new claim number version was sent back to "her" and that one was accepted and went to deductible

    - ☐

      but that doesn't appear anywhere on MY view of claims -- looked for that number and didn't find it

\

- - ☐

    2/1/2021

    - ☐

      entry fuckup -- no first name

  - ☐

    3/1/2021

    - ☐

      entry fuckup -- no last name

  - ☐

    She, Molly, will follow up next week, resubmitting these two with the name corrections

  - ☐

    A little suspicious, eh?, that two claims got fucked up for similar but not the same reason????

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 27-May-21 07:22 AM

- ☐

  Interface Project

  - ☐

    Complete collection of specification data

    - ☐

      DDS request/response

      - ☐

        Add responses to the instance population

    - ☐

      UDP

    - ☐

      Shared memory

  - ☐

    Modify interface model

    - ☐

      Move protocol morphology up a level

  - ☐

    Investigate interactions between comm library & interface modeled spec

  - ☐

    Produce generated tests following the existing integration test paradigm

- ☐

  Software Architecture Document

  - ☐

    Start a new SAD model in EA

  - ☐

    Migrate existing Jira-based items to the new model

  - ☐

    Migrate referenced diagrams to the new model

  - ☐

    Link text with diagrams

  - ☐

    Automation to produce a rough draft of the document in Word format

  - ☐

    Polish the process to produce a beautiful document

- ☐

  \

\

\

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 21-May-21 11:12 AM

- ☐

  Checked in with Dr. Patel

  - ☐

    ultrasound

    - ☐

      no testicle mass

    - ☐

      no change in size

    - ☐

      a bit of fluid

  - ☐

    bloodwork

    - - ☐

        beta HCG same

      - ☐

        borderline alpha  6.1

      - ☐

            repeat again, six months out

    - ☐

      PSA result

      - ☐

        5.5 last time in CA

      - ☐

        0-4 mine was 4.0 this time

      - ☐

        30-50% prob of cancer

        - ☐

          biopsy

          - ☐

            come in for swab to verify the right antibiotic

          - ☐

            no blood thinner

          - ☐

            infection possible

          - ☐

            clean bowel movement

          - ☐

            difficult urination temporary

        - ☐

          mri not quite as reliable as biopsy (about 80%)

        - ☐

          monitoring 3-4 months repeat the blood test

          - ☐

            opted for this one

  - ☐

    His office will send orders for ultrasound in 6, bloodwork in 4

    - ☐

      updated both insurance info and Bellefonte address

\

\

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 19-May-21 04:09 PM

- ☐

  Called State Farm about the couple of little bills coming

  - ☐

    We have several things assigned to different billing accounts--whatever that means

  - ☐

    She is moving them all over to a single billing account that will automatically pay the bill monthly

  - ☐

    Nessie is still not moved because of the CA registration issue. Need to remember to take care of that when we go to the DMV

- ☐

  Had another good session with J on Monday. Talked about her email response to my journal entry email. The fact that she omitted the "love" when she echoed the things that I said I feel. It is great that I can talk to her about anything, even something as awkward as that.

- ☐

  Felt good yesterday. +2

- ☐

  Today not quite as good but doing okay. +1 today.

- ☐

  Called Freddy about the irrigation system at Bellefonte, left a message: 571.405.8454

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 14-May-21 11:51 AM

- ☐

  Another day and things are looking pretty good

  - ☐

    Just took the dogs out for a walk and didn't feel the dizziness once

  - ☐

    Flushing sound seems to be gone as well

  - ☐

    +2 on the scale today...hope that lasts

  - ☐

    T is home and it's great to have her home. Felt kinda lost without her. Especially the first couple of really tough days.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 13-May-21 05:38 PM

- ☐

  Running an experiment with this dizziness thing. Feels like it could be chemical so I am suspending two supplement things that were added pretty recently:

  - ☐

    D3

  - ☐

    Niagen

- ☐

  If the dizziness goes away, I will add them back carefully to see

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 13-May-21 03:17 PM

- ☐

  Talked to the debt collector today

  - ☐

    see notes from Tue 27-Apr-21 10:20 AM about this below

  - ☐

    Claudia 888.525.0072 x421

  - ☐

    She said I should call Aetna to tell them they are not primary on this

  - ☐

    Aetna

    - ☐

      800.872.3862

    - ☐

      she sends me to another number: 877.512.0363

    - ☐

      Jules -- i can ask for her by name, they are a J&J support team

      - ☐

        Aetna coverage october 31 ended

  - ☐

    Back to Claudia now

    - ☐

      left her a message with the United Health Care info so they could resubmit

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 13-May-21 01:52 PM

- ☐

  Just finished with J

  - ☐

    Huge waves of feeling came over me during that session. Even tears. And it came back, then again, and again. Wow.

  - ☐

    I'm not sure how to describe what I felt. J asked and I couldn't say except that it was closer to Hope than Sadness or Despair.

  - ☐

    This session was (might have been) a breakthrough of some sort. Never before in therapy have I had that much feeling come to the surface that fast, that strong, with so many eddies and swirls (the anemones in the tide pools below sway wildly with the slosh of sea water in the aftermath of each of those waves crashing).

  - ☐

    And I feel hopeful.

  - ☐

    And I feel safe.

  - ☐

    And I feel loved and cared for.

  - ☐

    And I feel love and gratitude \[more tears well up here\] for J. Thank you for helping me with this.

  - ☐

    It isn't a dark pool of muck at the bottom of the basement stairs. That analogy is wrong. More like a thicket of brambles in which I am entangled (oh, also after the sun has long ago set so it's black as pitch here). Each adjustment, trying to get comfortable, relieves a pain point in one place but only scratches and pokes and makes bleed another place where the thorns are pressed against the flesh. \[Now writing directly to you...\] I could not have done this without your help.

  - ☐

    You have sat with me as I tried to describe the prickly feelings digging into my soft underbelly. At times you have offered hope that we could make progress. That the thicket, while formidable, is not composed of stainless steel barbs that will not yield, no matter how they are denied, manipulated, or thrashed against. It is just a bramble--huge and unforgiving in many respects--but one that can be navigated, disentangled, left behind one day.

  - ☐

    That need to express gratitude swells again (although the strength of that need still baffles me) so I will stop here with another simple thank you.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 13-May-21 11:30 AM

- ☐

  That weird dizziness persists. Quick eye movements make a strange wooshing sound in my ears. Plus a bit of dizziness comes along too. Seems to be up and down throughout the day over the last several days (while Terese happens to be in CT with Tala). I hope this will resolve on its own but if it lasts a few more days I will go to the doctor.

- ☐

  Emotionally doing pretty well today. Joelle this afternoon--looking forward to that.

- ☐

  BTW, last week T and I decided to quick drinking as of July 1, 2021. She plans to go a year. I plan to go a lifetime. It feels doable and the right thing to do.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 11-May-21 08:28 PM

- ☐

  Feeling slightly better today but still a bit lost and depressed. T is CT. Hilary and Nate are in the Catskills. I have two sad dogs here with me--they are missing their parents.

- ☐

  Off to bed early tonight so I can get an early restart tomorrow. Hoping for a better day than today.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 10-May-21 05:27 PM

- ☐

  My heart is broken today. After  session with Joelle, it doesn't seem much better. Maybe a little safer but still the ache is pounding.

- ☐

  Tears come  at the drop of a hat. I remember this fragility but it has been a long time. Maybe I should write to D and tell her that I understand something now that I didn't before: she made the right choice for her but I wasn't ready yet to be without her. It would take decades of work to get to this point, where I could grasp the profound truth that what she needed and what I needed didn't always coincide but my issues weren't hers to carry.

- ☐

  Maybe I should explain to them both. I understand now. Maybe I always understood at some subterranean level that my wounds/demons were mine to manage. Eventually it would become clear that ....and the profound realization slips away like a ghost in the midst.

- ☐

  The dam breaks with a cascade of feelings, tears, aches, and anguish--I am relieved and bereft, simultaneously. Racking sobs and overflowing emotions...I hope this doesn't last too long for me to stay with the rollercoaster ride.

- ☐

  I am torn between the need to stay here, ride the bucking bronco (because I know the ride will pay dividends no matter whether I make it all the way to the end), and the voice that warns with conviction, don't do it, don't stay here where the heat is hottest, where the pain is palpable (even when all the dials are spun down to zero). Don't  do it. Don't do it.

- ☐

  But I ride it out, stay the course, bite the bullet, (there so many metaphors for this)

- ☐

  Joelle, I hope you're right that this descent into maelstrom is worth the payoff on the other side--but did she claim that or did I just assume that was true?

  - ☐

    There is just too much raw feeling here (I realize as tears start streaming again).  Too much. Too much. Now that Pandora's Box is open...at least I am not (too much) afraid that I will never be able to slam that lid again.

  - ☐

    It has been decades since I let this pain pour out upon the page. Remember? Back when Melinda was listening. When letters were written on paper and a pen scratched both the surface and the written page?

  - ☐

    With no plan afoot, this week is perfect for this exploration. I am alone with all this angst, all this turmoil.

  - ☐

    Tonight I stayed the course. I rode the rollercoaster to the end: thank you for the message you sent (without even knowing at the time):  that I would survive the ordeal, that there was compassion at the end. 

  - ☐

    And tonight, as the scrapes and bruises begin to heal, I have no idea how to say thank you. No idea how to express the courage you have engendered.  All I can say is Thank. You. So. Much. For all you do to help me find my way.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 7-May-21 11:46 AM

- ☐

  Apparently, the problem with Nessie is just that a switch in the water heater is dangling some place it shouldn't be...

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 7-May-21 11:42 AM

- ☐

  I saw a tree that had been used as a scratching post by a cougar or a mountain lion once. That tree's bark was shredded the way a carpet covered cat post is shredded after a few years of cats sharpening their claws on it. This morning I was thinking about why I was feeling so upset, so lonely, so lost, and the image of that tree came to me. Like my emotions are all shredded up.

- ☐

  I am angry--probably a way to protect the hurt part--about everything. Even upset with Joelle for some reason. Because she left? Because she might? And I feel anxious about my relationship with her. Like that trust is shaken somehow. Combination of a difficult time for me and her absence for two weeks?

  - ☐

    Note: just read the article on food and depression. Was going to send it to J but then didn't with a sort of spiteful "ah forget it"   ????

- ☐

  I don't know but I'm not feeling very stable at the moment.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 6-May-21 07:51 AM

- ☐

  Yesterday T and I had a big fight..but why?

  - ☐

    I did that dumb thing with the wine glass that had some lettuce crap at the bottom

  - ☐

    don't know what i was thinking (a little spooky actually) but it wasn't a big deal

  - ☐

    she went nonlinear for some reason, wrapping up with "...you didn't do the dishes..."

  - ☐

    to which i exploded because i had spent hours yesterday

    - ☐

      helping her with computer issues as she tried to get HRBlock software to run

    - ☐

      with the refrigerator problem finally died

    - ☐

      bringing her coffee from Junction because there was no milk

  - ☐

    she has the impression that only she does all sorts of shit for the family

  - ☐

    and with that line i realize i am angry about that

  - ☐

    i told her i want her to stop with the "criticism/complaints" every day (she hates both words and claims they are inaccurate???)

- ☐

  Today J is back and I'm will be glad to talk to her

  - ☐

    Missed her while she has been out recovering from surgery

- ☐

  But I am on the verge of tears today after a session with J. What happened? Angry at her for leaving? Scared to be so dependent? Stirred some thing up today for sure. No

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 5-May-21 04:07 PM

- ☐

  Called Airstream of Virginia about Nessie

  - ☐

    no answer at the service desk so i left a message to have them call me

  - ☐

    Hilary had asked about the camping chairs that are in the trailer

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 27-Apr-21 10:20 AM

- ☐

  Started the Agile training this morning---gonna be a long, long week

- ☐

  Called Stanford billing

  - ☐

    800.549.3720 (13:30)

  - ☐

    Bind info

    - ☐

      771900185935

    - ☐

      United Health Care

    - ☐

      group# 78800154

  - ☐

    Are there any other outstanding bills that I don't know about?

    - ☐

      She verified that there are no other charges outstanding

    - ☐

      MyHealth shows 0

  - ☐

    She will send a statement from Stanford about this procedure which we should submit to United Health Care

    - ☐

      When they pay it (to Stanford) Stanford will inform the collection agency

- ☐

  Medtronic HR

  - ☐

    Benefits questions:  833-261-5740  (pressed \#9)

  - ☐

    Medtronic ID: 487079

  - ☐

    Monica answered (13:15)

  - ☐

    when did coverage start?

    - ☐

      forget Aetna coverage

    - ☐

      Bind oct 26 2020 -- dec 10 2020

      - ☐

        United Health Care

      - ☐

        Stanford should submit

      - ☐

        Are there any other outstanding bills that I don't know about?

        - ☐

          MyHealth shows 0

      - ☐

        worse case scenario

        - ☐

          if still on cobra--get more information and maybe reverse coverage

        - ☐

          how would i prove that i was covered without the cobra?

          - ☐

            plan summary only shows

          - ☐

            Certificate of Credible Coverage from Bind would do it

    - ☐

      BCBS dec 11 2020

    - ☐

      \

\

\

\

\

- - ☐

    lots of problems

    - ☐

      Bind confusion

  - ☐

    coverage information needed:

    - ☐

      name

    - ☐

      my id

    - ☐

      group id

    - ☐

      anything else Stanford might need to submit

    - ☐

      \

  - ☐

    \

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 26-Apr-21 06:41 PM

- ☐

  CMRE FSI called again so I called them

  - ☐

    Claudia at x421

- ☐

  ref# 006213766

- ☐

  Aetna call

  - ☐

    888.632.3862

  - ☐

    member id w259479277

  - ☐

    date of service nov 5 \$712

  - ☐

    what other insurance was in effect

  - ☐

    get the call reference#

- ☐

  But first, I will call Medtronic HR tomorrow and find out what coverage was on November 5 so we can figure out which is primary.

- ☐

  \

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 23-Apr-21 03:00 PM

- ☐

  Feeling really good the last couple of days--maybe the Niacin?

- ☐

  Bought new tennis rackets for me and Nate to enjoy and we are 30-40% improved

- ☐

  Feeling good about work too. The instance tool is working GREAT and I am generating a web page from that info now

- ☐

  Found LemonTree and told Stefan about it so we can move our EA work to Git

- ☐

  Got something from State Farm in the mail today

  - ☐

    Volvo insurance card says effective date 6-apr-2021 to 8-apr-2021 which was a few days ago

  - ☐

    I called and talked to Jamin about it. She says we are covered and requested new cards. Didn't know how that happened.

- ☐

  Called Airstream of Virginia about Nessie getting fixed

  - ☐

    End of next week or week after before it gets to the bay so nothing has happened yet. Put a tickler out two weeks to remind myself to call if nothing happens

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 19-Apr-21 03:02 PM

- ☐

  J: that sadness did prevail, like a scent in the air that feels so wistful, soft and feminine...like your presence was still lingering even though you had already gone. immediately i missed you. so much i wanted to hold you close (both in my arms and in my heart) to know that you would not abandon me. i want to write 'i love you' but it seems so strange to say. not like before because there is no lust there just now, only fully --

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 15-Apr-21 09:07 AM

- ☐

  Feeling very good this morning. Niacin? I sure hope so.

- ☐

  The Airstream dealer came back with \$21K for Nessie. Nope. We can do much better.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 14-Apr-21 11:02 AM

- ☐

  Started the Niacin yesterday. 90 day supply came in.

- ☐

  Talked to Airstream of Virginia

  - ☐

    Nessie goes in on Friday for service on the water heater

  - ☐

    Dana, sales, said they are interested in selling

  - ☐

    By consignment: we set a price and they get anything over that price which we get

  - ☐

    She will be back to me this afternoon

- ☐

  Made appointments in preparation for visit to Patel's office

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 9-Apr-21 08:08 AM

- ☐

  bad day yesterday even after a session with J

- ☐

  we are talking about being exhausted--with the move, the job, another move, across country, covid, a new house and a new move. what could be so tiring? i think T is also exhausted. J wants me to encourage her to take some breaks. we are going away for our anniversary for three days which will be great.

- ☐

  still feeling badly that the interface project is going so slowly but I am very happy with the InstancePopulationExplorer5 tool. Almost ready to use again.

- ☐

  Lisa called back (see the note below under Wed 7-apr)

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 8-Apr-21 08:21 AM

- ☐

  the gardeners showed up again today at the house, second week in a row

- ☐

  707.629.6266 West Landscaping

- ☐

  we called and left a message that this needs to stop

- ☐

  told the guys not to continue too but they seem to 1) not understand, or 2) not feel empowered enough to blow off the job

- ☐

  CVS called to say my extension time has been granted.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 7-Apr-21 02:52 PM

- ☐

  J&J COBRA is still fucked up

  - ☐

    Stanford sent us to collections

  - ☐

    Called J&J to talk to them about it

    - ☐

      800-565-0122

    - ☐

      she says there is a bill for over \$9K

    - ☐

      she sees "in the system the effective date was supposed to have been "

    - ☐

      sees "they dropped the coverage effective 12/1/2020 - but why do they keep sending bills? I don't know"

    - ☐

      I explained that the work done Oct and Nov isn't being covered as it should

    - ☐

      1/5/2021 T sent a check for \$1474.25 with a detailed letter about what the problem is:

      ![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iYk9KbjEiIHZpZXdib3g9IjAgMCA0MCA0MCI+PHVzZSB4bGluazpocmVmPSIjMlNXck4iIC8+PC9zdmc+)
      Untitled Attachment

      \

    - ☐

      ticket \# 19620679

    - ☐

      she explains in the notes what the problem is

    - ☐

      also notes that she has never seen a COBRA bill that big (and laughs)

    - ☐

      Lisa

      - ☐

        *she called back on 9-apr-2021 to say that the billing screw-up is now corrected*

- ☐

  State Farm is going to cancel coverage in 30 days if we don't get the registration changed to VA

  - ☐

    Made an appointment for June 21 (about two and half months away) with the DMV

  - ☐

    I will write a note to both agents (see below) about this:

    - ☐

      *I spoke to Beth Whitmore at Amanda Martin's office in California yesterday. She told me that she was concerned about the transfer of the auto coverage on our Volvo. She called the office here in Virginia (Nicole Edwards's office) to check up on that. I got a subsequent call from Nicole's office from a woman I have spoken with before but have forgotten her name. She said the transfer of coverage on both the Volvo and the Airstream trailer had been held up because the registration on both was still in California. She told me to make an appointment with the DMV to get those registrations moved to Virginia, which I did today. The problem is that no appointments are available until June. Mine is 29-jun-2021 at 8:45 AM. That's over two months from now. Obviously, I don't want coverage on either vehicle to be suspended but I don't know what I can do. Please let me know how we are going to resolve this problem. Thanks, Thomas*

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 6-Apr-21 09:47 AM

- ☐

  called CVS/Caremark for followup:  855-298-4259

  - ☐

    I asked about whether I could use another pharmacy

  - ☐

    She says

    - ☐

      Under my plan after two 30-day fills I have to get 90-day

      - ☐

        Safeway can't do it

      - ☐

        CVS is almost the only one (see below) who can fill the 90-day

      - ☐

        But i need the doctor to call in the 90-day script

    - ☐

      Teeter (sp?)  Pharmacy can do it too:

      - ☐

        735 No. Asaph Street, Alexandria  703.419.3855

    - ☐

      We filed a request for an extension so I can move over to the new doctor

    - ☐

      She went through the list of all the meds -- had to do each one i guess

      - ☐

        she includes that i have relocated from CA

      - ☐

        that team will inform me via phone if/when the request is approved

      - ☐

        i should call Safeway again then

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 5-Apr-21 01:54 PM

- ☐

  Safeway just called...

- ☐

  Print

[TABLE]

Print

*\*Some links may not be valid after the chat ends.*

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 2-Apr-21 10:11 AM

- ☐

  Ripped out all the ADT hardware yesterday. That was fun....

- ☐

  Volvo went in for its first service 10K, paid for by Volvo

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 1-Apr-21 04:30 PM

- ☐

  Good session with J today. We talked about the poem below. She said we "now have a picture, without having to relive and delve into all the bad memories that I have locked away for my protection..."

- ☐

  Started looking into Living Document tools

  - ☐

    Pickles

    - ☐

      but it seems only relevant to VS projects so it isn't useful for Einstein

  - ☐

    Concordion

    - ☐

      just started looking...

- ☐

  Started paying for Glary Utilities (\$19.95 / year) because it is a really nice suite of tools

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 31-Mar-21 07:09 AM

- ☐

  Doing pretty well today.

- ☐

  Brought Nessie home yesterday. They were pretty reasonable and only asked me to pay \$20 for propone they put in the tank.

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 30-Mar-21 11:22 AM

Under layers, slithers deep

The kind of danger kills in sleep

I didn't see it gliding by

But I could feel the ripples nigh.

Too close to touch, 'twas out of reach

A lesson in the making teach

My heart, my mind, my other side

Warned me then of what's implied:

Take care. Take care. Here something lurks

Ineffable and silent works,

Half century to calcify

What makes me think that I should try?

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 29-Mar-21 02:51 PM

- ☐

  where? tangled treachery of lost feelings hidden deep but seeping upward, outward, away from the boundary layer that keeps so much corralled. where? i didn't love or like or care for? could that even be true? doubts about my own understanding of my own inner workings--so much thinking without so much feeling. where? where do i keep all of that rat's nest of threads, connections, scars and complications? where is anger hiding in all that rubble? where have i laid my disappointment again and again and again? over and over the times he didn't show up.

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Sat 27-Mar-21 11:03 AM

- ☐

  Feeling pretty good today. Still feeling time pressure but that is probably just the work around the move. Medtronic is feeling good, although I do have to get cracking on producing something from the interface model. I really want to present something by Thursday.

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 25-Mar-21 10:16 AM

- ☐

  I'm going to call Annapolis RV and tell them to just wrap it up and I'll come get it tomorrow

- ☐

  Left a message for Tom

- ☐

  Going up tomorrow morning

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 24-Mar-21 10:26 AM

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 23-Mar-21 10:07 AM

- ☐

  Moved into the new house at 409 E. Bellefonte Avenue!

- ☐

  Lots of work to do but it feels great to be in our own house again.

- ☐

  Called and left a message for Tom of Annapolis RV to call

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 18-Mar-21 04:22 PM

- ☐

  Passed on Airstream contact information to Annapolis RV, Tom

  - ☐

    He said he would call him right now

- ☐

  Xfinity

  - ☐

    called about some confusion in accounting--looks like they are finding the old account not this new one

  - ☐

    she had to transfer me to a VA office or something

  - ☐

    she gave me to internet tech support to do the activation

  - ☐

    and they dumped the call...

  - ☐

    called back through the same channels--which will put me in touch with california people

  - ☐

    okay, here's the story so far

    - ☐

      quadrabyte2

    - ☐

      \_Xfinity314159

    - ☐

      both of these are the only Xfinity or Comcast in Remembear now

    - ☐

      looks like the modem isn't connected yet (although I attached to a cable upstairs, that one may not be active)

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 17-Mar-21 02:49 PM

- ☐

  Cancelled ADT walkthrough

  - ☐

    left a message for Slater 1866.595.1607 x0138

- ☐

  Renew 703.721.3500

  - ☐

    Virginia American Water -- 800.452.6863

    - ☐

      got the welcome letter

    - ☐

      account number: 1027-210042166701

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 15-Mar-21 11:54 AM

- ☐

  Volvo registration

  - ☐

    Called Palo Alto Volvo

    - ☐

      left a message to have them call

\

\

This is a useful site for all the different Alexandria services: [https://www.alexandriava.gov/Utilities](https://www.alexandriava.gov/Utilities)

\

- ☐

  \

- ☐

  Starting utilities at 409 E. Bellefonte Avenue

  - ☐

    Washington Gas

  - ☐

    ![](_attachments/image%20(66).png)

  - ☐

    Dominion Energy

    - ☐

      \

[TABLE]

- - ☐

    All Connect

    - ☐

      Green Power signup was affirmative

    - ☐

      COMCAST 1200 Mbs   

      - ☐

        \$99/mo first 12 months    

      - ☐

        (\$114.69 bill)  

      - ☐

        \$110/mo next 13 months

      - ☐

        slightly reduced discount

      - ☐

        Account number: 

    - ☐

      ADT service

      - ☐

        Safe Streets

        - ☐

          Slater 1866.595.1607 x0138

        - ☐

          gave a card Black AA for the file--no charge yet until we sign up

        - ☐

          updated keypad when they "take over"

        - ☐

          doorbell camera -- free

        - ☐

          monthly monitoring rate    \$58.99 + \$99 less 100 credit back

          - ☐

            police medical fire reporting via the monitoring mech

          - ☐

            stopping is somewhat expensive

        - ☐

          booked an appointment to have them come out for a walkthrough: Michael Nixon 30-mar 8-10 window

          - ☐

            36 months of payback

        - ☐

          \

    - ☐

      Need to connect water/sewage through Renew 703.721.3500

    - ☐

      Once we move in I have to call to get recycling and trash bins: 703.746.4357

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Sat 13-Mar-21 12:23 PM

- ☐

  Had a great idea for a tool to build to help with the source file reorganization project. See [Reorganization Tool for Source Code](https://www.evernote.com/shard/s3/sh/216016cc-b395-e676-490c-89b3b14e6361/845a64a0bf63679b20fffc7f2c586e8e) for more details.

- ☐

  Something I have to admit to J: this last couple of weeks have been bad...what I forgot is that I kinda decided to stop my Wellbutrin dose over that same period. Shit! What an idiot to not remember that. Could be a significant contribution to the problem. Sadly, I can't admit this to T because she would be so bitchy about it.

- ☐

  Have to talk to T about a couple of things. Maybe today we will go out to lunch

  - ☐

    The sex talk about meeting me half- or at least part-of-the-way (but only if the next subject goes well)

  - ☐

    I would like her to stop "correcting" me--she won't like this and probably won't be able to hear it

    - ☐

      The bus to the left and i want to turn right. it was his turn but i went because it wasn't going to cost him anything--he's a huge bus. She pointed out the error and was hurt that i snapped at her "i don't want you to criticize my driving"

    - ☐

      Last night called Susan "her" then immediately corrected myself with "they" but T also corrected me with "they" and I scowled at her--she didn't like that at all

    - ☐

      Here's the example I will give her: know how, of she said "it's me!" she would hate it if Ramona corrected her with "it is I" -- btw, [here](https://www.quickanddirtytips.com/education/grammar/it-is-i-versus-it-is-me) is a site about that particular construction

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 3-Feb-21 08:17 AM

- ☐

  Feeling much better today and yesterday. What's the variable? Joelle suggested that I talk to T about easing up on the house hunt because that seems to be part of the problem. I didn't, at least not yet, because there is a house over on Alexandria Drive that looks perfect but doesn't go on the market until 2/11. We are quite hopeful that this is the one but haven't seen the inside yet.

- ☐

  Finally got some responses from SWEs about meeting. The GUI folks are meeting me on Friday to talk about how to proceed.

- ☐

  Meeting with Brian today at 9:00 about mortgage preparation (if he calls like he is supposed to...already 5 min late...)

- ☐

  Brian

  - ☐

    gave him employment information

    - ☐

      Medtronic

    - ☐

      J&J

    - ☐

      Self-employed therapist

    - ☐

      he doesn't need Casti

  - ☐

    he will have to transfer us to DC licensed person if we go there

  - ☐

    2020 they looked at loan rates

    - - ☐

        765K was top for conventional

      - ☐

        now up to \$800K so we will qualify

    - ☐

      \$1M 20% down

      - ☐

        monthly mortgage/prop taxes/homeowners: \$4350 monthly

      - ☐

        to get to \$4000 or under we would need to put a bit down

    - ☐

      credit report is good for 4 months

    - ☐

      we said go ahead and set things up

    - ☐

      paperwork will need doing

      - ☐

        he will send it so we can start on that

      - ☐

        \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 29-Jan-21 08:04 AM

- ☐

  Yesterday Joelle and I began the the "uncover feelings" project where we are going to practice setting aside all the intellectual stuff and slog around in the feelings morass. Terese suggested this line of attack and when I described it to J she agreed. Will it help me avoid the mire and depressive pit? I sure hope so.

- ☐

  Starting to think about whether this interface project for Stefan is even worth pursuing. I sent out a plea for help to all the SW leads a couple of days ago and got back exactly one response that was throughtful. One that was dismissive. One apologetic. Otherwise silence...

- ☐

  Insurance coverage fuckup: yes, Safeway is using the CVS CareMark coverage

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 28-Jan-21 07:58 AM

- ☐

  Finally feeling quite a bit better today -- Joelle might point out it's a Joelle day so maybe that's why?

- ☐

  Good conversations with both T and H yesterday about feelings, living situations, etc.

- ☐

  I want to focus on getting down under the covers on the feelings thing with Joelle. I think I am suffering from the thick blanket of cover hiding those feelings. T thinks I am sort of in serious denial and recommends leaning in to the feelings as the way things are

- ☐

  Found an interesting code generation tool, Acceleo, that I am only this morning starting to explore. Might be huge (might be nothing).

- ☐

  I sent a note to CALPIRG asking to stop contributions

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 27-Jan-21 10:41 AM

- ☐

  Terese suggests a fundamental problem is that I wish-away (or actively deny) how/who i really am rather than just leaning into the bad feelings--i need to start talking to Joelle about this exactly. Prep before sessions to get down to the real feeling level...

- ☐

  We found a house in DC near Howard University that looks very promising

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 26-Jan-21 07:25 PM

- ☐

  back in the slump by the end of the day today

- ☐

  depressed...i just don't care

- ☐

  i reported to terese last night: "hanging on by my fingernails" and she liked me telling her

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 25-Jan-21 06:46 AM

- ☐

  still having a hard time

- ☐

  set to see Joelle twice a week for awhile to see if i can break free of this gloom

- ☐

  T of course is pissed at me for withdrawing and not taking care of her

- ☐

  Fair enough, but wow is this ever a nasty episode

- ☐

  Joelle points out the Jan/Feb is a bad time of year for me. Remember right after Africa? That was just like this one.

- ☐

  After therapy today

  - ☐

    J and I think the main problem is the job

  - ☐

    she gave me a framework in which to manage the stuck feeling -- having to ask for help is such a problem

    - ☐

      spreadsheet to track emails asking for help

    - ☐

      send out requests, follow up in four days if no reply then one more time after four more days

    - ☐

      i already feel much better

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 22-Jan-21 01:07 PM

- ☐

  Not doing well these days. The kids say I seem depressed. Terese says I seem angry--often at her. Not sure it's her but I am taking it out on her.

- ☐

  I'm going to ask Joelle for another time in the week for awhile (Rickie Jacob's idea, apparently)

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 20-Jan-21 03:11 PM

- ☐

  Biden is inaugurated and the country breathes a sigh of relief

- ☐

  Therapy today

  - ☐

    Get my office in order

  - ☐

    Get a working meeting set up with a SWE expert--to let him/her do the work

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 19-Jan-21 03:09 PM

- ☐

  Back from the West Virginia weekend

  - ☐

    Antietam was moving in a way I did not expect--I know enough to know there was so much death and danger there

  - ☐

    Harper's Ferry was interesting geologically, the confluence of two big rivers, but otherwise a yawn

  - ☐

    Nice hike with T though

  - ☐

    Hilary blew to pieces, thought Nate had gone off to kill himself when he went out for a post-fight walk

  - ☐

    She is having some existential turbulence

- ☐

  Settling down to work and feeling good about it

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 18-Jan-21 06:55 AM

- ☐

  Performance review with Stefan today

  - ☐

    SMAART actions

  - ☐

    goals on the interface project

  - ☐

    check HR site for SMART Action

  - ☐

    what

  - ☐

         approach every swe

  - ☐

         improve modeling paradigm   

  - ☐

    how

  - ☐

         implement one and review it

  - ☐

    workday update

  - ☐

    career interest add travel to germany

  - ☐

    *Stefan and I discussed the CDIP I had submitted. Generally, we are in very good agreement about expectations, goals, and avenues to pursue over the next year. I will need to make a few changes--mostly additions--to the plan to capture some items that came up in our conversation:*

  - ☐

    *-- add some detail (via SMART Actions) describing what/how the interface documentation project should proceed*

  - ☐

    *-- add to career interest section my desire to travel to Germany to meet with Stefan and Rosti in person*

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 15-Jan-21 09:24 AM

- ☐

  Terese found a great house in DC on Windom Place Northwest

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 14-Jan-21 08:39 AM

- ☐

  Ultrasound today

  - ☐

    went just fine

- ☐

  yesterday the meeting with Stefan sort of derailed the momentum L and i have been building up. i'll meet with her today to talk about that.

- ☐

  later, i'm feeling better about groking what S wants and we talk it over for half an hour--we are still well aligned

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 13-Jan-21 10:00 AM

- ☐

  signed up for Medtronic ESPP at Fidelity today: 10% of paycheck

- ☐

  signed up for 401(k) contributions (12%)

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 12-Jan-21 04:40 PM

- ☐

  had a good working session with Lalitha today--making progress on the state machine/sequence diagram paradigm to adopt

- ☐

  blood draw to check for cancer markers, PSA, etc.

- ☐

  met with Sabin today

  - ☐

    ESPP 10%

  - ☐

    401(k) 12% or about \$26000

  - ☐

    net worth is about \$1.7M so we are doing fine

  - ☐

    good returns lately because the stock market is soaring

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Sun 10-Jan-21 11:41 AM

- ☐

  feeling better--traction on the interface modeling problem

- ☐

  note that i had double coffee this morning

- ☐

  but also, we are getting a handle on where to live with the kids (they need more privacy)

- ☐

  Denise, Michael, and Max all have Covid

  - ☐

    D went to the hospital last night, getting some sleep now today which is good

- ☐

  Adding some

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 8-Jan-21 03:10 PM

- ☐

  feeling pretty good today. +2 maybe

- ☐

  getting some traction on the projects at work

- ☐

  the dryer is broken in the house but we should be getting a new one any day

- ☐

  went to the urologist, Patel, today. not sure i want him to be my doc though

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Thu 7-Jan-21 02:29 PM

- ☐

  Found a way, I think, to use a trigger/signal combination in EA to build interface state machines with data payloads.

- ☐

  It's going to be awkward and clumsy but just might work:

  - ☐

    Set the auto naming counter for Signal:   s 800 \_

  - ☐

    Set the auto naming counter for Trigger:  t 800 \_

  - ☐

    Create a package folder called Triggers where all the Trigger and Signal instances can be stored

  - ☐

    When a transition needs a new trigger

    - ☐

      Create a new Signal

      - ☐

        Toolbox / Class / Signal can be used to drag a new Signal out to the diagram (it won't stay here)

      - ☐

        The Signal's note/description field should get some text describing what the signal/trigger means

      - ☐

        If this Signal carries any parameters:

        - ☐

          go to window Features / Attributes and add the parameters as attributes

        - ☐

          note that we will use the Alias field as a description field

        - ☐

          ![](_attachments/image%20(55).png)

        - ☐

          \

    - ☐

      Create a new Trigger

      - ☐

        Draw the transition that will be assigned this new trigger

      - ☐

        Double click the transition in the diagram to get the Transition Properties dialog

        - ☐

          click the ... box to the right of the Name line to get the Select Trigger dialog

        - ☐

          be sure the Triggers folder is selected in the presented tree--if you forget to do this it isn't a problem because the tree location can changed later

        - ☐

          click the New button in the lower left corner to get the New Element dialog

        - ☐

          click the Auto button to the right of the Name line--you will get a name like 't800\_' automatically filled in to the Name field

        - ☐

          add the same meaning text as you did when the Signal was created

        - ☐

          Type will automatically be set to Signal as it should

        - ☐

          click Save to dismiss the New Element dialog

      - ☐

        ![](_attachments/image%20(67).png)

      - ☐

        click OK to dismiss the Select Trigger dialog, leaving you at the Transition Properties dialog

      - ☐

        click the ... box to the right of the Specification line to get the project tree again

      - ☐

        now you should have a trigger with a name like 't802_Initialize' connected to a Signal with an almost identical name 's802_Initialize'

      - ☐

        ![](_attachments/image%20(52).png)

      - ☐

        Click the OK button(s) to dismiss any open dialog boxes

      - ☐

        Your transition in the state machine diagram should now be labeled with the Trigger name--but notice any arguments associated through the related Signal don't show up on the diagram. That's a shortcoming of the EA tool.

      - ☐

        Last, you can just delete the Signal element on the state machine diagram. It will still be in the Project tree.

      - ☐

        Find both the Trigger and Signal instances you created in the Project tree, dragging them to the Triggers folder you created to hold them.

        - ☐

          While this step doesn't seem critical, just an organizational nicety, it turns out to be essential else EA will code the Trigger instances in a different way which carries less information (???)

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 6-Jan-21 11:43 AM

- ☐

  Feeling much better today. Excited about cycling with Nate. We have a goal to do a long ride in the Spring.

- ☐

  Good talk with H about the mechanisms behind the app she wants to build. I asked her to build a Trello board and let's go.

- ☐

  I think I want to take a sailing class. I was delighted that both the kids are interested.

- ☐

  Kiel says he paid first Verizon bill on: 15 Dec \$74    9 Nov \$152

  - ☐

    Told Citi we dispute the charges

  - ☐

    Claimed the split happened Oct 13, 2020 (i just guessed)

  - ☐

    See email confirmation of resolved disputes

    - ☐

      Jan 5, 2021

    - ☐

      Dec 5, 2020

    - ☐

      Nov 2020 -- not yet disputed but the page says it isn't available right now...

- ☐

  **Trump encourages a coup attempt!**

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 5-Jan-21 10:06 AM

- ☐

  Bad day yesterday. Maybe due to the Dry January. Could alcohol be that important to me? I guess so. This dry spell is no problem to manage--except for possibly feeling -2 the last couple of days--so I take that as a good sign.

- ☐

  Brandi sent a note to say she had forwarded my latest angry email to customer service.

- ☐

  Started a new mood log, here instead of in a separate document

- ☐

  Working on the Virginia DMV thing

  - ☐

    need to transfer vehicle registration to get insurance changed

  - ☐

    DMV Select possibilites (https://www.dmv.virginia.gov/DMVLocator/DMV.aspx?LocationType=S)

    - ☐

      6506 Loisdale Rd, Springfield, VA 22150, USA 9 miles

    - ☐

      ...

  - ☐

    Fuck that. I just put in a call to Beth at State Farm to have her call me. Let's just not move things as we may not stay in Virginia.

    - ☐

      Just left Nicole a message to  say that the plan has changed

  - ☐

    Talked to Beth at State Farm

    - ☐

      we will leave everything but renter's insurance address with her

    - ☐

      she suggested that I check on requirements when moving to Virginia and it turns out there is some stuff we have to do [Moving to Virginia Checklist](evernote:///view/225409/s3/859d19f2-3775-32d0-825d-9c5e37f39d1b/e719d2ef-4d96-4a74-a949-e6abfd5d1e13/)

  - ☐

    Talked to Nicole's office person (name? she is very nice) and she will

    - ☐

      Add Terese to the policy but needs her social last 4

    - ☐

      Change the renter's address for us--leaving all the other stuff alone for now

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 4-Jan-21 01:10 PM

- ☐

  The CORBA problem still isn't resolved so I will call them again now  800.565.0122

  - ☐

    Terese is going to write a letter and send a check

  - ☐

    She wants the dates of all the times I called

  - ☐

    I called at 12:30 and was on hold for over 60 minutes --- when the system then threw me off saying something was not working on their end

  - ☐

    Called again at 16:35

    - ☐

      Immediately told that expected wait time is between 1:13 and 1:30 !

    - ☐

      \

- ☐

  JK Moving, called Orion but got now answer at 703.996.1296

\

- ☐

  State Farm

  - ☐

    got a call from Nicole Edwards about changing agents

  - ☐

    policy numbers

    - ☐

      410 3667-05

    - ☐

      461 29545-05

  - ☐

    DMV appointment

    - ☐

      virginia dvm

    - ☐

      changing residence

    - ☐

      looks like i might be able to do it at AAA: [(703) 549-1080](tel:(703)%20549-1080)

  - ☐

    then call to let Nicole know i have an appt

  - ☐

    she will send proof of insurance for that appointment

  - ☐

    all transfer should be complete by Wednesday and she will send the declaration page

\

\

- ☐

  Vien, Lalitha, Me

  - ☐

    First meeting is essentially a waste of time -- he doesn't get what we are asking from him

  - ☐

    \

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 23-Dec-20 03:09 PM

- ☐

  feeling pretty blue today (again). terese thinks the problem is all the beer i had last night but i still don't think that's it. part of the problem maybe but not the whole problem. we'll see in january when we run dry for a month.

- ☐

  talked to Lalitha today about how to represent the protocol messages

  - ☐

    i think she will be good to work with

  - ☐

    she was pleased to have a collaborator to help get some traction

  - ☐

    she got bogged down on this project without any help--i am not surprised because it is going to be slow to grep through crappy code to find all the messages being sent

  - ☐

    we talked about whether our project should focus on inter-process or inter-subsystem messages. now i'm wondering if trying to target the process level is wrong for two reasons:

    - ☐

      it will be much more difficult to figure out what process runs a line of code to send or receive a message

    - ☐

      processes don't usually have names making it hard to identify a participating entity by name

  - ☐

    she also raised the question about using the seq diagrams: how can we represent parallel processes?

    - ☐

      but isn't a protocol a collection of non-parallel transactions by nature? if two things are happening simultaneously, isn't that just a pair of protocol transactions that happen to be concurrent? why would we have to represent that in the specification?

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Tue 22-Dec-20 10:39 AM

- ☐

  this is coding for things to follow up with Stefan about:

  - ☐

    ***search "both EIN-SSR?" in the model***

  - ☐

    ***search "three relationships necessary"***

- ☐

  COBRA call follow up

  - ☐

    no response by yesterday so i called back

  - ☐

    explained again the i only requested MEDICAL for the month of November. No dental, vision, FSA at all.

  - ☐

    she goes off to check with someone

    - ☐

      "was already processed" -- i said what does that mean?

    - ☐

      she removes the December coverage

    - ☐

      already the January coverage is gone

    - ☐

      ticket# 18132574 Gev is her name -- 2-3 business days to resolve this but the wheels are turning

- ☐

  Safeway

  - ☐

    transfer all the meds to VA

  - ☐

    change insurance to Bind

  - ☐

    talked to the woman on King St. -- she was very helpful but i don't have much confidence everything is right. i will go there tomorrow at 19:00 to pickup all the scripts

- ☐

  Medtronic

  - ☐

    Called AskHR

  - ☐

    She referred me to MBSC:

    - ☐

      Medtronic Benefit  Service Center

      - ☐

        ask a Rep  833.261.5740

        - ☐

          they have the wrong zip -- working through

        - ☐

          verify address change with Bind

          - ☐

            will take another few days to work through to all DB

          - ☐

            TU FRI they get new demographics week from tomorrow

        - ☐

          remove the R

        - ☐

          confirmation number: 11955389623

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 21-Dec-20 06:55 AM

- ☐

  Bad day yesterday. For the first time, I think, I had the feeling that this was a mistake. T had expressed this to me a couple of days ago so maybe that was the setup and I was just a bit slow to notice?

- ☐

  Todd leaving was announced on Friday. Damn. What will that mean to the modeling effort?

  - ☐

    *talked to Stefan about this and he explained that Delin is model oriented, was hired "ahead" of Todd, so he is leaving to pursue his own career*

- ☐

  Today, meeting with Stefan once more before he goes away on vacation till Jan 7, almost 3 weeks. I will propose the sequence diagram way of modeling interfaces. See what he says. The timing here just sucks though.

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Sat 19-Dec-20 01:13 PM

- ☐

  Cancelled Aetna coverage with Stanford for me

- ☐

  Asked Sattler again to transfer everything but that won't happen until Monday at the earliest

- ☐

  Called Alliance Special Pharmacy but they don't have us in the computer -- they are only specialty drugs

- ☐

  Called Alliance Rx Home Delivery

  - ☐

    insurance is correct

  - ☐

    address is now correct

  - ☐

    he recommends asking the doctor to just reissue scripts to do it quicker

  - ☐

    he adds Terese as my dependent

  - ☐

    they are just waiting to hear from the doctor, that will kick off refills

- ☐

  T and I went walking on Kingston Island -- not beautiful but got us out there...

- ☐

  Sent off a birthday card to Shirley today--handwritten, although it probably doesn't matter to her--because I can't think of a better way to make it count

- ☐

  \

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Fri 18-Dec-20 11:04 AM

- ☐

  Sent Dr. Sattler a request to help with the med transfer

- ☐

  Yesterday Walgreens couldn't fix the problems because they had a computer crash

  - ☐

    T is showing as primary

  - ☐

    Insurance may not be correct

- ☐

  Cleaner came today to sweep through the house for a couple of hours. Looks good.

- ☐

  We are negotiating the Christmas visit crap with Kiel

****

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Wed 16-Dec-20 03:39 PM

- ☐

  Transferred all of Terese's and Thomas's meds from Safeway to Walgreens

  - ☐

    also requested 90-day amounts with free delivery

  - ☐

    used the Bind coverage

- ☐

  Saw Joelle today. It helped to pull out of the depression that set in yesterday. Maybe just exhausted from the moving process?

  - ☐

    She will be out recovering from surgery until Jan 6 now

  - ☐

    I worry about her. She reassures me that she is in good hands.

- ☐

  Luckily I had the foresight to take some notes before we hit the road (see below) so I could remind myself what i was doing before we left.

- ☐

  Virginia

  - ☐

    It snowed today!

  - ☐

    Great living here with the kids. So far so good.

  - ☐

    The bad news: Terese's allergies have kicked up pretty badly. Better today but really bad the last couple of days.

- ☐

  Continuing to work on the diagram replacement in the SAD

- ☐

  Meeting tomorrow with Latitha to talk about interface stuff.

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Mon 30-Nov-20 07:24 AM

- ☐

  Thanksgiving is over and we are just about to hit the road (tomorrow). One more meeting with Stefan today.

- ☐

  Found some good stuff on the SAD diagram substitution problem. 7Zip can manipulate a Word "strict open" format file.

- ☐

  Success so far in substituting one image manually in a test project (see Downloads for the folder)

- ☐

  Next is getting python to mess with the meta data (see Pillow and the bookmark to a tutorial)

- ☐

  If I can figure out a way to use meta data to track version or something, we can update only the images that need to change.

- ☐

  **Be sure to use the Visual Code python debugger** to see if it is as good as the PyCharm tool--might be and that Pillow failed to load problem isn't an issue because this debugger uses the machine environment where Pillow loaded fine

\

- ☐

  I think I have a plan for linking the model diagrams to the SAD

  - ☐

    The addin (or python code) that does the diagram extraction grabs the version number field of the diagram

  - ☐

    Creates a file for the diagram

  - ☐

    Sets the Windows file version field to that version

  - ☐

    Outputs the file name and the version to an index document (do we need this?)

  - ☐

    Missing link: how to connect the image001.png type files to the appropriate diagrams?

    - ☐

      might work to use the Alt text field

\

\

\

\

\

\

\

\

\

\

\

\

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

original few entries that i didn't bother to move up....

\

Tue 17-Nov-20 10:00 AM

- ☐

  T and I go through a bunch of logistical stuff coming up. Took notes (which should have gone here) and got all those items either done or entered into Outlook/Things

- ☐

  Reinstalling Enterprise Architect because I screwed up my first install trying to get an addon to work (broke the license key)

  - ☐

    Here is the confluence page that Stefan wrote describing how: [http://tamans-ww120lv:8090/display/EINKB/Setup%3A+Enterprise+Architect](http://tamans-ww120lv:8090/display/EINKB/Setup%3A+Enterprise+Architect)

  - ☐

    success

- ☐

  Beautiful reformat of the Einstein overview diagram. Stefan liked it too.

Wed 18-Nov-20 07:58 AM

- ☐

  Starting here a list of diagrams that need to be moved into the real model soon because I have improved them. See the *Einstein (partial for reformat work)* model under git control.

  - ☐

    ![](_attachments/image%20(57).png)

  - ☐

    ![](_attachments/image%20(49).png)

  - ☐

    ![](_attachments/image%20(37).png)

  - ☐

    ![](_attachments/image%20(54).png)

  - ☐

    ![](_attachments/image%20(43).png)

  - ☐

    \

- ☐

  Asked about the two Einstein context diagrams that are almost identical on Slack

- ☐

  J&J sent a note about COBRA

  - ☐

    I will call to tell them

    - ☐

      no FSA

    - ☐

      no dental

    - ☐

      no vision

    - ☐

      one month

    - ☐

      Wed 18-Nov-20 08:57 AM

      - ☐

        Those three things removed

      - ☐

        termination can be done via a phone call to 1-800-565-0122 on December 7

      - ☐

        i put a reminder in Outlook

- ☐

  removed the original safety cables from Nessie and attached the new ones that are compatible with the Volvo

- ☐

  the piano was picked up today!

- ☐

  found a useful blog post with a couple of video links from the Jama guy to help with the Jama update project

  - ☐

    [https://community.jamasoftware.com/communities/community-home/digestviewer/viewthread?MessageKey=de0bdf91-8867-4036-b29e-3f37adf0a0cb](https://community.jamasoftware.com/communities/community-home/digestviewer/viewthread?MessageKey=de0bdf91-8867-4036-b29e-3f37adf0a0cb)

- ☐

  using the abstractitems GET I see the project is probably 10

19-nov-2020

- ☐

  turned 65 today. feeling old and sad about leaving California. We drove up to Glendeven for a three-day stay.

Wed 25-Nov-20 04:58 PM

- ☐

  Had a great stay at Glendeven.

- ☐

  Came home and went right to work packing up the house. That completed yesterday when the truck came to cart (almost) everything away.

- ☐

  Today I did the neuro test for baseline. That went great and I am sure I am quite healthy. The only difficult items on the test had to do with--wait for it--short term memory.

- ☐

  Had a good conversation with Stefan this morning for an hour. We talked about a number of things. Took some [notes](evernote:///view/225409/s3/15b373a4-fe49-926a-e6c6-82e371a9299f/e719d2ef-4d96-4a74-a949-e6abfd5d1e13/).

- ☐

  This afternoon I got back to work but only, starting at 3:00 in the afternoon, felt up to doing administrative stuff that needed my attention. Here it is 5:03 and I just finished all those chores.

- ☐

  Tomorrow I start to work for real.

\

\

\

\

\

\

\

\

\

\

\

\

\_\_\_\_\_\_\_\_\_  Mon 8-Jan-24 10:03 AM \_\_\_\_\_\_\_\_\_

\

\

\_\_\_\_\_\_\_\_\_  Tue 6-Feb-24 08:18 AM \_\_\_\_\_\_\_\_\_

\

\

\

## See also

- [[Enterprise Architect]]
- [[Maker & Electronics]]
- [[Running]]
- [[Software Development]]
- [[Woodworking]]
