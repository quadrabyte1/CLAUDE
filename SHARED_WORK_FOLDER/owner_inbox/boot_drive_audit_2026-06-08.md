## Boot Drive Audit — 2026-06-08

**Current free:** 46 GiB of 228 GiB on `/`. External `/Volumes/GIT` has 918 GiB free.
**Potential reclaim from GREEN moves alone:** ~58–62 GiB (more than doubles free space).
**If Parallels Win11 ISO and Autodesk webdeploy are also reclaimable:** ~73 GiB.

### Top reclamation candidates (sorted by size desc)

| Size  | Path | Class | Recommendation |
|-------|------|-------|----------------|
| 25 G  | `~/Library/Containers/com.utmapp.UTM/Data/Documents/Windows.utm` | GREEN | Move VM bundle to `/Volumes/GIT/VMs/UTM/`, symlink back. UTM follows symlinks for .utm bundles. Stop the VM first. |
| 9.8 G | `~/Library/Application Support/Claude` | YELLOW | 8.3 G is `vm_bundles/claudevm.bundle` (Claude Desktop's local agent VM). Safe to delete — it re-downloads on next use. Moving + symlinking also works but the app may not love it; deleting is the cleaner play. |
| 9.6 G | `~/Library/Application Support/Autodesk/webdeploy` | YELLOW | Fusion 360 installer payload (old version cache). Can be cleared via Fusion → Help → About → reinstall, or symlinked. Safer to just symlink to GIT. |
| 9.1 G | `~/Library/Application Support/protonmail/bridge-v3` | YELLOW | Proton Mail Bridge encrypted local cache. Quit Bridge before moving. Symlink works but performance over USB will be slower on heavy mail sync. |
| 5.5 G | `~/.colima/_lima` | GREEN | Colima/Lima VM disk. Stop colima (`colima stop`), move `_lima` to GIT, symlink. Standard supported approach. |
| 5.3 G | `~/Library/Parallels/Downloads/Windows11.iso` | GREEN | Installer ISO, no longer needed once Win11 is installed. Move to GIT (archive) or delete. |
| 4.9 G | `~/Library/Containers/com.utmapp.UTM/Data/Library/Caches` + Library | GREEN | Inside the same UTM container move above — handled by the 25 G move. |
| 3.2 G | `/opt/miniconda3` | GREEN | 2.1 G is `pkgs/` (conda's download cache). Run `conda clean --all` to reclaim ~2 G in place; or move the whole tree to GIT and symlink. |
| 2.2 G | `~/Library/Application Support/Evernote` | YELLOW | Local Evernote cache. Move + symlink works; quit Evernote first. |
| 1.8 G | `~/.npm` | GREEN | npm cache. `npm cache clean --force` or symlink to GIT. Rebuilds on demand. |
| 1.7 G | `~/Desktop/J U N K` | GREEN | User junk folder. Move wholesale to `/Volumes/GIT/Desktop_JUNK/` (no symlink needed if you don't care). |
| 1.7 G | `~/Library/CloudStorage/ProtonDrive-…-folder` | RED | CloudStorage providers (Proton Drive, iCloud, etc.) must live in `~/Library/CloudStorage`. Don't move. |
| 1.6 G | `~/Library/Caches/BraveSoftware` | GREEN | Browser cache. Safe to delete; auto-rebuilds. |
| 1.2 G | `~/Library/Application Support/Wispr Flow` | YELLOW | Transcription history/models. Symlink if you need it persistent. |
| 1.2 G | `/opt/homebrew` | RED | Leave in place. Hardcoded path for many bottles; moving breaks brew. Run `brew cleanup` for incremental reclaim. |
| 1.1 G | `~/.vscode/extensions` | GREEN | VS Code extensions. Symlinkable but minor; skip unless desperate. |
| 1.0 G | `~/Library/Application Support/Proton Mail` | YELLOW | Separate from bridge-v3 — desktop client cache. Symlink with app closed. |
| 985 M | `~/Library/Application Support/Claude/Cache` | GREEN | Electron cache. Safe to delete. |
| 971 M | `~/Library/Application Support/Google` | YELLOW | Chrome profile data. Symlinkable but risk of profile corruption on unmount; not worth it for <1 G. |
| 785 M | `~/Library/Caches/acmerstudio-updater` | GREEN | Stale updater payload. Safe to delete. |
| 779 M | `~/Library/Application Support/BraveSoftware` | YELLOW | Brave profile. Same caveat as Chrome. |
| 683 M | `~/Library/Application Support/BambuStudioBeta` | GREEN | Slicer profiles + cache. Symlinkable. |
| 675 M | `~/Library/Caches/com.anthropic.claudefordesktop.ShipIt` | GREEN | Old Claude Desktop updater payloads. Safe to delete. |
| 646 M | `~/Library/Caches/Homebrew` | GREEN | Brew download cache. `brew cleanup -s` reclaims it. |
| 637 M | `~/.dotnet` | GREEN | .NET SDK cache. Symlinkable. |
| 621 M | `~/Library/Application Support/Code` | YELLOW | VS Code workspace storage + state. Quit Code, then symlink. |
| 549 M | `~/Library/Caches/pip` | GREEN | `pip cache purge` or symlink. |
| 546 M | `~/Library/Caches/evernote-client-updater` | GREEN | Stale updater. Safe to delete. |
| 528 M | `~/Library/Caches/ms-playwright` | GREEN | Playwright browser binaries. Symlinkable; auto-redownloads on `npx playwright install`. |
| 552 M | `~/Library/Application Support/QIDIStudio` | GREEN | Slicer data. Symlinkable. |

### Quick-win bundles

- **Just the UTM Windows VM:** 25 G reclaim, single move.
- **UTM + Colima + Claude vm_bundles + Parallels ISO:** ~44 G reclaim, four discrete moves.
- **Add Autodesk webdeploy + Proton bridge + Desktop junk + cache purges:** ~70 G reclaim.

### Time Machine local snapshots

`tmutil listlocalsnapshots /` returned **zero snapshots**. No invisible space to reclaim there. Good news — APFS is not hoarding hourly snapshots on this machine.

### Notes / red flags

- **`~/Library/Application Support/Claude/vm_bundles/claudevm.bundle` (8.3 G)** is the new Claude Desktop local-agent VM. If you don't use Claude Desktop's local-agent mode, delete it outright; it only re-creates on first local-agent run.
- **UTM `Windows.utm` (25 G)** is the single biggest win and the safest move — UTM is symlink-friendly. Power off the VM before moving the bundle.
- **`/private/var/folders` is 815 MB** — normal, not worth touching.
- **Homebrew (1.2 G)**: do NOT move `/opt/homebrew`. Many bottles bake in the prefix. Instead, run `brew cleanup -s` and clear `~/Library/Caches/Homebrew` (646 MB).
- **CloudStorage providers** (Proton Drive folder, 1.7 G) are RED — their File Provider extension expects the fixed path.
- **`~/.cache` (264 M), `~/.docker` (32 K), no `.cargo/.rustup/.gradle/.m2/.pyenv/.nvm`** — nothing else lurking in dev caches.
- **Browser profile data (Chrome/Brave Application Support)**: technically YELLOW. If you ever unmount `/Volumes/GIT` while the browser is running, you can corrupt the profile. Skip unless you really need the GB back.
- **`~/Desktop/J U N K` (1.7 G)** — name suggests it's archivable. Recommend a wholesale move to GIT with no symlink.

### Recommended execution order (when you're ready to move)

1. UTM Windows VM (25 G, biggest single win)
2. Claude `vm_bundles` (delete, 8.3 G)
3. Parallels Win11 ISO (5.3 G, delete or archive)
4. Colima `_lima` (5.5 G, symlink)
5. Autodesk webdeploy (9.4 G, symlink)
6. Cache purges: Homebrew, pip, npm, BraveSoftware, ShipIt, acmerstudio/evernote updater stubs (~5 G)

Stop the related app/VM before each move. Use `ln -s /Volumes/GIT/<new_path> <original_path>` after `mv`.
