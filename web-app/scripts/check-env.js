#!/usr/bin/env node
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const MIN_NODE_VERSION = 18;

function getNodeVersion() {
  const version = process.version.replace('v', '');
  return parseInt(version.split('.')[0], 10);
}

function hasPnpm() {
  try {
    execSync('pnpm --version', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function checkAll() {
  const issues = [];

  const nodeVersion = getNodeVersion();
  if (nodeVersion < MIN_NODE_VERSION) {
    issues.push(`Node.js >= ${MIN_NODE_VERSION} required (found v${process.version})`);
    issues.push('Download: https://nodejs.org/');
  }

  if (!hasPnpm()) {
    issues.push('pnpm not found. Installing...');
    try {
      execSync('npm install -g pnpm', { stdio: 'inherit' });
      console.log('✅ pnpm installed successfully');
    } catch {
      issues.push('Failed to install pnpm. Run: npm install -g pnpm');
    }
  }

  const nodeModules = path.resolve(__dirname, '..', 'node_modules');
  const needsInstall = !fs.existsSync(nodeModules);

  if (issues.length > 0) {
    console.error('\n❌ Environment issues:');
    issues.forEach(i => console.error(`   • ${i}`));
    process.exit(1);
  }

  return { needsInstall };
}

if (require.main === module) {
  const { needsInstall } = checkAll();
  if (needsInstall) {
    console.log('📦 Installing dependencies...');
    execSync('pnpm install', { cwd: path.resolve(__dirname, '..'), stdio: 'inherit' });
  }
  console.log('✅ Environment ready!');
}

module.exports = { checkAll };
