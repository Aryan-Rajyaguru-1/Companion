#!/usr/bin/env node
/**
 * Synchronize a project directory from the Companion workspace into its
 * standalone split repository.
 *
 * The workspace is canonical. The split repository is a distribution mirror:
 * its README, sanitized firmware config, and split-only packaging files are
 * preserved, while the rest of the project is copied from the workspace.
 *
 * Usage:
 *   node scripts/sync-split-repos.mjs --plan [--project NAME|all]
 *   node scripts/sync-split-repos.mjs --project ide --target ../Companion_IDE --dry-run
 *   node scripts/sync-split-repos.mjs --project ide --target ../Companion_IDE --write
 *   node scripts/sync-split-repos.mjs --project ide --target ../Companion_IDE --push
 *
 * --dry-run is the default when no write mode is selected. --push also pushes
 * the resulting commit to the workspace's mirror branch (cli or ide).
 */

import { spawnSync } from "node:child_process";
import {
  chmodSync,
  copyFileSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  rmSync,
  rmdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_WORKSPACE = path.resolve(SCRIPT_DIR, "..");
const MANIFEST_PATH = ".github/sync-projects.json";
const SYNC_TRAILER = "Companion-Sync-Source";
const SYNC_ACTOR = {
  name: "github-actions[bot]",
  email: "41898282+github-actions[bot]@users.noreply.github.com",
};

class SyncError extends Error {}

function fail(message) {
  throw new SyncError(message);
}

function usage() {
  return `Usage:
  node scripts/sync-split-repos.mjs --plan [--project NAME|all]
  node scripts/sync-split-repos.mjs --project NAME --target PATH [--dry-run|--check|--write|--push]

Options:
  --plan                 Print the GitHub Actions matrix and exit.
  --project NAME         Project name from ${MANIFEST_PATH}, or "all" for --plan.
  --target PATH          Checkout of the split repository to update.
  --workspace PATH       Workspace root (default: repository containing this script).
  --dry-run              Show changes without writing (default).
  --check                Exit 1 when changes are needed; never writes.
  --write                Apply changes and commit locally; do not push.
  --push                 Apply changes, commit, and push the split repository.
  --no-workspace-branch  Do not push the same commit to the workspace mirror branch.
  -h, --help             Show this help.`;
}

function parseArgs(argv) {
  const opts = {
    workspace: DEFAULT_WORKSPACE,
    project: null,
    target: null,
    plan: false,
    dryRun: false,
    check: false,
    write: false,
    push: false,
    workspaceBranch: true,
    help: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const value = () => {
      const next = argv[i + 1];
      if (!next || next.startsWith("-")) fail(`${arg} requires a value`);
      i += 1;
      return next;
    };

    switch (arg) {
      case "--plan":
        opts.plan = true;
        break;
      case "--project":
        opts.project = value();
        break;
      case "--target":
        opts.target = value();
        break;
      case "--workspace":
        opts.workspace = path.resolve(value());
        break;
      case "--dry-run":
        opts.dryRun = true;
        break;
      case "--check":
        opts.check = true;
        break;
      case "--write":
        opts.write = true;
        break;
      case "--push":
        opts.push = true;
        break;
      case "--no-workspace-branch":
        opts.workspaceBranch = false;
        break;
      case "-h":
      case "--help":
        opts.help = true;
        break;
      default:
        fail(`unknown option: ${arg}`);
    }
  }

  if (opts.help) return opts;
  if (opts.plan) {
    if (opts.target || opts.write || opts.push || opts.check || opts.dryRun) {
      fail("--plan cannot be combined with --target, --dry-run, --check, --write, or --push");
    }
    return opts;
  }
  if (!opts.target) fail("--target is required unless --plan is used");
  if (!opts.project) fail("--project is required unless --plan is used");
  if (opts.project === "all") fail("--project all is only supported with --plan");

  const writeModes = [opts.write, opts.push, opts.check].filter(Boolean).length;
  if (writeModes > 1) fail("choose only one of --check, --write, or --push");
  if (opts.push) {
    opts.write = true;
  }
  if (opts.check && opts.dryRun) {
    fail("--check already implies a dry run");
  }
  if (opts.dryRun && (opts.write || opts.push)) {
    fail("--dry-run cannot be combined with --write or --push");
  }
  if (!opts.write && !opts.check) {
    opts.dryRun = true;
  }

  opts.target = path.resolve(opts.target);
  return opts;
}

function toPosix(value) {
  return value.replaceAll("\\", "/");
}

function safeRelative(value, label) {
  if (typeof value !== "string" || value.length === 0) {
    fail(`${label} must be a non-empty string`);
  }
  const normalized = toPosix(value);
  if (/^[A-Za-z]:\//.test(normalized) || path.isAbsolute(normalized) || normalized.split("/").includes("..")) {
    fail(`${label} must stay inside its repository: ${value}`);
  }
  if (normalized === ".") fail(`${label} cannot be the repository root`);
  const preserveTrailingSlash = normalized.endsWith("/");
  const cleaned = normalized.replace(/\/+$/, "");
  const parts = cleaned.split("/");
  if (!cleaned || cleaned === "." || parts.some((part) => part === "" || part === ".")) {
    fail(`${label} must be a normalized relative path: ${value}`);
  }
  if (parts.some((part) => part.trim().toLowerCase().replace(/\.+$/, "") === ".git")) {
    fail(`${label} must not reference .git: ${value}`);
  }
  return preserveTrailingSlash ? `${cleaned}/` : cleaned;
}

function assertInside(root, candidate, label) {
  const rootAbs = path.resolve(root);
  const candidateAbs = path.resolve(candidate);
  if (candidateAbs !== rootAbs && !candidateAbs.startsWith(`${rootAbs}${path.sep}`)) {
    fail(`${label} escapes ${rootAbs}: ${candidate}`);
  }
  return candidateAbs;
}

function loadManifest(workspace) {
  const manifestPath = path.join(workspace, MANIFEST_PATH);
  if (!existsSync(manifestPath)) {
    fail(`sync manifest not found: ${manifestPath}`);
  }

  let manifest;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  } catch (error) {
    fail(`could not parse ${manifestPath}: ${error.message}`);
  }
  if (!manifest || !Array.isArray(manifest.projects) || manifest.projects.length === 0) {
    fail(`${MANIFEST_PATH} must contain a non-empty "projects" array`);
  }

  const names = new Set();
  const projects = manifest.projects.map((raw, index) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      fail(`projects[${index}] must be an object`);
    }
    const allowed = new Set([
      "name",
      "source",
      "repo",
      "branch",
      "workspaceBranch",
      "preserve",
      "extraSources",
      "transform",
    ]);
    for (const key of Object.keys(raw)) {
      if (!allowed.has(key)) fail(`projects[${index}] has unknown key "${key}"`);
    }

    if (typeof raw.name !== "string" || !/^[a-z][a-z0-9-]*$/.test(raw.name)) {
      fail(`projects[${index}].name must be a lowercase identifier`);
    }
    if (names.has(raw.name)) fail(`duplicate project name "${raw.name}"`);
    names.add(raw.name);

    const source = safeRelative(raw.source, `projects[${index}].source`);
    const sourceAbs = assertInside(workspace, path.join(workspace, source), `projects[${index}].source`);
    assertNoSymlinkPath(workspace, source, `projects[${index}].source`);
    if (!existsSync(sourceAbs)) {
      fail(`projects[${index}].source does not exist as a directory: ${source}`);
    }
    if (!lstatSync(sourceAbs).isDirectory()) {
      fail(`projects[${index}].source is not a directory (symlinks are not supported): ${source}`);
    }

    if (typeof raw.repo !== "string" || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(raw.repo)) {
      fail(`projects[${index}].repo must look like owner/repository`);
    }
    for (const [key, fallback] of [
      ["branch", null],
      ["workspaceBranch", null],
    ]) {
      const value = raw[key] ?? fallback;
      if (typeof value !== "string" || !/^[A-Za-z0-9._/-]+$/.test(value) || value.startsWith("-") || value.includes("..")) {
        fail(`projects[${index}].${key} must be a safe branch name`);
      }
    }
    if (["main", "master"].includes(raw.workspaceBranch.toLowerCase())) {
      fail(`projects[${index}].workspaceBranch must not be the workspace default branch`);
    }

    const preserve = raw.preserve ?? [];
    if (!Array.isArray(preserve)) fail(`projects[${index}].preserve must be an array`);
    const preservePaths = preserve.map((entry, preserveIndex) =>
      safeRelative(entry, `projects[${index}].preserve[${preserveIndex}]`),
    );

    const extraSources = raw.extraSources ?? [];
    if (!Array.isArray(extraSources)) fail(`projects[${index}].extraSources must be an array`);
    const extras = extraSources.map((entry, extraIndex) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
        fail(`projects[${index}].extraSources[${extraIndex}] must be an object`);
      }
      for (const key of Object.keys(entry)) {
        if (key !== "from" && key !== "to") {
          fail(`projects[${index}].extraSources[${extraIndex}] has unknown key "${key}"`);
        }
      }
      const from = safeRelative(entry.from, `projects[${index}].extraSources[${extraIndex}].from`);
      const to = safeRelative(entry.to, `projects[${index}].extraSources[${extraIndex}].to`);
      if (to.endsWith("/")) {
        fail(`projects[${index}].extraSources[${extraIndex}].to must be a file path`);
      }
      if (isPreserved(to, preservePaths)) {
        fail(`projects[${index}].extraSources[${extraIndex}].to is also preserved: ${to}`);
      }
      const fromAbs = assertInside(
        workspace,
        path.join(workspace, from),
        `projects[${index}].extraSources[${extraIndex}].from`,
      );
      assertNoSymlinkPath(workspace, from, `projects[${index}].extraSources[${extraIndex}].from`);
      if (!existsSync(fromAbs) || !lstatSync(fromAbs).isFile()) {
        fail(`extra source does not exist as a regular file: ${from}`);
      }
      if (from === ".github" || from.startsWith(".github/") || to === ".github" || to.startsWith(".github/")) {
        fail(`extra sources must not contain .github files: ${from} -> ${to}`);
      }
      return { from, to };
    });

    const transform = raw.transform ?? null;
    if (transform !== null && transform !== "ide-package") {
      fail(`projects[${index}].transform is not supported: ${transform}`);
    }

    return {
      name: raw.name,
      source,
      repo: raw.repo,
      branch: raw.branch,
      workspaceBranch: raw.workspaceBranch ?? null,
      preserve: preservePaths,
      extraSources: extras,
      transform,
    };
  });

  return { projects };
}

