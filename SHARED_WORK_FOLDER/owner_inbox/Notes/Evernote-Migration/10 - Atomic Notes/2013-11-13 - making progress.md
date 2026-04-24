---
title: making progress
uid: 20131113T1919
created: '2013-11-13'
updated: '2024-04-01'
source: evernote
original_notebook: My Notes5
tags:
- edx
aliases: []
---

Found the place where the ‘Will Be Released” label is set/unset:  /Users/trbm/edx_all/edx-platform/cms/templates/overview.html

Found unpublish call:

\

@login_required

@expect_json

def unpublish_unit(request):

    "Unpublish a unit"

    location = request.POST\['id'\]

\

    print "unpublish_unit"

    import pdb; pdb.set_trace()

\

    \# check permissions for this user within this course

    if not has_access(request.user, location):

        raise PermissionDenied()

\

    item = modulestore().get_item(location)

    \_xmodule_recurse(item, lambda i: modulestore().unpublish(i.location))

\

    return HttpResponse()

\

looks like the publish and unpublish operations are recursive such that all descendants are set the same

\

found the mongo code to unpublish: convert_to_draft()

\

image files are stored: cmd/static/img

\

found in units.html a mechanism that goes through child units of a subsection and computes some stuff — useful

and here’s a function to return draft/public/private status: compute_unit_state( unit ) in utils.py

\

            \<%

            print "========================================="

            print " "

            print "Rendering overview.html -- Sections"

            %\>

\

\

            print "========================================="

            print " "

            print "Rendering overview.html -- Section"

           

\

\

\

\

\

            foundPrivate = 0            \# counts the number of private units

            foundPublic = 0             \# counts the number of public units

            foundUnits = 0              \# counts the total number of units

            for child in section.get_children():

              print "   Subsection '", child.display_name, child.position

\

              for unit in child.get_children():

                unit_state = compute_unit_state(unit)

                print "         Unit     '", unit.display_name, unit.position, "    ", unit_state

\

                if( foundPublic == foundUnits ):

                    print "Section '", section.display_name, "' status: All PUBLIC"

                else:

                    if( foundPrivate == foundUnits ):

                        print "Section '", section.display_name, "' status: All PRIVATE"

                    else:

                        print "Section '", section.display_name, "' status: Mixed Public and Private" 

\

\

\

\

\

            if( foundPublic == foundUnits ):

                print "Section '", section.display_name, "' status: All PUBLIC"

            else:

                if( foundPrivate == foundUnits ):

                    print "Section '", section.display_name, "' status: All PRIVATE"

                else:

                    print "Section '", section.display_name, "' status: Mixed Public and Private"

            

\

\

\

\

\

\

\

\

 \<%

            print "========================================="

            print " "

            print "Rendering overview.html -- Sections"

            %\>

\

\

\

\

\

          % for section in sections:

\

            \<%

\

            foundPrivate = 0            \# counts the number of private units

            foundDraft = 0              \# counts the number of draft units

            foundPublic = 0             \# counts the number of public units

            foundUnits = 0              \# counts the total number of units

            for child in section.get_children():

              print "   Subsection '", child.display_name, child.position

\

              foundPrivateSubsection = 0            \# counts the number of private units in this subsection

              foundDraftSubsection = 0              \# counts the number of draft units in this subsection

              foundPublicSubsection = 0             \# counts the number of public units in this subsection

              foundUnitsSubsection = 0              \# counts the total number of units in this subsection

              for unit in child.get_children():

                unit_state = compute_unit_state(unit)

                print "         Unit     '", unit.display_name, unit.position, "    ", unit_state

\

                foundUnits++

                foundUnitsSubsection++

\

                switch( unit_state )

                    case "public":

                        print "(public)"

                        break

\

                    case "private":

                        print "(private)"

                        break

\

                if( unit_state == "public"):

                    foundPublic++

                    foundPublicSubsection++

\

                if( unit_state == "private"):

                    foundPublic++

                    foundPublicSubsection++

\

            if( foundPublic == foundUnits ):

                print "Section '", section.display_name, "' status: All PUBLIC"

            else:

                if( foundPrivate == foundUnits ):

                    print "Section '", section.display_name, "' status: All PRIVATE"

                else:

                    print "Section '", section.display_name, "' status: Mixed Public and Private"

\

\

            %\>

\

\

\

\

\
