import { readFileSync } from 'node:fs'

const manifest = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'))
const packages = []
for (const name of Object.keys({ ...manifest.dependencies, ...manifest.devDependencies }).sort()) {
  const installed = JSON.parse(readFileSync(new URL(`../node_modules/${name}/package.json`, import.meta.url), 'utf8'))
  packages.push({ name, version: installed.version, license: installed.license || 'UNSPECIFIED', kind: name in manifest.dependencies ? 'runtime' : 'development' })
}
const document = `${JSON.stringify({ schemaVersion: 1, scope: 'Direct npm dependencies from installed package metadata', packages }, null, 2)}\n`
if (process.argv.includes('--json')) process.stdout.write(document)
else for (const item of packages) process.stdout.write(`${item.name}\t${item.version}\t${item.license}\t${item.kind}\n`)
