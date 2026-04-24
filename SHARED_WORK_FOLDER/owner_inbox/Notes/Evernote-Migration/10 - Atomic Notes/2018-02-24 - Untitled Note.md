---
title: Untitled Note
uid: 20180224T0046
created: '2018-02-24'
updated: '2024-04-01'
source: evernote
original_notebook: My Notes4
tags: []
aliases: []
source_url: https://mail.google.com/mail/u/0/#inbox/161c0273cf7c0a85
---

Jim, as you can see from my notes after your suggestions, almost everything you mentioned is addressed. There are a few small issues left to iron out. I highlighted those things still needing your attention:

\

\

\

> I'd conflate Aux Window Manager, aux_local_service_server, and viz_service_client
>
> Are the last two not apps then? And does it make sense to combine them into a single module called Aux Window Manager?
>
> \
>
> \
>
> I'd conflate cloud_to_robot and cloud_uploader
>
> Call the new combined module Cloud Service?
>
> \
>
> \
>
> interfaces/examples/generate_events.cc can be omitted
>
> gone
>
> \
>
> I'd rename Libraries Apps Manifest to something more like "Manifest" or "Manifest Infrastructure" or something like that. This represents infrastructure for parsing and processing the manifests that go inside apps.
>
> renamed to Manifest Infrastructure
>
> should I remove the "Library..." prefix on all of the modules in the "Library" domain? it doesn't seem like it adds any clarity to the names
>
> \
>
> \
>
> Libraries Apps Server isn't really a module. Most of what's there belongs more rightfully in other modules. In particular:
>
> i moved all the files you mention below but there are still several not dealt out to other modules yet:
>
> \<EAFile name="libraries\apps\server\generator\generator_controller.cc" subject="EAID_96D2B3DE_7C2C_42ef_91B4_F0A457D5B810"\>
>
> \<Properties/\>
>
> \</EAFile\>
>
> \<EAFile name="libraries\apps\server\generator\generator_controller_test.cc" subject="EAID_96D2B3DE_7C2C_42ef_91B4_F0A457D5B810"\>
>
> \<Properties/\>
>
> \</EAFile\>
>
> \<EAFile name="libraries\apps\server\generator\generator_server.cc" subject="EAID_96D2B3DE_7C2C_42ef_91B4_F0A457D5B810"\>
>
> \<Properties/\>
>
> \</EAFile\>
>
> \<EAFile name="libraries\apps\server\generator\generator_server_test.cc" subject="EAID_96D2B3DE_7C2C_42ef_91B4_F0A457D5B810"\>
>
> \<Properties/\>
>
> \</EAFile\>
>
> \<EAFile name="libraries\apps\server\generator\generator_thread.cc" subject="EAID_96D2B3DE_7C2C_42ef_91B4_F0A457D5B810"\>
>
> \<Properties/\>
>
> \</EAFile\>
>
> \<EAFile name="libraries\apps\server\generator\generator_thread_test.cc" subject="EAID_96D2B3DE_7C2C_42ef_91B4_F0A457D5B810"\>
>
> \<Properties/\>
>
> \</EAFile\>
>
> \<EAFile name="libraries\apps\server\generator\generator_utilities.cc" subject="EAID_96D2B3DE_7C2C_42ef_91B4_F0A457D5B810"\>
>
> \<Properties/\>
>
> \</EAFile\>
>
> \<EAFile name="libraries\apps\server\generator\generator_utilities_test.cc" subject="EAID_96D2B3DE_7C2C_42ef_91B4_F0A457D5B810"\>
>
> \<Properties/\>
>
> \</EAFile\>
>
> \<EAFile name="libraries\apps\server\manifest_handler.cc" subject="EAID_96D2B3DE_7C2C_42ef_91B4_F0A457D5B810"\>
>
> \<Properties/\>
>
> \</EAFile\>
>
> \
>
> auth_test.cc isn't really part of anything.
>
> gone
>
> \
>
> Everything under case_data should go with the case_data_server module
>
> moved
>
> \
>
> diary goes with the diary module
>
> looks like you must mean the "SDK Diary" module
>
> \
>
> identity_service should be grouped with the identity service
>
> I assumed you mean the "SDK Identify Service" module
>
> \
>
> Everything under prefbank should go with PrefBank
>
> I assumed you mean the "SDK Preference Bank" module
>
> \
>
> viz_processor should probably get its own module
>
> I created a new module in the Visualization Domain, a subtype of Viz Application Service: Visualization Processor
>
> \
>
> \
>
> Libraries Cloud and Libraries Cloud GRPC and Libraries Cloud Testing should probably go together with cloud_uploader. 
>
> done 
>
> \
>
> In general this module should be renamed to not imply that it's download-only, or cloud-to-robot only, since it's now taking on its bidirectional functionality.
>
> new combined module is now called Cloud Service as mentioned above. does that work?
>
> \
>
> \
>
> \
>
> Libraries Common should probably be conflated with Libraries Base.
>
> done
>
> \
>
> Libraries Eye Tracker should be grouped together with Eye Tracker Monitor
>
> done
>
> \
>
> \
>
> Libraries Gesture should get lumped together with a UID module somewhere.
>
> done
>
> \
>
> Libraries Monitor and Libraries Monitor Ham can get grouped together. (Although FWIW we're loosely planning to drop HAM.)
>
> done
>
> \
>
> Libraries Safety sure looks anemic! Maybe we should organize this content elsewhere, or maybe there's stuff that belongs here that we have improperly organized under other modules.
>
> yes, these two files probably should be moved elsewhere but for the moment i'll leave them until someone suggests a better home
>
> \
>
> Miimic is miisspelled :)
>
> no longer
>
> \
>
> fpga_mux can be rolled in with viz processor modules.
>
> done
>
> \
>
> It may be sensible to group persistence modules together into a subdomain or something. That's Diary, PrefBank, Library, and Briefcase.
>
> done
>
> \
>
> xeyes is now gone. :'(
>
> done
>
> \
>
> I feel like support for the generator and the UIDs is kind of scattered, and should be gathered together into a sensible place.
>
> i am open to suggestions...
>
> \
>
> Identification Service should be renamed to Identity Service
>
> done
>
> \
>
> I notice that we don't have any mention of third_party, or of Linux or QNX themselves. Is that intentional? Or is it just that this explicitly intends to only capture the first-party part of our system?
>
> i left those out only because 
>
>     -- the job was big enough as it stood when i started,
>
>     -- one of the first consumers of this model would be the SLOC classification effort (and those things are SOUP/OTC so they don't get SLOC classification)
>
>     -- the other early consumers would be the testing team and they won't test SOUP/OTC code
>
> if there is value in adding those elements to the model i am open to doing it, but that would be a lot of work because there are lots of those files
>
> \
>
> \
>
> Why do we omit .h files? IMO they're valid source files just like .c/.cc files, and in many ways they provide necessary context. In many cases they even result directly in compiled code.
>
> i left .h files out for much the same reason as the SOUP/OTC files but you have a good point. if there is value to adding them to the model i can do it. it wouldn't be a huge amount of work because the mapping for each of the .h files would be pretty easy to determine.
>
> \
>
> What's with this strange "\\ character? It looks like a typo of "/" maybe? :)
>
> i struggled with the stupid windows/linux difference--wasted way too much time getting string matches to work because of that--and finally settled on the \\ for no good reason except that i am a dyed-in-the-wool windows guy

\

On Fri, Feb 23, 2018 at 10:16 AM, Thomas Brennan-Marquez \<[thomasbrennan-marquez@verbsurgical.com](mailto:thomasbrennan-marquez@verbsurgical.com)\> wrote:

> Thanks for the detailed response, Jim. This is very helpful. I'll make the changes and post a new version today.
>
> \
>
> On Fri, Feb 23, 2018 at 9:47 AM, Jim Shuma \<[jshuma@verily.com](mailto:jshuma@verily.com)\> wrote:
>
> Wow, this looks great. It's actually a pretty logical organization of a codebase that was threatening to be quite amorphous. I think we'll need plenty more iterations, and I think designating owners is a good way to distribute this responsibility over time, but this is a great start.
>
> \
>
> A couple notes...
>
> - ☐
>
>   I'd conflate Aux Window Manager, aux_local_service_server, and viz_service_client
>
> - ☐
>
>   I'd conflate cloud_to_robot and cloud_uploader
>
> - ☐
>
>   interfaces/examples/generate_events.cc can be omitted
>
> - ☐
>
>   I'd rename Libraries Apps Manifest to something more like "Manifest" or "Manifest Infrastructure" or something like that. This represents infrastructure for parsing and processing the manifests that go inside apps.
>
> - ☐
>
>   Libraries Apps Server isn't really a module. Most of what's there belongs more rightfully in other modules. In particular:
>
>   - ☐
>
>     auth_test.cc isn't really part of anything.
>
>   - ☐
>
>     Everything under case_data should go with the case_data_server module
>
>   - ☐
>
>     diary goes with the diary module
>
>   - ☐
>
>     identity_service should be grouped with the identity service
>
>   - ☐
>
>     Everything under prefbank should go with PrefBank
>
>   - ☐
>
>     viz_processor should probably get its own module
>
> - ☐
>
>   Libraries Cloud and Libraries Cloud GRPC and Libraries Cloud Testing should probably go together with cloud_uploader. In general this module should be renamed to not imply that it's download-only, or cloud-to-robot only, since it's now taking on its bidirectional functionality.
>
> - ☐
>
>   Libraries Common should probably be conflated with Libraries Base.
>
> - ☐
>
>   Libraries Eye Tracker should be grouped together with Eye Tracker Monitor
>
> - ☐
>
>   Libraries Gesture should get lumped together with a UID module somewhere.
>
> - ☐
>
>   Libraries Monitor and Libraries Monitor Ham can get grouped together. (Although FWIW we're loosely planning to drop HAM.)
>
> - ☐
>
>   Libraries Safety sure looks anemic! Maybe we should organize this content elsewhere, or maybe there's stuff that belongs here that we have improperly organized under other modules.
>
> - ☐
>
>   Miimic is miisspelled :)
>
> - ☐
>
>   fpga_mux can be rolled in with viz processor modules.
>
> - ☐
>
>   It may be sensible to group persistence modules together into a subdomain or something. That's Diary, PrefBank, Library, and Briefcase.
>
> - ☐
>
>   xeyes is now gone. :'(
>
> - ☐
>
>   I feel like support for the generator and the UIDs is kind of scattered, and should be gathered together into a sensible place.
>
> - ☐
>
>   Identification Service should be renamed to Identity Service
>
> - ☐
>
>   I notice that we don't have any mention of third_party, or of Linux or QNX themselves. Is that intentional? Or is it just that this explicitly intends to only capture the first-party part of our system?
>
> - ☐
>
>   Why do we omit .h files? IMO they're valid source files just like .c/.cc files, and in many ways they provide necessary context. In many cases they even result directly in compiled code.
>
> - ☐
>
>   What's with this strange "\\ character? It looks like a typo of "/" maybe? :)
>
> \
>
> On Thu, Feb 22, 2018 at 4:54 PM Thomas Brennan-Marquez \<[thomasbrennan-marquez@verbsurgical.com](mailto:thomasbrennan-marquez@verbsurgical.com)\> wrote:
>
> The [Software Module Model](https://web.verbsurgicaleng.com/web/Models/KIWI_Module_Model/index.htm) is now in a first draft complete state. That means:
>
> - ☐
>
>   There are a whole bunch of **Software Modules** defined 
>
> - ☐
>
>   *Every* source file (.cc and .c) found in the important directories (bullet list below) of the source trees have been mapped to exactly one module
>
>   - ☐
>
>     EXECUTABLES
>
>   - ☐
>
>     DEVICES
>
>   - ☐
>
>     CONFIG
>
>   - ☐
>
>     INTERFACES
>
>   - ☐
>
>     LIBRARIES
>
>   - ☐
>
>     SDK
>
> - ☐
>
>   The latest list of modules and file mappings is [here](https://web.verbsurgicaleng.com/web/Models/KIWI_Module_Model/SoftwareModuleMap/ModuleListPage.html)
>
> - ☐
>
>   At this point I am only confident that about 50% of the model is actually *correct*. Correctness will be judged by the following metrics:
>
> - ☐
>
>   Are the modules called out in the model "real" in the sense that these are sensible bundles of functionality?
>
> - ☐
>
>   Are the names of these modules the correct names (now is the time to get the names right because we all will be living with them for a long time)?
>
> - ☐
>
>   Are the files that are linked to each module the right set of files?
>
>   - ☐
>
>     Is every file linked to a module truly and logically associated with that module?
>
>   - ☐
>
>     Are there any files missing that should be included in a module?
>
> - ☐
>
>   Note that some modules have zero files mapped to them. That probably means either those modules aren't "real" or the source files that implement a real module have been incorrectly mapped to a different module.
>
> - ☐
>
>   Now we need to vet the model and I don't have a good, methodical way of doing that ready to hand. The best process I can think of is:
>
> - ☐
>
>   For every module called out in the model, choose a logical person to "own" that module and ask him/her to take a look at every linked file to answer the questions posed above.
>
> \
>
> \
>
> -- 
>
> \
>
> \
>
> \
>
> \

\