function selectProjects(manifest, selector) {
  if (!selector || selector === "all") return manifest.projects;
  const project = manifest.projects.find((candidate) => candidate.name === selector);
  if (!project) {
    fail(`unknown project "${selector}"; expected one of: ${manifest.projects.map((p) => p.name).join(", ")}`);
  }
  return [project];
}

function redact(text) {
  let result = String(text);
  for (const key of ["GITHUB_TOKEN", "SYNC_TOKEN"]) {
    const value = process.env[key];
    if (value) result = result.split(value).join("***");
  }
  return result
    .replace(/(https?:\/\/)[^@\s/]+@/g, "$1***@")
    .replace(/github_pat_[A-Za-z0-9_]+/g, "***")
    .replace(/gh[pousr]_[A-Za-z0-9]+/g, "***");
}

function git(args, { cwd, allowFailure = false, env = {}, maxBuffer = 64 * 1024 * 1024 } = {}) {
  const result = spawnSync("git", args, {
    cwd,
    encoding: "utf8",
    env: { ...process.env, ...env },
    maxBuffer,
  });
  if (result.error) fail(`could not run git ${args.join(" ")}: ${result.error.message}`);
  if (result.status !== 0 && !allowFailure) {
    const detail = redact((result.stderr || result.stdout || "").trim());
    fail(`git ${args.join(" ")} failed in ${cwd}${detail ? `:\n${detail}` : ""}`);
  }
  return result;
}

