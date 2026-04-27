---
title: ErrorProvider
uid: 20121001T1950
created: '2012-10-01'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes4
tags:
- software
aliases: []
source_url: http://developingfor.net/2008/01/17/a-good-practical-linq-example/
---

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIiIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjMmlPRzUiIC8+PC9zdmc+)

HTML Content

## A Good, practical LINQ example

January 17, 2008[joelcochran](http://developingfor.net/author/joelcochran/ "Posts by joelcochran")[Leave a comment](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#respond)[Go to comments](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comments)

You may recall that one of my [New Year’s Resolutions](http://www.developingfor.net/miscellaneous/back-from-vacation.html "New Year's Resolutions") was to find and participate in a .NET Forum. Well, I have joined several, and have even posted a few times. While perusing the C# Corner forums today, I found [this post](http://www.c-sharpcorner.com/Forums/ShowMessages.aspx?ThreadID=37288 "C# Corner Forum Post") about not being able to break out of a loop. The code was using one of my favorite techniques for Windows Forms, the ErrorProvider. I like ErrorProvider and use it quite a bit, and I have done what the poster was trying to do many times: loop through the Controls on a Form and find out whether any of them have an active error message. If they do, then I use that information to warn the user or set some Form state so that it is apparent that an error exists.

My answer does not specifically address the issue the poster brought to the table, but the post got me to thinking: we should be able to use LINQ to solve this problem. Here is a typical example of the loop construct:

```
bool hasErrors = false;
foreach (Control c in this.Controls)
{
    if (!"".Equals(errorProvider1.GetError(c)))
    {
        hasErrors = true;
        break;
    }
}
```

In looking at this, it appears we have a good case for using LINQ: we have a Collection and we want to query that Collection for information about itself. Seems it should be pretty straightforward, and ultimately it is, but in this particular case it took a little trial and error to hack it out. Since it wasn’t as simple as I originally thought it would be, let’s walk through it in stages.

**Build a Queryable Object**

The first step is to try and build a LINQ query of all the Controls on the Form:

```
var q = from c in this.Controls
        select c;
```

When I tried to compile this, I got an error I did not expect:

*Could not find an implementation of the query pattern for source type ‘System.Windows.Forms.Control.ControlCollection’. ‘Select’ not found. Consider explicitly specifying the type of the range variable ‘c’.*

Naturally, I reexamined the code and couldn’t find anything odd about it, but what did seem odd was that I knew *this.Controls* was a Collection, and LINQ is supposed to work on Collections, right? Wrong!

**Getting a Sequence from a Collection**

If you read my recent [LINQ to Objects](http://www.developingfor.net/c-30/upgrade-your-c-skills-part-4-linq-to-objects.html "LINQ to Objects") post you may recall that LINQ does not work on Collections, but rather **Sequences**. It soon dawned on me that [ControlCollection](http://msdn2.microsoft.com/en-us/library/system.windows.forms.control.controlcollection.aspx "MSDN Documentation - ControlCollection") does not qualify as a Sequence because it does not implement *IEnumerable\<T\>*, but rather*IEnumerable*. This led me to uncharted territory: how do I get an *IEnumerable\<T\>* from an*IEnumerable*? Well, there was definitely some trial and error, and a lot of IntelliSense browsing, but I finally figured out an elegant solution.

Microsoft was gracious enough to provide an *IEnumerable* extension method ([my favorite new feature](http://www.developingfor.net/c-30/upgrade-your-c-skills-part-1-extension-methods.html "Extension Methods")) that will cast an *IEnumerable* to an *IEnumerable\<T\>*. Fittingly, this method is named*Cast\<T\>()*. Here is the code that will transform our *ControlCollection* into a usable Sequence:

```
var q = from c in this.Controls.Cast<Control>()
        select c;
```

Now we have a LINQ query object representing all the Controls on our Form.

**Querying the Queryable Object**

Now that we have a Sequence instead of a Collection to work with, this could come in quite handy. In fact, this would be a good candidate for a *ControlCollection* Extension Method in its own right. In the meantime, now that we have a queryable object, we have several options for how to complete our task. One way is to query the entire Sequence when we need it. I’m going to use our friend the Lambda Expression to find out if there are any Controls with Errors in the errorProvider:

```
// Query as needed
MessageBox.Show(q.Count(c => !"".Equals(errorProvider1.GetError(c))) > 0 ? "There are errors!" : "No errors!");
```

Again we are using a supplied Extension Method called *Count\<\>()* and passing it a *Func\<\>*defined by our Lambda Expression. If the count is greater than 0, then we have errors, else we do not.

This approach is especially handy if you may need to query the list in multiple ways. In our case, however, we know that this criteria is the only one we will need, so we have the option to embed our Lambda in the LINQ statement itself. To do so, we will use yet another Extension Method called *Where*:

```
var q = from c in this.Controls.Cast<Control>()
        .Where(c => !"".Equals(errorProvider1.GetError(c)))
        select c;
```

You’ll notice that this is the same logic just implemented as part of the LINQ statement. Now our consuming code is a bit simpler because our list is defined as only the items with messages in the ErrorProvider:

```
// Now we don't need the Lambda
MessageBox.Show(q.Count() > 0 ? "There are errors!" : "No errors!");
```

Here is the complete code block:

```
var q = from c in this.Controls.Cast<Control>()
        .Where(c => !"".Equals(errorProvider1.GetError(c)))
        select c;
MessageBox.Show(q.Count() > 0 ? "There are errors!" : "No errors!");
```

Hopefully, as you experiment with these new features, you will come to appreciate how they all complement each other. This example turns out to be fairly simple, even though it took a little effort to work through. In it, we have taken advantage of Extension Methods, LINQ, and Lambda Expressions because they all work together. While these are all great additions on their own, the cumulative power they represent is outstanding. I guess .NET really is worth more than the sum of its parts.

[About these ads](http://en.wordpress.com/about-these-ads/)

### Share this:

- [Twitter](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?share=twitter&amp;nb=1 "Click to share on Twitter")
- [Facebook](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?share=facebook&amp;nb=1 "Share on Facebook")

### Like this:

[Like](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?like=1&amp;_wpnonce=588a661b50 "I like this.")

Be the first to like this.

Categories:[.NET 3.5](http://developingfor.net/category/net-35/ "View all posts in .NET 3.5"), [C# 3.0](http://developingfor.net/category/c-30/ "View all posts in C# 3.0"), [Lambda Expressions](http://developingfor.net/category/lambda-expressions/ "View all posts in Lambda Expressions"), [LINQ](http://developingfor.net/category/linq/ "View all posts in LINQ")

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIiIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjMmlPRzUiIC8+PC9zdmc+)

HTML Content

Comments (13)Trackbacks (1)[Leave a comment](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#respond)[Trackback](http://developingfor.net/2008/01/17/a-good-practical-linq-example/trackback/)

1.  ![](http://0.gravatar.com/avatar/674c3b35d0757194ac7f067c8871a4a0?s=32&amp;d=identicon&amp;r=G)

    Ben

    June 16, 2008 at 8:05 pm \| [\#1](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-164)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=164#respond) \| Quote

    Hi,

    How can I do it in vb.net. It seems that there is no equivalent casting like c#. I tried with CType and DirectCast with no success.

    Thanks a lot,

    Ben

2.  ![](http://2.gravatar.com/avatar/e7c09cd2300e9e4928a25c41825ad2b1?s=32&amp;d=identicon&amp;r=G)

    [Joel](http://www.developingfor.net/)

    June 17, 2008 at 8:27 am \| [\#2](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-165)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=165#respond) \| Quote

    Hmmm… isn’t the Controls.Cast method available in VB.Net? It would seem to me that this should be .Net and not language specific.

3.  ![](http://0.gravatar.com/avatar/674c3b35d0757194ac7f067c8871a4a0?s=32&amp;d=identicon&amp;r=G)

    Ben

    June 17, 2008 at 8:54 am \| [\#3](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-166)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=166#respond) \| Quote

    I tried differents fashions and I have always an error “expression expected” after the controls.Cast. It’s the reason why I suspect Vb.Net to support the casting differently.

4.  ![](http://1.gravatar.com/avatar/a495213f7744ddf1e5a33000d4c333c6?s=32&amp;d=identicon&amp;r=G)

    Matthew

    June 19, 2008 at 10:41 am \| [\#4](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-167)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=167#respond) \| Quote

    Dim query = from c As Control in Me.Controls

    might just do the trick

5.  ![](http://1.gravatar.com/avatar/1b36cb10303144f08b08e5b2152094d8?s=32&amp;d=identicon&amp;r=G)

    Chato

    July 24, 2008 at 12:43 pm \| [\#5](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-168)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=168#respond) \| Quote

    Hey Ben I think linqhelp.com has a solution to your Control.cast problem. Try searching over there. Nice read btw!

6.  ![](http://1.gravatar.com/avatar/75e257760a0904be5256bd8a36527a01?s=32&amp;d=identicon&amp;r=G)

    Greg

    July 30, 2008 at 4:14 pm \| [\#6](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-169)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=169#respond) \| Quote

    Actually, Ben’s query can use the typical LINQ query using type inference for the range variable and it will work just fine. For example:

    Dim query = \_\
    From c in Controls \_\
    Where TypeOf c Is TextBox \_\
    Select c

    will select all the TextBoxes in the Controls collection. For some reason, VB does not place the same restriction on querying the Controls collection as C# does.

7.  ![](http://0.gravatar.com/avatar/0503492f1cc60e41f25a20188a63d60a?s=32&amp;d=identicon&amp;r=G)

    [vipin cherukara](http://vipinc007.blogspot.com/)

    June 16, 2009 at 10:38 pm \| [\#7](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-170)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=170#respond) \| Quote

    More abount LINQ visit

    [http://vipinc007.blogspot.com/2009/03/linq-examples.html](http://vipinc007.blogspot.com/2009/03/linq-examples.html)

    for Dot net articles visit\
    [http://dot-net-factory.blogspot.com](http://dot-net-factory.blogspot.com/)

8.  ![](http://0.gravatar.com/avatar/cc7af1fa2b5ce0c30a27a58252e86cb1?s=32&amp;d=identicon&amp;r=G)

    [More Article](http://www.7fasst.com/)

    January 28, 2010 at 4:01 am \| [\#8](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-171)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=171#respond) \| Quote

    Thank You for Helpful

9.  ![](http://2.gravatar.com/avatar/b8b76c6b590415cf4e0408b7c490660a?s=32&amp;d=identicon&amp;r=G)

    [Sergey Malyan](http://sergeymalyan.blogspot.com/)

    April 6, 2010 at 8:04 pm \| [\#9](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-172)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=172#respond) \| Quote

    “foreach” is doomed.

10. ![](http://0.gravatar.com/avatar/f620f4647fb816073c9152a284245e64?s=32&amp;d=identicon&amp;r=G)

    Fab

    May 19, 2010 at 6:52 am \| [\#10](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-173)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=173#respond) \| Quote

    I thinks the following works too:

    var q = from Control c in this.Controls\
    select c;

11. ![](http://2.gravatar.com/avatar/2fa2beead30e11e296bba42266524fd4?s=32&amp;d=identicon&amp;r=G)

    Eklavya Gupta

    July 7, 2010 at 2:05 am \| [\#11](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-174)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=174#respond) \| Quote

    Cool! Thanks for the post. Was very useful.

12. ![](http://2.gravatar.com/avatar/5d902cbbc4ad3e88710e151d1b2ce8b5?s=32&amp;d=identicon&amp;r=G)

    [c programming](http://pickatutorial.com/)

    December 11, 2010 at 11:47 am \| [\#12](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-175)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=175#respond) \| Quote

    Good work. Keep it up. Well explained.

13. ![](http://0.gravatar.com/avatar/3f009d72559f51e7e454b16e5d0687a1?s=32&amp;d=identicon&amp;r=G)

    Dharmesh Barochia

    January 10, 2011 at 3:54 am \| [\#13](http://developingfor.net/2008/01/17/a-good-practical-linq-example/#comment-176)

    [Reply](http://developingfor.net/2008/01/17/a-good-practical-linq-example/?replytocom=176#respond) \| Quote

    I found one more reference site for LINQ and LAMBDA example.

    [http://webmingle.blogspot.com/2010_09_01_archive.html](http://webmingle.blogspot.com/2010_09_01_archive.html)

### Leave a Reply

## See also

- [[Software Development]]
