---
title: import sqlite3
uid: 20250413T2231
created: '2025-04-13'
updated: '2025-04-14'
source: evernote
original_notebook: My Notes1
tags: []
aliases: []
---

import sqlite3

def get_classes_and_associations(qeax_path): conn = sqlite3.connect(qeax_path) cursor = conn.cursor()

`# Get all classes cursor.execute("""     SELECT ea_guid, Name, Package_ID     FROM t_object     WHERE Object_Type = 'Class' """) classes = cursor.fetchall() class_dict = {row[0]: row[1] for row in classes} print("Classes:") for guid, name in class_dict.items():     print(f"- {name}") # Get all associations cursor.execute("""     SELECT Connector_Type, Start_Object_ID, End_Object_ID     FROM t_connector     WHERE Connector_Type IN ('Association', 'Generalization', 'Aggregation', 'Dependency', 'Realization', 'Composition') """) connectors = cursor.fetchall() print("\nAssociations:") for conn_type, start_id, end_id in connectors:     # Get class GUIDs from object IDs     cursor.execute("SELECT ea_guid FROM t_object WHERE Object_ID = ?", (start_id,))     start_guid_row = cursor.fetchone()     cursor.execute("SELECT ea_guid FROM t_object WHERE Object_ID = ?", (end_id,))     end_guid_row = cursor.fetchone()     if start_guid_row and end_guid_row:         start_name = class_dict.get(start_guid_row[0], f"Unknown ({start_id})")         end_name = class_dict.get(end_guid_row[0], f"Unknown ({end_id})")         print(f"{start_name} --[{conn_type}]--> {end_name}") conn.close() `

# Example usage:

# Replace 'your_file.qeax' with the path to your .qeax file

get_classes_and_associations("your_file.qeax")

\
