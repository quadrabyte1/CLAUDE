---
title: Notes on generating XSD
uid: 20240427T2223
created: '2024-04-27'
updated: '2024-04-27'
source: evernote
original_notebook: My Notes2
tags: []
aliases: []
---

- ☐

  each class gets a plural container:

\<xs:element name="RangeLimitations"\>

                \<xs:complexType\>

                        \<xs:sequence\>

                                \<xs:element maxOccurs="unbounded" ref="RangeLimitation"/\>

                        \</xs:sequence\>

                \</xs:complexType\>

        \</xs:element\>

- ☐

  each class gets an element:

\<xs:element name="EngineeringUnit"\>

                \<xs:complexType\>

                        \<xs:attribute name="Description" use="required"/\>

                        \<xs:attribute name="Name" use="required" type="xs:ID"/\>

                \</xs:complexType\>

        \</xs:element\>

- ☐

  a class gets formalization attributes, indicating conditionality this way:

\<xs:element name="DataTopic"\>

                \<xs:complexType\>

                        \<xs:sequence\>                        note: use all rather than sequence to allow ordering

                                \<xs:element minOccurs="1" ref="StructuredData"/\>

                                \<xs:element minOccurs="0" ref="RangeLimitation"/\>

                        \</xs:sequence\>

                        \<xs:attribute name="DeprecatedVersion" use="required"/\>

                        \<xs:attribute name="Description" use="required"/\>

                        \<xs:attribute name="IntroducedVersion" use="required" type="xs:NMTOKEN"/\>

                        \<xs:attribute name="Name" use="required" type="xs:NCName"/\>

                \</xs:complexType\>

        \</xs:element\>

- ☐

  each simple attribute of a class (which must be set to something!) gets:

\<xs:element name="RangeLimitation"\>

                \<xs:complexType\>

                        \<xs:attribute name="IsUpperLimit" type="bool"/\>

                        \<xs:attribute name="LimitingValue" use="required" type="xs:integer"/\>

                        \<xs:attribute name="Name" use="required" type="xs:NCName"/\>

                        \<xs:attribute name="Color" type="color" use="required" /\>         

                \</xs:complexType\>

        \</xs:element\>

- ☐

  two ways to refer to an instance (first one is embedded define of a *new instance element*, second one is a *formal attribute* pointing to an instance elsewhere:

\<DataTopic Name="RaControlDesired" IntroducedVersion="D" DeprecatedVersion="4"                      Description="description of RaControlDesired "\>

\<StructuredData Name="RaControlDesired_SD"/\>

\<RangeLimitation LimitingValue="100" Name="myveryownlimitation" Color="red"/\>

\</DataTopic\>

\<DataTopic Name="UiActual" IntroducedVersion="E" DeprecatedVersion="5" Description="description of UiActual "    RangeLimitation="BozoRange"\>

\<StructuredData Name="UiActual_SD"/\>

\</DataTopic\>

- ☐

  instance created as children of an element may be referenced by other elements outside the parent element--scoping rules (ala C++) don't apply

- ☐

  \
