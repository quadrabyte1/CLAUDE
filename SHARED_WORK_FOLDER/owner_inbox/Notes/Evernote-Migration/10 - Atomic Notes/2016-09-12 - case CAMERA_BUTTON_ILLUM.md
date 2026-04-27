---
title: 'case CAMERA_BUTTON_ILLUM:'
uid: 20160912T2351
created: '2016-09-12'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes4
tags:
- jira-notes
aliases: []
---

Monday, September 12, 2016

4:51 PM

                case CAMERA_BUTTON_ILLUM: 

                    // On off toggle as long as camera is not on an arm.  

     

                   

                   

                    if(GetIlluminatorStatus() == ILLUM_MODE_OFF)                        // if the light is presently OFF

                    {

                        SetIlluminatorMode(ILLUM_MODE_ON_WHITE_LIGHT);                  // turn it on, irrespective of camera mount status

                    }

                    else                                                                // else the light is presently ON

                    {

                        if(CameraIsInstalledOnUsm())                                    // and if the camera is mounted

                        {

                            sudb_set_key_trig(comms.mid, SUDB_KEY_ILLEGAL_EVT_TRIG, 0); // requesting a change to OFF while mounted is illegal

                            sudb_publish(comms.mid);

                        }

                        else                                                            // else the camera is not mounted (and the light is ON)

                        {

                            SetIlluminatorMode(ILLUM_MODE_OFF);                         // it is legal to turn it off

                        }

                    }

                   

          

in core.cpp function CameraHeadBtnPressHandler()

 

 

     case CAMERA_BUTTON_MENU:  

                    if( CameraOffArm())// Off Arm - Swap on the longs too.

                    {     

                        if(scopeDir_OnArm == SCOPE_DIR_UP_ID)       // if the camera is in the UP direction

                        {

                            scopeDir_OnArm = SCOPE_DIR_DOWN_ID;       // change it to DOWN direction

                            SupervisorDebug(DEBUG_FULL, "CAMERA_BUTTON_MENU -- swap camera up/down mode to DOWN");

                        }

                        else                                        // else the camera is in the DOWN direction

                        {

                            scopeDir_OnArm = SCOPE_DIR_UP_ID;       // change it to UP direction

                            SupervisorDebug(DEBUG_FULL, "CAMERA_BUTTON_MENU -- swap camera up/down mode to UP");

                        }

                        UpdateScopeDir();

 

 

                        //ToggleLREye();

                    }

                    else

                    {                            

                        sudb_set_key_trig(comms.mid, SUDB_KEY_ILLEGAL_EVT_TRIG, 0);

                        sudb_publish(comms.mid);

                    }     

                    break;

 

Created with Microsoft OneNote 2010

One place for all your notes and information
