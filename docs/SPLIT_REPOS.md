# Split repositories

`Companion` is the **workspace and source of truth**. The standalone
repositories are distribution mirrors of the project directories:

| Workspace directory | Standalone repository | Mirror branch |
|---|---|---|
| `companion-cli/` | `Aryan-Rajyaguru-1/Companion_cli` | `cli` |
| `companion-ide/` | `Aryan-Rajyaguru-1/Companion_IDE` | `ide` |

Changes normally land in this repository first. When sync is enabled, a push to
`main` that touches a project, a shared setup script, `LICENSE`, or the sync
definition updates the matching split repository and the workspace mirror
branch. The split repositories are never the source of changes for the
workspace.

## How the sync works

[`.github/sync-projects.json`](../.github/sync-projects.json) is the manifest.
For each project it records the source directory, target repository and branch,
files that belong only to the split repository, extra files copied from the
workspace root, and any packaging transform.

[`scripts/sync-split-repos.mjs`](../scripts/sync-split-repos.mjs) implements the
operation:

1. Refuses to run if the workspace sync inputs (project tree, extra files, and
   manifest) or the split checkout have uncommitted changes.
2. Reads only files tracked in the workspace. Ignored files such as
   `node_modules/`, local firmware credentials, and firmware build output are
   never copied.
3. Copies the project tree, applies the IDE packaging transform, adds the shared
   setup scripts and `LICENSE`, and deletes tracked target files that no longer
   exist in the workspace.
4. Commits with a `Companion-Sync-Source: <workspace-sha>` trailer.
5. Pushes the split repository `main` branch and fast-forwards the workspace
   `cli` or `ide` branch to the same commit.

The workspace branch is updated by fetching the split commit into this
checkout and pushing it with the workspace's own origin credentials. This keeps
the split-repository token separate from the workspace token.

### What is preserved in the split repositories

| Project | Preserved path | Why |
|---|---|---|
| CLI and IDE | `README.md` | Split repositories carry their own clone/setup instructions. |
| IDE | `scripts/build-cli.js` | Workspace-only release helper; the standalone IDE uses the transformed package scripts instead. |
| IDE | `esp32-bridge-firmware/esp32_bridge/config.local.h` | Sanitized, tracked firmware template containing only `CHANGE_ME_*` placeholders. Local credentials remain untracked in the workspace and must never be copied. |

`.github/` is deliberately **not** synchronized and is rejected in both source
project directories and split repositories. A workflow from a split repository
would also become active on the workspace mirror branch, where it could run
with workspace permissions. Keep CI in the workspace.

## One-time setup

The workflow is inert until both of these repository settings exist on
`Aryan-Rajyaguru-1/Companion`:

1. **Secret `SYNC_TOKEN`** — a fine-grained personal access token with
   `Contents: Read and write` on `Companion_cli` and `Companion_IDE`. It does
   not need any access to the workspace repository.
2. **Variable `SYNC_ENABLED`** — set to `true` to enable the sync job.

The default `GITHUB_TOKEN` handles the workspace mirror branches; `SYNC_TOKEN`
checks out and pushes the two split repositories.

Until `SYNC_ENABLED` is `true`, the plan job still runs and shows what would be
synced, while the sync job is skipped. After saving both settings, run the
workflow manually once with `all`; setting the variable does not retrigger an
older push. That first enabled run will also remove generated firmware build
artifacts that were accidentally tracked in `Companion_IDE` and add files
missing from the split tree.

## Running it manually

Preview without writing:

```bash
node scripts/sync-split-repos.mjs --project ide --target ../Companion_IDE --dry-run
```

`--check` exits `1` when the target is out of date. `--write` applies the
changes and commits locally. `--push` also pushes the split branch and the
workspace mirror branch. For `--write` and `--push`, the split checkout must be
on the manifest branch. `--push` must run from the workspace `main` branch.

Both the workspace and target checkouts must have full Git history for
`--push`; the workflow checks out both with `fetch-depth: 0`. A local shallow
clone can be converted with `git fetch --unshallow`.

```bash
node scripts/sync-split-repos.mjs --plan
node scripts/sync-split-repos.mjs --project cli --target ../Companion_cli --check
node scripts/sync-split-repos.mjs --project ide --target ../Companion_IDE --write
```

Or run **Actions → Sync split repositories → Run workflow** and enter `all` or a
project name from the manifest. The workflow only writes from `main`; a manual
run from another branch plans but skips the sync job.

## Divergence and recovery

Before pushing, the script fetches the workspace mirror branch and requires it
to be the split branch's current tip (or an ancestor through commits that all
carry the `Companion-Sync-Source` trailer). If the split repository has an
independent commit, the sync refuses to overwrite it and asks for a manual
reconciliation.

If a split push succeeds but the workspace branch push fails, the split commit
is still valid. The next run recognizes the sync commit and fast-forwards the
workspace branch without rewriting the split repository. If the split push
itself fails after the commit is created, the next run retries that generated
commit before updating the workspace branch. A missing workspace mirror branch
is created on the first sync only when the split checkout is exactly at its
remote tip; otherwise push or update the split checkout first.

## Adding a project

Add an entry to `.github/sync-projects.json` with:

- `name`: a lowercase identifier used by `--project` and the workflow matrix
- `source`: the workspace directory
- `repo`: `owner/repository`
- `branch` and `workspaceBranch` (the workspace mirror branch must be dedicated;
  it cannot be `main` or `master`)
- `preserve`: split-only paths (files or directory prefixes)
- `extraSources`: workspace-root files to copy (`from`/`to`)
- `transform`: optional, currently `ide-package`

Add the new repository's path to the workflow's `on.push.paths`, grant
`SYNC_TOKEN` access to it, and run the workflow once with that project name (or
`all`). The first successful sync creates the workspace mirror branch if it is
missing and the split checkout is at its remote tip. The matrix and manual
project input are manifest-driven; the push path filter is the only per-project
workflow edit.

## Limitations

- The split `README.md` is maintained separately; updates do not flow from the
  workspace project README. Editing a preserved file in a split repository
  creates an independent commit; the sync will not overwrite it. Reconcile the
  workspace mirror branch manually (for example, fast-forward it to the split
  tip) before syncing again.
- The sanitized IDE firmware template
  (`esp32-bridge-firmware/esp32_bridge/config.local.h`) is preserved rather
  than sourced from the workspace. Update the split copy manually when its
  placeholder structure changes; never copy the ignored workspace file.
- The sync accepts only regular tracked files. Tracked symlinks are rejected in
  the workspace project and in the split checkout.
- The split repositories have no CI yet. Adding it requires a design that does
  not put workflows on the workspace mirror branches.
- The workflow needs a maintainer-managed PAT because the default
  `GITHUB_TOKEN` cannot write to the other repositories.
- Split-repository branch protection must allow the `SYNC_TOKEN` identity to
  push if protection is enabled later.
