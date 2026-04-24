---
title: translucent/transparent panel
uid: 20150422T1858
created: '2015-04-22'
updated: '2024-04-02'
source: evernote
original_notebook: My Notes3
tags: []
aliases: []
---

\

public class TransparentPanel : Panel

{

protected override CreateParams CreateParams

{

get {

CreateParams cp = base.CreateParams;

cp.ExStyle \|= 0x00000020; // WS_EX_TRANSPARENT

return cp;

}

}

protected override void OnPaintBackground(PaintEventArgs e)

{

//base.OnPaintBackground(e);

}

}

\

\

\
