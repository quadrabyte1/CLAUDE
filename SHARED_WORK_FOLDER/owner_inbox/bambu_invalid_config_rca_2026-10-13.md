# Bambu Studio Invalid Config Warning — Root Cause Analysis

**Date:** 2026-10-13  
**Issue:** Thomas encounters "The 3mf file has invalid config, load geometry data only" on every 3MF open in Bambu Studio 2.8.2.61, despite all templates version-matched to 02.08.02.61.

## Root Cause

**The `_rels/.rels` file is incomplete.** Our generator copies trimesh's minimal `_rels/.rels` (which contains only the 3dmodel relationship) without regenerating thumbnail relationship declarations.

### Evidence

**Generated 3MF** `Delaveaga (Hole 5f) [1431].3mf`:
```xml
<?xml version='1.0' encoding='utf-8'?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" 
                Target="/3D/3dmodel.model" Id="rel0"/>
</Relationships>
```

**Reference blank.3mf** (Bambu Studio export):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" 
               Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
 <Relationship Target="/Metadata/plate_1.png" Id="rel-2" 
               Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"/>
 <Relationship Target="/Metadata/plate_1.png" Id="rel-4" 
               Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-middle"/>
 <Relationship Target="/Metadata/plate_1_small.png" Id="rel-5" 
               Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-small"/>
</Relationships>
```

**Missing relationships:**
- `rel-2`: plate_1.png as standard OPC thumbnail
- `rel-4`: plate_1.png as Bambu Lab cover-thumbnail-middle (proprietary)
- `rel-5`: plate_1_small.png as Bambu Lab cover-thumbnail-small (proprietary)

The PNG files themselves are present in Metadata/ (verified: `plate_1.png`, `plate_1_small.png`, `plate_no_light_1.png`, `pick_1.png`, `top_1.png`), but the package relationships that declare them are missing. Bambu Studio's 3MF validation checks for consistency between declared relationships and actual files; missing relationship entries cause the parser to flag the config as "invalid."

## File Path
- **Generator:** `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/gradient_surface_diagnostic.py`, function `_inject_bambu_extruder_metadata()`, lines 8710–9039
- **Problematic code section:** Lines 9015–9019 (file copy loop) and lines 9007–9013 ([Content_Types].xml patching). The `.rels` file is not regenerated.

## Secondary Finding
The code at lines 9009–9013 **adds** `<Default Extension="config" ContentType="text/xml"/>` to [Content_Types].xml, which our diff shows is NOT present in the blank reference. However, this is likely benign or defensive (Bambu accepts the config extension regardless), but it is an inconsistency worth noting.