function gitOutput(args, options) {
  return git(args, options).stdout.trim();
}

function listTracked(cwd, pathspec = null) {
  const args = ["ls-files", "-z"];
  if (pathspec) args.push("--", pathspec);
  const result = git(args, { cwd });
  return result.stdout.split("\0").filter(Boolean);
}

function requireClean(cwd, label, pathspec = null) {
  const args = ["status", "--porcelain"];
  if (pathspec) {
    args.push("--", ...(Array.isArray(pathspec) ? pathspec : [pathspec]));
  }
  const status = gitOutput(args, { cwd });
  if (status) {
    fail(`${label} has uncommitted changes; commit or stash them before syncing:\n${status}`);
  }
}

function requireFullHistory(cwd, label) {
  if (gitOutput(["rev-parse", "--is-shallow-repository"], { cwd }) === "true") {
    fail(
      `${label} is a shallow clone; run "git fetch --unshallow" (or check out with full history) before pushing.`,
    );
  }
}

function requireTargetBranch(target, expected) {
  const current = git(["symbolic-ref", "--quiet", "--short", "HEAD"], {
    cwd: target,
    allowFailure: true,
  });
  if (current.status !== 0) {
    fail(`split repository is not on a branch; check out "${expected}" before writing`);
  }
  const branch = current.stdout.trim();
  if (branch !== expected) {
    fail(`split repository is on "${branch}", but the manifest targets "${expected}"`);
  }
}

