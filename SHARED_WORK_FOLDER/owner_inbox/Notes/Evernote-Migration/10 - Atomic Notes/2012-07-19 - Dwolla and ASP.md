---
title: Dwolla and ASP
uid: 20120719T0223
created: '2012-07-19'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes5
tags: []
aliases: []
source_url: https://github.com/coreyjonoliver/dwolla-sdk-dotnet
---

Dwolla and ASP 

- ☐

  here's a note I found:

> ## Usage

> Instantiate an instance of the `DwollaClient` class assigning your Dwolla application key and secret to the `ClientIdentifier` and `ClientSecret` instance variables respectively:
>
> `private static readonly DwollaClient client = new DwollaClient`
>
> `{`
>
> `ClientIdentifier = "hHLYjMVBBtl12+VKnzcFzCgXGO1lcjLARO7cJIQ8sEyCtzJaAT",`
>
> `ClientSecret = "HGJj2gbwCZuM4r3+4gbIEHfeJHfDebVmVOgfHBuRaWhO6XaEkL",`
>
> `};`
>
> Create a variable of type `IAuthorizationState` which will store the authorization response from Dwolla. If successful, it will store the access token; `null` otherwise:
>
> `IAuthorizationState authorization = client.ProcessUserAuthorization();`
>
> Now you must request for user authorization from Dwolla while indicating the scope needed by any api calls you will make:
>
> `client.RequestUserAuthorization(new Scope[] { Scope.REQUEST });`
>
> If authorized by the user, you can now perform any desired set of actions allowed by the scope(s) you indicated above:
>
> `var request = client.Request(authorization.AccessToken, 1111, "812-111-1111", 1, UserType.DWOLLA, null, "Test");`

> \

\

- ☐

  Here i created a quick personal token for my  account:

  Sometimes, you just need an access token to your own account, without going through the hassle of creating an entire OAuth flow. We hear ya. That's why we created this page that lets you generate a never-expiring token to your own Dwolla account. We generally recommend using this token in testing environments only.

> Great! Now, here's your token:
>
> **Y1rUYtYCbZDD3uXPJktAzZKE1COtrCju+zPZvtFndQ/TbeX25v**
>
> \
>
> \

- ☐

  **Problem is, i don't know how to use it....**

  **I sent a support email to Dwolla: how do i find these?created an application and got this (see the email from Michael Schonfeld at Dwolla):**

  **[Prank2](http://pwrpointz.com/) Verified**

  **OAuth Callback**

  \

  **Payment Callback**

  \

  **Payment Redirect**

  \

  **Key**

  \

  **6eX5nEUh1dwT2Q52wUFyJiL+i4jlrJhdUzYZP6X94iNh5ckwBr**

  \

  **Secret**

  \

  **/IQCTyhvKK6IFGtSNtzyYLwBsiWeXkoAkSiruTGUWw8v3RHL+F**

  \

  \

  \

## See also

- [[Software Development]]
