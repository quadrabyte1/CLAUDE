---
title: Equalizer APO / Documentation Wiki / Documentation
uid: 20240723T1825
created: '2024-07-23'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes2
tags: []
aliases: []
source_url: https://sourceforge.net/p/equalizerapo/wiki/Documentation/
---

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIgdHZmVV8iIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjaDJJaHYiIC8+PC9zdmc+)

Web Clip

\

- [Home](https://sourceforge.net/)
-  / [Browse](https://sourceforge.net/directory/)
-  / [Equalizer APO](https://sourceforge.net/p/equalizerapo/)
-  / Documentation Wiki

![](_attachments/svg_1%20(5).svg)

# Equalizer APO Documentation Wiki

## A system-wide equalizer for Windows 7 / 8 / 8.1 / 10 / 11

Brought to you by: [jthedering](https://sourceforge.net/u/jthedering/profile/)

- [Summary](https://sourceforge.net/projects/equalizerapo/)
- [Files](https://sourceforge.net/projects/equalizerapo/files/)
- [Reviews](https://sourceforge.net/projects/equalizerapo/reviews/)
- [Support](https://sourceforge.net/projects/equalizerapo/support)
- [Downloads](https://sourceforge.net/projects/equalizerapo/files/1.3.2/)
- [Documentation Wiki](https://sourceforge.net/p/equalizerapo/wiki/)
- [Code](https://sourceforge.net/p/equalizerapo/code/)
- [Tickets](https://sourceforge.net/p/equalizerapo/tickets/)
- [Discussion](https://sourceforge.net/p/equalizerapo/discussion/)

****

- [Wiki Home](https://sourceforge.net/p/equalizerapo/wiki/)
- [Browse Pages](https://sourceforge.net/p/equalizerapo/wiki/browse_pages/)
- [Browse Labels](https://sourceforge.net/p/equalizerapo/wiki/browse_tags/)

&nbsp;

- [Formatting Help](https://sourceforge.net/nf/markdown_syntax)

## Documentation [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/history "History") [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/feed "RSS") [**](https://sourceforge.net/p/equalizerapo/wiki/search "Search")

Authors: [![](_attachments/default-avatar.png)](https://sourceforge.net/u/jthedering/profile/)

Welcome to the Wiki of Equalizer APO. This is the documentation for users of Equalizer APO. Developers might also be interested in reading the [developer documentation](https://sourceforge.net/p/equalizerapo/wiki/Developer%20documentation/). To begin using Equalizer APO, you should read the [tutorials](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#install_tutorial). After that, you can look at more detailed information in the [configuration reference](https://sourceforge.net/p/equalizerapo/wiki/Configuration%20reference/).

**Table of contents:**

- [Installation tutorial](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#installation-tutorial)
- [Configuration tutorial](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#configuration-tutorial)
- [Configuration file format](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#configuration-file-format)
- [Troubleshooting](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#troubleshooting)
  - [Configurator](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#configurator)
  - [Control Panel](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#control-panel)
  - [Log files](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#log-files)
  - [Hardware-accelerated OpenAL](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#hardware-accelerated-openal)

# Installation tutorial

1.  Download the Equalizer APO setup for your version of Windows (32 or 64 bit). If you are unsure if you need the 32 or the 64 bit version, you can open Start Menu -\> Control Panel -\> System and look up the system type.
2.  Execute the setup program and follow the instructions. Remember your installation path if you don't use the default of C:Program FilesEqualizerAPO . From here on, for better readability it is assumed that you use the default path.
3.  During the installation process the program Configurator.exe will be run. Make sure that you select the correct audio device to install the APO to. If you are unsure you can open Start Menu -\> Control Panel -\> Sound and look for the default output device. If you need to install the APO to other audio devices later, you can run the program again from C:Program FilesEqualizerAPOConfigurator.exe .
4.  After the installation finished, you should allow the reboot of your system. This is needed because the newly installed APO will not be used immediately but only after the audio service is restarted.
5.  When the system has rebooted, the APO should be active. This will only be noticable by a small reduction in volume and a mild low frequency boost, because this is what the example configuration file specifies. To change the APO's behaviour to something more useful, you can now read the [Configuration](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#config_tutorial) chapter.

# Configuration tutorial

1.  Open Windows Explorer and navigate to C:Program FilesEqualizerAPOconfig . You should find the files config.txt and example.txt. The file config.txt is the main configuration file that will automatically be loaded by Equalizer APO.
2.  Open the file config.txt in a text editor and you will see that it first defines a preamplification value and then includes example.txt. To check if the APO is really working you can start some audio or video application and adjust the preamp value while music is running. You should notice that the volume changes immediately each time after you save the file.
3.  To begin creating your individual filter configuration you should now install and run [Room EQ Wizard](http://hometheatershack.com/roomeq).

Screenshot of Room EQ Wizard (click to enlarge):

[![](_attachments/RoomEQWizard-thumb.png)](https://sourceforge.net/p/equalizerapo/wiki/Images/attachment/RoomEQWizard.png)

A detailed explanation of the usage of Room EQ Wizard is out of the scope of this document, but here is the basic process:

1.  Click the "Measure" button in the toolbar (Mark A in the above screenshot) to bring up the measurement dialog. Here you should first do "Check Levels" and adjust your output volume appropriately, then "Start Measuring". After the measurement, the dialog will close automatically and a frequency response graph is shown.
2.  Click the "EQ" button (Mark B) in the toolbar. Here you can select an equalizer type (Mark C). Use either "Generic" or, if you prefer bandwidth instead of Q, the "FBQ2496" equalizer type. Beware that no other equalizer types are currently supported.
3.  Click the "EQ Filters" button (Mark D) in the EQ window. Now you can add filters by setting "Control" to Manual, "Type" to PK/PEQ and then adjusting "Frequency", "Gain" and "Q"/"Bw Oct" to your needs. The graph in the EQ window will directly show the filter's frequency response. Since version 0.8, you can also use any of the other filter types available if they suit your needs, but generally the peaking filters should be the most appropriate for room correction.
4.  To save the filter settings, you should first use the "Save this filter set" button (Mark E) in the EQ Filters window. This will save the settings in a format that Room EQ Wizard can read back later when you need to make further adjustments.
5.  Now save the filter settings in a format that Equalizer APO can read. To do this, go to the main window of Room EQ Wizard. Open the "File" menu (Mark F) and select "Export" -\> "Filter Settings as text". Save under a new filename into C:Program FilesEqualizerAPOconfig .
6.  Open C:Program FilesEqualizerAPOconfigconfig.txt in a text editor and change the "Include" line to refer to your newly created configuration file. The change should be effective immediately.

Congratulations, you have now created your first configuration for Equalizer APO. To learn more about the usage of RoomEQWizard, you can look into its [help file](http://www.hometheatershack.com/roomeq/wizardhelpv5/help_en-GB/html/index.html). The process can even be automated to some extent, as is explained in this [forum thread](https://sourceforge.net/p/equalizerapo/discussion/general/thread/3ba39cad/).

# Configuration file format

This information has been moved to the [configuration reference](https://sourceforge.net/p/equalizerapo/wiki/Configuration%20reference/).

# Troubleshooting

This section describes approaches to solve possible problems impeding the successful operation of Equalizer APO.

## Configurator

By default, Equalizer APO will try to keep the functionality of other APOs that have been shipped with the sound card driver ("original APOs"). In some cases, this causes instabilities in the audio processing. The Configurator offers troubleshooting options to adjust how the original APOs are used.

If you experience instabilities during playback or recording when using Equalizer APO, you can try to disable the usage of the original APOs in the Configurator:\
1. Select your audio device by clicking on its connection name.\
2. Enable the troubleshooting options.\
3. Uncheck both "Use original APO" checkboxes.\
[![](_attachments/thumb) (click to enlarge)](https://sourceforge.net/p/equalizerapo/wiki/Images/attachment/UseOriginalAPO.png)\
Note that you will lose all features that the sound card driver realizes through its APOs. You can also try to uncheck only one of the check boxes to preserve some functionality.

Some sound card drivers disable options when they detect that another APO has been registered. You can uncheck one of the "Install APO" checkboxes to only install Equalizer APO in the pre-mix or post-mix stage. For the other stage, the original APO will be registered then, which may help to recover some options of the sound card driver.

## Control Panel

If you installed Equalizer APO and no changes to the configuration file lead to any changes in the signal, APOs might have been disabled for the device in the Control Panel.\
To check this, open Start Menu -\> Control Panel -\> Sound and double click on your audio device to open the properties dialog.

If the dialog has an "Enhancements" tab, go to that tab. You should see a view similar to the left screenshot below. Make sure the "Disable all enhancements" check box (red box) is unchecked, even if you don't use any of the enhancements in the list.

If the dialog does not have an "Enhancements" tab, go to the "Advanced" tab. You should see a view similar to the right screenshot below. Make sure the "Enable audio enhancements" check box (red box) is checked.

[![](_attachments/thumb%20(1))](https://sourceforge.net/p/equalizerapo/wiki/Images/attachment/EnhancementsTab.png)[![](_attachments/thumb%20(2))](https://sourceforge.net/p/equalizerapo/wiki/Images/attachment/NoEnhancementsTab.png)

## Log files

When Equalizer APO encounters a critical problem while running, it writes a line into the log file C:WindowsServiceProfilesLocalServiceAppDataLocalTempEqualizerAPO.log . So, in case of problems this file might contain useful information. Under normal circumstances, this file does not even exist, as it will only be created when an error occurs.

To get more information, you can enable trace messages, which means that Equalizer APO will write lines marked with "(TRACE)" to the file even when running normally. To do this, open regedit.exe, go to HKEY_LOCAL_MACHINESOFTWAREEqualizerAPO and set the value EnableTrace to true. Then, when playing back or recording audio via a device that Equalizer APO is installed to, information about initialization and the configuration files will be output to the log file. This might help e.g. to see if the configuration files are interpreted as intended. After you have finished, you should set EnableTrace back to false, so that the log file does not grow unnecessarily.

## Hardware-accelerated OpenAL

Normally, applications utilizing OpenAL for their audio output do not present a problem as they will often use DirectSound as their backend, which supports APOs. Some sound card manufacturers however provide OpenAL libraries with hardware-acceleration that access the hardware directly, circumventing APOs. There is no way to enable APO support for hardware-accelerated OpenAL, so the only solution for this is to either switch to another output library, if the application supports that, or to make OpenAL fall back to software.

To force OpenAL to fall back to software, the OpenAL32.dll may be replaced with a different one, for example from [http://kcat.strangesoft.net/openal.html](http://kcat.strangesoft.net/openal.html)\
A way to globally disable OpenAL hardware-acceleration however is to move or rename the vendor-specific OpenAL library in C:WindowsSystem32 or C:WindowsSysWOW64, which is often called like \*\_oal.dll, for example ct_oal.dll . Warning: This is a modification to the sound driver, which is of course not officially supported and can lead to unexpected results.

------------------------------------------------------------------------

## Discussion

1 [2](https://sourceforge.net/p/equalizerapo/wiki/Documentation/?page=1) [\>](https://sourceforge.net/p/equalizerapo/wiki/Documentation/?page=1) [\>\>](https://sourceforge.net/p/equalizerapo/wiki/Documentation/?page=1) (Page 1 of 2)

- ![](_attachments/default-avatar.png)

  a
  [John Accardi](https://sourceforge.net/u/accardi/profile/) - *2014-07-19*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#c9db "Link")

  Hello ... just installed Equalizer APO and reading the documentation it looks like this is just to adjust effects for individual channels .. L, R, Center, etc. I need to be able to boost volume, across all channels (master adjustments), but only for certain frequencies ranges. For example, lower volume in base but boost volume in some frequency ranges. Is this possible with Equalizer APO. If not, any suggestions for Windows applications that do this? Thanks.

   

  - 

  - ![](_attachments/default-avatar.png)

    a
    [Jonas Thedering](https://sourceforge.net/u/jthedering/profile/) - *2014-07-20*
    [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#c9db/5bb6 "Link")

    The "effects" currently implemented are actually mostly used to adjust the frequency response (the volume) in certain frequency ranges. For example, the peaking EQ filter (PK) takes a center frequency and a bandwidth argument to select the frequency range and its gain argument determines the boost/cut to the volume in that range. Also helpful for you can be the shelving EQ filters (LS/HS) which adjust the volume below/above a given frequency in another way than is possible with peaking filters. Please use Room EQ Wizard as described in the tutorial above, it will show you how the different types of filters adjust the volume at certain frequencies and will make it much easier for you to do the adjustments wanted. You can also use it without doing any measurements, just open REW and go to EQ-\>EQ Filters.

    Normally, the filters are just applied to all channels, so for your desired behaviour, just don't use the Channel command, which would allow you to limit the filtering to selected channels.

    Also, be careful when using filters with positive gain to boost frequency ranges. If you use these, you should also use the Preamp command to lower the overall volume, so that the output is not clipped.

     

    \
    Last edit: Jonas Thedering 2014-07-20

    - 

&nbsp;

- ![](_attachments/default-avatar.png)

  a
  [Derald Grimwood](https://sourceforge.net/u/drgrimwo/profile/) - *2015-03-16*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#8f2d "Link")

  Is thee a way to make a donation?

   

  - 

&nbsp;

- ![](_attachments/default-avatar.png)

  a
  [Mike Sims](https://sourceforge.net/u/mikesims10670/profile/) - *2015-11-01*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#91c6 "Link")

  Your software is truly amazing. I have never before had the kind of granular control in an EQ as you have provided here. Literally any frequency at any level - seems like it would be simple to make software EQs like this, but no one has ever done it to my knowledge until now.

  THANK YOU!

  Will you be including the ability to resize the EQ window within Configuration Editor? Cause as it is now, I can only zoom in and out and use scroll bars ... makes it difficult to make quick changes.

  Thanks again.

   

  - 

  - ![](_attachments/default-avatar.png)

    a
    [Jonas Thedering](https://sourceforge.net/u/jthedering/profile/) - *2015-11-01*
    [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#91c6/dc7f "Link")

    You're welcome!

    > Will you be including the ability to resize the EQ window within Configuration Editor?

    Yes, this is one of the top missing features and is mostly implemented now. I just need to decide how to store the size information so that it will be retained when the Configuration Editor is restarted.

     

    - 

&nbsp;

- ![](_attachments/default-avatar.png)

  a
  [Tracy Lee](https://sourceforge.net/u/td351/profile/) - *2015-11-22*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#ea1f "Link")

  As stated before this software is truly amazing! The level of control is unbelievable! Thank you so much.

  It's effects are simply amazing for playing locally stored music! Thanks again.

   

  \
  Last edit: Tracy Lee 2015-11-22

  - 

  - ![](_attachments/default-avatar.png)

    a
    [Jonas Thedering](https://sourceforge.net/u/jthedering/profile/) - *2015-11-22*
    [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#ea1f/01e3 "Link")

    Maybe you are mixing up two things:\
    1. E-APO can only process uncompressed audio data. Therefore, if you have a Dolby Digital bitstream that should be output directly without decoding, E-APO can not process the audio. You would need to set your software to decode the audio so that E-APO can access the uncompressed data. I know that this can be a problem, especially when using SPDIF, where only Dolby Digital Live could be used to recompress the audio after the processing by E-APO so that all channels can still be output via SPDIF. With HDMI this is less of a problem as it has the bandwidth to output multichannel uncompressed audio.\
    2. The DisableProtectedAudioDG registry entry is required by E-APO because it is an unsigned APO. Normally, APOs are supplied by the sound card driver and they are signed by WHQL, but E-APO will never get such a signature. This means that the protected audio path is broken, making some software using DRM refuse to output any sound (have seen this with the Music app when trying to play protected music). So if your software checks for the validity of the protected audio path, it is practically incompatible with E-APO.

     

    - 

&nbsp;

- ![](_attachments/default-avatar.png)

  a
  [RCB](https://sourceforge.net/u/cognus/profile/) - *2015-12-29*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#cd57 "Link")

  Is there now a known bug with build 1511 of Windows 10? With Equalizer APO engaged and preamplification +20db now the sound is unstable. oscillates erratically until I uninstall the APO's for the devices. Conexant audio, 64 bit, 8GB system RAM

   

  - 

&nbsp;

- ![](_attachments/default-avatar.png)

  a
  [Harel Mechlovich](https://sourceforge.net/u/harelme2/profile/) - *2016-01-21*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#2b93 "Link")

  hi,

  looks like the equalizer has no effect over my playback device, which is a DAC.\
  I followed the troubleshooting section and enabled enhancements for the device, but the equalizer still makes no difference..\
  any idea?

  thx!

   

  - 

  - ![](_attachments/default-avatar.png)

    a
    [Jonas Thedering](https://sourceforge.net/u/jthedering/profile/) - *2016-01-26*
    [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#2b93/14f8 "Link")

    Could you please create a thread in the [forum](https://sourceforge.net/p/equalizerapo/discussion/general/) to discuss this in more detail? Please mention your operating system and enable trace messages to try generating a log file, as [described](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#log-files) on this page.

     

    - 

&nbsp;

- ![](_attachments/user_icon)

  a
  [Rick Davis](https://sourceforge.net/u/vegasrick/profile/) - *2016-04-13*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#45c7 "Link")

  OUTSTANDING! After weeks of endless searches to find a no BS, no scam, systemwide REAL equalizer, I landed here. Thank you so much for the APO EQ.

   

  - 

&nbsp;

- ![](_attachments/user_icon%20(1))

  a
  [Glenn Odagawa](https://sourceforge.net/u/flipflops2001/profile/) - *2016-07-04*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#f8f4 "Link")

  It's like having a [LAKE Audio Processor](http://labgruppen.com/view-model/lm-series/lm-26) on your computer.

  -GSO\
  Audio Engineer 1974-present

   

  - 

  - ![](_attachments/user_icon)

    a
    [Rick Davis](https://sourceforge.net/u/vegasrick/profile/) - *2016-07-06*
    [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#f8f4/7df6 "Link")

    Once I got it to work on Windows 10 it's been perfect. Has to be one of the\
    best EQ's around.

    On Mon, Jul 4, 2016 at 9:58 AM, Glenn Odagawa [flipflops2001@users.sf.net](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:flipflops2001@users.sf.net)\
    wrote:

    > It's like having a LAKE Audio Processor\
    > [http://labgruppen.com/view-model/lm-series/lm-26](http://labgruppen.com/view-model/lm-series/lm-26) on your computer.
    >
    > -GSO\
    > Audio Engineer 1974-present
    >
    > ------------------------------------------------------------------------
    >
    > Sent from sourceforge.net because you indicated interest in\
    > [https://sourceforge.net/p/equalizerapo/wiki/Documentation/](https://sourceforge.net/p/equalizerapo/wiki/Documentation/)
    >
    > To unsubscribe from further messages, please visit\
    > [https://sourceforge.net/auth/subscriptions/](https://sourceforge.net/auth/subscriptions/)

     

    ** [alternate](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/f8f4/7df6/attachment/alternate)

    [**](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/f8f4/7df6/attachment/alternate "Download File")

    - 

&nbsp;

- ![](_attachments/default-avatar.png)

  a
  [Adam Mc](https://sourceforge.net/u/uktab/profile/) - *2016-07-08*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#95f7 "Link")

  Sorry if this has already been answered, but can I adjust the eq of my mic - i.e. reduce the treble so my voice isn't tinny when I speak to my friends on skype?\
  Thanks!

   

  1

  - 

&nbsp;

- ![](_attachments/default-avatar.png)

  a
  [Peter Verbeek](https://sourceforge.net/u/peverbeek/profile/) - *2016-07-09*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#1b1a "Link")

  Yes, you can. Select your mic device and equalize it. This can be done in the Configuration Editor or Peace GUI.

   

  - 

  - ![](_attachments/default-avatar.png)

    a
    [Adam Mc](https://sourceforge.net/u/uktab/profile/) - *2016-07-09*
    [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#1b1a/5999 "Link")

    Thank you :)

     

    - 

    - ![](_attachments/user_icon%20(1))

      a
      [Glenn Odagawa](https://sourceforge.net/u/flipflops2001/profile/) - *2016-07-09*
      [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#1b1a/5999/86f0 "Link")

      "Treble" is such a vague, nondescript word. "Tinny" even worse. From your\
      description, it may seem that the reason your voice is "tinny" is a peak in\
      the upper-midrange (2.5-6.3Khz region) either in your microphone or your\
      friend's playback system, *not* in the high frequency area (see attached\
      article on High Frequency Energy). Try inserting this line in your\
      configuration file:

      Filter (*): ON PK Fc 3000 Hz Gain -4 dB\
      Q 1\
      Filter (*): ON PK Fc 125 Hz Gain +3 dB\
      Q 0.8

      \* *Your next available filter \#, no parenthesis, after the last line in the\
      file, no blank lines inbetween.*

      You may want to use both or one or the other of these filters. You will\
      have to tweak the parameters accordingly for you and your friend's audio\
      environment.

      Also take into consideration that your mic or your friend's playback system\
      may be defective and not performing to spec.

      On Sat, Jul 9, 2016 at 3:57 AM, Adam Mc [uktab@users.sf.net](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:uktab@users.sf.net) wrote:

      > ## Thank you :)
      >
      > Sent from sourceforge.net because you indicated interest in\
      > [https://sourceforge.net/p/equalizerapo/wiki/Documentation/](https://sourceforge.net/p/equalizerapo/wiki/Documentation/)
      >
      > To unsubscribe from further messages, please visit\
      > [https://sourceforge.net/auth/subscriptions/](https://sourceforge.net/auth/subscriptions/)

      --

      *Glenn S. Odagawa*

      *Chicago, IL(872) 235-7783*

       

      - 

      - ![](_attachments/default-avatar.png)

        a
        [Adam Mc](https://sourceforge.net/u/uktab/profile/) - *2016-07-09*
        [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#1b1a/5999/86f0/f5ba "Link")

        Thanks Glenn. I have a new Skype headset and friends said straight away the sound was more tinny. I've been in the music business for about 30 years, and I'm used to speaking in non-tech terms as many new recording artists don't have any idea about frequencies - hence I talk about bass, mid and treble when explaining things generally as most of the people I work with understand what happens when they move the bass and treble controls on whatever system they use to play their recordings back.\
        I appreciate the info on the filters too.\
        Adam

         

        - 

&nbsp;

- ![](_attachments/default-avatar.png)

  a
  [Miguel Lopez](https://sourceforge.net/u/prrican/profile/) - *2016-09-14*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#d902 "Link")

  Hi, I hope I'm the right section, I just installed Equalizer apo 32 bit, I don't see the configeration editer I've installed it twice still the same thing. I am running win 7, on an older abit motherboard. What is the problem. Thank you in advance

   

  - 

  - ![](_attachments/default-avatar.png)

    a
    [Peter Verbeek](https://sourceforge.net/u/peverbeek/profile/) - *2016-09-14*
    [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#d902/9ee6 "Link")

    After installing Equalizer APO there should be Equalizer APO 1.1.2 item in the Windows start menu. Within this folder you can start the Configuration Editor. I think there isn't a desktop shortcut to it.

     

    - 

&nbsp;

- ![](_attachments/default-avatar.png)

  a
  [Robert Steel](https://sourceforge.net/u/cwl900/profile/) - *2016-10-27*
  [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#981a "Link")

  Hi,

  I am wandering, How do i Change config.exe BACK to example.exe???

  I did the change and it says that there is somthing wrong with it and i tried reinstalling it but it didn't work.

  Please Help!

  Regards\
  Robert

   

  \
  Last edit: Robert Steel 2016-10-27

  - 

  - ![](_attachments/user_icon%20(1))

    a
    [Glenn Odagawa](https://sourceforge.net/u/flipflops2001/profile/) - *2016-10-27*
    [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#981a/f9db "Link")

    There is no \[config.exe\] or \[example.exe\] in EqualizerAPO. There is\
    \[config.txt\] and \[example.txt\]. If you edit the \[(dirve):Program\
    FilesEqualizerAPOconfig.txt\] file with Notepad or any other text editor\
    it should read something like this:

    # Common preamp

    Preamp: +0 dB

    Channel: L\
    Preamp: +0 dB\
    Include: example.txt

    Channel: R\
    Preamp: +0 dB\
    Include: example.txt

    If you have modified your \[config.txt\] file, I've attached the default file\
    to this message.

    *Regards,*

    *-Glenn*

    On Wed, Oct 26, 2016 at 10:11 PM, Robert Steel [cwl900@users.sf.net](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:cwl900@users.sf.net) wrote:

    > Hi,
    >
    > I am wandering, How do i Change config.exe BACK to example.exe???
    >
    > I did the change and it says that there is somthing wrong with it and i\
    > tried reinstalling it but it didn't work.
    >
    > Regards\
    > Robert
    >
    > ------------------------------------------------------------------------
    >
    > Sent from sourceforge.net because you indicated interest in\
    > [https://sourceforge.net/p/equalizerapo/wiki/Documentation/](https://sourceforge.net/p/equalizerapo/wiki/Documentation/)
    >
    > To unsubscribe from further messages, please visit\
    > [https://sourceforge.net/auth/subscriptions/](https://sourceforge.net/auth/subscriptions/)

    --

    *Glenn S. Odagawa*

    *Chicago, IL*

    *glenn.odagawa@gmail.com [glenn.odagawa@gmail.com](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:glenn.odagawa@gmail.com)*

    *glenlivet1p@yahoo.com [glenlivet1p@yahoo.com](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:glenlivet1p@yahoo.com)*

    *http://www.TheLayeredMix.co.nf [http://www.TheLayeredMix.co.nf](http://www.thelayeredmix.co.nf/)*

    *(773) 747-7546(872) 235-7783*

     

    ** [alternate](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/981a/f9db/attachment/alternate)

    [**](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/981a/f9db/attachment/alternate "Download File")

    ** [config.txt](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/981a/f9db/attachment/config.txt)

    [**](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/981a/f9db/attachment/config.txt "Download File")

    - 

    - ![](_attachments/user_icon%20(1))

      a
      [Glenn Odagawa](https://sourceforge.net/u/flipflops2001/profile/) - *2016-10-27*
      [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#9732 "Link")

      Here's the default \[example.txt\] file also.

      On Thu, Oct 27, 2016 at 9:35 AM, Glenn Odagawa [glenn.odagawa@gmail.com](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:glenn.odagawa@gmail.com)\
      wrote:

      > There is no \[config.exe\] or \[example.exe\] in EqualizerAPO. There is\
      > \[config.txt\] and \[example.txt\]. If you edit the \[(dirve):Program\
      > FilesEqualizerAPOconfig.txt\] file with Notepad or any other text editor\
      > it should read something like this:
      >
      > # Common preamp
      >
      > Preamp: +0 dB
      >
      > Channel: L\
      > Preamp: +0 dB\
      > Include: example.txt
      >
      > Channel: R\
      > Preamp: +0 dB\
      > Include: example.txt
      >
      > If you have modified your \[config.txt\] file, I've attached the default\
      > file to this message.
      >
      > *Regards,*
      >
      > *-Glenn*
      >
      > On Wed, Oct 26, 2016 at 10:11 PM, Robert Steel [cwl900@users.sf.net](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:cwl900@users.sf.net)\
      > wrote:
      >
      > > Hi,
      > >
      > > I am wandering, How do i Change config.exe BACK to example.exe???
      > >
      > > I did the change and it says that there is somthing wrong with it and i\
      > > tried reinstalling it but it didn't work.
      > >
      > > Regards\
      > > Robert
      > >
      > > ------------------------------------------------------------------------
      > >
      > > Sent from sourceforge.net because you indicated interest in\
      > > [https://sourceforge.net/p/equalizerapo/wiki/Documentation/](https://sourceforge.net/p/equalizerapo/wiki/Documentation/)
      > >
      > > To unsubscribe from further messages, please visit\
      > > [https://sourceforge.net/auth/subscriptions/](https://sourceforge.net/auth/subscriptions/)
      >
      > --
      >
      > *Glenn S. Odagawa*
      >
      > *Chicago, IL*
      >
      > *glenn.odagawa@gmail.com [glenn.odagawa@gmail.com](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:glenn.odagawa@gmail.com)*
      >
      > *glenlivet1p@yahoo.com [glenlivet1p@yahoo.com](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:glenlivet1p@yahoo.com)*
      >
      > *http://www.TheLayeredMix.co.nf [http://www.TheLayeredMix.co.nf](http://www.thelayeredmix.co.nf/)*
      >
      > *(773) 747-7546 \<%28773%29%20747-7546\>(872) 235-7783\
      > \<%28872%29%20235-7783\>*

      --

      *Glenn S. Odagawa*

      *Chicago, IL*

      *glenn.odagawa@gmail.com [glenn.odagawa@gmail.com](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:glenn.odagawa@gmail.com)*

      *glenlivet1p@yahoo.com [glenlivet1p@yahoo.com](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:glenlivet1p@yahoo.com)*

      *http://www.TheLayeredMix.co.nf [http://www.TheLayeredMix.co.nf](http://www.thelayeredmix.co.nf/)*

      *(773) 747-7546(872) 235-7783*

       

      ** [alternate](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/9732/attachment/alternate)

      [**](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/9732/attachment/alternate "Download File")

      ** [example.txt](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/9732/attachment/example.txt)

      [**](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/9732/attachment/example.txt "Download File")

      - 

      - ![](_attachments/default-avatar.png)

        a
        [Robert Steel](https://sourceforge.net/u/cwl900/profile/) - *2016-10-27*
        [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#9732/27dd "Link")

        Thanks

        On Friday, 28 October 2016, Glenn Odagawa [flipflops2001@users.sf.net](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:flipflops2001@users.sf.net)\
        wrote:

        > Here's the default \[example.txt\] file also.
        >
        > On Thu, Oct 27, 2016 at 9:35 AM, Glenn Odagawa glenn.odagawa@gmail.com\
        > [javascript:\_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');)\
        > wrote:
        >
        > There is no \[config.exe\] or \[example.exe\] in EqualizerAPO. There is\
        > \[config.txt\] and \[example.txt\]. If you edit the \[(dirve):Program\
        > FilesEqualizerAPOconfig.txt\] file with Notepad or any other text editor\
        > it should read something like this:\
        > Common preamp
        >
        > Preamp: +0 dB
        >
        > Channel: L\
        > Preamp: +0 dB\
        > Include: example.txt
        >
        > Channel: R\
        > Preamp: +0 dB\
        > Include: example.txt
        >
        > If you have modified your \[config.txt\] file, I've attached the default\
        > file to this message.
        >
        > *Regards,*
        >
        > *-Glenn*
        >
        > On Wed, Oct 26, 2016 at 10:11 PM, Robert Steel cwl900@users.sf.net\
        > [javascript:\_e(%7B%7D,'cvml','cwl900@users.sf.net');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','cwl900@users.sf.net');)\
        > wrote:
        >
        > Hi,
        >
        > I am wandering, How do i Change config.exe BACK to example.exe???
        >
        > I did the change and it says that there is somthing wrong with it and i\
        > tried reinstalling it but it didn't work.
        >
        > Regards\
        > Robert
        >
        > ------------------------------------------------------------------------
        >
        > Sent from sourceforge.net because you indicated interest in\
        > [https://sourceforge.net/p/equalizerapo/wiki/Documentation/](https://sourceforge.net/p/equalizerapo/wiki/Documentation/)
        >
        > To unsubscribe from further messages, please visit\
        > [https://sourceforge.net/auth/subscriptions/](https://sourceforge.net/auth/subscriptions/)
        >
        > --
        >
        > *Glenn S. Odagawa*
        >
        > *Chicago, IL*
        >
        > *glenn.odagawa@gmail.com\
        > [javascript:\_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');)\
        > glenn.odagawa@gmail.com\
        > [javascript:\_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');)*
        >
        > *glenlivet1p@yahoo.com\
        > [javascript:\_e(%7B%7D,'cvml','glenlivet1p@yahoo.com');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','glenlivet1p@yahoo.com');)\
        > glenlivet1p@yahoo.com\
        > [javascript:\_e(%7B%7D,'cvml','glenlivet1p@yahoo.com');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','glenlivet1p@yahoo.com');)*
        >
        > *http://www.TheLayeredMix.co.nf [http://www.TheLayeredMix.co.nf](http://www.thelayeredmix.co.nf/)\
        > [](http://www.thelayeredmix.co.nf/)[http://www.TheLayeredMix.co.nf](http://www.thelayeredmix.co.nf/) [http://www.TheLayeredMix.co.nf](http://www.thelayeredmix.co.nf/)*
        >
        > *(773) 747-7546 \<%28773%29%20747-7546\>(872) 235-7783\
        > \<%28872%29%20235-7783\>*
        >
        > --
        >
        > *Glenn S. Odagawa*
        >
        > *Chicago, IL*
        >
        > *glenn.odagawa@gmail.com\
        > [javascript:\_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');)\
        > glenn.odagawa@gmail.com\
        > [javascript:\_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','glenn.odagawa@gmail.com');)*
        >
        > *glenlivet1p@yahoo.com\
        > [javascript:\_e(%7B%7D,'cvml','glenlivet1p@yahoo.com');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','glenlivet1p@yahoo.com');)\
        > glenlivet1p@yahoo.com\
        > [javascript:\_e(%7B%7D,'cvml','glenlivet1p@yahoo.com');](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:javascript:_e(%7B%7D,'cvml','glenlivet1p@yahoo.com');)*
        >
        > *http://www.TheLayeredMix.co.nf [http://www.TheLayeredMix.co.nf](http://www.thelayeredmix.co.nf/)\
        > [](http://www.thelayeredmix.co.nf/)[http://www.TheLayeredMix.co.nf](http://www.thelayeredmix.co.nf/) [http://www.TheLayeredMix.co.nf](http://www.thelayeredmix.co.nf/)*
        >
        > ## *(773) 747-7546(872) 235-7783*
        >
        > Sent from sourceforge.net because you indicated interest in\
        > [https://sourceforge.net/p/equalizerapo/wiki/Documentation/](https://sourceforge.net/p/equalizerapo/wiki/Documentation/)
        >
        > To unsubscribe from further messages, please visit\
        > [https://sourceforge.net/auth/subscriptions/](https://sourceforge.net/auth/subscriptions/)

         

        ** [alternate](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/9732/27dd/attachment/alternate)

        [**](https://sourceforge.net/p/equalizerapo/wiki/_discuss/thread/e30e9265/9732/27dd/attachment/alternate "Download File")

        - 

  - ![](_attachments/user_icon)

    a
    [Rick Davis](https://sourceforge.net/u/vegasrick/profile/) - *2016-10-27*
    [**](https://sourceforge.net/p/equalizerapo/wiki/Documentation/#981a/a79b "Link")

    It should be .. example.txt

    On Wed, Oct 26, 2016 at 8:11 PM, Robert Steel [cwl900@users.sf.net](https://sourceforge.net/p/equalizerapo/wiki/Documentation/mailto:cwl900@users.sf.net) wrote:

    > Hi,
    >
    > I am wandering, How do i Change config.exe BACK to example.exe???
    >
    > I did the change and it says that there is somthing wrong with it and i\
    > tried reinstalling it but it didn't work.
    >
    > Regards\
    > Robert
    >
    > ------------------------------------------------------------------------
    >
    > Sent from sourceforge.net because you indicated interest in\
    > [https://sourceforge.net/p/equalizerapo/wiki/Documentation/](https://sourceforge.net/p/equalizerapo/wiki/Documentation/)
    >
    > To unsubscribe from further messages, please visit\
    > [https://sourceforge.net/auth/subscriptions/](https://sourceforge.net/auth/subscriptions/)

     

    - 

1 [2](https://sourceforge.net/p/equalizerapo/wiki/Documentation/?page=1) [\>](https://sourceforge.net/p/equalizerapo/wiki/Documentation/?page=1) [\>\>](https://sourceforge.net/p/equalizerapo/wiki/Documentation/?page=1) (Page 1 of 2)

\

## See also

- [[Software Development]]