function requireWorkspaceMain(workspace) {
  const current = git(["symbolic-ref", "--quiet", "--short", "HEAD"], {
    cwd: workspace,
    allowFailure: true,
  });
  if (current.status !== 0) {
    fail(`workspace is not on a branch; --push must run from "main"`);
  }
  const branch = current.stdout.trim();
  if (branch !== "main") {
    fail(`workspace is on "${branch}"; --push must run from "main"`);
  }
}

function hasDotGithub(entries) {
  return entries.some((entry) => entry === ".github" || entry.startsWith(".github/"));
}

function assertNoSymlinkPath(root, relative, label) {
  let current = root;
  for (const part of relative.split("/")) {
    current = path.join(current, part);
    let stat;
    try {
      stat = lstatSync(current);
    } catch (error) {
      if (error.code === "ENOENT" || error.code === "ENOTDIR") return;
      throw error;
    }
    if (stat.isSymbolicLink()) {
      fail(`${label} contains a symlink at ${relative}; symlinks are not supported by the sync`);
    }
  }
}

function isPreserved(relative, preserve) {
  return preserve.some((entry) => {
    if (entry.endsWith("/")) {
      const prefix = entry.replace(/\/+$/, "");
      return relative === prefix || relative.startsWith(`${prefix}/`);
    }
    return relative === entry;
  });
}

function isExecutable(file) {
  return (statSync(file).mode & 0o111) !== 0;
}

function filesEqual(left, right) {
  const leftStat = statSync(left);
  const rightStat = statSync(right);
  if (!leftStat.isFile() || !rightStat.isFile()) return false;
  if (leftStat.size !== rightStat.size) return false;
  if (isExecutable(left) !== isExecutable(right)) return false;
  return readFileSync(left).equals(readFileSync(right));
}

function stringifyJson(value) {
  return JSON.stringify(value, null, 2).replace(/[\u007f-\uffff]/g, (character) => {
    const code = character.charCodeAt(0).toString(16).padStart(4, "0");
    return `\\u${code}`;
  });
}

function transformPackage(text) {
  let pkg;
  try {
    pkg = JSON.parse(text);
  } catch (error) {
    fail(`cannot transform package.json: ${error.message}`);
  }
  if (!pkg || typeof pkg !== "object" || Array.isArray(pkg)) {
    fail("cannot transform package.json: expected an object");
  }
  if (pkg.scripts !== undefined && (typeof pkg.scripts !== "object" || Array.isArray(pkg.scripts))) {
    fail("cannot transform package.json: scripts must be an object");
  }
  if (pkg.build !== undefined && (typeof pkg.build !== "object" || Array.isArray(pkg.build))) {
    fail("cannot transform package.json: build must be an object");
  }
  pkg.scripts = pkg.scripts ?? {};
  pkg.scripts.build = "vite build && electron-builder";
  pkg.build = pkg.build ?? {};
  if (pkg.build.files !== undefined && !Array.isArray(pkg.build.files)) {
    fail("cannot transform package.json: build.files must be an array");
  }
  pkg.build.files = pkg.build.files ?? [];
  if (!pkg.build.files.includes("bin/**/*")) pkg.build.files.push("bin/**/*");
  delete pkg.build.extraResources;
  return `${stringifyJson(pkg)}\n`;
}

