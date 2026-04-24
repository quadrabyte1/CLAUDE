# Hiring Research: Consumer Hardware Reviewer — SSDs (M.2 NVMe / SATA)

**Prepared by:** Pax (Senior Researcher)
**Date:** 2026-04-22
**Trigger:** User needs an in-house expert to advise on consumer SSD purchases and upgrades (desktop + laptop, M.2 NVMe primarily, SATA secondarily). No current team member owns storage-hardware expertise.

---

## 1. Role & Common Titles

Real-world practitioners with this skill set typically hold one of these titles:

- **Storage Reviewer / Storage Editor** — lead role at outlets like Tom's Hardware, TechPowerUp, The SSD Review, Storage Review, Tweaktown. Writes long-form reviews and buyer's guides.
- **Senior Hardware Reviewer (Storage focus)** — generalist hardware reviewer whose coverage leans heavily into drives (e.g., Allyn Malventano — formerly PC Perspective / Intel, Sean Webster — Tom's Hardware, Billy Tallis — formerly AnandTech).
- **SSD Test Engineer / Validation Engineer** — manufacturer-side role (Samsung, WD, SK hynix, Crucial/Micron, Kioxia); runs compliance, firmware regression, endurance testing.
- **Independent YouTube reviewer** — e.g., Gamers Nexus (Steve Burke, occasionally deep on storage), Hardware Canucks, Level1Techs (Wendell — workstation/NAS angle), JayzTwoCents, Linus Tech Tips (mainstream coverage).
- **Enterprise Storage Analyst** — more B2B; not the right archetype for consumer advice.

For our team, the right archetype is a **Consumer SSD Reviewer / Buyer's-Guide Author** — someone who evaluates retail drives, writes for end-users doing upgrades, stays current on firmware/NAND swaps, and turns benchmark numbers into a concrete recommendation.

---

## 2. Core Expertise

### NAND Flash Fundamentals
- **SLC** (1 bit/cell) — fastest, highest endurance, effectively not sold to consumers anymore except as pseudo-SLC cache on TLC/QLC drives.
- **MLC** (2 bits/cell) — the old enthusiast favorite (Samsung 970 Pro was the last mainstream MLC drive); effectively extinct in new consumer releases as of 2026.
- **TLC** (3 bits/cell) — the dominant NAND in mainstream and enthusiast drives. Balances cost, performance, endurance. Most 2024-2026 TLC is **232-layer** (Micron B58R, YMTC X3-9070) or **218-layer** (SK hynix), with **2xx-300+ layer** stacks coming online.
- **QLC** (4 bits/cell) — denser, cheaper per GB, but lower endurance and dramatic post-cache write cliffs. Common in budget drives (Crucial P3/P3 Plus, WD Blue SN5000 QLC variants, Samsung 870 QVO SATA).
- **PLC** (5 bits/cell) — still experimental in 2026; not yet shipping in mainstream consumer drives.
- Reviewer must be able to **identify NAND type from the drive's behavior** (sustained write curve), not just the marketing page, because manufacturers don't always disclose cleanly.

### DRAM vs DRAM-less vs HMB
- **DRAM cache** — dedicated DDR4/LPDDR4 on the SSD (usually 1GB per 1TB) for the FTL (flash translation layer) mapping table. Better sustained performance, better for heavy random I/O.
- **DRAM-less** — no onboard cache; relies on SRAM inside the controller plus **Host Memory Buffer (HMB)** — a chunk of system RAM (typically 64MB) loaned to the drive via the NVMe HMB spec.
- HMB is **fine for most consumer workloads** (OS drive, gaming, general productivity) but falls behind DRAM drives on sustained random writes and heavy multitasking.
- Key tell: drives like the WD Blue SN580, Crucial P3 Plus, Samsung 990 EVO Plus are DRAM-less with HMB. Samsung 990 Pro, WD Black SN850X, Crucial T705 have full DRAM.

### Controllers (the chip that runs the show)
- **Phison E26** — flagship PCIe 5.0 controller; 12nm; powers Corsair MP700 Pro, Crucial T700/T705, Seagate FireCuda 540, Gigabyte Aorus Gen5 12000, Sabrent Rocket 5. Runs hot — heatsink mandatory.
- **Phison E31T / E27T** — PCIe 5.0 and 4.0 respectively, DRAM-less, low power, 7nm — used in efficient mid-range drives (Corsair MP700 Elite, Crucial P510).
- **Phison E18** — the PCIe 4.0 workhorse for years; powers Sabrent Rocket 4 Plus, Seagate FireCuda 530, Corsair MP600 Pro.
- **Phison E21T** — PCIe 4.0 DRAM-less mainstream (Corsair MP600 GS, Crucial P3 Plus).
- **Silicon Motion (SMI) SM2508** — PCIe 5.0, 6nm, much cooler than Phison E26; powers Crucial T705 variants, Micron 4600, Acer Predator GM9000. A major 2025 entrant that moved the thermal story forward.
- **SMI SM2264 / SM2262EN** — PCIe 4.0 / 3.0 respectively; mainstream and enthusiast.
- **SMI SM2267XT / SM2269XT** — DRAM-less mainstream PCIe 4.0.
- **InnoGrit IG5236 (Rainier) / IG5666 (Tacoma)** — PCIe 4.0 and 5.0 respectively; used in Adata, Inland, Netac drives.
- **Maxio MAP1602 / MAP1806** — DRAM-less PCIe 4.0 controllers that punch above their weight; common in Lexar, Acer, Fanxiang, TeamGroup value drives.
- **Samsung Pascal / Elpis / Presto** — Samsung's in-house controllers. Pascal = 990 Pro, Elpis = 980 Pro, Presto = 990 EVO/EVO Plus.
- **WD in-house (A101, B101)** — power SN850X, SN7100, SN5000.

### PCIe Generations & Form Factors
- **PCIe 3.0 x4** — ~3.5 GB/s ceiling; cheap, fine for most users, still common in laptops.
- **PCIe 4.0 x4** — ~7 GB/s ceiling; the mainstream sweet spot for 2024-2026.
- **PCIe 5.0 x4** — ~14 GB/s ceiling; thermal and price penalties; meaningful only for specific workloads (huge file transfers, pro video, DirectStorage games that actually use it).
- **Form factors:** M.2 2280 (22×80mm, by far the most common), 2230 (Steam Deck, ROG Ally, some ultrabooks), 2242 (older laptops, some NAS), 2260 (rare), 22110 (enterprise/workstation). Also **U.2/U.3** (enterprise), **E1.S/E1.L** (datacenter), **add-in card (AIC)**.
- **SATA III (6 Gbps)** — ~560 MB/s ceiling; relevant for 2.5" upgrades in older laptops and as cheap bulk secondary storage. Samsung 870 EVO and Crucial MX500 are the reference points.

### Endurance & TBW
- **TBW (Terabytes Written)** — manufacturer warranty spec; typical mainstream 1TB drive is rated **600 TBW**, enthusiast 1TB is **700–1400 TBW**. Warranty is usually the lesser of TBW or 5 years.
- **DWPD (Drive Writes Per Day)** — enterprise metric; consumer drives run ~0.3 DWPD.
- Real-world: consumers almost never hit TBW limits. The reviewer should not over-weight TBW for typical use cases but should flag it for heavy-write workloads (video editing, constant compilation, crypto).

### SLC Cache Behavior (the critical real-world metric)
- All TLC and QLC drives use a **dynamic pseudo-SLC cache** — a portion of the NAND temporarily running in SLC mode to absorb bursts of writes at full speed.
- Cache size scales with free space. A nearly-full drive has almost no cache.
- **Post-cache cliff** is where reviewers separate good drives from bad: when the SLC buffer fills, the drive drops to native TLC (usually 1–2 GB/s) or native QLC (often 80–400 MB/s — sometimes worse than SATA).
- A reviewer's **sustained write test** (writing, say, 80% of drive capacity in one shot) is the single most diagnostic benchmark for revealing this.

### Thermal Behavior
- PCIe 4.0 drives with DRAM can throttle at 70-80°C without a heatsink.
- PCIe 5.0 Phison E26 drives **require** active or substantial passive cooling; they will thermal-throttle within 30 seconds of sustained writes without it.
- SMI SM2508 (6nm) runs notably cooler — a meaningful differentiator.
- Motherboard-integrated M.2 heatsinks are usually adequate for Gen 4; Gen 5 often needs the drive's bundled cooler or an aftermarket unit.

### Power Consumption (laptops especially)
- Idle power matters for laptop battery life. Samsung 990 EVO Plus, WD SN5000, Crucial P3 Plus are known for good idle behavior.
- Some high-performance drives (SN850X, 990 Pro, Phison E26-based) have poor idle states and can cost 30-60 min of laptop runtime.
- **L1.2 low-power state support** is the key spec for laptop drives.

---

## 3. Tools & Benchmarks

### Synthetic Benchmarks
- **CrystalDiskMark** — the de facto standard for quick sequential + random reads/writes. Run with default (1 GiB test), NVMe profile, and larger test sizes (16 GiB, 64 GiB) to catch cache-fill behavior.
- **ATTO Disk Benchmark** — varies block size from 512B to 64MB; good for showing performance curves.
- **AS SSD Benchmark** — older but still used; includes a compression test and a "copy" test.
- **IOMeter / fio** — serious tools for sustained and mixed workloads; essential for proper enterprise-flavored reviews. `fio` is the Linux/scripting standard.
- **Anvil's Storage Utilities** — older, produces a composite score; less used in 2026.

### Real-World & Application Benchmarks
- **PCMark 10 Full System Drive Benchmark** — a trace-based benchmark replaying real application I/O (Office, Photoshop, game loads). Highly regarded as the best single "what will this feel like in use" number.
- **PCMark 10 Quick System Drive Benchmark** — shorter version of the above.
- **3DMark Storage Benchmark** — game-load-focused trace (Battlefield V, Call of Duty, Overwatch install/load, save/record, stream capture). The go-to for gamers.
- **PugetBench for Photoshop / Premiere / DaVinci Resolve** — trace workloads for creators.
- **DirectStorage test tools** — Microsoft's BulkLoadDemo, Forspoken's built-in benchmark; relevant for DirectStorage-era gaming.

### Real-World File-Copy Tests
- Large single-file copy (e.g., a 100 GB video file) — exposes sustained sequential write, cache cliff.
- Folder-of-small-files copy (e.g., 50,000 source files) — exposes random-write and metadata performance.
- Game install from Steam — mimics actual user pattern.

### Monitoring & Telemetry
- **CrystalDiskInfo** — SMART data, temperature, firmware version, NAND health %, TBW consumed. First-line diagnostic tool.
- **HWiNFO** — deeper sensor monitoring, including per-sensor logging during benchmarks.
- **Samsung Magician / WD Dashboard / Crucial Storage Executive / Corsair SSD Toolbox / Kingston SSD Manager** — vendor tools for firmware updates, over-provisioning, secure erase.
- **smartctl** (smartmontools) — cross-platform SMART reader; essential on Linux/macOS.
- **nvme-cli** — Linux tool for NVMe-specific commands (format, health log, feature set).

### Power Measurement
- **Quarch PPM** (professional) or a Keithley DMM for drive-level power at the M.2 slot — what AnandTech historically used.
- For less professional setups: whole-system power draw via a Kill-A-Watt, or laptop battery-life runs as a proxy.

### Thermal Measurement
- Thermal camera (FLIR, Hti) for spot-check imaging.
- Internal thermal sensors via HWiNFO, logged during a sustained write test.

---

## 4. Trusted Industry Sources (where real reviews live)

**Tier 1 — primary read daily:**
- **Tom's Hardware** — Sean Webster's reviews; the best-SSD lists are widely referenced. Regularly updated.
- **TechPowerUp** — extremely consistent test methodology, good for cross-comparing charts. Reviewers: Lawrence Lee, others.
- **The SSD Review (thessdreview.com)** — Les Tokar's site; specialized and deep.
- **StorageReview.com** — leans enterprise but covers high-end consumer too.
- **Tweaktown** — Jon Coulter's SSD reviews; thorough.

**Tier 2 — useful corroboration:**
- **Guru3D** — good long-form reviews.
- **AnandTech (historical archive)** — the gold standard for depth through 2023; Billy Tallis's reviews are still the reference methodology even though AT shut down in 2024.
- **Level1Techs** — Wendell covers workstation/NAS/ZFS storage with unique angles.
- **Hardware Canucks** — video-focused reviews.
- **Gamers Nexus** — less SSD-focused but their occasional deep-dives (e.g., on QLC, on SMR HDDs, on thermal throttling) are definitive.
- **Puget Systems blog** — workstation-centric, tested against real creative apps.
- **ServeTheHome** — enterprise/NAS-focused, useful for U.2/U.3.

**Tier 3 — aggregation & crowd signal:**
- **r/NewMaxx's SSD list (r/buildapc, r/NewMaxx)** — legendary community-maintained SSD tier list, frequently updated. "NewMaxx" is the single most trusted voice on Reddit for SSD recommendations.
- **TechPowerUp SSD Database** — searchable by controller, NAND, DRAM status.
- **Reddit r/buildapc, r/hardware** — crowd sanity-check.
- **Newegg / Amazon reviews** — mined specifically for **bait-and-switch complaints** and DOA rates, not performance claims.

**Manufacturer spec sheets:** Samsung, WD, Crucial, Kingston, Corsair, Sabrent, Seagate, SK hynix Solidigm, Kioxia, ADATA, TeamGroup, Lexar, Silicon Power — read with skepticism; real performance comes from third-party review.

---

## 5. Consumer Use-Case Tiers (early-to-mid 2026)

### Budget (~$60–$80 / 1TB)
Best for: secondary storage, cheap laptop upgrades, media drives. DRAM-less with HMB is fine here.
- **Crucial P3 Plus (PCIe 4.0, QLC)** — cheap; watch for post-cache cliff on big writes.
- **WD Blue SN580 (PCIe 4.0, TLC, DRAM-less + HMB)** — frequent sweet-spot pick. Good TLC in this price band.
- **Lexar NM790 (PCIe 4.0, TLC, Maxio MAP1602)** — overachiever; praised on r/NewMaxx.
- **TeamGroup MP44 / Fanxiang S770** — similar Maxio-based value picks.
- **SATA alternative: Crucial MX500, Samsung 870 EVO** — for 2.5" upgrades in older laptops.

### Mainstream (~$85–$120 / 1TB) — the **sweet spot** for most users
Best for: primary OS + apps + games, desktop or laptop upgrade. TLC, usually DRAM.
- **WD Black SN770 / SN7100 (PCIe 4.0, TLC, DRAM-less + HMB)** — excellent balance, often on sale.
- **Crucial P5 Plus / T500 (PCIe 4.0, TLC, DRAM)** — strong reviewer favorite; T500 is the 2024-2026 go-to mainstream DRAM TLC pick.
- **Samsung 990 EVO Plus (PCIe 4.0/5.0 x2, TLC, DRAM-less)** — hybrid PCIe spec is quirky; runs cool; good for laptops.
- **Kingston NV3 / KC3000** — solid.
- **Samsung 990 EVO (original)** — mainstream but less impressive than the Plus revision.

### Enthusiast (~$130–$180 / 1TB)
Best for: gaming mains, power users, anyone who opens the drive's task manager graph for fun. TLC + DRAM, top-tier sustained performance.
- **Samsung 990 Pro (PCIe 4.0, TLC, DRAM)** — the reference enthusiast PCIe 4.0 drive; excellent firmware maturity, good thermals without massive heatsink.
- **WD Black SN850X (PCIe 4.0, TLC, DRAM)** — direct 990 Pro competitor; often cheaper; PS5-friendly.
- **Crucial T500 (higher capacity tiers)** — aggressive pricing vs the flagships.
- **Seagate FireCuda 530 / 530R** — Phison E18-based workhorse.

### PCIe 5.0 Flagship (~$180–$280 / 1TB or $280-$450 / 2TB)
Best for: workstation users with Gen 5 motherboard and a real workload. Not justified for pure gaming in most cases.
- **Crucial T705 (Phison E26)** — the top-end numbers king; runs hot.
- **Crucial T700** — last-gen flagship, now discounted.
- **Corsair MP700 Pro / Elite** — E26 (Pro) or E31T (Elite); Elite is the efficient play.
- **Samsung 9100 Pro (Presto successor, 2025)** — Samsung's PCIe 5.0 flagship; controller is cooler than E26; strong competitor to T705.
- **Micron 4600 / Acer Predator GM9000 (SMI SM2508)** — thermally the best-behaved Gen 5 drives.
- **Sabrent Rocket 5, Gigabyte Aorus Gen5 12000, Seagate FireCuda 540** — E26 variants.

### Workstation / Creator
Best for: video editing scratch, large dataset loading, VM hosting.
- Prioritize **sustained write**, **DRAM**, **high TBW**, and **2TB+** capacity (larger SLC caches).
- Picks: Samsung 990 Pro 4TB, WD Black SN850X 4TB, Crucial T705 2TB+, Solidigm P44 Pro 2TB.

### Gaming / DirectStorage
- Most games don't yet saturate PCIe 4.0. PCIe 5.0 gives negligible load-time advantage for 99% of titles as of early 2026.
- **PCIe 4.0 DRAM TLC is the current gaming sweet spot** — SN850X, 990 Pro, T500.
- **Steam Deck / ROG Ally (2230 form factor):** WD Black SN770M 2230, Corsair MP600 Mini, Sabrent Rocket 2230, Inland TN446.

### Laptop Upgrades (watch form factor + interface!)
- **Always verify M.2 length** (2280 vs 2242 vs 2230) and **interface** (NVMe vs SATA M.2 — not all M.2 slots are NVMe).
- Prefer drives with **good idle power** (L1.2 support): Samsung 990 EVO Plus, WD SN580, Crucial P310.
- Single-sided drives preferred in slim laptops for thermal and clearance reasons.

---

## 6. Pitfalls Reviewers Watch For

### The Bait-and-Switch (silent component swaps)
One of the most important things a modern SSD reviewer tracks. Manufacturers ship a drive with one NAND/controller combo, reviewers rate it well, then a silent revision swaps in cheaper parts while keeping the name and SKU identical. Canonical cases:

- **WD Blue SN580 / SN570** — multiple NAND revisions; some units ship with slower BiCS NAND than the reviewed version.
- **Samsung 970 EVO Plus** — the infamous "V2" revision (2021) swapped to a different controller (Elpis variant) and NAND; real-world performance differed from original reviews. Samsung did not change the SKU.
- **Crucial P2** — originally TLC; silently swapped to QLC in later batches.
- **Adata XPG SX8200 Pro** — multiple controller/NAND revisions over its lifetime, some meaningfully slower.
- **Kingston A2000, A400** — component revisions over time.
- **Patriot P300, P400** — revision history complicates recommendations.

**How a reviewer defends against this:** flag it in reviews, recommend checking batch / check firmware revision, prefer brands with cleaner revision histories (Samsung Pro line, WD Black line, Crucial T-series tend to be more stable), and **buy from retailers with easy return policies** in case you get a bad revision.

### QLC Masquerading as TLC
Some drives market themselves ambiguously and only real testing reveals QLC behavior. The tell: a sustained write that drops to 80-150 MB/s after the cache fills is QLC; TLC falls to 500 MB/s – 2 GB/s.

### Post-SLC-Cache Write Cliff
Marketing shows peak numbers; reviewers show the cliff. A drive advertising "7000 MB/s" that drops to 200 MB/s for the last 80% of a 1TB write is a bad pick for anyone copying big video files.

### Thermal Throttling Without a Heatsink
Especially Gen 5 drives. Reviewers test with and without the motherboard heatsink to show the real-world delta.

### DRAM-less Drives in the Wrong Context
Fine as a gaming or OS drive; noticeably worse for heavy random writes, VMs, databases, or anything with a massive small-file working set. Reviewer's job: steer the user to the right class of drive, not just the cheapest.

### Firmware Bugs & Regression
- **Samsung 990 Pro** had a well-publicized firmware issue in late 2022 causing rapid health-percentage decline; fixed in firmware 1B2QJXD7.
- **Sabrent Rocket 4 Plus (E18)** firmware updates changed performance profiles between revisions.
- **WD Black SN850** had a firmware bug affecting game load times, fixed in later revisions.
Reviewers track these and re-test after firmware updates.

### "Marketing Numbers" vs Real Numbers
Sequential 7000 MB/s reads mean nothing if random 4K QD1 reads are mediocre. For OS and application feel, **4K random at low queue depth** matters far more than peak sequential. A reviewer constantly reminds readers of this.

### Endurance Theater
A 2400 TBW badge sounds great but no consumer hits it. More relevant: **what's the warranty length**, and does the manufacturer honor it cleanly.

---

## 7. Review Methodology (how a pro structures a recommendation)

A mature SSD review or buying recommendation follows a repeatable structure:

1. **Identify the use case first.** Gaming OS drive? Laptop upgrade? Scratch disk for Premiere? Steam Deck? NAS cache? Each changes the answer.
2. **Narrow form factor + interface.** What slot? What length? Is it NVMe, or SATA M.2? Does the motherboard/laptop support PCIe 4.0 or 5.0? Is there a heatsink built into the slot?
3. **Set a budget tier.** Budget / Mainstream / Enthusiast / Flagship.
4. **Filter on non-negotiables.** DRAM required for the workload? TLC only (no QLC)? Single-sided for laptop?
5. **Compare finalists on:**
   - **Sustained write performance** (post-cache cliff)
   - **4K random at low queue depth** (real-world feel)
   - **Thermal behavior** (with and without heatsink)
   - **Idle power** (for laptops)
   - **Endurance rating + warranty length**
   - **Price per GB**
   - **Firmware maturity + brand revision history**
6. **Name a winner with caveats.** Not "this is the best drive," but "this is the best drive **for this use case at this budget, assuming you don't need X**." Always state the caveat.
7. **Name a runner-up** in case the winner is out of stock or on a bad sale cycle.
8. **Flag upgrade paths.** "If you can spend $30 more, jump to Y and get X% better sustained write" — or, "the tier above isn't worth it for your case."

---

## 8. Decision-Making Patterns

### When to spend more
- Heavy sustained writes (video, large datasets, constant game installs).
- Need for DRAM (VMs, databases, heavy multitasking power users).
- Long-term keeper drives where firmware maturity matters.
- PCIe 5.0 only when the workload literally cannot be satisfied by PCIe 4.0 — rare in gaming, common in some creative pipelines.

### When "good enough" really is good enough
- Gaming load times past PCIe 4.0 are indistinguishable in almost all games.
- Office / browsing / general productivity saturates at PCIe 3.0 levels; any modern NVMe feels instant.
- Most users writing < 50 GB/day never notice the difference between a mainstream and an enthusiast drive.

### Price-per-GB heuristic
- As of early 2026 in the US retail market, rough pricing:
  - Budget TLC NVMe 1TB: ~$55–$75
  - Mainstream TLC NVMe 1TB: ~$85–$110
  - Enthusiast TLC NVMe 1TB: ~$115–$150
  - PCIe 5.0 flagship 1TB: ~$160–$220
  - **2TB is almost always the better $/GB and better sustained performance** (bigger SLC cache) — a reviewer nudges users to 2TB when the delta is <$40.

### Brand reliability heuristic (reviewer consensus)
- **Samsung, WD, Crucial (Micron), SK hynix Solidigm, Kioxia** — tier-1 reliability, clean revision history, long warranty support.
- **Kingston, Corsair, Seagate, Sabrent, Lexar, ADATA, Teamgroup** — tier-2; generally good but more revision variance.
- **Inland (Micro Center), Silicon Power, Fanxiang, Netac, Patriot** — budget; often great value but higher revision risk.
- **No-name Amazon brands** — avoid except as last resort; often re-badged budget drives with unverified NAND.

---

## 9. First-Task Preparation: "What's the best 1TB M.2-2280 SSD upgrade?"

The new hire should be ready to answer this immediately. The expected flow:

1. **Clarify:** What's the machine (desktop or laptop)? What's the motherboard/slot interface (PCIe 3.0, 4.0, 5.0)? What's the workload (gaming, OS, creator)? Is there a budget?
2. **Default answer (mainstream desktop PCIe 4.0 gaming OS drive, ~$100):**
   - **Primary pick:** **WD Black SN850X 1TB** (~$100-$120) — DRAM, TLC, excellent sustained write, mature firmware, strong warranty.
   - **Runner-up:** **Samsung 990 Pro 1TB** (~$110-$130) — comparable performance, better idle power, slightly better 4K random; watch firmware version.
   - **Value alternative:** **Crucial T500 1TB** (~$85-$95) — DRAM TLC at a mainstream price.
   - **Budget alternative:** **Lexar NM790 1TB** or **WD Blue SN580 1TB** (~$65-$80) — DRAM-less TLC, excellent for the price.
3. **Laptop variant (idle-power matters):** Samsung 990 EVO Plus or Crucial P310.
4. **PCIe 5.0 build:** Samsung 9100 Pro or Micron 4600 (cooler than Crucial T705).
5. **State caveats:** not worth PCIe 5.0 tax unless workload demands; if budget is tight, mainstream Gen 4 TLC with DRAM is the sweet spot; verify M.2 2280 slot length before ordering.

---

## 10. Recommended Persona Archetype for New Hire

**Who Nolan should create:**

A practical, numbers-grounded SSD reviewer who:

- Thinks in **use cases first**, not spec sheets. Asks the user what they're actually doing before recommending anything.
- Knows the **current (2025-2026) drive landscape cold** — Samsung 990 Pro / 990 EVO Plus / 9100 Pro, WD Black SN850X / SN7100, Crucial T500 / T705, Lexar NM790, Corsair MP700 variants, Phison E26 vs SMI SM2508 thermal story.
- Watches for **bait-and-switch revisions** and **firmware regressions**; treats brand trust as a real variable.
- Translates benchmarks into **"will you feel it"** — distinguishes marketing peak numbers from sustained real-world performance.
- Fluent in **CrystalDiskMark, CrystalDiskInfo, PCMark 10 Storage, 3DMark Storage, ATTO, IOMeter/fio**.
- Reads **Tom's Hardware, TechPowerUp, The SSD Review, r/NewMaxx** as daily inputs; references them when justifying picks.
- Writes recommendations in the pro format: use case → form factor → budget tier → finalist comparison → winner with caveats → runner-up.
- Personality: opinionated but evidence-based; unafraid to say "don't buy this" or "good enough is fine here"; patient enough to explain why a $70 drive is often the right choice over a $200 one.

**Suggested archetype title:** "Consumer Storage Reviewer" or "SSD & Storage Specialist." Practical, plain-spoken, not academic.

**Immediate first task:** Answer the user's question — *"What's the best 1TB M.2-2280 SSD upgrade?"* — by clarifying the use case and delivering a ranked pick + runner-up + budget alt, with caveats.

---

*Sources consulted: Tom's Hardware SSD reviews and best-of lists (2024-2026), TechPowerUp SSD review archive, The SSD Review, StorageReview, Tweaktown, AnandTech historical archive (Billy Tallis), r/NewMaxx SSD tier list, Gamers Nexus thermal coverage, Level1Techs workstation storage coverage, manufacturer spec sheets (Samsung, WD, Crucial, SK hynix, Kingston, Corsair, Sabrent, Lexar), Phison and Silicon Motion controller documentation, NVMe HMB specification notes.*
