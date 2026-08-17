const PACKAGE_SUFFIXES = [
  '.tar.gz',
  '.msix',
  '.exe',
  '.msi',
  '.zip',
  '.7z',
  '.rar',
  '.tar',
  '.tgz',
]

const VERSION_PATTERN = /(^|[^a-z0-9])v?(\d+(?:\.\d+){1,3})(?=$|[^a-z0-9])/i

function packageFileName(item) {
  return String(item?.file_name ?? item?.fileName ?? '')
}

function packageUploadedAt(item) {
  const value = item?.uploaded_at ?? item?.uploadedAt
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : 0
}

function stripPackageSuffix(fileName) {
  const lowerName = String(fileName || '').trim().toLowerCase()
  const suffix = PACKAGE_SUFFIXES.find((candidate) => lowerName.endsWith(candidate))
  return suffix ? lowerName.slice(0, -suffix.length) : lowerName
}

export function extractPackageVersion(fileName) {
  const match = stripPackageSuffix(fileName).match(VERSION_PATTERN)
  return match?.[2] || ''
}

export function packageFamily(fileName) {
  return stripPackageSuffix(fileName)
    .replace(VERSION_PATTERN, '$1')
    .replace(/[\s._-]+/g, ' ')
    .trim()
}

export function nextPatchVersion(version) {
  const match = String(version || '').trim().match(/^v?(\d+(?:\.\d+){0,3})/i)
  if (!match) return '1.0.0'

  const parts = match[1].split('.').map(Number)
  if (parts.length === 1) {
    return `${parts[0]}.0.1`
  }
  if (parts.length === 2) {
    return `${parts[0]}.${parts[1]}.1`
  }
  parts[parts.length - 1] += 1
  return parts.join('.')
}

export function suggestReleaseMetadata(fileName, packageHistory = []) {
  const family = packageFamily(fileName)
  const matchingPackages = packageHistory
    .filter((item) => packageFamily(packageFileName(item)) === family)
    .map((item, index) => ({ item, index }))
    .sort((left, right) =>
      packageUploadedAt(right.item) - packageUploadedAt(left.item) || left.index - right.index)
    .map(({ item }) => item)

  const previous = matchingPackages[0] || null
  const notesSource = matchingPackages.find((item) => String(item?.notes || '').trim()) || null
  const embeddedVersion = extractPackageVersion(fileName)
  const previousVersion = previous?.version || extractPackageVersion(packageFileName(previous))

  return {
    version: embeddedVersion || nextPatchVersion(previousVersion),
    notes: String(notesSource?.notes || '').trim(),
    previous,
    versionFromFileName: Boolean(embeddedVersion),
  }
}