function buildManagedFiles(workspace, project) {
  const sourceEntries = [];
  const managed = new Set();
  const sourceTracked = listTracked(workspace, project.source);

  if (hasDotGithub(sourceTracked.map((file) => toPosix(path.relative(project.source, file))))) {
    fail(
      `project "${project.name}" contains tracked .github files. Split repositories must not ` +
        "carry workflows: those files would also land on the workspace mirror branch. " +
        "Keep CI in the workspace instead.",
    );
  }

  for (const tracked of sourceTracked) {
    const relative = toPosix(path.relative(project.source, tracked));
    if (!relative || relative.startsWith("../") || path.isAbsolute(relative)) {
      fail(`source path escapes ${project.source}: ${tracked}`);
    }
    if (isPreserved(relative, project.preserve)) continue;

    const src = assertInside(workspace, path.resolve(workspace, tracked), "source file");
    const stat = lstatSync(src);
    if (stat.isSymbolicLink()) {
      fail(`symlinks are not supported by the sync: ${tracked}`);
    }
    if (!stat.isFile()) {
      fail(`tracked source is not a regular file: ${tracked}`);
    }
    if (managed.has(relative)) fail(`two source files map to ${relative}`);
    managed.add(relative);
    sourceEntries.push({ src, rel: relative, origin: tracked });
  }

  for (const extra of project.extraSources) {
    const tracked = listTracked(workspace, extra.from);
    if (tracked.length !== 1 || toPosix(tracked[0]) !== extra.from) {
      fail(`extra source is not a tracked file: ${extra.from}`);
    }
    if (managed.has(extra.to)) fail(`extra source target collides with a project file: ${extra.to}`);
    const src = assertInside(workspace, path.resolve(workspace, extra.from), "extra source");
    const stat = lstatSync(src);
    if (stat.isSymbolicLink() || !stat.isFile()) {
      fail(`extra source is not a regular file: ${extra.from}`);
    }
    managed.add(extra.to);
    sourceEntries.push({ src, rel: extra.to, origin: extra.from });
  }

  return { sourceEntries, managed };
}

function desiredContent(entry, project) {
  if (entry.rel === "package.json" && project.transform === "ide-package") {
    return { kind: "text", value: transformPackage(readFileSync(entry.src, "utf8")) };
  }
  return { kind: "file", value: entry.src };
}

function collectChanges(target, project, sourceEntries, managed) {
  const changes = [];
  const targetTracked = listTracked(target);

  if (hasDotGithub(targetTracked)) {
    fail(
      `split repository contains tracked .github files; refusing to mirror them onto the ` +
        "workspace branch. Remove them or extend the sync policy deliberately.",
    );
  }
  for (const tracked of targetTracked) {
    assertNoSymlinkPath(target, toPosix(tracked), "split repository");
  }

  for (const entry of sourceEntries) {
    const dest = assertInside(target, path.join(target, entry.rel), "target file");
    assertNoSymlinkPath(target, entry.rel, "target");
    if (!existsSync(dest)) {
      changes.push({ kind: "add", rel: entry.rel });
      continue;
    }
    const stat = lstatSync(dest);
    if (stat.isSymbolicLink()) {
      fail(`target path is a symlink, which is not supported: ${entry.rel}`);
    }
    if (stat.isDirectory()) {
      changes.push({ kind: "update", rel: entry.rel });
      continue;
    }
    if (!stat.isFile()) {
      fail(`target path exists but is not a regular file: ${entry.rel}`);
    }
    const desired = desiredContent(entry, project);
    const matches =
      desired.kind === "text"
        ? readFileSync(dest, "utf8") === desired.value && isExecutable(entry.src) === isExecutable(dest)
        : filesEqual(desired.value, dest);
    if (!matches) changes.push({ kind: "update", rel: entry.rel });
  }

  for (const tracked of targetTracked) {
    const relative = toPosix(tracked);
    if (managed.has(relative) || isPreserved(relative, project.preserve)) continue;
    changes.push({ kind: "delete", rel: relative });
  }

  changes.sort((left, right) => left.rel.localeCompare(right.rel) || left.kind.localeCompare(right.kind));
  return changes;
}

