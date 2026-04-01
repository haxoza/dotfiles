const path = require("node:path")
const os = require("node:os")

const home = os.homedir()

const blockedDirectories = [
  ".ssh",
  ".aws",
  ".gnupg",
  "Library/Keychains",
  ".config/gcloud",
  ".config/op",
  ".config/gh",
  ".kube",
  ".terraform.d",
].map((relativePath) => path.resolve(home, relativePath))

const blockedFiles = [
  ".docker/config.json",
  ".pypirc",
  ".npmrc",
  ".git-credentials",
].map((relativePath) => path.resolve(home, relativePath))

const allBlockedPaths = [...blockedDirectories, ...blockedFiles]

function normalizeFilePath(filePath) {
  if (!filePath || typeof filePath !== "string") return null
  if (filePath === "~") return home
  if (filePath === "$HOME" || filePath === "${HOME}") return home
  if (filePath.startsWith("~/")) return path.resolve(home, filePath.slice(2))
  if (filePath.startsWith("$HOME/")) return path.resolve(home, filePath.slice(6))
  if (filePath.startsWith("${HOME}/")) return path.resolve(home, filePath.slice(8))
  return path.resolve(filePath)
}

function isBlockedPath(filePath) {
  const normalized = normalizeFilePath(filePath)
  if (!normalized) return null

  for (const blockedFile of blockedFiles) {
    if (normalized === blockedFile) {
      return blockedFile
    }
  }

  for (const blockedDirectory of blockedDirectories) {
    if (
      normalized === blockedDirectory ||
      normalized.startsWith(`${blockedDirectory}${path.sep}`)
    ) {
      return blockedDirectory
    }
  }

  return null
}

function commandTouchesBlockedPath(command) {
  if (!command || typeof command !== "string") return null

  const normalizedCommand = command
    .replaceAll("${HOME}", "~")
    .replaceAll("$HOME", "~")
    .replaceAll(home, "~")

  for (const blockedPath of allBlockedPaths) {
    if (normalizedCommand.includes(`~/${path.relative(home, blockedPath)}`)) {
      return blockedPath
    }
  }

  return null
}

function rejectBlockedPath(tool, blockedPath) {
  const displayPath = blockedPath.startsWith(home)
    ? blockedPath.replace(home, "~")
    : blockedPath
  throw new Error(`${tool} access is blocked for sensitive path: ${displayPath}`)
}

module.exports.SensitivePathGuard = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "bash") {
        const blockedPath = commandTouchesBlockedPath(output.args.command)
        if (blockedPath) {
          rejectBlockedPath("bash", blockedPath)
        }
        return
      }

      if (["read", "edit", "write"].includes(input.tool)) {
        const blockedPath = isBlockedPath(output.args.filePath)
        if (blockedPath) {
          rejectBlockedPath(input.tool, blockedPath)
        }
        return
      }

      if (input.tool === "list") {
        const blockedPath = isBlockedPath(output.args.path)
        if (blockedPath) {
          rejectBlockedPath("list", blockedPath)
        }
        return
      }

      if (input.tool === "glob") {
        const blockedPath = isBlockedPath(output.args.path)
        if (blockedPath) {
          rejectBlockedPath("glob", blockedPath)
        }
        return
      }

      if (input.tool === "grep") {
        const blockedPath = isBlockedPath(output.args.path)
        if (blockedPath) {
          rejectBlockedPath("grep", blockedPath)
        }
      }
    },
  }
}
