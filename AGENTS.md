# Working on ios-sweet

- Read `NOTES.md` before starting; it contains the project goal, hardware facts,
  current blocker, local artifact locations and the next concrete action.
- The user switches agents frequently. Update the active handoff in `NOTES.md`
  after each milestone and before stopping. Record commits, CI run IDs, exact
  build/boot results and unfinished work. Distinguish observations from guesses.
- Commit completed changes. Use `gh` for GitHub Actions kernel builds and logs.
  Local single-file cross-compiles are useful before spending a CI run.
- Device bring-up uses temporary `fastboot boot` images. Preserve the Android
  installation and partition backups. The user approved (2026-10-15) using
  internal UFS for iOS and said Android may be deleted: the iOS root goes
  into the existing `userdata` partition (no GPT changes). Keep bootloaders,
  recovery, modem, persist and the backups intact, and confirm each
  destructive step with the user before running it.
- Keep device dumps, serial numbers and downloaded Apple artifacts out of git.

- User override (2026-10-22): skip QEMU tests from now on. Continue local
  object compile, strict patch application/repository checks and full CI,
  then temporary phone boot and persistent-log validation. Do not run
  QEMU automatically based on older notes or original procedure.

## Independent renoir repository (2026-10-22)

- origin is the standalone daimile2/ios-renoir repository (GitHub ID1429589218, fork=false); defaultmain contains renoir code, not the original sweet baseline. Keep upstream attribution and original file licenses.
- docs/renoir contains the portable handoff documentation. workspace-tools contains host scripts meant to be installed in the workspace tools/ sibling to src/. When editing a host script in workspace tools/, update its workspace-tools copy before publishing; keep the handoff documents in sync.
- Local backup bundles and old CI archives are in ../artifacts/repository-migration-20261022 and must stay out of git.

- User preference (2026-10-23): prioritize the pinned local HackiOS driver
  approach for future ports, verify renoir-specific hardware differences,
  and avoid prolonged independent exploration when a reference path exists.
  Pause while workflows run until user reports completion; pause when
  awaiting user feedback with no mandatory background work.
