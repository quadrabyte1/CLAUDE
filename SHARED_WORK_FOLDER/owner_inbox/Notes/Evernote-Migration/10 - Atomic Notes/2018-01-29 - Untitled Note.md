---
title: Untitled Note
uid: 20180129T0050
created: '2018-01-29'
updated: '2024-04-01'
source: evernote
original_notebook: My Notes5
tags:
- enterprise-architect
aliases: []
---

Export to XMI via automation -- notes

\

From the User Guide - Enterprise Architect Object Model

> *ExportPackageXMI* *(string PackageGUID, enumXMIType XMIType, long DiagramXML, long DiagramImage, long FormatXML, long UseDTD, string FileName) protected abstract: String Notes: Exports XMI for a specified Package. Parameters: · PackageGUID: String - the GUID (in XML format) of the Package to be exported · XMIType: EnumXMIType - specifies the XMI type and version information; see XMIType Enum for accepted values · DiagramXML: Long - True if XML for diagrams is required; accepted values: 0 = Do not export diagrams 1 = Export diagrams 2 = Export diagrams along with alternate images · DiagramImage: Long - the format for diagram images to be created at the same time; accepted values: -1 = NONE 0 = EMF 1 = BMP 2 = GIF 3 = PNG 4 = JPG · FormatXML: Long - True if XML output should be formatted prior to saving · UseDTD: Long - True if a DTD should be used · FileName: String - the filename to output to*
>
> \
>
> *ExportPackageXMIEx* *(string PackageGUID, enumXMIType XMIType, long DiagramXML, long protected abstract: String Notes: Exports XMI for a specified Package, with a flag to determine whether the export includes Package content below the first level. (c) Sparx Systems 2015 - 2017 Page 219 of 280 Created with Enterprise Architect User Guide - Enterprise Architect Object Model 30 June, 2017 DiagramImage, long FormatXML, long UseDTD, string FileName, ea.ExportPackageXMIFlag Flags) Parameters: · PackageGUID: String - the GUID (in XML format) of the Package to be exported · XMIType: EnumXMIType - specifies the XMI type and version information; see XMIType Enum for accepted values · DiagramXML: Long - true if XML for diagrams is required; accepted values: 0 = Do not export diagrams 1 = Export diagrams 2 = Export diagrams along with alternate images · DiagramImage: Long - the format for diagram images to be created at the same time; accepted values: -1 =NONE 0 =EMF 1 =BMP 2 =GIF 3 =PNG 4 =JPG · FormatXML: Long - True if XML output should be formatted prior to saving · UseDTD: Long - True if a DTD should be used. · FileName: String - the filename to output to · Flags: ea.ExportPackageXMIFlag - specify whether or not to include Package content below the first level (currently supported for xmiEADefault), whether or not to exclude tool-specific information from export*

\

EA.Project.ExportPackageXMIEx(Package.PackageGUID, EA.EnumXMIType.xmiEA12, 0, -1, 1, 0, @"C:\Users\tbrennan-marquez\Documents\GIT\\ThomasPersonal\_\VerbSurgical\Models\KIWI Module Model", 2)

\

EA.Project.ExportPackageXMI(Package.PackageGUID, EA.EnumXMIType.xmiEA12, 0, -1, 1, 0, @"C:\Users\tbrennan-marquez\Documents\GIT\\ThomasPersonal\_\VerbSurgical\Models\KIWI Module Model\x.xmi")

\

this worked (in a contexts where Package is defined):

> m_Repository.GetProjectInterface().ExportPackageXMI(Package.PackageGUID, EA.EnumXMIType.xmiEA12, 0, -1, 1, 0, @"C:\Users\tbrennan-marquez\Documents\GIT\\ThomasPersonal\_\VerbSurgical\Models\KIWI Module Model\x.xmi")
>
> \

this worked better because the XMI format output was better:

> m_Repository.GetProjectInterface().ExportPackageXMI(Package.PackageGUID, EA.EnumXMIType.xmiEA21, 0, -1, 1, 0, @"C:\Users\tbrennan-marquez\Documents\GIT\\ThomasPersonal\_\VerbSurgical\Models\KIWI Module Model\xmiEA21.xmi")
>
> \
>
> \

\