function printChanges(project, target, changes) {
  console.error(`${project.name} -> ${project.repo} (${target})`);
  if (changes.length === 0) {
    console.error("  already in sync");
    return;
  }
  for (const change of changes) {
    const symbol = change.kind === "add" ? "+" : change.kind === "update" ? "~" : "-";
    console.error(`  ${symbol} ${change.rel}`);
  }
  console.error(`  ${changes.length} change${changes.length === 1 ? "" : "s"}`);
}

function removeEmptyParents(target, fromDirectory) {
  let directory = fromDirectory;
  while (directory !== target) {
    try {
      rmdirSync(directory);
    } catch (error) {
      if (["ENOTEMPTY", "EEXIST", "ENOENT", "ENOTDIR", "EPERM"].includes(error.code)) return;
      throw error;
    }
    const parent = path.dirname(directory);
    if (parent === directory) return;
    directory = parent;
  }
}

function applyChanges(target, project, sourceEntries, changes) {
  const entryByRelative = new Map(sourceEntries.map((entry) => [entry.rel, entry]));

  // Delete stale files first so a repository can change a file into a
  // directory, or a directory into a file.
  for (const change of changes) {
    if (change.kind !== "delete") continue;
    const dest = assertInside(target, path.join(target, change.rel), "target file");
    assertNoSymlinkPath(target, change.rel, "target");
    if (!existsSync(dest)) continue;
    const stat = lstatSync(dest);
    if (stat.isDirectory() && !stat.isSymbolicLink()) {
      fail(`refusing to delete a directory: ${change.rel}`);
    }
    rmSync(dest, { force: true });
    removeEmptyParents(target, path.dirname(dest));
  }

  for (const change of changes) {
    if (change.kind === "delete") continue;
    const entry = entryByRelative.get(change.rel);
    if (!entry) fail(`internal error: no source entry for ${change.rel}`);
    const dest = assertInside(target, path.join(target, entry.rel), "target file");
    assertNoSymlinkPath(target, entry.rel, "target");
    if (existsSync(dest)) {
      const stat = lstatSync(dest);
      if (stat.isSymbolicLink()) {
        fail(`target path is a symlink, which is not supported: ${entry.rel}`);
      }
      if (stat.isDirectory()) {
        try {
          rmdirSync(dest);
        } catch (error) {
          if (["ENOTEMPTY", "EEXIST", "EPERM"].includes(error.code)) {
            fail(`cannot replace directory ${entry.rel}: it contains files not managed by the sync`);
          }
          throw error;
        }
      } else if (!stat.isFile()) {
        fail(`target path exists but is not a regular file: ${entry.rel}`);
      }
    }
    mkdirSync(path.dirname(dest), { recursive: true });
    copyFileSync(entry.src, dest);
    chmodSync(dest, statSync(entry.src).mode & 0o777);
    if (entry.rel === "package.json" && project.transform === "ide-package") {
      writeFileSync(dest, transformPackage(readFileSync(dest, "utf8")));
    }
  }
}

function sourceRevision(workspace) {
  return gitOutput(["rev-parse", "HEAD"], { cwd: workspace });
}

function commitMessage(workspace) {
  const revision = sourceRevision(workspace);
  return {
    revision,
    message: `sync: Companion workspace ${revision.slice(0, 12)}\n\n${SYNC_TRAILER}: ${revision}\n`,
  };
}

function hasSyncTrailer(message) {
  return new RegExp(`^${SYNC_TRAILER}: [0-9a-f]{40}$`, "m").test(message);
}

function isSyncCommit(message) {
  return message.startsWith("sync: Companion workspace ") && hasSyncTrailer(message);
}

function targetRemoteTip(target, branch) {
  const ref = `refs/heads/${branch}`;
  const probe = git(["ls-remote", "--exit-code", "origin", ref], {
    cwd: target,
    allowFailure: true,
  });
  if (probe.status === 2) {
    fail(`target remote branch "${branch}" does not exist`);
  }
  if (probe.status !== 0) {
    const detail = redact((probe.stderr || probe.stdout || "").trim());
    fail(
      `could not read target remote branch "${branch}"` + `${detail ? `:\n${detail}` : ""}`,
    );
  }
  const tip = probe.stdout.trim().split(/\s+/)[0];
  if (!/^[0-9a-f]{40}$/.test(tip)) {
    fail(`could not parse target remote branch "${branch}"`);
  }
  return tip;
}

