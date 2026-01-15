#!/bin/bash
set -e

# Local Pipeline Logic Validator
# This script simulates the pipeline without ESRP signing to catch errors early

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$SCRIPT_DIR/_local_test"
UNSIGNED_TARBALL_URL="https://github.com/naga-nandyala/azure-cli-pkg-1/releases/download/v2.77.0-tarball/azure-cli-2.77.0-macos-arm64.tar.gz"

echo "=========================================="
echo "Local Pipeline Logic Validation"
echo "=========================================="
echo ""

# Cleanup previous run
if [ -d "$WORK_DIR" ]; then
  echo "Cleaning up previous test run..."
  rm -rf "$WORK_DIR"
fi

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

echo ""
echo "=========================================="
echo "STAGE 1: Download and Extract (macOS)"
echo "=========================================="
echo ""

echo "Downloading unsigned tar.gz..."
curl -L -o unsigned.tar.gz "$UNSIGNED_TARBALL_URL"
ls -lh unsigned.tar.gz

echo ""
echo "Extracting tar.gz..."
mkdir -p unsigned-contents
tar -xzf unsigned.tar.gz -C unsigned-contents

echo ""
echo "=== Identifying Mach-O binaries for signing ==="
echo "NOTE: Only actual binaries (not Python scripts) should be signed"
echo ""

PAYLOAD_DIR="$WORK_DIR/unsigned-contents"
FILES_TO_SIGN="$WORK_DIR/files-to-sign.txt"

cd "$PAYLOAD_DIR"

# Find all binaries that need signing using 'file' command
# Only include Mach-O binaries (excludes text-based Python scripts)

echo "Scanning for Mach-O binaries..."

find . -type f | while read filepath; do
  # Get file type
  filetype=$(file -b "$filepath")
  
  # Check if it's a Mach-O binary (not text, not ELF, not shell script)
  if echo "$filetype" | grep -q -i "Mach-O"; then
    echo "$filepath"
  fi
done | sort -u > "$FILES_TO_SIGN"

echo ""
echo "=== Files identified for signing ==="
BINARY_COUNT=$(wc -l < "$FILES_TO_SIGN")
echo "Total Mach-O binaries: $BINARY_COUNT"
echo ""

if [ "$BINARY_COUNT" -ne 17 ]; then
  echo "❌ ERROR: Expected 17 Mach-O binaries, found $BINARY_COUNT"
  echo ""
  echo "Files found:"
  cat "$FILES_TO_SIGN"
  exit 1
fi

echo "✅ Correct number of binaries found (17)"
echo ""
echo "All files to be signed:"
cat "$FILES_TO_SIGN"

# Show file type breakdown
echo ""
echo "=== File type breakdown ==="
echo "Python binaries:"
grep 'bin/python' "$FILES_TO_SIGN" || echo "  (none)"
echo ".dylib files:"
grep '\.dylib$' "$FILES_TO_SIGN" || echo "  (none)"
echo ".so files:"
grep '\.so$' "$FILES_TO_SIGN" || echo "  (none)"

cd "$WORK_DIR"

echo ""
echo "=========================================="
echo "STAGE 2: Create ZIPs and Mock Signing (Windows simulation)"
echo "=========================================="
echo ""

echo "Creating individual ZIP files for each Mach-O binary..."

mkdir -p toBeSigned
UNSIGNED_PATH="$WORK_DIR/unsigned-contents"
TO_BE_SIGNED_DIR="$WORK_DIR/toBeSigned"

zipped_count=0

while IFS= read -r file_path_from_list; do
  # Remove leading './'
  relative_path="${file_path_from_list#./}"
  full_path="$UNSIGNED_PATH/$relative_path"
  
  if [ ! -f "$full_path" ]; then
    echo "❌ WARNING: File not found: $full_path"
    continue
  fi
  
  # Create unique flat filename (replace / with __)
  flat_name="${relative_path//\//__}"
  zip_name="${flat_name}.zip"
  zip_path="$TO_BE_SIGNED_DIR/$zip_name"
  
  # Create ZIP (macOS zip command)
  (cd "$(dirname "$full_path")" && zip -q "$zip_path" "$(basename "$full_path")")
  
  zipped_count=$((zipped_count + 1))
  
  if [ $zipped_count -le 10 ]; then
    zip_size=$(du -h "$zip_path" | cut -f1)
    echo "  ✓ $relative_path -> $zip_name ($zip_size)"
  fi
done < "$FILES_TO_SIGN"

echo ""
echo "✅ Created $zipped_count ZIP files"

echo ""
echo "Simulating ESRP signing (copying originals as 'signed')..."
mkdir -p signed-zips

