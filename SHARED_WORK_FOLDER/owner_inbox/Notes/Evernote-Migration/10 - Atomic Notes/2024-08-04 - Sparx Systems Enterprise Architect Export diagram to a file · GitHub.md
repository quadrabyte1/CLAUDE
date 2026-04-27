---
title: 'Sparx Systems Enterprise Architect: Export diagram to a file · GitHub'
uid: 20240804T1404
created: '2024-08-04'
updated: '2026-04-27'
source: evernote
original_notebook: My Notes2
tags: []
aliases: []
source_url: https://gist.github.com/ssproessig/113053c4f8d4f11245d0
---

![](data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iVmN2WnIgdHZmVV8iIHZpZXdib3g9IjAgMCAyNCAyNCI+PHVzZSB4bGluazpocmVmPSIjaDJJaHYiIC8+PC9zdmc+)

Web Clip

\

|  |  |
|---:|----|
| 1 | using System; |
| 2 |  |
| 3 |  |
| 4 | namespace ea_export_diagram |
| 5 | { |
| 6 | class Program |
| 7 | { |
| 8 | static int Main() |
| 9 | { |
| 10 | // ...should be taken from command-line arguments btw... |
| 11 | // connection string or local file |
| 12 | const string filePath = @"E:Repo.eap"; |
| 13 | // credentials in case of login required |
| 14 | const string user = ""; |
| 15 | const string password = ""; |
| 16 | // GUID of the diagram to export; to get it in EA: |
| 17 | // 1. Project Explorer, Right click the diagram |
| 18 | // 2. Copy Reference, as GUID to clipboard |
| 19 | const string guid = "{9FA8B4A3-1133-4ba4-8F62-084AEE8B3C7D}"; |
| 20 | // target file |
| 21 | const string targetFile = @"E:exported.png"; |
| 22 | // refer to http://www.sparxsystems.com/enterprise_architect_user_guide/9.3/automation/project_2.html |
| 23 | // under: PutDiagramImageToFile |
| 24 | const int DIAGRAM_SAVE_AS_DERIVED_FROM_EXT = 1; |
| 25 |  |
| 26 | // try acquiring the automation interface |
| 27 | EA.Repository r; |
| 28 | try |
| 29 | { |
| 30 | // open the repository |
| 31 | r = new EA.Repository(); |
| 32 | } |
| 33 | catch (Exception ex) |
| 34 | { |
| 35 | Console.Error.WriteLine("Acquiring the EA automation interface failed\!"); |
| 36 | return 1; |
| 37 | } |
| 38 |  |
| 39 | // OpenFile2 can open repositories from Databases |
| 40 | if (r.OpenFile2(filePath, user, password) == false) |
| 41 | { |
| 42 | Console.Error.WriteLine("Unable to open file\!"); |
| 43 | return 2; |
| 44 | } |
| 45 |  |
| 46 | // find the diagram |
| 47 | var e = r.GetDiagramByGuid(guid); |
| 48 | var d = e as EA.Diagram; |
| 49 | if (d == null) |
| 50 | { |
| 51 | Console.Error.WriteLine("GUID {0} is no diagram\!", guid); |
| 52 | return 3; |
| 53 | } |
| 54 |  |
| 55 | // get the project interface |
| 56 | var p = r.GetProjectInterface(); |
| 57 |  |
| 58 | // store the diagram as image |
| 59 | var res = p.PutDiagramImageToFile(guid, targetFile, DIAGRAM_SAVE_AS_DERIVED_FROM_EXT); |
| 60 |  |
| 61 | if (!res) |
| 62 | { |
| 63 | Console.Error.WriteLine("Unable to write {0} to {1}", guid, targetFile); |
| 64 | } |
| 65 |  |
| 66 | Console.WriteLine("Successfully wrote {0} to {1}", guid, targetFile); |
| 67 | return 0; |
| 68 | } |
| 69 | } |
| 70 | } |

\

## See also

- [[Enterprise Architect]]
- [[Software Development]]