function checkWorkspaceBranch(workspace, target, project) {
  if (!project.workspaceBranch) return null;

  const remoteBranchProbe = git(
    ["ls-remote", "--exit-code", "--heads", "origin", `refs/heads/${project.workspaceBranch}`],
    {
      cwd: workspace,
      allowFailure: true,
    },
  );
  if (remoteBranchProbe.status === 2) {
    const targetHead = gitOutput(["rev-parse", "HEAD"], { cwd: target });
    const targetTip = targetRemoteTip(target, project.branch);
    if (targetHead !== targetTip) {
      fail(
        `workspace branch "${project.workspaceBranch}" does not exist, and the split checkout is not ` +
          `at its remote tip (${targetHead.slice(0, 12)} vs ${targetTip.slice(0, 12)}). ` +
          `Update or push the split checkout before creating the mirror branch.`,
      );
    }
    return { workspaceTip: null, mode: "create" };
  }
  if (remoteBranchProbe.status !== 0) {
    const detail = redact((remoteBranchProbe.stderr || remoteBranchProbe.stdout || "").trim());
    fail(
      `could not check workspace branch "${project.workspaceBranch}" in ${workspace}` +
        `${detail ? `:\n${detail}` : ""}`,
    );
  }

  const remoteRef = `refs/remotes/origin/${project.workspaceBranch}`;
  const fetch = git(["fetch", "--no-tags", "--force", "origin", `refs/heads/${project.workspaceBranch}:${remoteRef}`], {
    cwd: workspace,
    allowFailure: true,
  });
  if (fetch.status !== 0) {
    const detail = redact((fetch.stderr || fetch.stdout || "").trim());
    fail(
      `could not fetch workspace branch "${project.workspaceBranch}" in ${workspace}` +
        `${detail ? `:\n${detail}` : ""}`,
    );
  }

  const workspaceTip = gitOutput(["rev-parse", remoteRef], { cwd: workspace });
  const targetHead = gitOutput(["rev-parse", "HEAD"], { cwd: target });
  if (workspaceTip === targetHead) {
    return { workspaceTip, mode: "direct" };
  }

  const ancestor = git(["merge-base", "--is-ancestor", workspaceTip, targetHead], {
    cwd: target,
    allowFailure: true,
  });
  if (ancestor.status !== 0) {
    fail(
      `split repository ${project.repo} has diverged from the workspace ` +
        `"${project.workspaceBranch}" branch (target ${targetHead.slice(0, 12)}, workspace ` +
        `${workspaceTip.slice(0, 12)}). Refusing to overwrite it; reconcile the two branches manually.`,
    );
  }

  const commits = gitOutput(["rev-list", `${workspaceTip}..${targetHead}`], { cwd: target })
    .split("\n")
    .filter(Boolean);
  for (const commit of commits) {
    const body = gitOutput(["show", "-s", "--format=%B", commit], { cwd: target });
    if (!isSyncCommit(body)) {
      fail(
        `split repository ${project.repo} contains non-sync commit ${commit.slice(0, 12)} ` +
          `after the workspace branch. Refusing to overwrite it; reconcile manually.`,
      );
    }
  }
  return { workspaceTip, mode: "recover" };
}

function pushWorkspaceBranch(workspace, target, project) {
  if (!project.workspaceBranch) return false;

  // Fetch the already-created split commit into the workspace checkout, then
  // push it with the workspace's own origin credentials. This avoids mixing
  // the split checkout's credentials with the workspace remote.
  git(["fetch", "--no-tags", target, "HEAD"], { cwd: workspace });
  const commit = gitOutput(["rev-parse", "FETCH_HEAD"], { cwd: workspace });
  git(["push", "origin", `${commit}:refs/heads/${project.workspaceBranch}`], { cwd: workspace });
  return true;
}

