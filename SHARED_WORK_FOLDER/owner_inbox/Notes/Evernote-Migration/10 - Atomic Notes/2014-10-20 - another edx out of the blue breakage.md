---
title: another edx out of the blue breakage
uid: 20141020T2102
created: '2014-10-20'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes4
tags: []
aliases: []
---

**if this failure:**

OperationFailure at /course/

command SON(\[('authenticate', 1), ('user', u'edxapp'), ('nonce', u'5b6fe141c0f3ef09'), ('key', u'448fe0b40c575883808750134612ca27')\]) failed: auth fails

Request Method: GET

Request URL: [http://localhost:8001/course/](http://localhost:8001/course/)

Django Version: 1.4.14

Exception Type: OperationFailure

Exception Value:

command SON(\[('authenticate', 1), ('user', u'edxapp'), ('nonce', u'5b6fe141c0f3ef09'), ('key', u'448fe0b40c575883808750134612ca27')\]) failed: auth fails

Exception Location: /edx/app/edxapp/venvs/edxapp/local/lib/python2.7/site-packages/pymongo/helpers.py in \_check_command_response, line 178

Python Executable: /edx/app/edxapp/venvs/edxapp/bin/python

\

**try these commands:**

vagrant ssh 

cd /edx/app/edx_ansible/edx_ansible/playbooks

sudo /edx/app/edx_ansible/venvs/edx_ansible/bin/ansible-playbook -i localhost, -c local run_role.yml -e 'role=mongo' -e 'mongo_create_users=True'

## See also

- [[Software Development]]