for zip_file in "$TO_BE_SIGNED_DIR"/*.zip; do
  # In real pipeline, ESRP would sign and output to signed-zips
  # Here we just copy to simulate
  cp "$zip_file" signed-zips/
done

echo "✅ Mock signing complete"

echo ""
echo "Extracting signed binaries to flat structure..."
mkdir -p signed-binaries

cd signed-zips
for zip_file in *.zip; do
  unzip -q "$zip_file" -d "$WORK_DIR/signed-binaries"
done
cd "$WORK_DIR"

SIGNED_BINARY_COUNT=$(find signed-binaries -type f | wc -l)
echo "✅ Extracted $SIGNED_BINARY_COUNT signed binaries"

if [ "$SIGNED_BINARY_COUNT" -ne 17 ]; then
  echo "❌ ERROR: Expected 17 signed binaries, found $SIGNED_BINARY_COUNT"
  exit 1
fi

echo ""
echo "=========================================="
echo "STAGE 3: Merge and Create Tar.gz (macOS)"
echo "=========================================="
echo ""

echo "Merging signed binaries back into package structure..."

ORIGINAL_PAYLOAD="$WORK_DIR/unsigned-contents"
SIGNED_BINARIES="$WORK_DIR/signed-binaries"
MERGED_PAYLOAD="$WORK_DIR/merged-payload"

# Use cp -R to preserve symlinks (this is the critical operation)
echo "Copying original structure with cp -R (preserves symlinks)..."
mkdir -p "$MERGED_PAYLOAD"
cp -R "$ORIGINAL_PAYLOAD"/* "$MERGED_PAYLOAD"/

echo "✅ Original structure copied"

# Overlay signed binaries
echo ""
echo "Overlaying signed binaries..."

while IFS= read -r file_path_from_list; do
  # Remove leading './'
  relative_path="${file_path_from_list#./}"
  
  # Get just the filename
  filename=$(basename "$relative_path")
  
  # Find the signed binary in flat structure
  signed_file="$SIGNED_BINARIES/$filename"
  target_file="$MERGED_PAYLOAD/$relative_path"
  
  if [ -f "$signed_file" ] && [ -f "$target_file" ]; then
    cp "$signed_file" "$target_file"
    echo "  ✓ Overlaid: $relative_path"
  else
    echo "  ⚠️  Skip: $relative_path (signed: $([ -f "$signed_file" ] && echo 'Y' || echo 'N'), target: $([ -f "$target_file" ] && echo 'Y' || echo 'N'))"
  fi
done < "$FILES_TO_SIGN"

echo ""
echo "✅ Signed binaries overlaid"

echo ""
echo "=== Verifying symlinks are preserved ==="

EXPECTED_SYMLINKS=(
  "bin/az"
  "libexec/bin/python"
  "libexec/bin/python3.13"
)

symlink_errors=0
for symlink_path in "${EXPECTED_SYMLINKS[@]}"; do
  full_symlink="$MERGED_PAYLOAD/$symlink_path"
  if [ -L "$full_symlink" ]; then
    target=$(readlink "$full_symlink")
    echo "  ✅ $symlink_path -> $target (symlink preserved)"
  else
    echo "  ❌ $symlink_path is NOT a symlink!"
    ls -lh "$full_symlink"
    symlink_errors=$((symlink_errors + 1))
  fi
done

if [ $symlink_errors -gt 0 ]; then
  echo ""
  echo "❌ ERROR: $symlink_errors symlinks were not preserved!"
  exit 1
fi

echo ""
echo "✅ All symlinks verified"

echo ""
echo "Creating signed tar.gz..."
cd "$MERGED_PAYLOAD"
tar -czf "$WORK_DIR/azure-cli-signed-test.tar.gz" *
cd "$WORK_DIR"

SIGNED_SIZE=$(du -h azure-cli-signed-test.tar.gz | cut -f1)
echo "✅ Signed tar.gz created: $SIGNED_SIZE"

echo ""
echo "=== Final Verification ==="

echo "Extracting signed tar.gz for verification..."
mkdir -p verify-signed
tar -xzf azure-cli-signed-test.tar.gz -C verify-signed

echo ""
echo "Symlink verification in final package:"
for symlink_path in "${EXPECTED_SYMLINKS[@]}"; do
  full_symlink="verify-signed/$symlink_path"
  if [ -L "$full_symlink" ]; then
    target=$(readlink "$full_symlink")
    echo "  ✅ $symlink_path -> $target"
  else
    echo "  ❌ $symlink_path is NOT a symlink!"
    symlink_errors=$((symlink_errors + 1))
  fi
done

if [ $symlink_errors -gt 0 ]; then
  echo ""
  echo "❌ FINAL ERROR: Symlinks not preserved in final package!"
  exit 1
fi

echo ""
echo "Binary count verification:"
FINAL_BINARY_COUNT=$(find verify-signed -type f | while read f; do
  if file -b "$f" | grep -q -i "Mach-O"; then
    echo "$f"
  fi
done | wc -l)
echo "  Mach-O binaries in final package: $FINAL_BINARY_COUNT"

if [ "$FINAL_BINARY_COUNT" -ne 17 ]; then
  echo "  ❌ ERROR: Expected 17, found $FINAL_BINARY_COUNT"
  exit 1
fi
echo "  ✅ Correct number of binaries"

echo ""
echo "=========================================="
echo "✅ ALL VALIDATIONS PASSED!"
echo "=========================================="
echo ""
echo "Pipeline logic validated successfully:"
echo "  ✅ Stage 1: Identified exactly 17 Mach-O binaries"
echo "  ✅ Stage 2: Created ZIPs for all binaries"
echo "  ✅ Stage 3: Merged preserving all 3 symlinks"
echo "  ✅ Final package: Structure verified"
echo ""
echo "Test artifacts available in: $WORK_DIR"
echo ""
