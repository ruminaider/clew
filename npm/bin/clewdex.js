#!/usr/bin/env node

"use strict";

const { execFileSync } = require("child_process");

const args = process.argv.slice(2);

// Try clew (installed via pip/pipx)
try {
  execFileSync("clew", args, { stdio: "inherit" });
  process.exit(0);
} catch (e) {
  if (e.code !== "ENOENT") {
    process.exit(e.status || 1);
  }
}

// Try pipx run as fallback
try {
  execFileSync("pipx", ["run", "clewdex", ...args], { stdio: "inherit" });
  process.exit(0);
} catch (e) {
  if (e.code !== "ENOENT") {
    process.exit(e.status || 1);
  }
}

console.error(`error: clewdex is not installed

Install with one of:
  pip install clewdex
  pipx install clewdex
  brew install ruminaider/tap/clewdex

Learn more: https://github.com/ruminaider/clew`);
process.exit(1);