function syncProject(workspace, opts, project) {
  const target = opts.target;
  if (!existsSync(target) || !statSync(target).isDirectory()) {
    fail(`target directory does not exist: ${target}`);
  }
  if (!existsSync(path.join(target, ".git"))) {
    fail(`target is not a git checkout: ${target}`);
  }

  if (opts.push) {
    requireWorkspaceMain(workspace);
    requireFullHistory(target, "split repository");
    if (opts.workspaceBranch && project.workspaceBranch) {
      requireFullHistory(workspace, "workspace");
    }
  }

  const sourcePaths = [MANIFEST_PATH, project.source, ...project.extraSources.map((extra) => extra.from)];
  requireClean(workspace, "workspace", sourcePaths);
  requireClean(target, "split repository");
  if (opts.write) requireTargetBranch(target, project.branch);

  const { sourceEntries, managed } = buildManagedFiles(workspace, project);
  const changes = collectChanges(target, project, sourceEntries, managed);
  printChanges(project, target, changes);

  if (opts.check) {
    return { changed: changes.length > 0 };
  }
  if (opts.dryRun) {
    console.error("dry run: no files written");
    return { changed: changes.length > 0 };
  }

  let workspaceState = null;
  if (opts.push && opts.workspaceBranch && project.workspaceBranch) {
    workspaceState = checkWorkspaceBranch(workspace, target, project);
  }

  if (changes.length === 0) {
    // If a previous attempt created the sync commit but failed while pushing,
    // retry that push before advancing the workspace mirror branch. Only push
    // commits that this tool generated; never publish an arbitrary local HEAD.
    if (opts.push) {
      const targetHead = gitOutput(["show", "-s", "--format=%B", "HEAD"], { cwd: target });
      if (isSyncCommit(targetHead)) {
        console.error(`pushing split repository ${project.repo} to "${project.branch}"`);
        git(["push", "origin", `HEAD:refs/heads/${project.branch}`], { cwd: target });
      }
    }
    if (workspaceState && (workspaceState.mode === "recover" || workspaceState.mode === "create")) {
      console.error(
        workspaceState.mode === "create"
          ? `creating workspace branch "${project.workspaceBranch}"`
          : `fast-forwarding workspace branch "${project.workspaceBranch}"`,
      );
      pushWorkspaceBranch(workspace, target, project);
    } else {
      console.error("nothing to commit");
    }
    return { changed: false };
  }

  applyChanges(target, project, sourceEntries, changes);
  git(["add", "-A"], { cwd: target });

  const diff = git(["diff", "--cached", "--quiet"], { cwd: target, allowFailure: true });
  if (diff.status === 0) {
    console.error("no staged changes after applying the sync");
    return { changed: false };
  }

  const { message } = commitMessage(workspace);
  git(["-c", "commit.gpgsign=false", "commit", "-m", message], {
    cwd: target,
    env: {
      GIT_AUTHOR_NAME: SYNC_ACTOR.name,
      GIT_AUTHOR_EMAIL: SYNC_ACTOR.email,
      GIT_COMMITTER_NAME: SYNC_ACTOR.name,
      GIT_COMMITTER_EMAIL: SYNC_ACTOR.email,
    },
  });

  if (opts.push) {
    git(["push", "origin", `HEAD:refs/heads/${project.branch}`], { cwd: target });
    if (workspaceState) {
      console.error(
        `${workspaceState.mode === "create" ? "creating" : "updating"} workspace branch "${project.workspaceBranch}"`,
      );
      pushWorkspaceBranch(workspace, target, project);
    }
  }

  return { changed: true };
}

function printPlan(manifest, selector) {
  const projects = selectProjects(manifest, selector);
  const matrix = {
    include: projects.map((project) => ({
      name: project.name,
      repo: project.repo,
      branch: project.branch,
      workspaceBranch: project.workspaceBranch,
    })),
  };
  process.stdout.write(`matrix=${JSON.stringify(matrix)}\n`);
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) {
    process.stdout.write(`${usage()}\n`);
    return;
  }

  const manifest = loadManifest(opts.workspace);
  if (opts.plan) {
    printPlan(manifest, opts.project);
    return;
  }

  const [project] = selectProjects(manifest, opts.project);
  const result = syncProject(opts.workspace, opts, project);
  if (opts.check) {
    process.exitCode = result.changed ? 1 : 0;
  }
}

try {
  main();
} catch (error) {
  if (error instanceof SyncError) {
    console.error(`error: ${error.message}`);
    process.exitCode = 2;
  } else {
    console.error(error.stack || error.message || String(error));
    process.exitCode = 2;
  }
}
