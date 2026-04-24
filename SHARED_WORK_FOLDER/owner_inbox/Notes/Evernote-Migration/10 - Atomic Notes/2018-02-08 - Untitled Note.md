---
title: Untitled Note
uid: 20180208T1929
created: '2018-02-08'
updated: '2024-04-02'
source: evernote
original_notebook: My Notes3
tags:
- git
aliases: []
---

\## Git

\

\# Initialize

git clone project1

cd project1

\

\# Start some work

git checkout -b branchname

\

\# Hack and request review

git commit

git push origin HEAD:refs/for/master

\

\# Incorporate feedback and request another review

git commit --amend

git push origin HEAD:refs/for/master

\

\# Incorporate feedback and request another review

git commit --amend

git push origin HEAD:refs/for/master

\

\# Submitted! Resync and clean up

git checkout master

git pull

git branch -D branchname

\
